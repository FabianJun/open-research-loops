"""Run-scoped service functions shared by direct fake and MCP transports."""

import os
from pathlib import Path

from research_loops.domain import Artifact, IntegrityError, WorkerContract, WorkerReport, canonical, digest
from research_loops.paths import atomic_write, confined
from research_loops.candidate_schema import validate_submission


class ToolService:
    def __init__(self, contract: WorkerContract, root: Path, *, submission_name: str = "report.json", shared_files=False, public_root: Path | None = None):
        self.contract = contract
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.registered = False
        self.submission_name = submission_name
        self.shared_files = shared_files
        self.public_root = public_root if public_root is not None else root.parent / "public"

    def sealed(self) -> bool:
        return (self.root / self.submission_name).exists() or (self.root / "report.json").exists()

    def read_contract(self) -> dict:
        value = self.contract.model_dump(mode="json")
        self.journal("read_contract", value)
        return value

    def read_findings(self, ids: list[str]) -> list:
        if ids:
            raise IntegrityError("no findings are in this assignment's public scope")
        return []

    def read_artifact(self, relative: str) -> bytes:
        if relative.startswith("inputs/"):
            if relative != "inputs/training.json":
                raise IntegrityError("public input is outside this assignment")
            path = confined(self.public_root, "training.json")
            if not path.is_file() or path.stat().st_size > 1_000_000:
                raise IntegrityError("public training input missing or oversized")
            data = path.read_bytes()
            if digest(data) != self.contract.input_hash:
                raise IntegrityError("public training input hash mismatch")
            return data
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
        if self.registered or self.sealed():
            raise IntegrityError("one variant per assignment; no hidden retries")
        if not prediction.strip():
            raise IntegrityError("prediction required")
        self.journal("proposal", {"prediction": prediction, "seed": self.contract.seed})
        self.registered = True

    def write_artifact(self, relative: str, content: bytes) -> Artifact:
        if self.sealed():
            raise IntegrityError("outbox is sealed")
        path = confined(self.root, relative)
        reserved = {"report.json", "submission.json", "journal.jsonl", "candidate.json", "transcript.json", "adapter-trace.json"}
        if relative.split("/")[0].casefold() in reserved or relative.startswith("inputs/"):
            raise IntegrityError("reserved outbox path")
        if not self.registered or not 0 < len(content) <= 1_000_000:
            raise IntegrityError("register before writing; artifact size bounded")
        atomic_write(path, content, exclusive=True)
        if self.shared_files:
            path.chmod(0o644)
        return Artifact(path=relative, sha256=digest(content), size=len(content))

    def submit_result(self, candidate: dict) -> WorkerReport:
        if self.sealed():
            raise IntegrityError("outbox is sealed")
        if not self.registered:
            raise IntegrityError("register a prediction before submitting a candidate")
        validate_submission(candidate)
        prompt = canonical(self.contract)
        artifacts = []
        for name, value in (("candidate.json", candidate), ("transcript.json", {"prompt": prompt, "response": candidate})):
            data = canonical(value).encode()
            if not 0 < len(data) <= 1_000_000:
                raise IntegrityError("submission artifact size exceeds 1 MB")
            atomic_write(confined(self.root, name), data, exclusive=True)
            if self.shared_files:
                (self.root / name).chmod(0o644)
            artifacts.append(Artifact(path=name, sha256=digest(data), size=len(data)))
        report = WorkerReport(report_id=self.contract.run_id, run_id=self.contract.run_id,
            contract_hash=self.contract.registration_hash, seed=self.contract.seed,
            prompt_hash=digest(prompt.encode()), candidate=artifacts[0], transcript=artifacts[1])
        atomic_write(self.root / self.submission_name, canonical(report).encode(), exclusive=True)
        if self.shared_files:
            (self.root / self.submission_name).chmod(0o644)
        return report

    def execute_candidate(self, *_args, **_kwargs):
        raise IntegrityError("candidate code execution is disabled; Phase 3b Sandbox isolation is required")
