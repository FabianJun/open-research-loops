"""Run-scoped service functions shared by direct fake and MCP transports."""

import os
from pathlib import Path

from research_loops.domain import Artifact, IntegrityError, WorkerContract, WorkerReport, canonical, digest
from research_loops.paths import atomic_write, confined
from research_loops.candidate_schema import validate_submission
from research_loops.contracts import is_grain


class ToolService:
    def __init__(self, contract: WorkerContract, root: Path, *, submission_name: str = "report.json", shared_files=False, public_root: Path | None = None):
        self.contract = contract
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.registered = False
        self.submission_name = submission_name
        self.shared_files = shared_files
        self.public_root = public_root if public_root is not None else root.parent / "public"
        self.training_calls = 0
        self.training = None
        if is_grain(contract):
            import json
            capability = root.parent / "training-tool.json"
            if capability.is_file():
                self.training = json.loads(capability.read_bytes())
                if (set(self.training) != {"manifest", "data_root"}
                        or self.training["manifest"].get("split") != "train"
                        or len(self.training["manifest"].get("images", [])) > 32):
                    raise IntegrityError("training tool requires only the fixed train subset")
            journal = self.root / "journal.jsonl"
            if journal.exists():
                self.training_calls = sum(json.loads(line).get("kind") == "training_start" for line in journal.read_bytes().splitlines())

    @property
    def tool_names(self):
        from research_loops.transports.protocol import TOOL_NAMES
        return TOOL_NAMES + (("try_on_training",) if is_grain(self.contract) else ())

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
        if is_grain(self.contract):
            from research_loops.grain_evaluator import validate_params
            candidate = validate_params(candidate)
        else:
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

    def try_on_training(self, params: dict) -> dict:
        from research_loops.domain import content_hash
        if not is_grain(self.contract):
            raise IntegrityError("try_on_training is available only for grain-316l protocol v3")
        from research_loops.grain_evaluator import validate_params
        from research_loops.evaluation import SubprocessEvaluator
        if self.sealed():
            raise IntegrityError("outbox is sealed")
        try:
            params_hash = content_hash(params)
        except (ValueError, TypeError):
            params_hash = digest(b"invalid-json-parameters")
        if self.training_calls >= 6:
            self.journal("training_refused", {"params_hash": params_hash, "result": {"error": "six-call cap reached"}})
            raise IntegrityError("try_on_training is capped at 6 calls per worker run; submit one candidate")
        self.training_calls += 1
        self.journal("training_start", {"call": self.training_calls, "params_hash": params_hash})
        try:
            p = validate_params(params)
            if self.training is None:
                raise IntegrityError("protected training capability missing")
            result = SubprocessEvaluator().evaluate(canonical(p).encode(),
                canonical(self.training["manifest"]).encode(), 300, data_root=Path(self.training["data_root"]))
            value = result.model_dump(mode="json")
            self.journal("training_result", {"call": self.training_calls, "params_hash": params_hash, "result": value})
            return value
        except (ValueError, OSError) as exc:
            self.journal("training_error", {"call": self.training_calls, "params_hash": params_hash, "error": str(exc)})
            raise

    def execute_candidate(self, *_args, **_kwargs):
        raise IntegrityError("candidate code execution is disabled; Phase 3b Sandbox isolation is required")
