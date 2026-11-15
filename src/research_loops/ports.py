"""Application boundaries, independent of SDKs and transports."""

from typing import Protocol

from research_loops.domain import Limits, Verdict, WorkerContract, Workspace
from research_loops.reports import WorkerReport


class AgentBackend(Protocol):
    async def run(self, contract: WorkerContract, workspace: Workspace, limits: Limits) -> WorkerReport: ...


class Sandbox(Protocol):
    image: str | None
    def tool_launch(self, contract: WorkerContract, workspace, *, adapter=True): ...
    def execute_candidate(self, *args, **kwargs): ...
    def cleanup(self, workspace): ...


class Evaluator(Protocol):
    def evaluate(self, candidate: bytes, dataset: bytes, seconds: float) -> Verdict: ...


class ResearchRepository(Protocol):
    def register(self, contract: dict, evaluator_hash: str, inputs: dict) -> str: ...
    def import_report(self, report: WorkerReport, outbox: Workspace) -> bool: ...
