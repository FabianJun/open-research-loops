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
        direct = Dispatcher(ToolService(assignment, tmp_path / "direct"))
        launch = local_launch(assignment, tmp_path / "remote" / "outbox")
        async with session(launch) as client:
            assert {t.name for t in (await client.list_tools()).tools} == set(TOOL_NAMES)
            async def call(name, arguments):
                a = direct.call(name, arguments)
                b = value(await client.call_tool(name, arguments))
                assert a == b
                return a
            assert (await call("read_contract", {}))["ok"]
            assert not (await call("read_artifact", {"relative": "../private/final.json"}))["ok"]
            assert not (await call("read_artifact", {"relative": "/evaluator.py"}))["ok"]
            assert not (await call("read_findings", {"ids": ["final-score"]}))["ok"]
            assert (await call("read_findings", {"ids": []}))["value"] == []
            assert (await call("register_variant", {"prediction": assignment.prediction}))["ok"]
            assert not (await call("write_artifact", {"relative": "../escape", "content": "YQ=="}))["ok"]
            candidate_bytes = b'{"constant":0}'
            candidate = (await call("write_artifact", {"relative": "candidate.json", "content": base64.b64encode(candidate_bytes).decode()}))["value"]
            assert (await call("read_artifact", {"relative": "candidate.json"}))["value"]["base64"] == base64.b64encode(candidate_bytes).decode()
            prompt = canonical(assignment)
            transcript_bytes = canonical({"prompt": prompt, "response": {"constant": 0}}).encode()
            transcript = (await call("write_artifact", {"relative": "transcript.json", "content": base64.b64encode(transcript_bytes).decode()}))["value"]
            report = WorkerReport(report_id="parity", run_id="parity", contract_hash=assignment.registration_hash,
                candidate=candidate, transcript=transcript, prompt_hash=digest(prompt.encode()), seed=7)
            assert (await call("submit_result", {"report": report.model_dump(mode="json")}))["ok"]
            assert not (await call("write_artifact", {"relative": "late.txt", "content": "YQ=="}))["ok"]
            assert not (await call("register_variant", {"prediction": "retry"}))["ok"]
            assert not (await call("submit_result", {"report": report.model_dump(mode="json")}))["ok"]
        audit = json.loads((tmp_path / "remote" / "tool-environment.json").read_bytes())
        assert not any("API_KEY" in k or "TOKEN" in k or "SECRET" in k for k in audit["environment_keys"])
    asyncio.run(check())
