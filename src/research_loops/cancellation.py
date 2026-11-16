"""Atomic, job-bound cancellation requests; no coordinator lock is required."""

import json
from pathlib import Path

from research_loops.domain import canonical
from research_loops.paths import atomic_write


class RunCancelled(Exception):
    pass


def active_job(repo) -> str | None:
    row = repo.db.execute("SELECT record_id FROM events WHERE kind='job_started' ORDER BY seq DESC LIMIT 1").fetchone()
    if row and not repo.db.execute("SELECT 1 FROM events WHERE kind='job_finished' AND record_id=?", (row[0],)).fetchone():
        return row[0]
    return None


class Cancellation:
    def __init__(self, root: Path, job_id: str):
        self.path = root / "cancel.json"
        self.job_id = job_id

    def requested(self) -> bool:
        try:
            value = json.loads(self.path.read_bytes())
            return isinstance(value, dict) and value.get("job_id") == self.job_id
        except (FileNotFoundError, ValueError):
            return False

    def check(self) -> None:
        if self.requested():
            raise RunCancelled()


def request(repo) -> dict:
    job_id = active_job(repo)
    value = {"job_id": job_id}
    path = repo.root / "cancel.json"
    # Identical repeats leave the request file unchanged.
    try:
        same = json.loads(path.read_bytes()) == value
    except (FileNotFoundError, ValueError):
        same = False
    if not same:
        atomic_write(path, canonical(value).encode())
    return {"schema": "rloop.cancel/1", "job_id": job_id, "cancel_requested": job_id is not None}
