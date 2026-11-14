"""Run-scoped service functions, called directly by fake; MCP comes in Phase 3."""

import json
import os
from pathlib import Path

from research_loops.domain import Artifact, IntegrityError, WorkerContract, WorkerReport, canonical, digest
from research_loops.paths import atomic_write, confined


class ToolService:
    def __init__(self, contract: WorkerContract, root: Path):
        self.contract = contract
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.registered = False

    def read_contract(self) -> dict:
        value = self.contract.model_dump(mode="json")
        self.journal("read_contract", value)
        return value

    def read_findings(self, ids: list[str]) -> list:
        if ids:
            raise IntegrityError("no findings are in this assignment's public scope")
        return []

    def read_artifact(self, relative: str) -> bytes:
        path = confined(self.root, relative)
        if not path.is_file() or path.stat().st_size > 1_000_000:
            raise IntegrityError("missing or oversized artifact")
        return path.read_bytes()

    def journal(self, kind: str, payload: dict) -> None:
        line = canonical({"id": f"{self.contract.run_id}:{kind}", "kind": kind, "payload": payload}) + "\n"
        with (self.root / "journal.jsonl").open("ab") as stream:
            stream.write(line.encode())
            stream.flush()
            os.fsync(stream.fileno())

    def register_variant(self, prediction: str) -> None:
        if self.registered or (self.root / "report.json").exists():
            raise IntegrityError("one variant per assignment; no hidden retries")
        if not prediction.strip():
            raise IntegrityError("prediction required")
        self.journal("proposal", {"prediction": prediction, "seed": self.contract.seed})
        self.registered = True

    def write_artifact(self, relative: str, content: bytes) -> Artifact:
        if not self.registered or not 0 < len(content) <= 1_000_000:
            raise IntegrityError("register before writing; artifact size bounded")
        path = confined(self.root, relative)
        atomic_write(path, content, exclusive=True)
        return Artifact(path=relative, sha256=digest(content), size=len(content))

    def submit_result(self, report: WorkerReport) -> WorkerReport:
        if not self.registered or report.run_id != self.contract.run_id or report.contract_hash != self.contract.registration_hash:
            raise IntegrityError("report scope differs from assignment")
        for artifact in (report.candidate, report.transcript):
            data = self.read_artifact(artifact.path)
            if digest(data) != artifact.sha256 or len(data) != artifact.size:
                raise IntegrityError("artifact hash/size mismatch")
        atomic_write(self.root / "report.json", canonical(report).encode(), exclusive=True)
        return report

    def execute_candidate(self, *_args, **_kwargs):
        raise IntegrityError("candidate code execution is disabled; Phase 3b Sandbox isolation is required")
