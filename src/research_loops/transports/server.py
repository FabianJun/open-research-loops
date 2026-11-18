"""The single MCP stdio tool implementation; no DB, evaluator or credentials."""

import argparse
import json
import os
from pathlib import Path

from mcp.server import MCPServer

from research_loops.domain import WorkerContract, canonical
from research_loops.paths import atomic_write
from research_loops.tools import ToolService
from research_loops.transports.protocol import Dispatcher


def create_server(dispatch: Dispatcher) -> MCPServer:
    server = MCPServer("rloop", version="0.2.0")

    @server.tool()
    def read_contract() -> dict:
        return dispatch.call("read_contract", {})

    @server.tool()
    def read_findings(ids: list[str]) -> dict:
        return dispatch.call("read_findings", {"ids": ids})

    @server.tool()
    def read_artifact(relative: str) -> dict:
        return dispatch.call("read_artifact", {"relative": relative})

    @server.tool()
    def register_variant(prediction: str) -> dict:
        return dispatch.call("register_variant", {"prediction": prediction})

    @server.tool()
    def write_artifact(relative: str, content: str, encoding: str = "utf-8") -> dict:
        """Write UTF-8 text; use encoding='base64' explicitly for binary notes. Reserved host files are forbidden."""
        return dispatch.call("write_artifact", {"relative": relative, "content": content, "encoding": encoding})

    @server.tool()
    def submit_result(candidate: dict) -> dict:
        """Validate one expression tree and seal its host-built report and transcript. Correct tool errors and resubmit."""
        return dispatch.call("submit_result", {"candidate": candidate})

    if "try_on_training" in dispatch.service.tool_names:
        @server.tool()
        def try_on_training(params: dict) -> dict:
            """Evaluate pipeline params on the fixed train subset; at most six calls per run. No pixels returned."""
            return dispatch.call("try_on_training", {"params": params})

    return server


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--outbox", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--adapter", action="store_true")
    parser.add_argument("--shared-files", action="store_true")
    parser.add_argument("--public", type=Path)
    args = parser.parse_args()
    # Store names only; never dump environment values.
    atomic_write(args.audit, canonical({"environment_keys": sorted(os.environ)}).encode())
    if args.shared_files:
        args.audit.chmod(0o644)
    if any("API_KEY" in name.upper() or "TOKEN" in name.upper() or "SECRET" in name.upper() for name in os.environ):
        raise RuntimeError("tool server received a credential environment variable")
    from research_loops.contracts import parse_worker
    contract = parse_worker(args.context.read_bytes())
    service = ToolService(contract, args.outbox, submission_name="submission.json" if args.adapter else "report.json", shared_files=args.shared_files, public_root=args.public)
    create_server(Dispatcher(service)).run(transport="stdio")


if __name__ == "__main__":
    main()
