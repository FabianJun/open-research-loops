import json
import subprocess
import sys
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from research_loops.authorization import authorize
from research_loops.cli import app
from research_loops.domain import IntegrityError
from research_loops.owner import initialize_owner, resolve_owner
from test_authorization import approval


def test_init_records_explicit_owner_and_preserves_other_host_settings(example):
    path = example / "project.json"
    path.write_text(json.dumps({"sandbox": {"name": "none"}}))
    result = CliRunner().invoke(app, ["init", str(example), "--owner", "  Ada Lovelace  "])
    assert result.exit_code == 0, (result.output, result.exception)
    config = json.loads(path.read_bytes())
    assert config == {"owner": {"name": "Ada Lovelace", "source": "argument"}, "sandbox": {"name": "none"}, "mode": "autonomous"}
    assert (example / ".rloop" / "report.md").is_file()
    assert initialize_owner(example, None) == config["owner"]


@pytest.mark.parametrize("name", ["", " \t\n "])
def test_init_rejects_empty_owner_before_creating_project(tmp_path, name):
    project = tmp_path / "new"
    result = CliRunner().invoke(app, ["init", str(project), "--owner", name])
    assert result.exit_code != 0 and "nonempty project owner" in result.output
    assert not project.exists()


def test_owner_resolution_uses_project_git_configuration(tmp_path, monkeypatch):
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Git Owner"], check=True)
    monkeypatch.setattr("research_loops.owner.getpass.getuser", lambda: pytest.fail("OS lookup must not override Git"))
    assert initialize_owner(tmp_path / "new" / "pilot", None) == {"name": "Git Owner", "source": "git"}
    assert resolve_owner(" Explicit Owner ", tmp_path) == {"name": "Explicit Owner", "source": "argument"}


@pytest.mark.parametrize("git_result", ["missing", "error", "empty"])
def test_owner_resolution_falls_back_to_os(tmp_path, monkeypatch, git_result):
    def git(*args, **kwargs):
        if git_result == "missing":
            raise FileNotFoundError()
        return SimpleNamespace(returncode=1 if git_result == "error" else 0, stdout=" \n ")
    monkeypatch.setattr("research_loops.owner.subprocess.run", git)
    monkeypatch.setattr("research_loops.owner.getpass.getuser", lambda: " OS Owner ")
    assert resolve_owner(None, tmp_path) == {"name": "OS Owner", "source": "os"}


@pytest.mark.parametrize("owner", ["Ada", "Grace Hopper", "研究者"])
def test_checkpoint_b_matches_configured_owner_after_strip(tmp_path, owner):
    config = {"owner": {"name": f" {owner} ", "source": "argument"}, "checkpoint_b": approval()}
    config["checkpoint_b"]["approved_by"] = f" {owner} "
    (tmp_path / "project.json").write_text(json.dumps(config))
    assert authorize(tmp_path, "openai", "offline-stub").approved_by.strip() == owner


@pytest.mark.parametrize("owner", [None, {}, {"name": ""}, {"name": " "}, {"name": "ada"}, {"name": "Mallory"}])
def test_checkpoint_b_rejects_missing_invalid_or_mismatched_owner_before_sdk_import(tmp_path, owner):
    config = {"owner": owner, "checkpoint_b": approval()}
    (tmp_path / "project.json").write_text(json.dumps(config))
    # A separate interpreter proves refusal precedes every vendor SDK import.
    script = '''import sys
from pathlib import Path
from research_loops.execution import load_backend
from research_loops.domain import IntegrityError
try: load_backend('openai_agents', Path(sys.argv[1]))
except IntegrityError: pass
else: raise AssertionError('invalid owner authorized')
assert not any(n in sys.modules for n in ('agents', 'openai', 'claude_agent_sdk'))
'''
    result = subprocess.run([sys.executable, "-I", "-c", script, str(tmp_path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    with pytest.raises(IntegrityError):
        authorize(tmp_path, "openai", "offline-stub")
