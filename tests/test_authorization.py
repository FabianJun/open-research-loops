import asyncio
import json
import os
import subprocess
import sys

import pytest

from research_loops.authorization import authorize, LimitReached
from research_loops.domain import IntegrityError


def approval(provider="openai", mode="chatgpt", **updates):
    return dict(approved_by="Ada", provider=provider, model="offline-stub", auth_mode=mode,
        run_limits=dict(max_worker_runs=8, max_parallel_workers=1, max_turns_per_worker=16,
            max_wall_seconds_per_worker=10), **updates)


@pytest.mark.parametrize("mode", ["chatgpt", "api_key"])
def test_explicit_gate(tmp_path, mode):
    record = approval(mode=mode)
    if mode == "api_key":
        record["usd_cap"] = "2.50"
    (tmp_path / "project.json").write_text(json.dumps({"owner": {"name": "Ada", "source": "argument"}, "checkpoint_b": record}))
    value = authorize(tmp_path, "openai", "offline-stub")
    assert value.auth_mode == mode
    assert value.cap_micro_usd == (2500000 if mode == "api_key" else None)
    with pytest.raises(IntegrityError):
        authorize(tmp_path, "openai", "cheaper-model")
    record["usd_cap"] = 1
    record["auth_mode"] = "chatgpt"
    (tmp_path / "project.json").write_text(json.dumps({"owner": {"name": "Ada", "source": "argument"}, "checkpoint_b": record}))
    with pytest.raises(IntegrityError):
        authorize(tmp_path, "openai", "offline-stub")


def test_run_and_parallel_limits_survive_restart(example):
    from research_loops.coordinator import prepare
    from test_integrity import assignment
    repo, _, key = prepare(example)
    metadata = dict(provider="openai", run_limits=approval()["run_limits"])
    metadata["run_limits"]["max_worker_runs"] = 2
    repo.dispatch(assignment(repo, key, "one"), execution_metadata=metadata)
    with pytest.raises(LimitReached, match="parallel"):
        repo.dispatch(assignment(repo, key, "two"), execution_metadata=metadata)
    repo.fail("one", "cancelled", "test")
    repo.dispatch(assignment(repo, key, "two"), execution_metadata=metadata)
    repo.fail("two", "cancelled", "test")
    root = repo.root
    repo.close()
    from research_loops.storage import Repository
    repo = Repository(root)
    try:
        with pytest.raises(LimitReached, match="worker runs"):
            repo.dispatch(assignment(repo, key, "three"), execution_metadata=metadata)
    finally:
        repo.close()


@pytest.mark.parametrize("host_managed", [False, True])
def test_claude_child_env_has_no_overriding_credentials(tmp_path, host_managed):
    pytest.importorskip("claude_agent_sdk")
    from research_loops.adapters.claude_transport import child_environment
    secrets = {name: "sentinel-not-a-real-secret" for name in ["ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN",
        "CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_PROFILE", "ANTHROPIC_FEDERATION_RULE_ID", "CLAUDE_CODE_USE_BEDROCK",
        "CLAUDE_CONFIG_DIR", "AWS_ACCESS_KEY_ID", "GOOGLE_APPLICATION_CREDENTIALS"]}
    source = {**os.environ, **secrets}
    source.pop("CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST", None)
    if host_managed:
        source["CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST"] = "1"
    env = child_environment(source, "claude_code")
    assert "CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST" not in env
    result = subprocess.run([sys.executable, "-I", "-c", "import os,json;print(json.dumps(sorted(os.environ)))"],
        env=env, capture_output=True, check=True, text=True)
    assert not set(json.loads(result.stdout)) & set(secrets)
    assert not set(env) & set(secrets)
    explicit = child_environment(secrets, "api_key")
    assert explicit["ANTHROPIC_API_KEY"] == secrets["ANTHROPIC_API_KEY"]
    assert "ANTHROPIC_AUTH_TOKEN" not in explicit


def test_provider_limit_stops_pilot_and_is_persistent(example):
    from research_loops.coordinator import run
    from research_loops.storage import Repository
    class Limited:
        name, provider, model = "fake", "offline", "deterministic-v1"
        calls = 0
        async def run(self, *args):
            self.calls += 1
            raise LimitReached("stub rate limit")
    data = json.loads((example / "contract.json").read_bytes())
    data.setdefault("limits", {})["concurrency"] = 1
    (example / "contract.json").write_text(json.dumps(data))
    backend = Limited()
    with pytest.raises(LimitReached):
        asyncio.run(run(example, backend=backend, pilot_only=True))
    assert backend.calls == 1
    repo = Repository(example / ".rloop")
    try:
        assert repo.runs()[0]["execution_status"] == "limit_reached"
        assert not repo.db.execute("SELECT final_ticket FROM project").fetchone()[0]
    finally:
        repo.close()


def test_claude_limit_protocol():
    pytest.importorskip("claude_agent_sdk")
    from research_loops.adapters.claude_agent import limit_message
    assert limit_message({"rate_limit_info": {"status": "rejected"}})
    assert not limit_message({"rate_limit_info": {"status": "allowed_warning"}})
    assert limit_message({"error": "rate_limit"})
    assert not limit_message({"error": {"unrelated": "failure"}})


