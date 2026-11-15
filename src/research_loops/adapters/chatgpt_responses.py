"""Pinned Agents SDK Responses model constrained to the ChatGPT preview route."""

from agents import Agent, tool_namespace
from agents.models.openai_responses import OpenAIResponsesModel

from research_loops.authorization import LimitReached
from research_loops.domain import IntegrityError
from research_loops.transports.protocol import TOOL_NAMES

UNSUPPORTED = {"background", "conversation", "max_output_tokens", "max_tool_calls", "metadata", "moderation",
    "multi_agent", "prompt", "prompt_cache_retention", "safety_identifier", "temperature", "top_logprobs",
    "top_p", "truncation", "user", "previous_response_id"}
LIMIT_CODES = {"subscription_sharing_usage_limit_exceeded", "subscription_sharing_usage_unavailable",
    "rate_limit_exceeded", "rate_limit_error", "insufficient_quota"}


class MCPAgent(Agent):
    async def get_all_tools(self, run_context):
        tools = await super().get_all_tools(run_context)
        if {tool.name for tool in tools} != set(TOOL_NAMES) or len(tools) != len(TOOL_NAMES):
            raise IntegrityError("effective worker tools differ from rloop MCP policy")
        return tool_namespace(name="rloop", description="The six run-scoped rloop MCP tools", tools=tools)


class ChatGPTResponsesModel(OpenAIResponsesModel):
    def _build_response_create_kwargs(self, *args, **kwargs):
        request = super()._build_response_create_kwargs(*args, **kwargs)
        for name in UNSUPPORTED:
            request.pop(name, None)
        request.update(store=False)
        if request.get("stream") is not True or not isinstance(request.get("input"), list):
            raise IntegrityError("ChatGPT requires streaming and explicit input history")
        if any(item.get("role") == "system" for item in request["input"]):
            raise IntegrityError("system input messages are unsupported by the ChatGPT preview")
        tools = request.get("tools", [])
        if (len(tools) != 1 or tools[0].get("type") != "namespace" or tools[0].get("name") != "rloop"
                or {tool.get("name") for tool in tools[0]["tools"]} != set(TOOL_NAMES)
                or any(tool.get("type") != "function" for tool in tools[0]["tools"])):
            raise IntegrityError("ChatGPT tool namespace differs from MCP policy")
        return request

    async def stream_response(self, *args, **kwargs):
        completed = False
        async for event in super().stream_response(*args, **kwargs):
            if event.type in {"response.failed", "response.incomplete", "error", "response.error"}:
                error = getattr(getattr(event, "response", None), "error", None)
                code = getattr(error, "code", None) or getattr(event, "code", None)
                if code in LIMIT_CODES:
                    raise LimitReached("OpenAI subscription or rate limit reached")
                raise IntegrityError("OpenAI stream failed or was incomplete")
            if event.type == "response.completed":
                if event.response.status != "completed":
                    raise IntegrityError("invalid terminal Responses status")
                completed = True
            yield event
        if not completed:
            raise IntegrityError("OpenAI stream ended without response.completed")
