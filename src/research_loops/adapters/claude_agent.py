"""Claude Agent SDK adapter, with CLI and effective-tool-list enforcement."""

from dataclasses import asdict
from importlib.metadata import version

from research_loops.adapters.common import SDKBackend, instructions, micro_usd, cleanup_worker
from research_loops.domain import IntegrityError
from research_loops.transports.protocol import TOOL_NAMES


class ClaudeBackend(SDKBackend):
    name = "claude_agent"
    provider = "anthropic"

    def __init__(self, model: str, *, offline_transport_factory=None, **kwargs):
        super().__init__(model, **kwargs)
        self.transport_factory = offline_transport_factory
        self.offline = offline_transport_factory is not None

    @cleanup_worker
    async def run(self, contract, workspace, limits):
        cap = self.check_authorization()
        from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, PermissionResultAllow, PermissionResultDeny, ResultMessage, SystemMessage
        launch = await self.launch(contract, workspace)
        allowed = {"mcp__rloop__" + name for name in TOOL_NAMES}
        async def permission(name, arguments, context):
            if name in allowed:
                return PermissionResultAllow(updated_input=arguments)
            return PermissionResultDeny(message="Only run-scoped rloop MCP tools are permitted")
        options = ClaudeAgentOptions(model=self.model, tools=[], allowed_tools=[],
            disallowed_tools=["Bash", "Read", "Write", "Edit", "Glob", "Grep", "WebFetch", "WebSearch", "Task", "Agent", "Skill"],
            setting_sources=[], skills=[], plugins=[], agents={}, strict_mcp_config=True,
            mcp_servers={"rloop": {"type": "stdio", "command": launch.command, "args": launch.args, "env": launch.env}},
            can_use_tool=permission, permission_mode="default", system_prompt=instructions(contract),
            cwd=str(workspace.root), max_turns=16, max_budget_usd=(cap / 1_000_000 if cap is not None else None))
        transport = self.transport_factory(options) if self.transport_factory else None
        messages, init_seen, result = [], False, None
        async with ClaudeSDKClient(options=options, transport=transport) as client:
            await client.query("Execute the assigned public contract.")
            async for message in client.receive_response():
                messages.append(asdict(message))
                if isinstance(message, SystemMessage) and message.subtype == "init":
                    if set(message.data.get("tools", [])) != allowed:
                        raise IntegrityError("Claude effective tool list includes missing or unauthorized tools")
                    init_seen = True
                if isinstance(message, ResultMessage):
                    result = message
        if not init_seen or result is None or result.is_error:
            raise IntegrityError("Claude failed or omitted effective tool list/result")
        return self.finish(contract, workspace, launch, sdk_version=version("claude-agent-sdk"),
            cost=micro_usd(result.total_cost_usd), usage=result.usage or {},
            trace={"instructions": instructions(contract), "input": "Execute the assigned public contract.",
                "messages": messages, "effective_tools": sorted(allowed), "offline_seam": self.offline})