@pytest.mark.parametrize("error, expected", [
    (IntegrityError("Claude response model differs from authorization"),
        "IntegrityError: Claude response model differs from authorization"),
    (IntegrityError("x" * 400), ("IntegrityError: " + "x" * 400)[:300]),
    (RuntimeError("private SDK text or local path"), "RuntimeError: SDK failure (details suppressed)"),
])
def test_approved_worker_records_only_rloop_error_details(example, error, expected):
    from research_loops.authorization import Authorization
    from research_loops.coordinator import run
    from research_loops.storage import Repository
    policy = Authorization.model_validate(approval())
    class Failed:
        name, provider, model = "fake", "openai", "offline-stub"
        def check_authorization(self):
            return policy
        async def run(self, *args):
            raise error
    with pytest.raises(ExceptionGroup):
        asyncio.run(run(example, backend=Failed(), worker_runs=1))
    repo = Repository(example / ".rloop")
    try:
        rows = repo.runs()
        assert len(rows) == 1
        assert rows[0]["execution_status"] == "technical_error"
        assert rows[0]["error"] == expected
        event = repo.db.execute("SELECT payload FROM events WHERE kind='technical_error'").fetchone()
        assert json.loads(event[0])["reason"] == expected
    finally:
        repo.close()


def test_actual_claude_sdk_child_transport_strips_credentials_and_stops(tmp_path, monkeypatch):
    pytest.importorskip("claude_agent_sdk")
    from research_loops.adapters.claude_transport import LoginTransport, SubprocessCLITransport
    from research_loops.adapters.claude_agent import ClaudeBackend
    from research_loops.domain import Workspace, Limits
    from research_loops.transports.protocol import TOOL_NAMES
    from test_mcp import task
    script = tmp_path / "stub_cli.py"
    audit = tmp_path / "child-environment.json"
    source = '''import json,os,sys
with open(sys.argv[1], 'w') as f: json.dump(sorted(os.environ),f)
for line in sys.stdin:
 m=json.loads(line)
 if m['type']=='control_request':
  print(json.dumps({'type':'control_response','response':{'subtype':'success','request_id':m['request_id'],'response':{}}}),flush=True)
 elif m['type']=='user':
  print(json.dumps({'type':'system','subtype':'init','tools':json.loads(sys.argv[2])}),flush=True)
  print(json.dumps({'type':'rate_limit_event','uuid':'offline','session_id':'offline','rate_limit_info':{'status':'rejected'}}),flush=True)
'''
    script.write_text(source)
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "offline-override-must-disappear")
    monkeypatch.setattr(SubprocessCLITransport, "_find_cli", lambda self: sys.executable)
    monkeypatch.setattr(SubprocessCLITransport, "_build_command", lambda self: [sys.executable, str(script), str(audit),
        json.dumps(["mcp__rloop__" + name for name in TOOL_NAMES])])
    adapter = ClaudeBackend("offline-stub", offline_transport_factory=lambda options: LoginTransport(options, "claude_code"))
    with pytest.raises(LimitReached):
        asyncio.run(adapter.run(task(), Workspace(root=tmp_path / "outbox"), Limits()))
    keys = json.loads(audit.read_bytes())
    assert not {"ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN"} & set(keys)
    assert not (tmp_path / "outbox" / "report.json").exists()


def test_configured_wall_limit_stops_further_dispatch(example):
    pytest.importorskip("agents")
    from research_loops.authorization import Authorization
    from research_loops.coordinator import run
    from research_loops.storage import Repository
    value = approval()
    value["run_limits"]["max_wall_seconds_per_worker"] = 1
    policy = Authorization.model_validate(value)
    class Slow:
        name, provider, model, auth_mode, effort = "openai_agents", "openai", "offline-stub", "chatgpt", "high"
        calls = 0
        def check_authorization(self):
            return policy
        async def run(self, contract, workspace, limits):
            assert limits.worker_seconds == 1 and limits.concurrency == 1
            self.calls += 1
            await asyncio.sleep(10)
    backend = Slow()
    with pytest.raises(LimitReached):
        asyncio.run(run(example, backend=backend, worker_runs=2))
    assert backend.calls == 1
    repo = Repository(example / ".rloop")
    try:
        assert len(repo.runs()) == 1 and repo.runs()[0]["execution_status"] == "limit_reached"
        metadata = json.loads(repo.runs()[0]["execution_metadata"])
        assert metadata["usage"] is None and metadata["cost_is_estimate"]
        with pytest.raises(LimitReached, match="previously"):
            from test_integrity import assignment
            repo.dispatch(assignment(repo, repo.runs()[0]["registration_hash"], "later"), execution_metadata=metadata)
    finally:
        repo.close()
    with pytest.raises(LimitReached, match="previously"):
        asyncio.run(run(example, backend=backend, worker_runs=2))
    assert backend.calls == 1


def test_openai_turn_limit_is_passed_to_actual_sdk(tmp_path):
    pytest.importorskip("agents")
    from agents import Model, ModelResponse, Usage
    from openai.types.responses import ResponseFunctionToolCall
    from research_loops.adapters.openai_agents import OpenAIBackend
    from research_loops.authorization import Authorization
    from research_loops.domain import Limits, Workspace
    from test_mcp import task
    class Repeating(Model):
        calls = 0
        async def get_response(self, *args, **kwargs):
            self.calls += 1
            return ModelResponse(output=[ResponseFunctionToolCall(type="function_call", name="read_contract",
                arguments="{}", call_id=f"repeat-{self.calls}")], usage=Usage(requests=1), response_id=None)
        async def stream_response(self, *args, **kwargs):
            raise AssertionError()
            yield
    model = Repeating()
    backend = OpenAIBackend("offline-stub", offline_model=model)
    value = approval()
    value["run_limits"]["max_turns_per_worker"] = 2
    backend.check_authorization = lambda: Authorization.model_validate(value)
    with pytest.raises(LimitReached, match="turn limit"):
        asyncio.run(backend.run(task(), Workspace(root=tmp_path / "outbox"), Limits()))
    assert model.calls == 2
