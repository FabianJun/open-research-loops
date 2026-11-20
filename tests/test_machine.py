import asyncio
import json
import os
import sqlite3
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from typer.testing import CliRunner

from research_loops.cancellation import Cancellation, active_job, request
from research_loops.cli import app
from research_loops.coordinator import prepare, run
from research_loops.domain import WorkerContract
from research_loops.fake import FakeBackend
from research_loops.machine import report as machine_report, status
from research_loops.processes import WindowsJob, process_identity
from research_loops.reporting import export_bytes, render
from research_loops.storage import ReadOnlyRepository, Repository


def small(example):
    path = example / "contract.json"
    value = json.loads(path.read_bytes())
    value.update(seeds=[7], variants_per_seed=2)
    value.setdefault("limits", {})["concurrency"] = 2
    path.write_text(json.dumps(value), encoding="utf-8")


def files(root):
    result = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        stat = path.stat()
        try:
            content = path.read_bytes()
        except PermissionError:
            # Windows byte locks also prohibit reads of the lock's one byte.
            assert os.name == "nt" and path.name in ("coordinator.lock", "state.sqlite-shm")
            content = None
        result[path.relative_to(root).as_posix()] = stat.st_mtime_ns, stat.st_size, content
    return result


def invoke(command, example):
    result = CliRunner().invoke(app, [command, str(example), *([] if command == "cancel" else ["--json"])])
    value = json.loads(result.stdout)
    assert result.stdout.count("\n") == 1
    assert result.stderr == ""
    return result, value


@pytest.mark.parametrize("command", ["status", "report", "cancel"])
def test_missing_database_is_structured_and_creates_nothing(tmp_path, command):
    project = tmp_path / "missing"
    result, value = invoke(command, project)
    assert result.exit_code == 2
    assert value == {"schema": f"rloop.{command}/1", "error": {"code": "no_database", "message": "Project has no database yet."}}
    assert not project.exists()


def test_readers_under_another_threads_lock_do_not_change_any_file(example):
    ready, finish = threading.Event(), threading.Event()
    def writer():
        repo, _, key = prepare(example)
        try:
            repo.dispatch(WorkerContract(run_id="in-flight", registration_hash=key, goal="test",
                prediction="test", seed=7, variant=0, input_hash="a" * 64))
            # Make the WAL essential; the main DB must not be a stale source.
            ready.set()
            assert finish.wait(20)
        finally:
            repo.close()
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(writer)
        assert ready.wait(15)
        try:
            root = example / ".rloop"
            before = files(root)
            result, value = invoke("status", example)
            assert result.exit_code == 0, result.exception
            assert value["schema"] == "rloop.status/1"
            assert value["project_state"] == "running"
            assert value["runs"][0] == {"id": "in-flight", "execution_status": "running",
                "scientific_outcome": None, "started_at": value["runs"][0]["started_at"],
                "finished_at": None, "prediction_registered": False, "report_paths": None}
            assert value["runs"][0]["started_at"]
            result, value = invoke("report", example)
            assert result.exit_code == 2
            assert value["error"]["code"] == "not_ready"
            text = CliRunner().invoke(app, ["status", str(example)])
            assert text.exit_code == 0
            assert text.stdout == "in-flight: running / None\n"
            assert files(root) == before
        finally:
            finish.set()
        future.result()


def test_report_uses_shared_summary_and_does_not_rewrite_files(example):
    small(example)
    asyncio.run(run(example))
    root = example / ".rloop"
    # Host settings and worker prose are never read into the projection.
    (example / "project.json").write_text('{"owner":{"name":"PRIVATE-IDENTITY"}}')
    before = files(root)
    result, value = invoke("report", example)
    assert result.exit_code == 0, result.exception
    assert value["schema"] == "rloop.report/1"
    assert value["attempted_variants"] == 4
    markdown = (root / "report.md").read_text(encoding="utf-8")
    for row in value["runs"]:
        assert row["finished_at"] and row["started_at"] <= row["finished_at"]
        assert row["verification_status"] == "checked"
        score = row["development_metrics"]["mse"]
        assert f"| {row['id']} | {row['execution_status']} | {row['scientific_outcome']} | checked | {score:.12g}" in markdown
    text = json.dumps(value)
    for forbidden in ("PRIVATE-IDENTITY", str(example), "predictions", "squared_errors", "candidate", "transcript", "final_ticket", "owner"):
        assert forbidden not in text
    result, saved = invoke("status", example)
    assert all(row["report_paths"] == {"markdown": ".rloop/report.md", "html": ".rloop/report.html"} for row in saved["runs"])
    assert files(root) == before


