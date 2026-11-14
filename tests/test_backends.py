import asyncio
import json
from importlib.metadata import version

import pytest

from research_loops.coordinator import run
from research_loops.domain import IntegrityError, Limits, Workspace
from research_loops.storage import Repository
from test_mcp import task
from sdk_seams import openai_model, claude_transport


def backend(name):
    if name == "fake":
        from research_loops.fake import FakeBackend
        return FakeBackend()
    if name == "openai_agents":
        pytest.importorskip("agents")
        from research_loops.adapters.openai_agents import OpenAIBackend
        return OpenAIBackend("offline-stub", offline_model=openai_model())
    pytest.importorskip("claude_agent_sdk")
    from research_loops.adapters.claude_agent import ClaudeBackend
    return ClaudeBackend("offline-stub", offline_transport_factory=claude_transport)


@pytest.mark.parametrize("name", ["fake", "openai_agents", "claude_agent"])
def test_shared_backend_contract(name, example):
    asyncio.run(run(example, backend=backend(name), pilot_only=True))
    repo = Repository(example / ".rloop")
    try:
        rows = repo.runs()
        assert len(rows) == 2
        assert {row["scientific_outcome"] for row in rows} == {"negative", "supported"}
        for row in rows:
            assert row["execution_status"] == "completed", row["error"]
            metadata = json.loads(row["execution_metadata"])
            assert metadata["backend"] == name
            assert metadata["cost_micro_usd"] == (0 if name == "fake" else None)
            assert metadata["model"] == ("deterministic-v1" if name == "fake" else "offline-stub")
            if name != "fake":
                assert metadata["sdk_version"] == version("openai-agents" if name == "openai_agents" else "claude-agent-sdk")
                trace = json.loads(repo.artifact(row["id"], "sdk_trace"))
                assert len(trace["effective_tools"]) == 6 and trace["offline_seam"]
        audits = list((repo.root / "runs").rglob("tool-environment.json"))
        assert len(audits) == (0 if name == "fake" else 2)
        for audit in audits:
            assert not any("API_KEY" in key or "SECRET" in key or "TOKEN" in key
                for key in json.loads(audit.read_bytes())["environment_keys"])
    finally:
        repo.close()


@pytest.mark.parametrize("name", ["openai_agents", "claude_agent"])
def test_checkpoint_b_required_even_with_keys(name, tmp_path):
    from research_loops.execution import load_backend
    with pytest.raises(IntegrityError, match="checkpoint B"):
        load_backend(name, tmp_path)
    cls = type(backend(name))
    with pytest.raises(IntegrityError, match="checkpoint B"):
        asyncio.run(cls("unauthorized-model").run(task(), Workspace(root=tmp_path / "outbox"), Limits()))
    assert not (tmp_path / "outbox").exists()


def test_claude_rejects_effective_builtin(tmp_path):
    from research_loops.adapters.claude_agent import ClaudeBackend
    adapter = ClaudeBackend("offline-stub", offline_transport_factory=lambda options: claude_transport(options, extra_tool=True))
    with pytest.raises(IntegrityError, match="effective tool list"):
        asyncio.run(adapter.run(task(), Workspace(root=tmp_path / "outbox"), Limits()))


def test_sdk_cost_unknown_is_not_zero():
    from research_loops.adapters.common import micro_usd
    assert micro_usd(None) is None
    assert micro_usd(0) == 0
    assert micro_usd(0.0012341) == 1235


def test_claude_records_sdk_reported_cost(tmp_path):
    from research_loops.adapters.claude_agent import ClaudeBackend
    adapter = ClaudeBackend("offline-stub", offline_transport_factory=lambda options: claude_transport(options, cost=0.001234))
    result = asyncio.run(adapter.run(task(), Workspace(root=tmp_path / "outbox"), Limits()))
    assert result.cost_micro_usd == 1234


@pytest.mark.parametrize("approval", [{}, {"approved_by": "scaled-thinking", "provider": "anthropic", "model": "x", "usd_cap": 1},
    {"approved_by": "scaled-thinking", "provider": "openai", "model": "x", "usd_cap": 0}])
def test_checkpoint_b_must_match_and_have_positive_cap(tmp_path, approval):
    from research_loops.authorization import authorize
    (tmp_path / "project.json").write_text(json.dumps({"checkpoint_b": approval}))
    with pytest.raises(IntegrityError):
        authorize(tmp_path, "openai", "x")
