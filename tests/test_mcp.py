import asyncio
import base64
import json

import pytest

pytest.importorskip("mcp", reason="install research-loops[mcp] for MCP parity tests")

from research_loops.domain import WorkerContract, WorkerReport, canonical, digest
from research_loops.tools import ToolService
from research_loops.transports.client import session, value
from research_loops.transports.launch import local_launch
from research_loops.transports.protocol import Dispatcher, TOOL_NAMES


def task():
    return WorkerContract(run_id="parity", registration_hash="a" * 64, goal="recover signal", prediction="zero fails", seed=7, variant=0, input_hash="b" * 64)


def test_direct_and_stdio_results_and_refusals_match(tmp_path):
    async def check():
        assignment = task()
        owner_path = tmp_path / "project.json"
        owner_record = b'{"owner":{"name":"Private Owner","source":"argument"}}'
        owner_path.write_bytes(owner_record)
        direct = Dispatcher(ToolService(assignment, tmp_path / "direct"))
        launch = local_launch(assignment, tmp_path / "remote" / "outbox")
        async with session(launch) as client:
            assert {t.name for t in (await client.list_tools()).tools} == set(TOOL_NAMES)
            async def call(name, arguments):
                a = direct.call(name, arguments)
                b = value(await client.call_tool(name, arguments))
                assert a == b
                return a
            contract = await call("read_contract", {})
            assert contract["ok"] and "owner" not in contract["value"]
            assert "Private Owner" not in json.dumps(contract)
            assert not (await call("read_artifact", {"relative": "../private/final.json"}))["ok"]
            assert not (await call("read_artifact", {"relative": "/evaluator.py"}))["ok"]
            assert not (await call("read_findings", {"ids": ["final-score"]}))["ok"]
            assert (await call("read_findings", {"ids": []}))["value"] == []
            assert (await call("register_variant", {"prediction": assignment.prediction}))["ok"]
            for relative in ("../project.json", "../../project.json", str(owner_path.resolve())):
                assert not (await call("read_artifact", {"relative": relative}))["ok"]
                assert not (await call("write_artifact", {"relative": relative, "content": "YQ=="}))["ok"]
            assert owner_path.read_bytes() == owner_record
            assert not (await call("write_artifact", {"relative": "../escape", "content": "YQ=="}))["ok"]
            for relative in ("candidate.json", "transcript.json", "CANDIDATE.JSON", "candidate.json/nested", "adapter-trace.json"):
                assert not (await call("write_artifact", {"relative": relative, "content": "{}"}))["ok"]
            for relative, data, encoding in (("notes.txt", "Signal: \u03bb".encode(), "utf-8"), ("binary.dat", b"\xff\x00", "base64")):
                content = data.decode() if encoding == "utf-8" else base64.b64encode(data).decode()
                descriptor = (await call("write_artifact", {"relative": relative, "content": content, "encoding": encoding}))["value"]
                result = (await call("read_artifact", {"relative": relative}))["value"]
                assert descriptor["sha256"] == result["sha256"] == digest(data)
                assert descriptor["size"] == result["size"] == len(data)
                assert result == {("text" if encoding == "utf-8" else "base64"): content, "sha256": digest(data), "size": len(data)}
            assert (await call("write_artifact", {"relative": "default.txt", "content": "plain text"}))["ok"]
            assert not (await call("write_artifact", {"relative": "bad.bin", "content": "Y Q==", "encoding": "base64"}))["ok"]
            assert not (await call("write_artifact", {"relative": "bad.txt", "content": "a", "encoding": "unknown"}))["ok"]
            assert (await call("submit_result", {"candidate": {"constant": 0}}))["ok"]
            assert not (await call("write_artifact", {"relative": "late.txt", "content": "late"}))["ok"]
            assert not (await call("register_variant", {"prediction": "retry"}))["ok"]
            assert not (await call("submit_result", {"candidate": {"constant": 0}}))["ok"]
        audit = json.loads((tmp_path / "remote" / "tool-environment.json").read_bytes())
        assert not any("API_KEY" in k or "TOKEN" in k or "SECRET" in k for k in audit["environment_keys"])
    asyncio.run(check())
