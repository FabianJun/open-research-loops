"""SDK adapter lifecycle and host-owned completion evidence."""

from decimal import Decimal, ROUND_CEILING
from pathlib import Path
from functools import wraps
import asyncio

from research_loops.authorization import authorize
from research_loops.domain import Artifact, IntegrityError, WorkerContract, Workspace, canonical, digest
from research_loops.paths import atomic_write
from research_loops.reports import WorkerReport
from research_loops.transports.launch import local_launch


def cleanup_worker(operation):
    @wraps(operation)
    async def run(self, contract, workspace, limits):
        try:
            return await operation(self, contract, workspace, limits)
        finally:
            if self.sandbox:
                self.sandbox.cleanup(workspace.root)
    return run


def instructions(contract: WorkerContract) -> str:
    return ("You are a bounded research worker. Use only the six rloop MCP tools. "
        "Read the contract, register one prediction, propose one bounded JSON expression candidate, "
        "write candidate.json and transcript.json, then submit_result once. "
        "The transcript JSON must contain prompt (the exact public JSON string below) and response (the candidate tree). "
        "Artifact tools return path, sha256, size descriptors. Return no scientific verdict. "
        "The host supplies trusted provider/cost metadata after completion. Public JSON: " + canonical(contract)
        + "\nExpected prompt_hash: " + digest(canonical(contract).encode())
        + "\nSubmission schema: " + canonical(WorkerReport.model_json_schema()))


def micro_usd(value) -> int | None:
    if value is None:
        return None
    amount = Decimal(str(value))
    if not amount.is_finite() or amount < 0:
        raise IntegrityError("invalid SDK cost")
    return int((amount * 1_000_000).to_integral_value(rounding=ROUND_CEILING))


class SDKBackend:
    name: str
    provider: str

    def __init__(self, model: str, *, project: Path | None = None, sandbox=None):
        self.model = model
        self.project = project
        from research_loops.sandbox import NoneSandbox
        self.sandbox = sandbox or NoneSandbox()
        self.offline = False

    def check_authorization(self) -> int | None:
        if self.offline:
            return None  # Only an explicitly injected SDK model/transport seam, never CLI configuration.
        return authorize(self.project, self.provider, self.model)

    async def launch(self, contract: WorkerContract, workspace: Workspace):
        workspace.root.mkdir(parents=True, exist_ok=True)
        if self.sandbox:
            return await asyncio.to_thread(self.sandbox.tool_launch, contract, workspace.root, adapter=True)
        return local_launch(contract, workspace.root, adapter=True)

    def finish(self, contract, workspace, launch, *, sdk_version, cost, usage, trace) -> WorkerReport:
        if hasattr(self.sandbox, "materialize"):
            self.sandbox.materialize(workspace.root)
        submitted = workspace.root / "submission.json"
        if not submitted.exists():
            raise IntegrityError("SDK finished without a sealed tool submission")
        report = WorkerReport.model_validate_json(submitted.read_bytes())
        if report.run_id != contract.run_id or report.contract_hash != contract.registration_hash:
            raise IntegrityError("SDK submission scope mismatch")
        data = canonical(trace).encode()
        if len(data) > 1_000_000:
            raise IntegrityError("SDK trace quota exceeded")
        atomic_write(workspace.root / "adapter-trace.json", data, exclusive=True)
        result = report.model_copy(update={"backend": self.name, "provider": self.provider, "model": self.model,
            "sdk_version": sdk_version, "cost_micro_usd": cost, "usage": usage,
            "sdk_trace": Artifact(path="adapter-trace.json", sha256=digest(data), size=len(data)),
            "sandbox_image": launch.image})
        atomic_write(workspace.root / "report.json", canonical(result).encode(), exclusive=True)
        return result
