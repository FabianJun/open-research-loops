"""Coaching is host-only; predictions are durable pre-scoring evidence."""

import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import tomllib

import pytest
from typer.testing import CliRunner

from research_loops import skills
from research_loops.cli import app
from research_loops.coordinator import prepare, run
from research_loops.domain import IntegrityError, canonical
from research_loops.fake import FakeBackend
from research_loops.prediction import record
from research_loops.reporting import render, export
from research_loops.settings import working_mode
from research_loops.storage import Repository
from research_loops.transports.launch import local_launch


def invoke(*args):
    result = CliRunner().invoke(app, [str(arg) for arg in args])
    assert result.exit_code == 0, (result.output, result.exception)
    return result.output


@pytest.mark.parametrize("mode", [None, "autonomous", "coached"])
def test_init_mode_and_scoring(tmp_path, mode):
    project = tmp_path / "project"
    invoke("init", project, "--owner", "Ada", *(["--mode", mode] if mode else []))
    config = json.loads((project / "project.json").read_bytes())
    assert config["mode"] == (mode or "autonomous")
    assert working_mode(project) == config["mode"]
    if mode == "coached":
        assert not (project / ".rloop").exists()
    else:
        repo = Repository(project / ".rloop")
        try:
            assert len(repo.runs()) == 2
            assert all(row["verdict"] for row in repo.runs())
        finally:
            repo.close()


def test_mode_preserved_and_changed_like_owner(tmp_path):
    invoke("init", tmp_path, "--mode", "coached", "--owner", "Ada")
    invoke("init", tmp_path)
    assert working_mode(tmp_path) == "coached"
    config = json.loads((tmp_path / "project.json").read_bytes())
    config["sandbox"] = {"name": "none"}
    config["mode"] = "autonomous"
    (tmp_path / "project.json").write_text(canonical(config), encoding="utf-8")
    assert working_mode(tmp_path) == "autonomous"
    invoke("init", tmp_path, "--mode", "coached")
    updated = json.loads((tmp_path / "project.json").read_bytes())
    assert updated == {**config, "mode": "coached"}


@pytest.mark.parametrize("value", ["Coached", "unknown", "", " coached "])
def test_init_unknown_mode_has_no_side_effects(tmp_path, value):
    project = tmp_path / "new"
    result = CliRunner().invoke(app, ["init", str(project), "--mode", value])
    assert result.exit_code != 0
    assert not project.exists()


@pytest.mark.parametrize("value", [None, 1, True, [], {}, "COACHED", "unknown"])
def test_host_mode_strictly_validated_before_execution(example, value):
    path = example / "project.json"
    path.write_text(canonical({"mode": value}), encoding="utf-8")
    before = path.read_bytes()
    with pytest.raises(IntegrityError, match="mode"):
        prepare(example)
    result = CliRunner().invoke(app, ["init", str(example), "--owner", "Changed"])
    assert result.exit_code != 0
    assert path.read_bytes() == before
    assert not (example / ".rloop").exists()


def test_old_project_defaults_to_autonomous(example):
    assert working_mode(example) == "autonomous"
    repo, _, _ = prepare(example)
    try:
        assert "Prediction vs result" not in render(repo)
    finally:
        repo.close()