def test_prediction_flag_is_registration_scoped(example):
    from research_loops.prediction import record
    repo, _, key = prepare(example)
    try:
        record(repo, 0.5, "PRIVATE-NOTE")
        repo.dispatch(WorkerContract(run_id="prediction", registration_hash=key, goal="test",
            prediction="PRIVATE-WORKER-TEXT", seed=7, variant=0, input_hash="a" * 64))
        reader = ReadOnlyRepository(repo.root)
        try:
            value = status(reader)
            assert value["runs"][0]["prediction_registered"] is True
            assert "PRIVATE" not in json.dumps(value)
            with pytest.raises(sqlite3.OperationalError):
                reader.db.execute("UPDATE project SET revision=0")
        finally:
            reader.close()
    finally:
        repo.close()


def test_wal_snapshot_ignores_uncommitted_frames_and_survives_checkpoint(example):
    repo, _, _ = prepare(example)
    try:
        for index in range(3):
            with repo.db:
                repo.db.execute("UPDATE project SET revision=?", (index,))
            repo.db.execute("UPDATE project SET revision=999")
            before = files(repo.root)
            reader = ReadOnlyRepository(repo.root)
            try:
                assert reader.db.execute("SELECT revision FROM project").fetchone()[0] == index
            finally:
                reader.close()
            assert before == files(repo.root)
            repo.db.rollback()
            repo.db.execute("PRAGMA wal_checkpoint(RESTART)" if index % 2 == 0 else "PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        repo.close()


def test_cancel_before_job_start_is_idle_and_stale_request_is_ignored(example):
    small(example)
    repo, _, _ = prepare(example)
    repo.close()
    result, value = invoke("cancel", example)
    assert result.exit_code == 0
    assert value["cancel_requested"] is False and value["job_id"] is None
    asyncio.run(run(example))
    result, value = invoke("status", example)
    assert value["project_state"] == "completed"
    assert all(row["execution_status"] == "completed" for row in value["runs"])


def test_cancel_before_first_worker_dispatch(example, monkeypatch):
    import research_loops.coordinator as coordinator
    small(example)
    original = coordinator.campaign
    async def cancel_first(repo, *args, **kwargs):
        request(repo)
        return await original(repo, *args, **kwargs)
    monkeypatch.setattr(coordinator, "campaign", cancel_first)
    asyncio.run(run(example))
    reader = ReadOnlyRepository(example / ".rloop")
    try:
        assert status(reader)["project_state"] == "cancelled"
        assert reader.runs() == []
    finally:
        reader.close()
    # The real old job ID remains in the request file while a new job dispatches.
    monkeypatch.setattr(coordinator, "campaign", original)
    asyncio.run(run(example))
    reader = ReadOnlyRepository(example / ".rloop")
    try:
        assert status(reader)["project_state"] == "completed"
        assert len(reader.runs()) == 4
        assert all(row["execution_status"] == "completed" for row in reader.runs())
    finally:
        reader.close()


def test_cancel_after_sealing_never_starts_evaluation(example, monkeypatch):
    small(example)
    class SealingFake(FakeBackend):
        async def run(self, contract, workspace, limits):
            result = await super().run(contract, workspace, limits)
            reader = ReadOnlyRepository(example / ".rloop")
            try:
                request(reader)
            finally:
                reader.close()
            return result
    def forbidden(*args, **kwargs):
        pytest.fail("evaluation started after cancellation")
    monkeypatch.setattr("research_loops.coordinator.evaluate_saved", forbidden)
    asyncio.run(run(example, backend=SealingFake()))
    reader = ReadOnlyRepository(example / ".rloop")
    try:
        assert status(reader)["project_state"] == "cancelled"
        assert reader.runs()
        assert all(row["execution_status"] == "cancelled" and row["verdict"] is None for row in reader.runs())
    finally:
        reader.close()


def test_cancel_awaits_an_evaluator_already_in_flight(example, monkeypatch):
    small(example)
    started, finish = threading.Event(), threading.Event()
    original = __import__("research_loops.coordinator", fromlist=["evaluate_saved"]).evaluate_saved
    def blocked(*args, **kwargs):
        started.set()
        assert finish.wait(15)
        return original(*args, **kwargs)
    monkeypatch.setattr("research_loops.coordinator.evaluate_saved", blocked)
    async def scenario():
        job = asyncio.create_task(run(example))
        try:
            async with asyncio.timeout(15):
                while not started.is_set():
                    await asyncio.sleep(.01)
            result, value = invoke("cancel", example)
            assert result.exit_code == 0 and value["cancel_requested"]
            await asyncio.sleep(.15)
            assert not job.done(), "ledger closed before evaluator cleanup"
        finally:
            finish.set()
        await asyncio.wait_for(job, 15)
    asyncio.run(scenario())
    reader = ReadOnlyRepository(example / ".rloop")
    try:
        assert status(reader)["project_state"] == "cancelled"
        assert all(row["execution_status"] == "cancelled" for row in reader.runs())
    finally:
        reader.close()


def test_cancel_in_flight_cleans_process_trees_and_resume_does_not_rerun(example):
    import importlib.util
    if importlib.util.find_spec("claude_agent_sdk") is None:
        pytest.skip("install research-loops[claude] for the Claude transport cleanup test")
    small(example)
    class ProcessFake(FakeBackend):
        calls = []
        processes = []
        async def run(self, contract, workspace, limits):
            # Existing transport cleanup contains both the parent and descendants.
            from research_loops.adapters.claude_transport import LoginTransport
            transport = LoginTransport(None, "claude_code")
            script = "import sys,subprocess,time,pathlib; sys.stdin.readline(); p=subprocess.Popen([sys.executable,'-I','-c','import time; time.sleep(60)']); pathlib.Path(sys.argv[1]).write_text(str(p.pid)); time.sleep(60)"
            receipt = workspace.root.parent / "child.pid"
            transport.process = subprocess.Popen([sys.executable, "-I", "-c", script, str(receipt)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, start_new_session=os.name != "nt")
            if os.name == "nt":
                transport.job = WindowsJob(transport.process)
            transport.process.stdin.write(b"go\n")
            transport.process.stdin.flush()
            self.processes.append(transport.process.pid)
            self.calls.append(contract.run_id)
            try:
                while not receipt.exists():
                    await asyncio.sleep(.01)
                self.processes.append(int(receipt.read_text()))
                await asyncio.Event().wait()
            finally:
                await transport.close()
    backend = ProcessFake()
    async def scenario():
        job = asyncio.create_task(run(example, backend=backend))
        try:
            async with asyncio.timeout(20):
                while len(backend.processes) < 4:
                    await asyncio.sleep(.02)
            first, value = invoke("cancel", example)
            assert first.exit_code == 0 and value["cancel_requested"]
            before = files(example / ".rloop")
            second, repeated = invoke("cancel", example)
            assert second.exit_code == 0 and repeated == value
            assert files(example / ".rloop") == before
            _, pending = invoke("status", example)
            assert pending["cancel_requested"] is True
            await asyncio.wait_for(job, 15)
        finally:
            if not job.done():
                job.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await job
    asyncio.run(scenario())
    deadline = time.monotonic() + 5
    while any(process_identity(pid) for pid in backend.processes) and time.monotonic() < deadline:
        time.sleep(.02)
    assert all(process_identity(pid) is None for pid in backend.processes)
    repo = Repository(example / ".rloop")
    try:
        assert len(repo.runs()) == 2
        assert all(row["execution_status"] == "cancelled" and not row["verdict"] for row in repo.runs())
        assert status(repo)["project_state"] == "cancelled"
        assert not status(repo)["cancel_requested"]
        assert "cancelled" in render(repo)
        assert (repo.root / "events.jsonl").read_bytes() == export_bytes(repo)
        saved = repo.runs()
        stale_job = json.loads((repo.root / "cancel.json").read_bytes())["job_id"]
    finally:
        repo.close()
    asyncio.run(run(example, resume_only=True, backend=backend))
    assert len(backend.calls) == 2
    reader = ReadOnlyRepository(example / ".rloop")
    try:
        assert reader.runs() == saved
        assert active_job(reader) is None
        assert not Cancellation(reader.root, "new-job").requested()
        assert Cancellation(reader.root, stale_job).requested()
        assert machine_report(reader)["runs"][0]["execution_status"] == "cancelled"
    finally:
        reader.close()
