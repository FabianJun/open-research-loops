import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from typer.testing import CliRunner

from research_loops.cli import app
from research_loops.coordinator import prepare, run
from research_loops.domain import IntegrityError, WorkerContract
from research_loops.storage import Repository
from research_loops.tools import ToolService


def test_cli_commands_and_provider_refusal(example):
    runner = CliRunner()
    for command in ("init", "plan", "status", "report", "export", "resume"):
        result = runner.invoke(app, [command, str(example)])
        assert result.exit_code == 0, result.output
    refused = runner.invoke(app, ["run", str(example), "--backend", "openai_agents"])
    assert refused.exit_code != 0
    assert "provider calls" in refused.output and "authorized" in refused.output


def test_cli_run_and_final_flags(example):
    payload = json.loads((example / "contract.json").read_text())
    payload.update({"seeds": [7], "variants_per_seed": 2})
    (example / "contract.json").write_text(json.dumps(payload))
    runner = CliRunner()
    for arguments in (["run", str(example)], ["report", str(example), "--check"], ["run", str(example), "--final"]):
        result = runner.invoke(app, arguments)
        assert result.exit_code == 0, (result.output, result.exception)
    assert runner.invoke(app, ["run", str(example), "--final"]).exit_code != 0


def test_no_candidate_code_without_sandbox(tmp_path):
    task = WorkerContract(run_id="test", registration_hash="a" * 64, goal="test", prediction="test", seed=7, variant=0, input_hash="b" * 64)
    tools = ToolService(task, tmp_path / "outbox")
    with pytest.raises(IntegrityError, match="disabled"):
        tools.execute_candidate("print('should never run')")


def test_worker_timeout_is_visible_counted_and_has_no_claim(example):
    data = json.loads((example / "contract.json").read_text())
    data.update({"seeds": [7], "variants_per_seed": 2, "limits": {"worker_seconds": 0.02}})
    (example / "contract.json").write_text(json.dumps(data))
    class SleepingBackend:
        async def run(self, contract, workspace, limits):
            await asyncio.sleep(60)
    with pytest.raises(ExceptionGroup):
        asyncio.run(run(example, backend=SleepingBackend()))
    repo = Repository(example / ".rloop")
    try:
        rows = repo.runs()
        assert len(rows) == 4
        assert all(row["execution_status"] == "timed_out" and row["scientific_outcome"] is None for row in rows)
        assert repo.db.execute("SELECT count(*) FROM claims").fetchone()[0] == 0
        assert "timed_out" in (repo.root / "report.md").read_text(encoding="utf-8")
    finally:
        repo.close()


def test_failed_control_blocks_all_worker_dispatch(example, monkeypatch):
    from research_loops.evaluation import SubprocessEvaluator
    from research_loops.domain import Verdict
    monkeypatch.setattr(SubprocessEvaluator, "evaluate", lambda *a, **k: Verdict(mse=1, baseline_mse=2, improvement=.5, supported=False, predictions=(0,), squared_errors=(1,)))
    with pytest.raises(IntegrityError, match="pilot"):
        asyncio.run(run(example))
    repo = Repository(example / ".rloop")
    assert repo.runs() == []
    assert repo.db.execute("SELECT pilot FROM project").fetchone()[0] is None
    repo.close()


def test_killed_coordinator_releases_lock_and_preserves_interruption(example):
    # A real process is killed after dispatch; resume must not invent success.
    script = "from pathlib import Path; import sys,time; from research_loops.coordinator import prepare; from research_loops.domain import WorkerContract; r,c,k=prepare(Path(sys.argv[1])); r.dispatch(WorkerContract(run_id='killed',registration_hash=k,goal='test',prediction='negative',seed=7,variant=0,input_hash='a'*64)); Path(sys.argv[2]).write_text('ready'); time.sleep(60)"
    ready = example / "ready"
    process = subprocess.Popen([sys.executable, "-I", "-c", script, str(example), str(ready)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        deadline = time.monotonic() + 10
        while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(.02)
        assert ready.exists(), process.stderr.read() if process.poll() is not None else "child not ready"
    finally:
        process.kill()
        process.wait()
        process.stderr.close()
    asyncio.run(run(example, resume_only=True))
    repo = Repository(example / ".rloop")
    assert repo.runs()[0]["execution_status"] == "interrupted"
    repo.close()
