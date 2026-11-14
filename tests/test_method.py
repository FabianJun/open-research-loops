import json
from pathlib import Path

import pytest

from research_loops.coordinator import prepare
from research_loops.data import datasets
from research_loops.domain import Contract, IntegrityError
from research_loops.evaluator_worker import evaluate
from research_loops.fake import oracle
from research_loops.ideas import Idea, ideation, literature
from research_loops.licensing import license_issues
from research_loops.verification import check


def test_independent_verifier_catches_plausible_but_wrong_outputs():
    request = json.loads(datasets(Contract(goal="test", falsifier="test", prediction="test"))["development"])
    request["candidate"] = oracle()
    verdict = evaluate(request)
    check(request, verdict)
    with pytest.raises(IntegrityError, match="verifier"):
        check(request, verdict.model_copy(update={"predictions": tuple(0 for _ in verdict.predictions)}))


def test_splits_are_disjoint_tuples_and_not_constant():
    data = datasets(Contract(goal="test", falsifier="test", prediction="test"))
    tuples = {key: {tuple(row["x"]) for row in json.loads(value)["rows"]} for key, value in data.items()}
    assert [len(tuples[name]) for name in ("training", "development", "final")] == [64, 64, 128]
    assert not (tuples["training"] & tuples["development"] or tuples["training"] & tuples["final"] or tuples["development"] & tuples["final"])


def test_ideas_rank_and_die_on_paper_and_retrieval_fails_loudly(example):
    repo, _, _ = prepare(example)
    try:
        kept = ideation(repo, [Idea(id="a", hypothesis="expensive", rank=10, reason="too expensive"), Idea(id="b", hypothesis="cheap", rank=90, reason="cheap informative check")], 1)
        assert [p.id for p in kept] == ["b"]
        assert "killed_on_paper" in repo.db.execute("SELECT payload FROM events WHERE kind='idea' AND record_id='a'").fetchone()[0]
        with pytest.raises(IntegrityError, match="memory"):
            literature(repo, "missing", url="https://example.invalid", license="unknown", error="offline")
        assert repo.db.execute("SELECT count(*) FROM events WHERE kind='retrieval_failed'").fetchone()[0] == 1
        literature(repo, "known", url="https://example.invalid/source", license="CC0-1.0", source=b"Saved exact evidence.", quotation="exact evidence")
    finally:
        repo.close()


def test_license_metadata_and_repository_check(tmp_path):
    root = Path(__file__).parents[1]
    assert license_issues(root, ["CC0-1.0"]) == []
    assert license_issues(root, ["unknown"])
    assert len(license_issues(tmp_path, [])) == 2
