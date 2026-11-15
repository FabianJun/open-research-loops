"""OpenAI Agents SDK adapter; real model calls require checkpoint B."""

from dataclasses import asdict
from importlib.metadata import version

from research_loops.adapters.common import SDKBackend, instructions, cleanup_worker
from research_loops.domain import IntegrityError
from research_loops.transports.protocol import TOOL_NAMES
from research_loops.authorization import LimitReached


class OpenAIBackend(SDKBackend):
    name = "openai_agents"
    provider = "openai"

    def __init__(self, model: str, *, offline_model=None, offline_client=None, offline_auth=None, **kwargs):
        super().__init__(model, **kwargs)
        self.offline_model = offline_model
        self.offline_client, self.offline_auth = offline_client, offline_auth
        self.offline = offline_model is not None or offline_client is not None

    @cleanup_worker
    async def run(self, contract, workspace, limits):
        approval = self.check_authorization()  # Before SDK import, MCP launch, or model call.
        from agents import Agent, ModelSettings, Runner, RunConfig
        from agents.mcp import MCPServerStdio
        client = None
        model = self.offline_model
        agent_class = Agent
        if model is None:
            from openai import AsyncOpenAI
            if self.auth_mode == "chatgpt":
                from research_loops.openai_auth import ChatGPTAuth, TokenStore
                from research_loops.adapters.chatgpt_responses import ChatGPTResponsesModel, MCPAgent
                auth = self.offline_auth or ChatGPTAuth(TokenStore(project=self.project)).pin_account()
                import asyncio
                catalog = await asyncio.to_thread(auth.models)
                if self.model not in {item["slug"] for item in catalog}:
                    raise IntegrityError("configured model is not listed for the selected ChatGPT account; no fallback")
                async def credential():
                    return await asyncio.to_thread(auth.access_token)
                client = self.offline_client or AsyncOpenAI(api_key=credential, base_url="https://api.openai.com/v1",
                    max_retries=0, organization="", project="")
                model = ChatGPTResponsesModel(self.model, client)
                agent_class = MCPAgent
            elif self.auth_mode == "api_key":
                import os
                from agents.models.openai_responses import OpenAIResponsesModel
                key = os.environ.get("OPENAI_API_KEY")
                if not key:
                    raise IntegrityError("explicit API-key mode requires OPENAI_API_KEY")
                client = self.offline_client or AsyncOpenAI(api_key=key, base_url="https://api.openai.com/v1",
                    max_retries=0, organization="", project="")
                catalog = await client.models.list()
                if self.model not in {item.id for item in catalog.data}:
                    await client.close()
                    raise IntegrityError("configured model is not listed; no fallback")
                model = OpenAIResponsesModel(self.model, client)
            else:
                raise IntegrityError("unknown OpenAI auth mode")
        try:
            return await self.execute(contract, workspace, limits, approval, model, agent_class)
        finally:
            if client:
                await client.close()

    async def execute(self, contract, workspace, limits, approval, model, agent_class):
        from agents import ModelSettings, Runner, RunConfig, MaxTurnsExceeded
        from agents.mcp import MCPServerStdio
        from openai import APIStatusError
        launch = await self.launch(contract, workspace)
        server = MCPServerStdio(params={"command": launch.command, "args": launch.args, "env": launch.env,
            **({"cwd": launch.cwd} if launch.cwd else {})}, name="rloop", cache_tools_list=True,
            use_structured_content=True, client_session_timeout_seconds=limits.worker_seconds,
            tool_filter={"allowed_tool_names": list(TOOL_NAMES)})
        prompt = instructions(contract)
        async with server:
            agent = agent_class(name="rloop-worker", instructions=prompt, model=model,
                tools=[], handoffs=[], mcp_servers=[server],
                model_settings=ModelSettings(parallel_tool_calls=False, store=False,
                    reasoning={"effort": self.effort}, response_include=["reasoning.encrypted_content"], retry=None))
            exposed = await server.list_tools()
            if {tool.name for tool in exposed} != set(TOOL_NAMES):
                raise IntegrityError("effective MCP tool list differs from rloop policy")
            arguments = dict(input=[{"role": "user", "content": "Execute the assigned public contract."}],
                max_turns=approval.run_limits.max_turns_per_worker if approval else 16,
                run_config=RunConfig(tracing_disabled=True, trace_include_sensitive_data=False))
            try:
                if self.offline_model is not None:
                    result = await Runner.run(agent, **arguments)
                else:
                    result = Runner.run_streamed(agent, **arguments)
                    async for _ in result.stream_events():
                        pass
            except MaxTurnsExceeded:
                raise LimitReached("OpenAI rate or turn limit reached; no retry or fallback") from None
            except APIStatusError as exc:
                from research_loops.adapters.chatgpt_responses import LIMIT_CODES
                if exc.status_code == 429 or exc.code in LIMIT_CODES:
                    raise LimitReached("OpenAI subscription or rate limit reached; no retry or fallback") from None
                raise IntegrityError("OpenAI request refused; no retry or fallback") from None
        usage = asdict(result.context_wrapper.usage)
        # Agents Usage reports tokens/requests, not a USD invoice. Do not invent zero.
        return self.finish(contract, workspace, launch, sdk_version=version("openai-agents"), cost=None,
            usage=usage, trace={"instructions": prompt, "input": "Execute the assigned public contract.",
                "items": result.to_input_list(), "effective_tools": sorted(TOOL_NAMES), "offline_seam": self.offline})
