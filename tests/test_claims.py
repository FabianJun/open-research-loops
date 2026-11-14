import asyncio
import sqlite3

import pytest

from research_loops.coordinator import prepare, reconcile
from research_loops.domain import IntegrityError, Limits, WorkerContract, Workspace
from research_loops.fake import FakeBackend


def test_claim_gate_challenge_and_append_only_resolution(example):
    repo, contract, key = prepare(example)
    try:
        task = WorkerContract(run_id="test", registration_hash=key, goal="test", prediction="zero fails", seed=7, variant=0, input_hash="a" * 64)
        repo.dispatch(task)
        with pytest.raises(IntegrityError, match="promotion"):
            repo.promote_claim(task.run_id)
        work = Workspace(root=repo.root / "runs" / task.run_id / "outbox")
        asyncio.run(FakeBackend().run(task, work, Limits()))
        reconcile(repo, contract, key)
        claim = repo.promote_claim(task.run_id)
        original = dict(repo.db.execute("SELECT * FROM claims WHERE id=?", (claim,)).fetchone())
        repo.challenge("challenge-1", claim, task.run_id, "Scope may be overstated; inspect per-example errors.")
        repo.resolve_challenge("challenge-1", "Retain narrow simulated scope; no discovery claim.")
        assert dict(repo.db.execute("SELECT * FROM claims WHERE id=?", (claim,)).fetchone()) == original
        with pytest.raises(sqlite3.IntegrityError):
            repo.db.execute("UPDATE claims SET statement='overwritten'")
        repo.db.rollback()
        assert repo.db.execute("SELECT count(*) FROM events WHERE kind='challenge_resolution'").fetchone()[0] == 1
    finally:
        repo.close()
