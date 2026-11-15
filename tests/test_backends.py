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
            public = repo.root / "runs" / row["id"] / "public"
            assert {p.name for p in public.iterdir()} <= {"training.json", "worker-context.json"}
            assert len(json.loads((public / "training.json").read_bytes())["rows"]) == 64
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


def test_authorization_cap_is_shared_even_with_larger_contract_budget(example):
    from research_loops.coordinator import prepare
    from test_integrity import assignment
    path = example / "contract.json"
    contract = json.loads(path.read_bytes())
    contract.setdefault("limits", {})["budget_micro_usd"] = 1000
    path.write_text(json.dumps(contract))
    repo, _, key = prepare(example)
    try:
        repo.dispatch(assignment(repo, key, "first"), 80, execution_metadata={"authorization_cap_micro_usd": 100})
        with pytest.raises(IntegrityError, match="shared budget"):
            repo.dispatch(assignment(repo, key, "second"), 80, execution_metadata={"authorization_cap_micro_usd": 100})
        assert len(repo.runs()) == 1
    finally:
        repo.close()


def test_phase_two_report_duplicate_preserves_original_bytes(example):
    from research_loops.coordinator import prepare
    from research_loops.domain import canonical, digest
    from research_loops.fake import FakeBackend
    from research_loops.reports import WorkerReport
    from test_integrity import assignment
    repo, _, key = prepare(example)
    try:
        assigned = assignment(repo, key)
        repo.dispatch(assigned)
        workspace = Workspace(root=repo.root / "runs" / assigned.run_id / "outbox")
        legacy = asyncio.run(FakeBackend().run(assigned, workspace, Limits()))
        raw = canonical(legacy)
        with repo.db:
            repo.db.execute("UPDATE runs SET report=?,report_hash=? WHERE id=?", (raw, digest(raw.encode()), assigned.run_id))
        before = repo.runs()
        events = repo.db.execute("SELECT count(*) FROM events").fetchone()[0]
        assert not repo.import_report(WorkerReport.model_validate_json(raw), workspace)
        assert repo.runs() == before
        assert repo.db.execute("SELECT count(*) FROM events").fetchone()[0] == events
    finally:
        repo.close()
