"""Single-writer SQLite state and content-addressed import."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from research_loops.domain import IntegrityError, Verdict, WorkerContract, WorkerReport, Workspace, canonical, content_hash, digest, validate_candidate
from research_loops.paths import atomic_write, confined


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Repository:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(root / "state.sqlite")
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA busy_timeout=3000")
        self.db.execute("CREATE TABLE IF NOT EXISTS schema_migrations (number TEXT PRIMARY KEY, hash TEXT NOT NULL)")
        for path in sorted((Path(__file__).parent / "migrations").glob("*.sql")):
            data = path.read_bytes()
            checksum = digest(data)
            row = self.db.execute("SELECT hash FROM schema_migrations WHERE number=?", (path.name,)).fetchone()
            if row and row[0] != checksum:
                raise IntegrityError("migration checksum changed")
            if not row:
                # Migration contents are package-owned SQL, not worker data.
                self.db.executescript("BEGIN IMMEDIATE;\n" + data.decode() + "\nINSERT INTO schema_migrations VALUES ('" + path.name + "','" + checksum + "');\nCOMMIT;")

    def close(self) -> None:
        self.db.close()

    def event(self, kind: str, record_id: str, payload: dict) -> None:
        self.db.execute("INSERT INTO events(kind,record_id,payload,created) VALUES(?,?,?,?)", (kind, record_id, canonical(payload), now()))
        self.db.execute("UPDATE project SET revision=revision+1 WHERE id=1")

    def register(self, contract: dict, evaluator_hash: str, inputs: dict, *, supersedes: str | None = None, reason: str | None = None) -> str:
        value = {"contract": contract, "evaluator_hash": evaluator_hash, "inputs": inputs}
        key = content_hash(value)
        if not self.db.execute("SELECT 1 FROM registrations WHERE hash=?", (key,)).fetchone():
            with self.db:
                self.db.execute("INSERT INTO registrations VALUES(?,?,?,?,?,?,?)", (key, canonical(contract), evaluator_hash, canonical(inputs), supersedes, reason, now()))
                self.event("registration", key, value)
        return key

    def dispatch(self, assignment: WorkerContract) -> None:
        with self.db:
            self.db.execute("INSERT INTO runs(id,registration_hash,assignment,execution_status,prediction,created) VALUES(?,?,?,'running',?,?)", (assignment.run_id, assignment.registration_hash, canonical(assignment), assignment.prediction, now()))
            self.event("dispatch", assignment.run_id, assignment.model_dump(mode="json"))

    def import_report(self, report: WorkerReport, outbox: Workspace) -> bool:
        row = self.db.execute("SELECT * FROM runs WHERE id=?", (report.run_id,)).fetchone()
        if not row or row["registration_hash"] != report.contract_hash or report.report_id != report.run_id:
            raise IntegrityError("unknown report scope")
        payload = canonical(report)
        checksum = digest(payload.encode())
        if row["report_hash"]:
            if row["report_hash"] != checksum:
                raise IntegrityError("conflicting duplicate report")
            return False
        if row["execution_status"] != "running":
            raise IntegrityError("run is not importing")
        staged = []
        for kind, artifact in (("candidate", report.candidate), ("transcript", report.transcript)):
            path = confined(outbox.root, artifact.path)
            if not path.is_file() or path.stat().st_size > 1_000_000:
                raise IntegrityError("missing/oversized artifact")
            data = path.read_bytes()
            if digest(data) != artifact.sha256 or len(data) != artifact.size:
                raise IntegrityError("evidence hash mismatch")
            if kind == "candidate":
                validate_candidate(json.loads(data))
            if kind == "transcript" and digest(json.loads(data)["prompt"].encode()) != report.prompt_hash:
                raise IntegrityError("prompt hash mismatch")
            target = self.root / "objects" / artifact.sha256
            if not target.exists():
                atomic_write(target, data, exclusive=True)
            if digest(target.read_bytes()) != artifact.sha256:
                raise IntegrityError("content-addressed object corrupt")
            staged.append((f"{report.run_id}:{kind}", report.run_id, kind, artifact.sha256, artifact.size))
        with self.db:
            self.db.executemany("INSERT INTO artifacts VALUES(?,?,?,?,?)", staged)
            self.db.execute("UPDATE runs SET report_hash=?,report=? WHERE id=?", (checksum, payload, report.run_id))
            self.event("import", report.run_id, {"report": report.model_dump(mode="json"), "artifacts": staged})
        return True

    def artifact(self, run_id: str, kind: str) -> bytes:
        row = self.db.execute("SELECT hash FROM artifacts WHERE run_id=? AND kind=?", (run_id, kind)).fetchone()
        if not row:
            raise IntegrityError("artifact missing")
        data = (self.root / "objects" / row[0]).read_bytes()
        if digest(data) != row[0]:
            raise IntegrityError("sealed artifact modified")
        return data

    def verdict(self, run_id: str, value: Verdict) -> None:
        with self.db:
            row = self.db.execute("SELECT report_hash,verdict FROM runs WHERE id=?", (run_id,)).fetchone()
            if not row or not row[0] or row[1]:
                raise IntegrityError("verdict requires imported, unevaluated run")
            self.db.execute("UPDATE runs SET execution_status='completed',scientific_outcome=?,verification_status='checked',verdict=? WHERE id=?", ("supported" if value.supported else "negative", canonical(value), run_id))
            self.event("verdict", run_id, value.model_dump(mode="json"))

    def fail(self, run_id: str, status: str, reason: str) -> None:
        if status not in ("technical_error", "timed_out", "interrupted", "cancelled"):
            raise IntegrityError("invalid failure status")
        with self.db:
            self.db.execute("UPDATE runs SET execution_status=?,scientific_outcome=NULL,verification_status='unverified',error=? WHERE id=? AND execution_status='running'", (status, reason, run_id))
            self.event(status, run_id, {"reason": reason})

    def runs(self) -> list[dict]:
        return [dict(row) for row in self.db.execute("SELECT * FROM runs ORDER BY id")]
