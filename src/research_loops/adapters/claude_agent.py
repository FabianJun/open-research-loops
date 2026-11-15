"""Claude Agent SDK adapter, with CLI and effective-tool-list enforcement."""

from dataclasses import asdict
from importlib.metadata import version
import json
from typing import get_args

from research_loops.adapters.common import SDKBackend, instructions, micro_usd, cleanup_worker
from research_loops.domain import IntegrityError
from research_loops.transports.protocol import TOOL_NAMES
from research_loops.authorization import LimitReached


class ClaudeBackend(SDKBackend):
    name = "claude_agent"
    provider = "anthropic"

    def __init__(self, model: str, *, offline_transport_factory=None, **kwargs):
        super().__init__(model, **kwargs)
        self.transport_factory = offline_transport_factory
        self.offline = offline_transport_factory is not None

    @cleanup_worker
    async def run(self, contract, workspace, limits):
        approval = self.check_authorization()
        cap = approval.cap_micro_usd if approval else None
        from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, PermissionResultAllow, PermissionResultDeny, ResultMessage, SystemMessage
        from claude_agent_sdk.types import AssistantMessageError
        launch = await self.launch(contract, workspace)
        allowed = {"mcp__rloop__" + name for name in TOOL_NAMES}
        async def permission(name, arguments, context):
            if name in allowed:
                return PermissionResultAllow(updated_input=arguments)
            return PermissionResultDeny(message="Only run-scoped rloop MCP tools are permitted")
        settings = {"disableAllHooks": True, "autoMemoryEnabled": False}
        if self.auth_mode == "claude_code":
            settings["forceLoginMethod"] = "claudeai"
        options = ClaudeAgentOptions(model=self.model, tools=[], allowed_tools=[],
            disallowed_tools=["Bash", "Read", "Write", "Edit", "Glob", "Grep", "WebFetch", "WebSearch", "Task", "Agent", "Skill"],
            setting_sources=[], skills=[], plugins=[], agents={}, strict_mcp_config=True,
            settings=json.dumps(settings),
            mcp_servers={"rloop": {"type": "stdio", "command": launch.command, "args": launch.args, "env": launch.env}},
            can_use_tool=permission, permission_mode="default", system_prompt=instructions(contract),
            cwd=str(workspace.root), effort=self.effort,
            max_turns=approval.run_limits.max_turns_per_worker if approval else 16,
            max_budget_usd=(cap / 1_000_000 if cap is not None else None))
        from research_loops.adapters.claude_transport import LoginTransport
        transport = self.transport_factory(options) if self.transport_factory else LoginTransport(options, self.auth_mode)
        messages, init_seen, result = [], False, None
        async with ClaudeSDKClient(options=options, transport=transport) as client:
            await client.query("Execute the assigned public contract.")
            async for message in client.receive_response():
                if (isinstance(message, SystemMessage) and message.subtype == "permission_denied"
                        and message.data.get("tool_name") in allowed):
                    raise IntegrityError("Claude CLI denied an authorized rloop tool; the can_use_tool permission bridge is not active")
                messages.append(asdict(message))
                # SDK reports these as protocol fields; never retry or change auth.
                if limit_message(asdict(message)):
                    raise LimitReached("Claude subscription or rate limit reached")
                if error := getattr(message, "error", None):
                    if error == "authentication_failed":
                        raise IntegrityError("Claude Code is not logged in for this worker (authentication_failed); run `claude` and /login in a terminal, then start a new pilot. No API-key fallback.")
                    # The SDK parser does not validate its Literal field. Record only enum values.
                    if error not in get_args(AssistantMessageError):
                        error = "unknown"
                    raise IntegrityError(f"Claude CLI reported error: {error}")
                if isinstance(message, SystemMessage) and message.subtype == "init":
                    if set(message.data.get("tools", [])) != allowed:
                        raise IntegrityError("Claude effective tool list includes missing or unauthorized tools")
                    init_seen = True
                    if message.data.get("model", self.model) != self.model:
                        raise IntegrityError("Claude selected a different model; no fallback permitted")
                if hasattr(message, "model") and message.model != self.model:
                    raise IntegrityError("Claude response model differs from authorization")
                if isinstance(message, ResultMessage):
                    result = message
        if not init_seen or result is None or result.is_error:
            raise IntegrityError("Claude failed or omitted effective tool list/result")
        return self.finish(contract, workspace, launch, sdk_version=version("claude-agent-sdk"),
            cost=micro_usd(result.total_cost_usd), usage=result.usage or {},
            trace={"instructions": instructions(contract), "input": "Execute the assigned public contract.",
                "messages": messages, "effective_tools": sorted(allowed), "offline_seam": self.offline})


def limit_message(value):
    if isinstance(value, dict):
        if "rate_limit_info" in value:
            return value.get("rate_limit_info", {}).get("status") in {"rejected", "limit_reached"}
        if isinstance(value.get("error"), str) and value["error"] in {"rate_limit", "rate_limit_error", "subscription_limit", "billing_error"}:
            return True
        if value.get("subtype") in {"error_max_budget_usd", "error_max_turns"}:
            return True
        return any(limit_message(item) for item in value.values())
    if isinstance(value, list):
        return any(limit_message(item) for item in value)
    return False
