import asyncio
import json
import os
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

import pytest

from research_loops.adapters.common import SDKBackend
from research_loops.compute.core import fetch_outputs, new_receipt, no_links, package
from research_loops.contracts import GrainContract
from research_loops.coordinator import data_root, prepare, reconcile, run
from research_loops.domain import IntegrityError, Limits, WorkerContract, Workspace, digest
from research_loops.fake import FakeBackend
from research_loops.paths import long_path, plain_path
from research_loops.sandbox import ContainerSandbox
from research_loops.tools import ToolService
from test_compute import job_dir, outputs
from test_long_paths import deep_folder


def linked_folder(path, target):
    target.mkdir(exist_ok=True)
    if os.name == "nt":
        import _winapi
        _winapi.CreateJunction(str(target), str(long_path(path)))
    else:
        path.symlink_to(target, target_is_directory=True)
    return path


def assignment(key="a" * 64):
    return WorkerContract(run_id="case", registration_hash=key, goal="test", prediction="positive",
        seed=7, variant=0, input_hash="b" * 64)


@pytest.fixture
def running(example):
    repo, contract, key = prepare(example)
    with closing(repo):
        task = assignment(key)
        repo.dispatch(task)
        work = Workspace(root=repo.root / "runs" / task.run_id / "outbox")
        work.root.mkdir(parents=True)
        yield repo, contract, task, work


def test_links_below_root(tmp_path):
    from research_loops.paths import refuse_links_below

    target = tmp_path / "target"
    root = linked_folder(tmp_path / "linked", target)
    with pytest.raises(IntegrityError, match="forbidden"):
        refuse_links_below(root, root / "missing")
    middle = linked_folder(target / "middle", tmp_path / "other")
    with pytest.raises(IntegrityError, match="forbidden: target/middle$"):
        refuse_links_below(target, middle / "missing")
    refuse_links_below(target, target / "missing" / "tail")
    for outside in (tmp_path / "other", target / "missing" / ".." / ".." / "other"):
        with pytest.raises(IntegrityError, match="outside its trusted root"):
            refuse_links_below(target, outside)


def test_run_refuses_linked_runs(example, tmp_path):
    repo, _, _ = prepare(example)
    outside = tmp_path / "outside"
    with closing(repo):
        linked_folder(repo.root / "runs", outside)
    with pytest.RaisesGroup(pytest.RaisesExc(IntegrityError, match="forbidden: .rloop/runs$")):
        asyncio.run(run(example, worker_runs=1))
    repo, _, _ = prepare(example)
    with closing(repo):
        assert repo.runs() == []  # The assignment is not used up; it runs once the folder is fixed.
    assert not list(outside.iterdir())


def test_tool_launch_refuses_linked_run(tmp_path, monkeypatch):
    outside = tmp_path / "outside"
    run_dir = linked_folder(tmp_path / "run", outside)
    sandbox = ContainerSandbox("sha256:" + "a" * 64)

    def unexpected(*args, **kwargs):
        pytest.fail("preflight ran for a linked run folder")

    monkeypatch.setattr(sandbox, "preflight", unexpected)
    with pytest.raises(IntegrityError, match="sandbox mount links forbidden: run folder run$"):
        sandbox.tool_launch(assignment(), run_dir / "outbox")
    assert not list(outside.iterdir())
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(IntegrityError, match="workspace folder outbox$"):
        sandbox.tool_launch(assignment(), linked_folder(plain / "outbox", tmp_path / "other"))
    with pytest.raises(IntegrityError, match="public folder public$"):
        sandbox.command("test", plain / "work", linked_folder(plain / "public", tmp_path / "other"))


def test_data_root_refuses_linked_data(tmp_path):
    root = tmp_path / ".rloop"
    root.mkdir()
    linked_folder(root / "data", tmp_path / "outside")
    with pytest.raises(IntegrityError, match="forbidden"):
        data_root(SimpleNamespace(root=root), GrainContract(), "development")


@pytest.mark.parametrize("name", ["journal.jsonl", "report.json"])
def test_recovery_refuses_linked_file(running, tmp_path, name):
    repo, contract, task, work = running
    linked_folder(work.root / name, tmp_path / "outside")
    with pytest.raises(IntegrityError, match="forbidden"):
        reconcile(repo, contract, task.registration_hash)


def test_finish_refuses_linked_submission(tmp_path):
    work = Workspace(root=tmp_path / "outbox")
    work.root.mkdir()
    linked_folder(work.root / "submission.json", tmp_path / "outside")
    backend = SDKBackend("test", auth_mode="claude_code")
    with pytest.raises(IntegrityError, match="forbidden"):
        backend.finish(assignment(), work, None, sdk_version="test", cost=0, usage={}, trace={})


