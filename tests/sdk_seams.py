"""Offline SDK seams. Real SDK orchestration and real MCP, no provider transports."""
import asyncio
import json

from research_loops.domain import canonical, digest
from research_loops.fake import oracle
from research_loops.transports.protocol import TOOL_NAMES


def script():
    response = yield "read_contract", {}
    contract = response["value"]
    training = yield "read_artifact", {"relative": "inputs/training.json"}
    if training["ok"]:  # Standalone transport fixtures intentionally have no dataset.
        data = training["value"]["text"].encode()
        assert digest(data) == contract["input_hash"] and json.loads(data)["rows"]
    for name, args in [("read_artifact", {"relative": "../private/final.json"}),
                       ("read_artifact", {"relative": "/evaluator.py"}),
                       ("read_findings", {"ids": ["final"]})]:
        assert not (yield name, args)["ok"]
    assert (yield "read_findings", {"ids": []})["value"] == []
    assert (yield "register_variant", {"prediction": contract["prediction"]})["ok"]
    tree = oracle() if contract["variant"] == 1 else {"constant": contract["variant"] - 1}
    invalid = {"op": "add", "args": [{"constant": 2}, {"feature": 0}]}
    rejected = yield "submit_result", {"candidate": invalid}
    assert rejected == {"ok": False, "error": "candidate node keys must be exactly feature, constant, or op/left/right; replace args with left and right"}
    assert not (yield "read_artifact", {"relative": "candidate.json"})["ok"]
    assert (yield "submit_result", {"candidate": tree})["ok"]
    assert (yield "read_artifact", {"relative": "candidate.json"})["value"]["text"] == canonical(tree)
    assert not (yield "write_artifact", {"relative": "late.txt", "content": "late"})["ok"]
    assert not (yield "submit_result", {"candidate": tree})["ok"]


def openai_model(*, plan_factory=script):
    from agents import Model, ModelResponse, Usage
    from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputText

    class Stub(Model):
        def __init__(self):
            self.plans = {}
            self.index = 0

        async def get_response(self, system_instructions, input, model_settings, tools, output_schema, handoffs, tracing, **kwargs):
            assert {tool.name for tool in tools} == set(TOOL_NAMES)
            assert all(type(tool).__name__ == "FunctionTool" for tool in tools)
            assert not handoffs and tracing.is_disabled()
            try:
                if system_instructions not in self.plans:
                    self.plans[system_instructions] = plan_factory()
                    step = next(self.plans[system_instructions])
                else:
                    outputs = [item for item in input if isinstance(item, dict) and item.get("type") == "function_call_output"]
                    raw = outputs[-1]["output"]
                    value = json.loads(raw[0]["text"] if isinstance(raw, list) else raw)
                    # SDK MCP wrapper serializes structuredContent as a JSON object.
                    if "structured_content" in value:
                        value = value["structured_content"]
                    step = self.plans[system_instructions].send(value)
                self.index += 1
                output = [ResponseFunctionToolCall(type="function_call", name=step[0], arguments=json.dumps(step[1]), call_id=f"offline-{self.index}")]
            except StopIteration:
                del self.plans[system_instructions]
                output = [ResponseOutputMessage(id="offline-final", type="message", role="assistant", status="completed",
                    content=[ResponseOutputText(type="output_text", text="Submitted.", annotations=[])])]
            return ModelResponse(output=output, usage=Usage(requests=1, input_tokens=1, output_tokens=1), response_id=None)

        async def stream_response(self, *args, **kwargs):
            raise AssertionError("streaming seam not requested")
            yield
    return Stub()


def claude_transport(options, *, extra_tool=False, cost=None, assistant_error=None, denied_tool=None, plan_factory=script):
    from claude_agent_sdk._internal.transport import Transport
    from claude_agent_sdk._internal.transport.subprocess_cli import SubprocessCLITransport
    from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny
    from research_loops.transports.client import session, value
    from research_loops.transports.launch import Launch

    class Stub(Transport):
        def __init__(self):
            self.queue = asyncio.Queue()
            self.connected = False

        async def connect(self):
            self.connected = True
            options.cli_path = "offline-cli-must-not-run"
            async def empty():
                if False:
                    yield {}
            command = SubprocessCLITransport(prompt=empty(), options=options)._build_command()
            assert command[command.index("--tools") + 1] == ""
            assert "--strict-mcp-config" in command
            assert "--setting-sources=" in command
            assert not options.skills and not options.plugins and not options.agents
            assert options.allowed_tools == [] and options.permission_mode == "default"
            assert "permissions" not in json.loads(options.settings)
            for name in TOOL_NAMES:
                assert isinstance(await options.can_use_tool("mcp__rloop__" + name, {}, None), PermissionResultAllow)
            assert isinstance(await options.can_use_tool("Bash", {}, None), PermissionResultDeny)
            assert isinstance(await options.can_use_tool("mcp__other__read_contract", {}, None), PermissionResultDeny)

        async def write(self, data):
            message = json.loads(data)
            if message["type"] == "control_request":
                await self.queue.put({"type": "control_response", "response": {"subtype": "success",
                    "request_id": message["request_id"], "response": {}}})
            elif message["type"] == "user":
                names = ["mcp__rloop__" + name for name in TOOL_NAMES]
                await self.queue.put({"type": "system", "subtype": "init", "tools": names + (["Bash"] if extra_tool else [])})
                if denied_tool:
                    await self.queue.put({"type": "system", "subtype": "permission_denied", "tool_name": denied_tool,
                        "tool_input": {"private": "tool input must not be recorded"},
                        "message": "private CLI message must not be recorded"})
                    if denied_tool in names:
                        return
                if assistant_error:
                    await self.queue.put({"type": "assistant", "error": assistant_error,
                        "message": {"model": "<synthetic>", "content": [
                            {"type": "text", "text": "private SDK text must not be recorded"}]}})
                    return
                if not extra_tool:
                    config = options.mcp_servers["rloop"]
                    async with session(Launch(command=config["command"], args=config["args"], env=config["env"])) as client:
                        assert {t.name for t in (await client.list_tools()).tools} == set(TOOL_NAMES)
                        plan = plan_factory()
                        try:
                            name, arguments = next(plan)
                            while True:
                                name, arguments = plan.send(value(await client.call_tool(name, arguments)))
                        except StopIteration:
                            pass
                await self.queue.put({"type": "result", "subtype": "success", "duration_ms": 1, "duration_api_ms": 0,
                    "is_error": False, "num_turns": 1, "session_id": "offline-stub", "total_cost_usd": cost, "usage": {"input_tokens": 1}})

        async def read_messages(self):
            while self.connected:
                item = await self.queue.get()
                if item is None:
                    return
                yield item

        async def close(self):
            self.connected = False
            await self.queue.put(None)

        async def end_input(self):
            pass

        def is_ready(self):
            return self.connected
    return Stub()
