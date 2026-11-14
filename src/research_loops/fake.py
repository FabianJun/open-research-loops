"""Deterministic offline backend. No SDK loading or credential reads."""

import asyncio
import random

from research_loops.domain import Limits, WorkerContract, WorkerReport, Workspace, canonical, digest
from research_loops.tools import ToolService


def oracle() -> dict:
    return {"op": "add", "left": {"op": "sub", "left": {"op": "mul", "left": {"constant": 2}, "right": {"feature": 0}}, "right": {"op": "mul", "left": {"constant": 3}, "right": {"feature": 2}}}, "right": {"op": "mul", "left": {"feature": 1}, "right": {"feature": 3}}}


class FakeBackend:
    async def run(self, contract: WorkerContract, workspace: Workspace, limits: Limits) -> WorkerReport:
        tools = ToolService(contract, workspace.root)
        prompt = canonical(tools.read_contract()).encode()
        tools.register_variant(contract.prediction)
        await asyncio.sleep(0)  # Cooperatively bounded by the coordinator.
        if contract.arm == "random":
            rng = random.Random(contract.seed * 100 + contract.variant)
            def expression(depth=0):
                if depth == 4 or rng.random() < 0.4:
                    return {"feature": rng.randrange(4)} if rng.random() < 0.7 else {"constant": rng.randint(-3, 3)}
                return {"op": rng.choice(("add", "sub", "mul")), "left": expression(depth + 1), "right": expression(depth + 1)}
            tree = expression()
        else:
            tree = oracle() if contract.variant == 1 else {"constant": contract.variant - 1}
        candidate = tools.write_artifact("candidate.json", canonical(tree).encode())
        transcript = tools.write_artifact("transcript.json", canonical({"prompt": prompt.decode(), "response": tree}).encode())
        return tools.submit_result(WorkerReport(report_id=contract.run_id, run_id=contract.run_id,
            contract_hash=contract.registration_hash, candidate=candidate, prompt_hash=digest(prompt),
            transcript=transcript, seed=contract.seed))
