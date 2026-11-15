"""JSON envelopes shared by direct and MCP callers; text uses UTF-8."""

import base64
import threading

from pydantic import BaseModel

from research_loops.domain import IntegrityError, digest
from research_loops.tools import ToolService

TOOL_NAMES = ("read_contract", "read_findings", "read_artifact", "register_variant", "write_artifact", "submit_result")


def tool_names(contract):
    from research_loops.contracts import is_grain
    return TOOL_NAMES + (("try_on_training",) if is_grain(contract) else ())


class Dispatcher:
    def __init__(self, service: ToolService):
        self.service = service
        self.lock = threading.RLock()

    def call(self, name: str, arguments: dict) -> dict:
        with self.lock:
            try:
                args = dict(arguments)
                if name not in self.service.tool_names:
                    raise IntegrityError("unknown tool")
                if name == "write_artifact":
                    encoding = args.pop("encoding", "utf-8")
                    if encoding not in {"utf-8", "base64"}:
                        raise IntegrityError("encoding must be utf-8 or base64")
                    content = args["content"]
                    if not isinstance(content, str) or len(content) > 1_333_336:
                        raise IntegrityError("artifact content must be bounded text")
                    args["content"] = content.encode("utf-8") if encoding == "utf-8" else base64.b64decode(content, validate=True)
                result = getattr(self.service, name)(**args)
                if isinstance(result, bytes):
                    data = result
                    try:
                        result = {"text": data.decode("utf-8")}
                    except UnicodeDecodeError:
                        result = {"base64": base64.b64encode(data).decode()}
                    result.update(sha256=digest(data), size=len(data))
                if isinstance(result, BaseModel):
                    result = result.model_dump(mode="json")
                return {"ok": True, "value": result}
            except (ValueError, TypeError, OSError) as exc:
                return {"ok": False, "error": str(exc)}
