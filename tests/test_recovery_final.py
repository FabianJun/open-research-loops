import asyncio
import json
import os
from pathlib import Path

import pytest

from research_loops.coordinator import prepare, reconcile, run
from research_loops.domain import IntegrityError, Limits, WorkerContract, Workspace, canonical
from research_loops.fake import FakeBackend
from research_loops.paths import atomic_write
from research_loops.processes import process_identity
from research_loops.storage import Repository


def small(example):
    data = json.loads((example / "contract.json").read_text())
    data.update({"seeds": [7], "variants_per_seed": 2})
    (example / "contract.json").write_text(json.dumps(data))


def test_final_is_once_and_seals_workers(example):
    small(example)
    asyncio.run(run(example))
    asyncio.run(run(example, final=True))
    with pytest.raises(IntegrityError, match="already consumed"):
        asyncio.run(run(example, final=True))
    with pytest.raises(IntegrityError, match="sealed"):
        asyncio.run(run(example))
    repo = Repository(example / ".rloop")
    ticket = json.loads(repo.db.execute("SELECT final_ticket FROM project").fetchone()[0])
    assert ticket["verdict"]["mse"] == 0
    assert len(ticket["verdict"]["predictions"]) == 128
    repo.close()


def test_crashed_final_does_not_reset_ticket(example):
    small(example)
    asyncio.run(run(example))
    repo = Repository(example / ".rloop")
    selection = json.loads(repo.db.execute("SELECT selection FROM project").fetchone()[0])
    repo.consume_final(selection["winner"])
    repo.close()
    asyncio.run(run(example, resume_only=True))
    with pytest.raises(IntegrityError, match="already consumed"):
        asyncio.run(run(example, final=True))


def test_final_labels_are_not_reopened_before_ticket(example, monkeypatch):
    import sqlite3
    small(example)
    repo, _, _ = prepare(example)
    repo.close()
    original = Path.read_bytes
    seen = []
    def guarded(path):
        if path.name == "final.json" and "private" in path.parts:
            db = sqlite3.connect(f"file:{example / '.rloop' / 'state.sqlite'}?mode=ro", uri=True)
            try:
                ticket = db.execute("SELECT final_ticket FROM project").fetchone()[0]
            finally:
                db.close()
            assert ticket is not None, "final data opened before durable ticket"
            seen.append(ticket)
        return original(path)
    monkeypatch.setattr(Path, "read_bytes", guarded)
    asyncio.run(run(example))
    assert seen == []
    asyncio.run(run(example, final=True))
    assert len(seen) == 1
    with pytest.raises(IntegrityError):
        asyncio.run(run(example, final=True))
    assert len(seen) == 1


def test_resume_dead_worker_counts_partial_outbox(example):
    repo, contract, key = prepare(example)
    task = WorkerContract(run_id="interrupted", registration_hash=key, goal="test", prediction="negative", seed=7, variant=0, input_hash="a" * 64)
    repo.dispatch(task)
    outbox = repo.root / "runs" / task.run_id / "outbox"
    outbox.mkdir(parents=True)
    (outbox / "journal.jsonl").write_text('{"kind":"proposal"}\n')
    repo.close()
    asyncio.run(run(example, resume_only=True))
    repo = Repository(example / ".rloop")
    try:
        assert repo.runs()[0]["execution_status"] == "interrupted"
        assert repo.db.execute("SELECT count(*) FROM events WHERE kind='partial_outbox'").fetchone()[0] == 1
        before = list(repo.db.iterdump())
        reconcile(repo, contract, key)
        assert before == list(repo.db.iterdump())
    finally:
        repo.close()


def test_resume_imports_sealed_report_once(example):
    repo, contract, key = prepare(example)
    task = WorkerContract(run_id="sealed", registration_hash=key, goal="test", prediction="positive", seed=7, variant=1, input_hash="a" * 64)
    repo.dispatch(task)
    work = Workspace(root=repo.root / "runs" / task.run_id / "outbox")
    asyncio.run(FakeBackend().run(task, work, Limits()))
    repo.close()
    asyncio.run(run(example, resume_only=True))
    repo = Repository(example / ".rloop")
    try:
        assert repo.runs()[0]["execution_status"] == "completed"
        assert repo.runs()[0]["scientific_outcome"] == "supported"
        before = list(repo.db.iterdump())
        reconcile(repo, contract, key)
        assert before == list(repo.db.iterdump())
    finally:
        repo.close()


def test_resume_never_kills_reused_pid_and_blocks_live_evaluator(example):
    repo, contract, key = prepare(example)
    task = WorkerContract(run_id="live", registration_hash=key, goal="test", prediction="test", seed=7, variant=0, input_hash="a" * 64)
    repo.dispatch(task)
    work = Workspace(root=repo.root / "runs" / task.run_id / "outbox")
    result = asyncio.run(FakeBackend().run(task, work, Limits()))
    repo.import_report(result, work)
    receipt = repo.root / "evaluation_receipts" / "live.json"
    identity = process_identity(os.getpid())
    atomic_write(receipt, canonical({"state": "running", "pid": os.getpid(), "creation": identity}).encode())
    with pytest.raises(IntegrityError, match="alive"):
        reconcile(repo, contract, key)
    assert repo.runs()[0]["execution_status"] == "running"
    atomic_write(receipt, canonical({"state": "running", "pid": os.getpid(), "creation": "old-reused-pid"}).encode())
    reconcile(repo, contract, key)
    assert repo.runs()[0]["execution_status"] == "interrupted"
    assert process_identity(os.getpid()) == identity
    repo.close()