def test_journal_refuses_linked_file(tmp_path):
    service = ToolService(assignment(), tmp_path / "outbox")
    linked_folder(service.root / "journal.jsonl", tmp_path / "outside")
    with pytest.raises(IntegrityError, match="forbidden"):
        service.journal("proposal", {})


def test_compute_refuses_deep_link(tmp_path):
    root = deep_folder(tmp_path, 200) / ("nested-" + "x" * 64)
    long_path(root).mkdir(parents=True)
    link = linked_folder(root / "linked", tmp_path / "outside")
    assert len(str(link)) > 260
    with pytest.raises(IntegrityError, match="compute paths must not contain symlinks or junctions"):
        no_links(link / "missing")


def test_compute_names_other_reparse_points(tmp_path, monkeypatch):
    from research_loops.compute import core

    def refusal(path):
        raise IntegrityError("reparse points are forbidden")

    monkeypatch.setattr(core, "refuse_link", refusal)
    with pytest.raises(IntegrityError, match="^compute reparse points forbidden$"):
        no_links(tmp_path)


def test_import_refuses_artifact_with_two_links(running, tmp_path):
    repo, _, task, work = running
    result = asyncio.run(FakeBackend().run(task, work, Limits()))
    artifact = work.root / result.candidate.path
    os.link(artifact, tmp_path / "copy.json")
    with artifact.open("rb") as stream:
        assert os.fstat(stream.fileno()).st_nlink == 2
    with pytest.raises(IntegrityError, match="artifact must be a regular file with one link"):
        repo.import_report(result, work)
    assert repo.runs()[0]["report_hash"] is None


def test_compute_refuses_output_with_two_links(job_dir):
    receipt = new_receipt(package(job_dir), "manual", False)
    source, target = job_dir / "source", job_dir / "target"
    outputs(source)
    os.link(source / "labels.npz", job_dir / "copy.npz")
    with pytest.raises(IntegrityError, match="compute outputs must have one link"):
        fetch_outputs(receipt, source, target)
    assert not target.exists()


def test_compute_refetch_replaces_linked_target(job_dir):
    receipt = new_receipt(package(job_dir), "manual", False)
    source, target = job_dir / "source", job_dir / "target"
    outputs(source)
    receipt = fetch_outputs(receipt, source, target)
    other = job_dir / "copy.json"
    os.link(target / "result.json", other)
    original = other.read_bytes()
    updated = b'{"ok":false}\n'
    (source / "result.json").write_bytes(updated)
    receipt = fetch_outputs(receipt, source, target)
    assert other.read_bytes() == original
    assert (target / "result.json").read_bytes() == updated
    assert receipt.outputs["result.json"].sha256 == digest(updated)
    assert not list(target.glob(".pending-*"))


@pytest.mark.parametrize("oversized", [False, True], ids=["normal", "oversized"])
def test_recovery_journal_payload(running, monkeypatch, oversized):
    repo, contract, task, work = running
    journal = work.root / "journal.jsonl"
    data = b"x" * 999_999 + b"\xc3\xbc\n" if oversized else b'{"kind":"proposal"}\r\n'
    journal.write_bytes(data)
    modes = []
    original = Path.open

    def track(path, mode="r", *args, **kwargs):
        if plain_path(path) == journal:
            modes.append(mode)
        return original(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", track)
    reconcile(repo, contract, task.registration_hash)
    saved = json.loads(repo.db.execute("SELECT payload FROM events WHERE kind='partial_outbox'").fetchone()[0])
    if oversized:
        assert saved == {"journal_hash": digest(data[:1_000_000]),
            "text": "x" * 999_999 + "\ufffd", "truncated": True}
    else:
        assert saved == {"journal_hash": digest(data), "text": '{"kind":"proposal"}\n'}
    assert modes == ["rb"]


def test_final_checks_data_before_ticket(monkeypatch):
    from research_loops import coordinator, selection

    def refusal(*args):
        raise IntegrityError("links/reparse points are forbidden: .rloop/data")

    monkeypatch.setattr(selection, "select", lambda *args: {"winner": "case"})
    monkeypatch.setattr(coordinator, "data_root", refusal)
    repo = SimpleNamespace(consume_final=lambda run_id: pytest.fail("final ticket used before the folder check"))
    with pytest.raises(IntegrityError, match="forbidden"):
        coordinator.final_evaluation(repo, GrainContract(), "a" * 64)
