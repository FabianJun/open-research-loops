"""The offline fake's optional MCP profile, using the same Sandbox port as SDKs."""
import base64
import random

from research_loops.adapters.common import SDKBackend, cleanup_worker
from research_loops.domain import canonical, digest
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
            prompt = canonical(await call("read_contract", {}))
            await call("register_variant", {"prediction": contract.prediction})
            tree = oracle() if contract.variant == 1 else {"constant": contract.variant - 1}
            if contract.arm == "random":
                rng = random.Random(contract.seed * 100 + contract.variant)
                def expression(depth=0):
                    if depth == 4 or rng.random() < 0.4:
                        return {"feature": rng.randrange(4)} if rng.random() < 0.7 else {"constant": rng.randint(-3, 3)}
                    return {"op": rng.choice(("add", "sub", "mul")), "left": expression(depth + 1), "right": expression(depth + 1)}
                tree = expression()
            artifacts = []
            for path, data in [("candidate.json", canonical(tree).encode()), ("transcript.json", canonical({"prompt": prompt, "response": tree}).encode())]:
                artifacts.append(await call("write_artifact", {"relative": path, "content": base64.b64encode(data).decode()}))
            report = WorkerReport(report_id=contract.run_id, run_id=contract.run_id, contract_hash=contract.registration_hash,
                candidate=artifacts[0], transcript=artifacts[1], prompt_hash=digest(prompt.encode()), seed=contract.seed,
                sandbox_image=launch.image)
            await call("submit_result", {"report": report.model_dump(mode="json")})
        if hasattr(self.sandbox, "materialize"):
            self.sandbox.materialize(workspace.root)
        atomic_write(workspace.root / "report.json", canonical(report).encode(), exclusive=True)
        return report