@pytest.mark.parametrize("mode", ["autonomous", "coached"])
def test_prediction_and_report_before_after_scoring(example, mode):
    (example / "project.json").write_text(canonical({"mode": mode}), encoding="utf-8")
    invoke("plan", example)
    output = invoke("report", example)
    assert ("no prediction recorded" in output) == (mode == "coached")
    before = datetime.now(timezone.utc)
    invoke("predict", example, "--value", "0.25", "--note", "My own reasoning")
    pending = invoke("report", example, "--check")
    assert "Predicted development mse: 0.25" in pending
    assert "unavailable; no matching checked result yet" in pending
    second = CliRunner().invoke(app, ["predict", str(example), "--value", "0.4"])
    assert second.exit_code != 0 and "already recorded" in second.output
    asyncio.run(run(example, pilot_only=True))
    report = invoke("report", example, "--check")
    assert "Actual development mse: 0" in report
    assert "Difference (actual minus predicted): -0.25" in report
    repo = Repository(example / ".rloop")
    try:
        event = dict(repo.db.execute("SELECT * FROM events WHERE kind='prediction'").fetchone())
        payload = json.loads(event["payload"])
        assert payload["value"] == 0.25 and payload["note"] == "My own reasoning"
        assert before <= datetime.fromisoformat(event["created"]) <= datetime.now(timezone.utc)
        verdicts = repo.db.execute("SELECT * FROM events WHERE kind='verdict'").fetchall()
        assert all(row["seq"] > event["seq"] and row["created"] > event["created"] for row in verdicts)
        assert event["created"] in report and any(row["created"] in report for row in verdicts)
        exported = export(repo).read_text(encoding="utf-8")
        assert '"kind":"prediction"' in exported
    finally:
        repo.close()


def test_prediction_refused_after_scoring_even_after_amendment(example):
    asyncio.run(run(example, pilot_only=True))
    result = CliRunner().invoke(app, ["predict", str(example), "--value", "0.1"])
    assert result.exit_code != 0 and "scoring has already started" in result.output
    contract = json.loads((example / "contract.json").read_bytes())
    contract["goal"] = "Amended question"
    (example / "contract.json").write_text(canonical(contract), encoding="utf-8")
    invoke("plan", example, "--reason", "An explicit amendment")
    result = CliRunner().invoke(app, ["predict", str(example), "--value", "0.1"])
    assert result.exit_code != 0 and "scoring has already started" in result.output


def test_prediction_refuses_during_controls_and_after_interrupted_scoring(example):
    repo, _, _ = prepare(example)
    try:
        repo.reserve_control()
        with pytest.raises(IntegrityError, match="scoring has already started"):
            record(repo, 0.1)
        assert not repo.db.execute("SELECT 1 FROM events WHERE kind='prediction'").fetchone()
    finally:
        repo.close()


@pytest.mark.parametrize("value", ["nan", "inf", "-inf"])
def test_prediction_refuses_nonfinite(example, value):
    invoke("plan", example)
    result = CliRunner().invoke(app, ["predict", str(example), "--value", value])
    assert result.exit_code != 0 and "finite number" in result.output


def test_prediction_requires_current_registered_plan(example):
    result = CliRunner().invoke(app, ["predict", str(example), "--value", "0.1"])
    assert result.exit_code != 0 and "rloop plan" in result.output
    invoke("plan", example)
    contract = json.loads((example / "contract.json").read_bytes())
    contract["goal"] = "Another question"
    (example / "contract.json").write_text(canonical(contract), encoding="utf-8")
    result = CliRunner().invoke(app, ["predict", str(example), "--value", "0.1"])
    assert result.exit_code != 0 and "contract changed" in result.output


def test_prediction_stays_bound_to_registration(example):
    invoke("plan", example)
    invoke("predict", example, "--value", "0.3")
    contract = json.loads((example / "contract.json").read_bytes())
    contract["goal"] = "Changed question before scoring"
    (example / "contract.json").write_text(canonical(contract), encoding="utf-8")
    invoke("plan", example, "--reason", "New question")
    asyncio.run(run(example, pilot_only=True))
    output = invoke("report", example)
    assert "unavailable; no matching checked result yet" in output
    result = CliRunner().invoke(app, ["predict", str(example), "--value", "0.1"])
    assert result.exit_code != 0 and "already recorded" in result.output


