"""Single-writer SQLite state and content-addressed import."""

from __future__ import annotations

import json
import sqlite3
import time
import sys
import os
import struct
from datetime import datetime, timezone
from pathlib import Path

from research_loops.domain import IntegrityError, Verdict, WorkerContract, Workspace, canonical, content_hash, digest, validate_candidate
from research_loops.reports import WorkerReport
from research_loops.paths import atomic_write, confined
from research_loops.locking import ProjectLock


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _wal_image(database: bytes, wal: bytes) -> bytes:
    """Replay only checksum-verified committed WAL frames into a memory image."""
    if len(wal) < 32:
        return database
    magic, version, page_size = struct.unpack(">III", wal[:12])
    if magic not in (0x377F0682, 0x377F0683) or version != 3007000:
        raise IntegrityError("unsupported SQLite WAL")
    if page_size < 512 or page_size > 65536 or page_size & (page_size - 1):
        raise IntegrityError("invalid SQLite WAL page size")
    endian = "<" if magic == 0x377F0682 else ">"

    def checksum(data, seed=(0, 0)):
        a, b = seed
        words = struct.unpack(endian + "I" * (len(data) // 4), data)
        for index in range(0, len(words), 2):
            a = (a + words[index] + b) & 0xFFFFFFFF
            b = (b + words[index + 1] + a) & 0xFFFFFFFF
        return a, b

    seed = checksum(wal[:24])
    if seed != struct.unpack(">II", wal[24:32]):
        raise IntegrityError("invalid SQLite WAL header checksum")
    frames, committed, size = [], 0, 0
    for offset in range(32, len(wal) - page_size - 23, page_size + 24):
        frame = wal[offset:offset + page_size + 24]
        page, pages = struct.unpack(">II", frame[:8])
        if not page or frame[8:16] != wal[16:24]:
            break  # An unused tail can remain after a WAL reset.
        seed = checksum(frame[:8] + frame[24:], seed)
        if seed != struct.unpack(">II", frame[16:24]):
            break  # An incomplete transaction is never visible to readers.
        frames.append((page, frame[24:]))
        if pages:
            committed, size = len(frames), pages
    if not committed:
        return database
    image = bytearray(database[:size * page_size])
    image.extend(b"\0" * (size * page_size - len(image)))
    for page, data in frames[:committed]:
        if page <= size:
            image[(page - 1) * page_size:page * page_size] = data
    return bytes(image)


class ReadOnlyRepository:
    """Lock-free memory snapshot; never map or create the project's WAL index.

    Opening WAL directly with mode=ro can still write read marks in -shm.
    Two matching DB/WAL reads detect checkpoints and concurrent commits; SQLite
    reads the resulting committed image, with query_only enforcing SELECTs.
    """

    def __init__(self, root: Path):
        self.root = root
        path = (root / "state.sqlite").resolve()
        if not path.is_file():
            raise FileNotFoundError("project has no database")
        wal_path = path.with_name(path.name + "-wal")

        def capture():
            database = path.read_bytes()
            try:
                wal = wal_path.read_bytes()
            except FileNotFoundError:
                wal = b""
            return database, wal

        for _ in range(5):
            first = capture()
            if first == capture():
                break
        else:
            raise IntegrityError("database changed during snapshot; poll again")
        # immutable prevents SQLite from touching journal/-shm files at open.
        # WAL is applied above, rather than silently ignored by immutable mode.
        self.db = sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True)
        try:
            image = bytearray(_wal_image(*first))
            # An in-memory database has no WAL VFS; its committed pages are
            # already materialised, so use the rollback-format header there.
            image[18:20] = b"\x01\x01"
            self.db.deserialize(bytes(image))
            self.db.row_factory = sqlite3.Row
            self.db.execute("PRAGMA query_only=ON")
            self.db.execute("BEGIN")
        except BaseException:
            self.db.close()
            raise

    def runs(self) -> list[dict]:
        return [dict(row) for row in self.db.execute("SELECT * FROM runs ORDER BY id")]

    def close(self) -> None:
        self.db.close()


class Repository:
    def __init__(self, root: Path):
        self.lock = ProjectLock(root)
        self.lock.__enter__()
        try:
            for attempt in range(3):
                try:
                    self._open(root)
                    break
                except sqlite3.OperationalError as exc:
                    if hasattr(self, "db"):
                        self.db.close()
                    # Windows can finish closing killed-process file handles after wait().
                    # Retry startup only, never replay a research action or delete WAL files.
                    if os.name != "nt" or getattr(exc, "sqlite_errorcode", 0) & 255 != sqlite3.SQLITE_IOERR or attempt == 2:
                        raise
                    time.sleep(0.05 * (attempt + 1))
        except BaseException:
            if hasattr(self, "db"):
                self.db.close()
            self.lock.__exit__()
            raise

    def _open(self, root: Path) -> None:
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
        self.lock.__exit__()

    def event(self, kind: str, record_id: str, payload: dict) -> None:
        self.db.execute("INSERT INTO events(kind,record_id,payload,created) VALUES(?,?,?,?)", (kind, record_id, canonical(payload), now()))
        self.db.execute("UPDATE project SET revision=revision+1 WHERE id=1")

    def register(self, contract: dict, evaluator_hash: str, inputs: dict, *, supersedes: str | None = None, reason: str | None = None) -> str:
        value = {"contract": contract, "evaluator_hash": evaluator_hash, "inputs": inputs}
        key = content_hash(value)
        current = self.db.execute("SELECT current_registration FROM project").fetchone()[0]
        if current and current != key and (supersedes != current or not reason or not reason.strip()):
            raise IntegrityError("registration changed; explicitly plan an amendment with a reason")
        if self.db.execute("SELECT final_ticket FROM project").fetchone()[0] and current != key:
            raise IntegrityError("sealed campaign cannot amend registration or reset final use")
        if not self.db.execute("SELECT 1 FROM registrations WHERE hash=?", (key,)).fetchone():
            with self.db:
                self.db.execute("INSERT INTO registrations VALUES(?,?,?,?,?,?,?)", (key, canonical(contract), evaluator_hash, canonical(inputs), supersedes, reason, now()))
                self.event("registration", key, value)
                limits = contract.get("limits", {})
                self.db.execute("UPDATE project SET current_registration=?,cap_micro_usd=?,max_attempts=?,pilot=NULL,selection=NULL WHERE id=1", (key, limits.get("budget_micro_usd", 0), limits.get("max_attempts", 48)))
                if supersedes:
                    self.event("amendment", key, {"supersedes": supersedes, "reason": reason, "comparisons_flagged": True})
        return key

    def dispatch(self, assignment: WorkerContract, reserve_micro_usd: int = 0, *, execution_metadata: dict | None = None) -> None:
        with self.db:
            state = self.db.execute("SELECT * FROM project").fetchone()
            if assignment.registration_hash != state["current_registration"]:
                raise IntegrityError("assignment does not use current registration")
            if state["final_ticket"]:
                raise IntegrityError("campaign sealed; no worker may see final results")
            limits = (execution_metadata or {}).get("run_limits")
            if limits:
                from research_loops.authorization import LimitReached
                rows = [row for row in self.runs() if json.loads(row["execution_metadata"]).get("provider") == execution_metadata["provider"]]
                if any(row["execution_status"] == "limit_reached" for row in rows):
                    raise LimitReached("pilot previously reached a provider limit; owner review required")
                if len(rows) >= limits["max_worker_runs"]:
                    raise LimitReached("maximum worker runs reached")
                if sum(row["execution_status"] == "running" for row in rows) >= limits["max_parallel_workers"]:
                    raise LimitReached("maximum parallel workers reached")
            if self.db.execute("SELECT count(*) FROM runs").fetchone()[0] + state["control_attempts"] >= state["max_attempts"]:
                raise IntegrityError("attempt allowance exhausted")
            authorized_cap = (execution_metadata or {}).get("authorization_cap_micro_usd")
            cap = min(state["cap_micro_usd"], authorized_cap) if authorized_cap is not None else state["cap_micro_usd"]
            if reserve_micro_usd < 0 or state["spent_micro_usd"] + state["reserved_micro_usd"] + reserve_micro_usd > cap:
                raise IntegrityError("shared budget exceeded")
            registration = json.loads(self.db.execute("SELECT payload FROM registrations WHERE hash=?", (assignment.registration_hash,)).fetchone()[0])
            deadline = state["deadline"] or time.time() + registration["limits"]["project_seconds"]
            if time.time() >= deadline:
                raise IntegrityError("project deadline reached")
            self.db.execute("UPDATE project SET deadline=?,reserved_micro_usd=reserved_micro_usd+?", (deadline, reserve_micro_usd))
            self.db.execute("INSERT INTO runs(id,registration_hash,assignment,execution_status,prediction,created,reserved_micro_usd) VALUES(?,?,?,'running',?,?,?)", (assignment.run_id, assignment.registration_hash, canonical(assignment), assignment.prediction, now(), reserve_micro_usd))
            if execution_metadata:
                self.db.execute("UPDATE runs SET execution_metadata=? WHERE id=?", (canonical(execution_metadata), assignment.run_id))
            self.event("dispatch", assignment.run_id, assignment.model_dump(mode="json"))
            self.event("execution", assignment.run_id, execution_metadata or {"backend": "fake", "provider": "offline", "model": "deterministic-v1", "sdk_version": None, "cost_micro_usd": 0})
            folder = Path(__file__).parent
            self.event("runtime", assignment.run_id, {"framework": "0.2.0", "python": sys.version.split()[0],
                "source_hash": digest(b"".join(path.read_bytes() for path in sorted(folder.rglob("*.py"))))})

    def import_report(self, report: WorkerReport, outbox: Workspace) -> bool:
        report = WorkerReport.model_validate(report.model_dump(mode="json"))
        row = self.db.execute("SELECT * FROM runs WHERE id=?", (report.run_id,)).fetchone()
        if not row or row["registration_hash"] != report.contract_hash or report.report_id != report.run_id:
            raise IntegrityError("unknown report scope")
        payload = canonical(report)
        checksum = digest(payload.encode())
        if row["report_hash"]:
            if row["report_hash"] != checksum:
                # Phase-2 envelopes omit the new optional execution fields. Compare
                # validated values without rewriting their immutable original bytes.
                if (digest(row["report"].encode()) != row["report_hash"]
                        or WorkerReport.model_validate_json(row["report"]) != report):
                    raise IntegrityError("conflicting duplicate report")
            return False
        expected = json.loads(row["execution_metadata"])
        if (report.backend != expected["backend"] or report.provider != expected["provider"] or report.model != expected["model"]
            or report.sandbox_image != expected.get("sandbox_image") or report.sdk_version != expected.get("sdk_version")
            or (report.backend == "fake" and report.cost_micro_usd != 0)):
            raise IntegrityError("report backend/provider/model/cost is not authorized for this dispatch")
        if report.backend != "fake" and (not report.sdk_trace or report.sdk_version != expected.get("sdk_version")
                or report.sandbox_image != expected.get("sandbox_image")):
            raise IntegrityError("SDK report lacks trusted dispatch metadata/trace")
        assignment = json.loads(row["assignment"])
        if report.seed != assignment["seed"]:
            raise IntegrityError("report seed differs from registration")
        if row["execution_status"] != "running":
            raise IntegrityError("run is not importing")
        staged = []
        candidate_value = None
        for kind, artifact in (("candidate", report.candidate), ("transcript", report.transcript), ("sdk_trace", report.sdk_trace)):
            if artifact is None:
                continue
            path = confined(outbox.root, artifact.path)
            if not path.is_file() or path.stat().st_size > 1_000_000:
                raise IntegrityError("missing/oversized artifact")
            data = path.read_bytes()
            if digest(data) != artifact.sha256 or len(data) != artifact.size:
                raise IntegrityError("evidence hash mismatch")
            if kind == "candidate":
                candidate_value = json.loads(data)
                registration = json.loads(self.db.execute("SELECT payload FROM registrations WHERE hash=?", (report.contract_hash,)).fetchone()[0])
                if registration.get("name") == "grain-316l":
                    from research_loops.grain_evaluator import validate_params
                    validate_params(candidate_value)
                else:
                    validate_candidate(candidate_value)
            if kind == "transcript":
                transcript = json.loads(data)
                if (digest(transcript["prompt"].encode()) != report.prompt_hash
                    or json.loads(transcript["prompt"]) != assignment
                    or transcript["response"] != candidate_value):
                    raise IntegrityError("prompt/transcript differs from assigned public context or candidate")
            target = self.root / "objects" / artifact.sha256
            if not target.exists():
                atomic_write(target, data, exclusive=True)
            if digest(target.read_bytes()) != artifact.sha256:
                raise IntegrityError("content-addressed object corrupt")
            staged.append((f"{report.run_id}:{kind}", report.run_id, kind, artifact.sha256, artifact.size))
        with self.db:
            self.db.executemany("INSERT INTO artifacts VALUES(?,?,?,?,?)", staged)
            self.db.execute("UPDATE runs SET report_hash=?,report=? WHERE id=?", (checksum, payload, report.run_id))
            metadata = {**expected, "sdk_version": report.sdk_version, "cost_micro_usd": report.cost_micro_usd,
                "usage": report.usage, "sandbox_image": report.sandbox_image}
            self.db.execute("UPDATE runs SET execution_metadata=? WHERE id=?", (canonical(metadata), report.run_id))
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
        raw = canonical(value).encode()
        checksum = digest(raw)
        target = self.root / "objects" / checksum
        if not target.exists():
            atomic_write(target, raw, exclusive=True)
        elif digest(target.read_bytes()) != checksum:
            raise IntegrityError("raw evaluation object corrupt")
        with self.db:
            row = self.db.execute("SELECT report_hash,verdict FROM runs WHERE id=?", (run_id,)).fetchone()
            if not row or not row[0] or row[1]:
                raise IntegrityError("verdict requires imported, unevaluated run")
            self.db.execute("UPDATE runs SET execution_status='completed',scientific_outcome=?,verification_status='checked',verdict=? WHERE id=?", ("supported" if value.supported else "negative", canonical(value), run_id))
            self.db.execute("INSERT INTO artifacts VALUES(?,?,?,?,?)", (f"{run_id}:evaluation", run_id, "evaluation", checksum, len(raw)))
            self.event("verdict", run_id, value.model_dump(mode="json"))
            self._settle(run_id)

    def _settle(self, run_id: str) -> None:
        metadata = json.loads(self.db.execute("SELECT execution_metadata FROM runs WHERE id=?", (run_id,)).fetchone()[0])
        if metadata.get("auth_mode") in {"chatgpt", "claude_code"}:
            self.db.execute("UPDATE runs SET settled=1 WHERE id=?", (run_id,))
            return  # SDK USD estimates are not subscription charges.
        row = self.db.execute("SELECT reserved_micro_usd,settled,report FROM runs WHERE id=?", (run_id,)).fetchone()
        if row and not row[1] and row[2]:
            cost = WorkerReport.model_validate_json(row[2]).cost_micro_usd
            if cost is None:
                return  # Unknown SDK cost keeps its reservation; never silently charge zero.
            if cost > row[0] and (metadata.get("auth_mode") != "api_key" or metadata.get("authorization_cap_micro_usd") is not None):
                raise IntegrityError("cost exceeds reservation")
            self.db.execute("UPDATE project SET reserved_micro_usd=reserved_micro_usd-?,spent_micro_usd=spent_micro_usd+?", (row[0], cost))
            self.db.execute("UPDATE runs SET settled=1 WHERE id=?", (run_id,))

    def fail(self, run_id: str, status: str, reason: str) -> None:
        if status not in ("technical_error", "timed_out", "interrupted", "cancelled", "limit_reached"):
            raise IntegrityError("invalid failure status")
        with self.db:
            self.db.execute("UPDATE runs SET execution_status=?,scientific_outcome=NULL,verification_status='unverified',error=? WHERE id=? AND execution_status='running'", (status, reason, run_id))
            self.event(status, run_id, {"reason": reason})
            self._settle(run_id)

    def pilot(self, evidence: dict) -> None:
        if set(evidence) != {"positive_control", "negative_control", "nonconstant", "baseline"} or not all(evidence.values()):
            raise IntegrityError("pilot gate failed")
        with self.db:
            self.db.execute("UPDATE project SET pilot=?", (canonical(evidence),))
            self.event("pilot", "project", evidence)

    def reserve_control(self) -> None:
        with self.db:
            state = self.db.execute("SELECT * FROM project").fetchone()
            count = self.db.execute("SELECT count(*) FROM runs").fetchone()[0] + state["control_attempts"]
            registration = json.loads(self.db.execute("SELECT payload FROM registrations WHERE hash=?", (state["current_registration"],)).fetchone()[0])
            deadline = state["deadline"] or time.time() + registration["limits"]["project_seconds"]
            if count >= state["max_attempts"]:
                raise IntegrityError("control attempt allowance exhausted")
            if time.time() >= deadline:
                raise IntegrityError("project deadline reached")
            self.db.execute("UPDATE project SET control_attempts=control_attempts+1,deadline=?", (deadline,))
            self.event("control_start", str(count + 1), {"counted": True})

    def require_pilot(self) -> None:
        if not self.db.execute("SELECT pilot FROM project").fetchone()[0]:
            raise IntegrityError("pilot required before fan-out")

    def consume_final(self, run_id: str) -> dict:
        with self.db:
            state = self.db.execute("SELECT * FROM project").fetchone()
            if state["final_ticket"]:
                raise IntegrityError("final split already consumed (including interrupted attempts)")
            count = self.db.execute("SELECT count(*) FROM runs").fetchone()[0] + state["control_attempts"]
            if count >= state["max_attempts"] or (state["deadline"] and time.time() >= state["deadline"]):
                raise IntegrityError("final attempt/time allowance exhausted")
            if self.db.execute("SELECT 1 FROM runs WHERE execution_status='running'").fetchone():
                raise IntegrityError("reconcile running workers before final")
            row = self.db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
            if not row or row["execution_status"] != "completed" or row["verification_status"] != "checked" or row["registration_hash"] != state["current_registration"]:
                raise IntegrityError("final candidate must be a checked current result")
            inputs = json.loads(self.db.execute("SELECT inputs FROM registrations WHERE hash=?", (state["current_registration"],)).fetchone()[0])
            ticket = {"run_id": run_id, "split_hash": inputs["final"], "state": "started"}
            self.db.execute("UPDATE project SET final_ticket=?,control_attempts=control_attempts+1", (canonical(ticket),))
            self.event("final_started", run_id, ticket)
        return ticket

    def final_result(self, ticket: dict, verdict: Verdict) -> None:
        saved = self.db.execute("SELECT final_ticket FROM project").fetchone()[0]
        if saved != canonical(ticket) or ticket["state"] != "started":
            raise IntegrityError("final ticket mismatch")
        value = {**ticket, "state": "completed", "verdict": verdict.model_dump(mode="json")}
        with self.db:
            self.db.execute("UPDATE project SET final_ticket=?", (canonical(value),))
            self.event("final_completed", ticket["run_id"], value)

    def runs(self) -> list[dict]:
        return [dict(row) for row in self.db.execute("SELECT * FROM runs ORDER BY id")]

    def promote_claim(self, run_id: str) -> str:
        row = self.db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if not row or row["execution_status"] != "completed" or row["verification_status"] != "checked" or not row["verdict"]:
            raise IntegrityError("claim promotion requires checked evaluator evidence")
        self.artifact(run_id, "candidate")
        key = f"claim:{run_id}"
        if not self.db.execute("SELECT 1 FROM claims WHERE id=?", (key,)).fetchone():
            registration = json.loads(self.db.execute("SELECT payload FROM registrations WHERE hash=?", (row["registration_hash"],)).fetchone()[0])
            grain = registration.get("name") == "grain-316l"
            payload = {"id": key, "run_id": run_id,
                "statement": "Candidate development grain error." if grain else "Candidate development error on synthetic data.",
                "tag": "measured" if grain else "simulated", "metric": "max_rel_error" if grain else "mse"}
            with self.db:
                self.db.execute("INSERT INTO claims(id,run_id,statement,tag,metric) VALUES(?,?,?,?,?)", tuple(payload.values()))
                self.event("claim", key, payload)
        return key

    def challenge(self, challenge_id: str, claim_id: str, evidence_run: str, grounds: str) -> None:
        if not grounds.strip():
            raise IntegrityError("challenge grounds required")
        row = self.db.execute("SELECT verdict FROM runs WHERE id=?", (evidence_run,)).fetchone()
        if not row or not row[0]:
            raise IntegrityError("challenge evidence must exist")
        with self.db:
            self.db.execute("INSERT INTO challenges VALUES(?,?,?,?)", (challenge_id, claim_id, evidence_run, grounds))
            self.event("challenge", challenge_id, {"claim_id": claim_id, "evidence_run": evidence_run, "grounds": grounds})

    def resolve_challenge(self, challenge_id: str, decision: str) -> None:
        if not self.db.execute("SELECT 1 FROM challenges WHERE id=?", (challenge_id,)).fetchone() or not decision.strip():
            raise IntegrityError("existing challenge and decision required")
        with self.db:
            self.event("challenge_resolution", challenge_id, {"decision": decision})
