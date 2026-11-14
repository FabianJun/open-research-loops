"""Execution report evolution, independent of the anchored numerical evaluator.

Accepts Phase-2 reports unchanged. Unknown SDK cost is explicitly null. The
legacy domain.WorkerReport remains readable for old fake outboxes.
"""

from pydantic import Field

from research_loops.domain import Artifact, Message


class WorkerReport(Message):
    report_id: str
    run_id: str
    contract_hash: str
    candidate: Artifact
    prompt_hash: str
    transcript: Artifact
    seed: int
    backend: str = "fake"
    provider: str = "offline"
    model: str = "deterministic-v1"
    sdk_version: str | None = None
    cost_micro_usd: int | None = Field(default=0, ge=0)
    usage: dict = Field(default_factory=dict)
    sdk_trace: Artifact | None = None
    sandbox_image: str | None = None