@pytest.mark.parametrize("mode", ["autonomous", "coached"])
def test_grain_prediction_report_uses_saved_statistics_only(tmp_path, mode):
    """Synthetic ledger records only: no images, manifests or holdout are opened."""
    from research_loops.contracts import GrainContract, GrainWorkerContract
    from research_loops.domain import Workspace
    from research_loops.grain_evaluator import GrainVerdict
    from research_loops.tools import ToolService

    (tmp_path / "project.json").write_text(canonical({"mode": mode}), encoding="utf-8")
    repo = Repository(tmp_path / ".rloop")
    try:
        contract = GrainContract()
        key = repo.register(contract.model_dump(mode="json"), "a" * 64, {})
        assert ("no prediction recorded" in render(repo)) == (mode == "coached")
        record(repo, 0.1)
        task = GrainWorkerContract(run_id="synthetic-grain", registration_hash=key,
            goal=contract.goal, prediction=contract.prediction, seed=7, variant=0, input_hash="b" * 64)
        repo.dispatch(task)
        workspace = Workspace(root=tmp_path / "outbox")
        tools = ToolService(task, workspace.root)
        tools.register_variant(task.prediction)
        repo.import_report(tools.submit_result({}), workspace)
        repo.verdict(task.run_id, GrainVerdict(max_rel_error=0.2,
            median_count_rel_error=0.2, median_size_rel_error=0.15,
            median_count_bias=-0.2, median_size_bias=-0.15,
            n_images=1, n_images_size=1, per_image={}, supported=False))
        text = render(repo)
        assert "Predicted development max_rel_error: 0.1" in text
        assert "Actual development max_rel_error: 0.2" in text
        assert "Difference (actual minus predicted): 0.1" in text
        assert "Prediction recorded before result" in text
        with pytest.raises(IntegrityError, match="already recorded"):
            record(repo, 0.15)
    finally:
        repo.close()


def test_mode_prediction_and_profile_never_reach_workers_or_project_artifacts(example, isolated_home):
    # Only a synthetic sentinel profile is used, outside the project.
    profile = isolated_home / ".competence-profiles" / "research-loops.md"
    profile.parent.mkdir(parents=True)
    sentinel = "private competence evidence never to leave home"
    profile.write_text(sentinel, encoding="utf-8")
    invoke("init", example, "--owner", "Ada", "--mode", "coached")
    invoke("plan", example)
    invoke("predict", example, "--value", "0.314159", "--note", "private headline expectation")

    class Capture(FakeBackend):
        async def run(self, contract, workspace, limits):
            public = canonical(contract)
            assert "mode" not in json.loads(public)
            assert "0.314159" not in public and "private headline expectation" not in public
            assert sentinel not in public and ".competence-profiles" not in public
            launch = local_launch(contract, workspace.root)
            context = (workspace.root.parent / "worker-context.json").read_text(encoding="utf-8")
            assert context == public
            assert "HOME" not in launch.env and "USERPROFILE" not in launch.env
            return await super().run(contract, workspace, limits)

    asyncio.run(run(example, pilot_only=True, backend=Capture()))
    for command in ("status", "report", "export", "self-assess", "resume"):
        invoke(command, example)
    invoke("skills", "list")
    invoke("skills", "show", "rloop-coach")
    invoke("skills", "install", "--target", "agents", "--dry-run")
    assert profile.read_text(encoding="utf-8") == sentinel
    for path in example.rglob("*"):
        if path.is_file():
            assert sentinel.encode() not in path.read_bytes(), path
    profile.unlink()
    invoke("init", example)
    invoke("report", example)
    assert not profile.exists()  # No command restores or creates a profile.


def test_coach_references_links_and_wheel_packaging():
    root = skills.resources()
    path = skills.skill_path("rloop-coach")
    references = {"methods.md", "competence-profile.md", "research-brief-template.md", "method-card-template.md"}
    assert {p.name for p in (path / "references").glob("*.md")} == references
    packaging = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"]
    for document in [path / "SKILL.md", *sorted((path / "references").glob("*.md"))]:
        for target in re.findall(r"\[[^]]+\]\(([^)]+)\)", document.read_text(encoding="utf-8")):
            local = (document.parent / target.split("#")[0]).resolve()
            assert local.is_file(), (document, target)
            relative = local.relative_to(root).as_posix()
            if not relative.startswith("skills/"):
                assert packaging[relative] == "research_loops/" + relative
    output = invoke("skills", "show", "rloop-coach")
    assert "name: rloop-coach" in output and "sha256:" in output
