import asyncio
from unittest.mock import Mock

import pytest

from research_loops.domain import IntegrityError


def test_login_transport_routes_permission_prompts_to_callback(monkeypatch):
    pytest.importorskip("claude_agent_sdk")
    from claude_agent_sdk import ClaudeAgentOptions, PermissionResultDeny
    from research_loops.adapters import claude_transport

    async def permission(name, arguments, context):
        return PermissionResultDeny(message="offline test")

    options = ClaudeAgentOptions(can_use_tool=permission, tools=[], allowed_tools=[], permission_mode="default")
    monkeypatch.setattr(claude_transport.SubprocessCLITransport, "_find_cli", lambda self: "offline-cli-must-not-run")
    popen = Mock()
    monkeypatch.setattr(claude_transport.subprocess, "Popen", popen)
    monkeypatch.setattr(claude_transport, "WindowsJob", lambda process: None)

    asyncio.run(claude_transport.LoginTransport(options, "claude_code").connect())

    command = popen.call_args.args[0]
    assert command[command.index("--permission-prompt-tool") + 1] == "stdio"
    assert command[command.index("--permission-mode") + 1] == "default"
    assert "--allowedTools" not in command
    assert options.permission_prompt_tool_name is None
    assert options.can_use_tool is permission


@pytest.mark.parametrize("route", [[], ["--permission-prompt-tool"], ["--permission-prompt-tool", "other"]])
def test_login_transport_fails_closed_without_stdio_route(monkeypatch, route):
    pytest.importorskip("claude_agent_sdk")
    from claude_agent_sdk import ClaudeAgentOptions
    from research_loops.adapters import claude_transport

    async def permission(name, arguments, context):
        raise AssertionError("callback must not run without the permission bridge")

    options = ClaudeAgentOptions(can_use_tool=permission)
    monkeypatch.setattr(claude_transport.SubprocessCLITransport, "_find_cli", lambda self: "offline-cli-must-not-run")
    monkeypatch.setattr(claude_transport.SubprocessCLITransport, "_build_command", lambda self: ["offline-cli-must-not-run", *route])
    popen = Mock()
    monkeypatch.setattr(claude_transport.subprocess, "Popen", popen)

    with pytest.raises(IntegrityError) as caught:
        asyncio.run(claude_transport.LoginTransport(options, "claude_code").connect())

    assert str(caught.value) == "Claude CLI command is missing the can_use_tool stdio permission route"
    popen.assert_not_called()
