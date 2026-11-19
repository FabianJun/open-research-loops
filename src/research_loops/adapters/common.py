"""SDK adapter lifecycle and host-owned completion evidence."""

from decimal import Decimal, ROUND_CEILING
from pathlib import Path
from functools import wraps
import asyncio

from research_loops.authorization import authorize
from research_loops.domain import Artifact, IntegrityError, WorkerContract, Workspace, canonical, digest
from research_loops.paths import atomic_write, long_path, plain_io_errors
from research_loops.reports import WorkerReport
from research_loops.candidate_schema import CANDIDATE_GRAMMAR
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
    from research_loops.contracts import is_grain
    if is_grain(contract):
        from research_loops.grain_instructions import INSTRUCTIONS
        return INSTRUCTIONS + " Public JSON: " + canonical(contract)
    return ("You are a bounded research worker. Use only the six rloop MCP tools. "
        "Read the contract and read_artifact('inputs/training.json') for public labeled samples (UTF-8 text). "
        "Infer the signal from those samples; no development/final labels are available. "
        "Register one prediction with register_variant(prediction), then submit_result(candidate) with only the expression tree. "
        + CANDIDATE_GRAMMAR + " "
        "If validation fails, correct the tree and submit again in this session. A successful submission seals the outbox. "
        "Optional notes: write_artifact(relative, content) writes UTF-8 text; encoding='base64' is for binary content. "
        "candidate.json and transcript.json are reserved for the host. Return no scientific verdict. "
        "Public JSON: " + canonical(contract))


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

    def __init__(self, model: str, *, project: Path | None = None, sandbox=None, auth_mode=None, effort="high"):
        self.model = model
        self.project = project
        self.auth_mode = auth_mode or ("chatgpt" if self.provider == "openai" else "claude_code")
        self.effort = effort
        from research_loops.sandbox import NoneSandbox
        self.sandbox = sandbox or NoneSandbox()
        self.offline = False

    def check_authorization(self):
        if self.offline:
            return None  # Only an explicitly injected SDK model/transport seam, never CLI configuration.
        approval = authorize(self.project, self.provider, self.model)
        if approval.auth_mode != self.auth_mode or approval.effort != self.effort:
            raise IntegrityError("checkpoint B auth mode or effort differs from backend")
        return approval

    async def launch(self, contract: WorkerContract, workspace: Workspace):
        with plain_io_errors():
            long_path(workspace.root).mkdir(parents=True, exist_ok=True)
        if self.sandbox:
            return await asyncio.to_thread(self.sandbox.tool_launch, contract, workspace.root, adapter=True)
        return local_launch(contract, workspace.root, adapter=True)

    @plain_io_errors()
    def finish(self, contract, workspace, launch, *, sdk_version, cost, usage, trace) -> WorkerReport:
        self.save_trace(workspace, trace)
        submitted = workspace.root / "submission.json"
        if not long_path(submitted).exists():
            raise IntegrityError("SDK finished without a sealed tool submission")
        report = WorkerReport.model_validate_json(long_path(submitted).read_bytes())
        if report.run_id != contract.run_id or report.contract_hash != contract.registration_hash:
            raise IntegrityError("SDK submission scope mismatch")
        data = long_path(workspace.root / "adapter-trace.json").read_bytes()
        result = report.model_copy(update={"backend": self.name, "provider": self.provider, "model": self.model,
            "sdk_version": sdk_version, "cost_micro_usd": cost, "usage": usage,
            "sdk_trace": Artifact(path="adapter-trace.json", sha256=digest(data), size=len(data)),
            "sandbox_image": launch.image})
        atomic_write(workspace.root / "report.json", canonical(result).encode(), exclusive=True)
        return result

    def save_trace(self, workspace, trace):
        if hasattr(self.sandbox, "materialize"):
            self.sandbox.materialize(workspace.root)
        data = canonical(trace).encode()
        oversized = len(data) > 1_000_000
        if oversized:
            # Preserve bounded failure evidence even when the full item list is
            # too large. Quota exhaustion still fails the run; it never retries.
            field = "items" if "items" in trace else "messages"
            bounded = {**trace, field: [], "truncated": True}
            size = len(canonical(bounded).encode())
            for item in reversed(trace[field]):
                addition = len(canonical(item).encode()) + bool(bounded[field])
                if size + addition <= 1_000_000:
                    bounded[field].append(item)
                    size += addition
            bounded[field].reverse()
            data = canonical(bounded).encode()
        if len(data) > 1_000_000:  # Trusted instructions/metadata alone exceed the quota.
            raise IntegrityError("SDK trace quota exceeded")
        atomic_write(workspace.root / "adapter-trace.json", data, exclusive=True)
        if oversized:
            raise IntegrityError("SDK trace quota exceeded")
