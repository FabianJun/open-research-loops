import inspect
import json

import pytest

from research_loops.adapters.common import instructions
from research_loops.candidate_schema import CANDIDATE_GRAMMAR, validate_submission
from research_loops.domain import IntegrityError, canonical, digest, validate_candidate
from research_loops.reports import WorkerReport
from research_loops.tools import ToolService
from research_loops.transports.protocol import Dispatcher
from test_mcp import task


@pytest.mark.parametrize("submission_name", ["report.json", "submission.json"])
def test_host_fills_scope_and_rejected_tree_leaves_session_open(tmp_path, submission_name):
    contract = task()
    service = ToolService(contract, tmp_path / "outbox", submission_name=submission_name)
    dispatcher = Dispatcher(service)
    service.register_variant(contract.prediction)
    invalid = {"op": "add", "args": [{"constant": 2}, {"feature": 0}]}
    result = dispatcher.call("submit_result", {"candidate": invalid})
    assert result == {"ok": False, "error": "candidate node keys must be exactly feature, constant, or op/left/right; replace args with left and right"}
    assert not service.sealed()
    assert not (service.root / "candidate.json").exists()
    assert not (service.root / "transcript.json").exists()
    assert service.registered
    # Scope cannot be supplied or overridden through the tool.
    assert not dispatcher.call("submit_result", {"candidate": {"constant": 0}, "report_id": "forged"})["ok"]
    assert dispatcher.call("submit_result", {"candidate": {"constant": 0}})["ok"]
    report = WorkerReport.model_validate_json((service.root / submission_name).read_bytes())
    assert report.report_id == report.run_id == contract.run_id
    assert report.contract_hash == contract.registration_hash
    assert report.seed == contract.seed
    assert report.prompt_hash == digest(canonical(contract).encode())
    assert json.loads((service.root / "candidate.json").read_bytes()) == {"constant": 0}
    assert json.loads((service.root / "transcript.json").read_bytes()) == {"prompt": canonical(contract), "response": {"constant": 0}}


def test_instructions_and_diagnostics_are_locked_to_anchored_grammar():
    # Any validator change requires reviewing the public grammar and diagnostics.
    assert digest(inspect.getsource(validate_candidate).encode()) == "06df3882754b9e36833f2ce37d7b31a48c7c5315bef172398be31a32638b9560"
    assert CANDIDATE_GRAMMAR == (
        'Each node is exactly one of: {"op":"add"|"sub"|"mul","left":node,"right":node}, '
        '{"feature":integer 0..3}, or {"constant":integer -10..10}. '
        'No extra keys; booleans are not integers. Maximum depth is 4 (root depth 0); '
        'maximum total nodes is 31. Example: '
        '{"op":"mul","left":{"constant":2},"right":{"feature":0}}.'
    )
    text = instructions(task())
    assert CANDIDATE_GRAMMAR in text
    # Public context still contains scope; instructions must never request it.
    directions = text.split("Public JSON: ")[0]
    for name in ("report_id", "run_id", "contract_hash", "prompt_hash", "registration_hash"):
        assert name not in directions
    assert "write candidate.json" not in directions
    assert "submit_result(candidate)" in directions


def full_tree(depth):
    return {"op": "add", "left": full_tree(depth - 1), "right": full_tree(depth - 1)} if depth else {"constant": 0}


@pytest.mark.parametrize("candidate", [
    *({"constant": n} for n in range(-10, 11)),
    *({"feature": n} for n in range(4)), full_tree(4),
    *({"op": op, "left": {"constant": 2}, "right": {"feature": 0}} for op in ("add", "sub", "mul")),
])
def test_documented_grammar_accepts_evaluator_nodes(candidate):
    validate_candidate(candidate)
    validate_submission(candidate)


@pytest.mark.parametrize("candidate,rule", [
    ({"feature": -1}, "feature must be an integer in 0..3"),
    ({"feature": 4}, "feature must be an integer in 0..3"),
    ({"feature": True}, "not a boolean"),
    ({"constant": -11}, "constant must be an integer in -10..10"),
    ({"constant": 11}, "constant must be an integer in -10..10"),
    ({"constant": 2.0}, "constant must be an integer"),
    ({"constant": False}, "not a boolean"),
    ({"op": "div", "left": {"constant": 1}, "right": {"constant": 1}}, "op must be add, sub, or mul"),
    ({"op": "add", "args": []}, "replace args with left and right"),
    ({"constant": 0, "extra": "PRIVATE"}, "keys must be exactly"),
    (["add", 2, "x0"], "must be a JSON object"),
    (full_tree(5), "depth must be at most 4"),
])
def test_rule_errors_are_constant_and_match_evaluator_rejections(candidate, rule):
    with pytest.raises(IntegrityError):
        validate_candidate(candidate)
    with pytest.raises(IntegrityError, match=rule) as caught:
        validate_submission(candidate)
    assert "PRIVATE" not in str(caught.value)
