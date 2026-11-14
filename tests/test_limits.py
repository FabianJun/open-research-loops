import asyncio
import json
import sqlite3
import time

import pytest

from research_loops.coordinator import prepare
from research_loops.domain import IntegrityError, WorkerContract
from research_loops.scheduler import bounded


def task(key, run_id):
    return WorkerContract(run_id=run_id, registration_hash=key, goal="signal", prediction="test", seed=7, variant=0, input_hash="a" * 64)


def test_budget_reservation_and_attempt_gate(example):
    payload = json.loads((example / "contract.json").read_text())
    payload["limits"] = {"budget_micro_usd": 10, "max_attempts": 2}
    (example / "contract.json").write_text(json.dumps(payload))
    repo, _, key = prepare(example)
    try:
        repo.dispatch(task(key, "a"), 6)
        with pytest.raises(IntegrityError, match="budget"):
            repo.dispatch(task(key, "b"), 5)
        repo.dispatch(task(key, "b"), 4)
        with pytest.raises(IntegrityError, match="attempt"):
            repo.dispatch(task(key, "c"), 0)
        repo.fail("a", "interrupted", "unknown usage retains reservation")
        assert repo.db.execute("SELECT reserved_micro_usd FROM project").fetchone()[0] == 10
    finally:
        repo.close()


def test_deadline_and_pilot_gate(example):
    repo, _, key = prepare(example)
    try:
        with pytest.raises(IntegrityError, match="pilot"):
            repo.require_pilot()
        with pytest.raises(IntegrityError, match="pilot"):
            repo.pilot({"positive_control": False, "negative_control": True, "nonconstant": True, "baseline": True})
        repo.pilot({"positive_control": True, "negative_control": True, "nonconstant": True, "baseline": True})
        repo.require_pilot()
        with repo.db:
            repo.db.execute("UPDATE project SET deadline=?", (time.time() - 1,))
        with pytest.raises(IntegrityError, match="deadline"):
            repo.dispatch(task(key, "a"))
    finally:
        repo.close()


def test_pool_overlaps_exactly_four():
    async def check():
        active = peak = 0
        async def operation(item):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.02)
            active -= 1
            return item
        assert await bounded(range(12), operation, 4) == list(range(12))
        assert peak == 4
    asyncio.run(check())


def test_amendment_is_explicit_and_retains_history(example):
    repo, contract, key = prepare(example)
    try:
        from research_loops.evaluation import evaluator_hash
        payload = contract.model_copy(update={"goal": "amended goal"}).model_dump(mode="json")
        inputs = json.loads(repo.db.execute("SELECT inputs FROM registrations").fetchone()[0])
        with pytest.raises(IntegrityError, match="amendment"):
            repo.register(payload, evaluator_hash(), inputs)
        newer = repo.register(payload, evaluator_hash(), inputs, supersedes=key, reason="owner changed scientific goal")
        assert newer != key
        assert repo.db.execute("SELECT count(*) FROM registrations").fetchone()[0] == 2
        assert "comparisons_flagged" in repo.db.execute("SELECT payload FROM events WHERE kind='amendment'").fetchone()[0]
    finally:
        repo.close()
