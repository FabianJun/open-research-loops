import asyncio
import json

import pytest

from research_loops.authorization import LimitReached
from research_loops.domain import IntegrityError, Limits, Workspace
from test_mcp import task
from sdk_seams import script

pytest.importorskip("agents")


def stream_client(mode="success"):
    import httpx2
    from openai import AsyncOpenAI
    from research_loops.adapters.chatgpt_responses import UNSUPPORTED
    requests = []
    plan = script()
    def handler(request):
        assert str(request.url) == "https://api.openai.com/v1/responses"
        assert request.headers["authorization"] == "Bearer offline-access"
        body = json.loads(request.content)
        requests.append(body)
        assert body["stream"] is True and body["store"] is False and isinstance(body["input"], list)
        assert body["include"] == ["reasoning.encrypted_content"]
        assert not UNSUPPORTED & body.keys()
        assert body["tools"][0]["type"] == "namespace" and body["tools"][0]["name"] == "rloop"
        assert len(body["tools"][0]["tools"]) == 6
        if mode in {"http_limit", "http_unavailable"}:
            return httpx2.Response(429 if mode == "http_limit" else 503, json={"error": {"message": "offline limit",
                "type": "rate_limit_error", "code": "subscription_sharing_usage_limit_exceeded" if mode == "http_limit" else "subscription_sharing_usage_unavailable"}})
        try:
            if len(requests) == 1:
                name, arguments = next(plan)
            else:
                outputs = [item for item in body["input"] if item.get("type") == "function_call_output"]
                raw = outputs[-1]["output"]
                value = json.loads(raw[0]["text"] if isinstance(raw, list) else raw)
                if "structured_content" in value:
                    value = value["structured_content"]
                name, arguments = plan.send(value)
            output = dict(id=f"fc_{len(requests)}", type="function_call", name=name, namespace="rloop",
                call_id=f"call_{len(requests)}", arguments=json.dumps(arguments), status="completed")
        except StopIteration:
            output = dict(id="msg_final", type="message", role="assistant", status="completed",
                content=[dict(type="output_text", text="Submitted.", annotations=[])])
        response = dict(id=f"resp_{len(requests)}", object="response", created_at=1, status="completed",
            model="gpt-6-astra", output=[output], parallel_tool_calls=False, tool_choice="auto", tools=[],
            usage=dict(input_tokens=1, output_tokens=1, total_tokens=2, input_tokens_details=dict(cached_tokens=0),
                output_tokens_details=dict(reasoning_tokens=0)))
        events = [dict(type="response.created", response={**response, "output": [], "status": "in_progress"}),
            dict(type="response.output_item.added", output_index=0, item=output),
            dict(type="response.output_item.done", output_index=0, item=output)]
        if mode in {"failed", "incomplete"}:
            response.update(status=mode, error=dict(code="subscription_sharing_usage_limit_exceeded", message="offline limit"))
            events.append(dict(type="response." + mode, response=response))
        elif mode != "interrupted":
            events.append(dict(type="response.completed", response=response))
        return httpx2.Response(200, headers={"content-type": "text/event-stream"},
            content="".join("data: " + json.dumps({**event, "sequence_number": i}) + "\n\n" for i, event in enumerate(events)).encode())
    async def credential():
        return "offline-access"
    client = AsyncOpenAI(api_key=credential, max_retries=0, base_url="https://api.openai.com/v1",
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)))
    return client, requests


class StubAuth:
    def models(self):
        return [{"slug": "gpt-6-astra", "display_name": "GPT-6 Astra"}]
    def access_token(self):
        return "offline-access"


def test_actual_sdk_streaming_mcp_worker(tmp_path):
    from research_loops.adapters.openai_agents import OpenAIBackend
    client, requests = stream_client()
    backend = OpenAIBackend("gpt-6-astra", offline_client=client, offline_auth=StubAuth())
    result = asyncio.run(backend.run(task(), Workspace(root=tmp_path / "outbox"), Limits()))
    assert result.cost_micro_usd is None and result.usage["input_tokens"] > 0
    assert len(requests) > 6
    assert len(requests[-1]["input"]) > len(requests[0]["input"])


@pytest.mark.parametrize("mode,exception", [("failed", LimitReached), ("http_limit", LimitReached),
    ("http_unavailable", LimitReached), ("incomplete", LimitReached), ("interrupted", IntegrityError)])
def test_stream_limits_and_interruptions_do_not_retry(tmp_path, mode, exception):
    from research_loops.adapters.openai_agents import OpenAIBackend
    client, requests = stream_client(mode)
    backend = OpenAIBackend("gpt-6-astra", offline_client=client, offline_auth=StubAuth())
    with pytest.raises(exception):
        asyncio.run(backend.run(task(), Workspace(root=tmp_path / "outbox"), Limits()))
    assert len(requests) == 1
    trace = (tmp_path / "outbox" / "adapter-trace.json").read_bytes()
    assert b"offline-access" not in trace and b"offline limit" not in trace
    assert len(json.loads(trace)["effective_tools"]) == 6
    assert not (tmp_path / "outbox" / "report.json").exists()


def test_unlisted_model_refused_before_tools_or_inference(tmp_path):
    from research_loops.adapters.openai_agents import OpenAIBackend
    client, requests = stream_client()
    backend = OpenAIBackend("cheaper-unlisted", offline_client=client, offline_auth=StubAuth())
    with pytest.raises(IntegrityError, match="not listed"):
        asyncio.run(backend.run(task(), Workspace(root=tmp_path / "outbox"), Limits()))
    assert not requests and not (tmp_path / "outbox").exists()
    asyncio.run(client.close())
