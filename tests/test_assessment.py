import asyncio
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from research_loops.assessment import assess
from research_loops.cli import app
from research_loops.coordinator import run
from research_loops.domain import WorkerContract
from research_loops.reporting import export, report
from research_loops.storage import Repository


@pytest.fixture
def initialized(tmp_path):
    project = tmp_path / "project space ü"
    result = CliRunner().invoke(app, ["init", str(project)])
    assert result.exit_code == 0, result.output
    return project


def test_fresh_init_assessment_is_offline_deterministic_and_read_only(initialized):
    root = initialized / ".rloop"
    paths = [root / "state.sqlite", root / "report.md", root / "events.jsonl"]
    before = {path: path.read_bytes() for path in paths}
    value = assess(initialized)
    assert value == assess(initialized)
    assert {path: path.read_bytes() for path in paths} == before
    for dimension in ("Problem", "Loop", "Evidence", "Honesty", "Reproducibility", "License review", "Impact review"):
        assert f"## {dimension}\n" in value
    assert "known-answer sanity check" in value
    assert "registration" in value and "event anchor" in value
    assert "controls precede all 2 worker dispatches" in value
    assert "negative=1" in value and "supported=1" in value and "technical_error=0" in value
    assert "every reported verdict has its evidence object" in value
    assert "report --check would pass" in value and "Export prefix: verified" in value
    assert "CC0-1.0" in value
    assert value.endswith("public-ready: needs human review\n")
    assert not (root / "self-assessment.md").exists()
    result = CliRunner().invoke(app, ["self-assess", str(initialized), "--write"])
    assert result.exit_code == 0, result.output
    assert result.output == (root / "self-assessment.md").read_text(encoding="utf-8") == value


@pytest.mark.parametrize("tamper", ["report", "export", "object", "input", "contract", "license", "verdict_object"])
def test_assessment_blocks_drift_integrity_and_license_issues(initialized, tmp_path, tamper):
    root = initialized / ".rloop"
    options = {}
    if tamper == "report":
        (root / "report.md").write_text("unsupported headline", encoding="utf-8")
    elif tamper == "export":
        (root / "events.jsonl").write_text("{}\n", encoding="utf-8")
    elif tamper in {"object", "verdict_object"}:
        repo = Repository(root)
        row = repo.db.execute("SELECT hash FROM artifacts WHERE kind=? LIMIT 1", ("evaluation" if tamper == "verdict_object" else "candidate",)).fetchone()
        repo.close()
        (root / "objects" / row[0]).unlink()
    elif tamper == "input":
        next((root / "private").glob("*/development.json")).write_text("{}", encoding="utf-8")
    elif tamper == "contract":
        payload = json.loads((initialized / "contract.json").read_bytes())
        payload["goal"] = "changed without registration"
        (initialized / "contract.json").write_text(json.dumps(payload), encoding="utf-8")
    elif tamper == "license":
        options["repository_root"] = tmp_path
    value = assess(initialized, **options)
    assert value.endswith("public-ready: no\n")
    assert "Open questions requiring human judgment" in value
    if tamper == "report":
        assert "Report check: FAIL" in value
        assert (root / "report.md").read_text() == "unsupported headline"
        result = CliRunner().invoke(app, ["self-assess", str(initialized)])
        assert result.exit_code == 0 and "public-ready: no" in result.output


def test_failed_runs_and_valid_partial_export_are_visible(initialized):
    repo = Repository(initialized / ".rloop")
    try:
        key = repo.db.execute("SELECT current_registration FROM project").fetchone()[0]
        repo.dispatch(WorkerContract(run_id="failed", registration_hash=key, goal="test", prediction="uncertain",
            seed=7, variant=0, input_hash="a" * 64))
        repo.fail("failed", "technical_error", "test failure")
        report(repo)
        # Existing export is still a valid prefix; assessment never appends to it.
        before = (repo.root / "events.jsonl").read_bytes()
    finally:
        repo.close()
    value = assess(initialized)
    assert "technical_error=1" in value and "unevaluated=1" in value
    assert value.endswith("public-ready: needs human review\n")
    assert (initialized / ".rloop/events.jsonl").read_bytes() == before


def test_final_saved_evidence_recheck(example):
    payload = json.loads((example / "contract.json").read_bytes())
    payload.update(seeds=[7], variants_per_seed=2)
    (example / "contract.json").write_text(json.dumps(payload), encoding="utf-8")
    asyncio.run(run(example))
    asyncio.run(run(example, final=True))
    value = assess(example)
    assert "saved final receipt matches ticket; independent arithmetic re-check passes" in value
    assert value.endswith("public-ready: needs human review\n")


def test_missing_project_is_reported_without_creating_state(tmp_path):
    target = tmp_path / "absent"
    assert assess(target).endswith("public-ready: no\n")
    assert not target.exists()
