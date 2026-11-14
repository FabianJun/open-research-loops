"""JSON envelopes shared by direct and MCP callers; bytes use base64."""

import base64
import threading

from pydantic import BaseModel

from research_loops.domain import IntegrityError
from research_loops.reports import WorkerReport
from research_loops.tools import ToolService

TOOL_NAMES = ("read_contract", "read_findings", "read_artifact", "register_variant", "write_artifact", "submit_result")


class Dispatcher:
    def __init__(self, service: ToolService):
        self.service = service
        self.lock = threading.RLock()

    def call(self, name: str, arguments: dict) -> dict:
        with self.lock:
            try:
                args = dict(arguments)
                if name not in TOOL_NAMES:
                    raise IntegrityError("unknown tool")
                if name == "write_artifact":
                    args["content"] = base64.b64decode(args["content"], validate=True)
                if name == "submit_result":
                    args["report"] = WorkerReport.model_validate(args["report"])
                result = getattr(self.service, name)(**args)
                if isinstance(result, bytes):
                    result = {"base64": base64.b64encode(result).decode()}
                if isinstance(result, BaseModel):
                    result = result.model_dump(mode="json")
                return {"ok": True, "value": result}
            except (ValueError, TypeError, OSError) as exc:
                return {"ok": False, "error": str(exc)}
