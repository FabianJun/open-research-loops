"""The offline fake's optional MCP profile, using the same Sandbox port as SDKs."""
import random

from research_loops.adapters.common import SDKBackend, cleanup_worker
from research_loops.domain import canonical
from research_loops.fake import oracle
from research_loops.paths import atomic_write
from research_loops.reports import WorkerReport
from research_loops.transports.client import session, value


class MCPFakeBackend(SDKBackend):
    name, provider = "fake", "offline"

    def __init__(self, sandbox=None):
        super().__init__("deterministic-v1", sandbox=sandbox)
        self.offline = True

    @cleanup_worker
    async def run(self, contract, workspace, limits):
        launch = await self.launch(contract, workspace)
        async with session(launch) as client:
            async def call(name, args):
                result = value(await client.call_tool(name, args))
                if not result["ok"]:
                    raise ValueError(result["error"])
                return result["value"]
            await call("read_contract", {})
            await call("register_variant", {"prediction": contract.prediction})
            tree = oracle() if contract.variant == 1 else {"constant": contract.variant - 1}
            if contract.arm == "random":
                rng = random.Random(contract.seed * 100 + contract.variant)
                def expression(depth=0):
                    if depth == 4 or rng.random() < 0.4:
                        return {"feature": rng.randrange(4)} if rng.random() < 0.7 else {"constant": rng.randint(-3, 3)}
                    return {"op": rng.choice(("add", "sub", "mul")), "left": expression(depth + 1), "right": expression(depth + 1)}
                tree = expression()
            report = WorkerReport.model_validate(await call("submit_result", {"candidate": tree}))
            report = report.model_copy(update={"sandbox_image": launch.image})
        if hasattr(self.sandbox, "materialize"):
            self.sandbox.materialize(workspace.root)
        atomic_write(workspace.root / "report.json", canonical(report).encode(), exclusive=True)
        return report
