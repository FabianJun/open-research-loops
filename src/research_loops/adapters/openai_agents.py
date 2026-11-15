"""OpenAI Agents SDK adapter; real model calls require checkpoint B."""

from dataclasses import asdict
from importlib.metadata import version

from research_loops.adapters.common import SDKBackend, instructions, cleanup_worker
from research_loops.domain import IntegrityError
from research_loops.transports.protocol import TOOL_NAMES


class OpenAIBackend(SDKBackend):
    name = "openai_agents"
    provider = "openai"

    def __init__(self, model: str, *, offline_model=None, **kwargs):
        super().__init__(model, **kwargs)
        self.offline_model = offline_model
        self.offline = offline_model is not None

    @cleanup_worker
    async def run(self, contract, workspace, limits):
        self.check_authorization()  # Before SDK import, MCP launch, or any possible model call.
        from agents import Agent, ModelSettings, Runner, RunConfig
        from agents.mcp import MCPServerStdio
        launch = await self.launch(contract, workspace)
        server = MCPServerStdio(params={"command": launch.command, "args": launch.args, "env": launch.env,
            **({"cwd": launch.cwd} if launch.cwd else {})}, name="rloop", cache_tools_list=True,
            use_structured_content=True, client_session_timeout_seconds=limits.worker_seconds,
            tool_filter={"allowed_tool_names": list(TOOL_NAMES)})
        prompt = instructions(contract)
        async with server:
            agent = Agent(name="rloop-worker", instructions=prompt, model=self.offline_model or self.model,
                tools=[], handoffs=[], mcp_servers=[server],
                model_settings=ModelSettings(max_tokens=2048, parallel_tool_calls=False))
            exposed = await server.list_tools()
            if {tool.name for tool in exposed} != set(TOOL_NAMES):
                raise IntegrityError("effective MCP tool list differs from rloop policy")
            result = await Runner.run(agent, input="Execute the assigned public contract.", max_turns=16,
                run_config=RunConfig(tracing_disabled=True, trace_include_sensitive_data=False))
        usage = asdict(result.context_wrapper.usage)
        # Agents Usage reports tokens/requests, not a USD invoice. Do not invent zero.
        return self.finish(contract, workspace, launch, sdk_version=version("openai-agents"), cost=None,
            usage=usage, trace={"instructions": prompt, "input": "Execute the assigned public contract.",
                "items": result.to_input_list(), "effective_tools": sorted(TOOL_NAMES), "offline_seam": self.offline})
