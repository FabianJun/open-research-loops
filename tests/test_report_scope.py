import pytest

from research_loops.adapters.common import instructions
from research_loops.domain import WorkerContract, digest
from research_loops.reports import WorkerReport
from research_loops.tools import ToolService
from research_loops.transports.protocol import Dispatcher


@pytest.mark.parametrize("submission_name", ["report.json", "submission.json"])
@pytest.mark.parametrize("field, wrong", [
    ("report_id", "assignment-report"), ("run_id", "another-run"), ("contract_hash", "c" * 64),
])
def test_rejected_scope_leaves_session_open_for_corrected_submit(tmp_path, submission_name, field, wrong):
    contract = WorkerContract(run_id="assignment", registration_hash="a" * 64, goal="signal",
        prediction="zero fails", seed=7, variant=0, input_hash="b" * 64)
    service = ToolService(contract, tmp_path / "outbox", submission_name=submission_name)
    dispatcher = Dispatcher(service)
    service.register_variant(contract.prediction)
    candidate = service.write_artifact("candidate.json", b'{"constant":0}')
    transcript = service.write_artifact("transcript.json", b'{}')
    report = WorkerReport(report_id=contract.run_id, run_id=contract.run_id,
        contract_hash=contract.registration_hash, candidate=candidate, transcript=transcript,
        prompt_hash=digest(b"prompt"), seed=7)
    rejected = report.model_copy(update={field: wrong})
    result = dispatcher.call("submit_result", {"report": rejected.model_dump(mode="json")})
    assert result == {"ok": False, "error": "report scope differs from assignment: run_id and report_id must equal the assigned run_id; contract_hash must equal registration_hash"}
    assert not service.sealed()
    assert not (service.root / submission_name).exists()
    assert service.registered
    assert dispatcher.call("submit_result", {"report": report.model_dump(mode="json")})["ok"]
    assert service.sealed()
    assert WorkerReport.model_validate_json((service.root / submission_name).read_bytes()) == report


def test_instructions_explain_report_scope():
    contract = WorkerContract(run_id="assignment", registration_hash="a" * 64, goal="signal",
        prediction="zero fails", seed=7, variant=0, input_hash="b" * 64)
    assert ("report_id and run_id must both be exactly the run_id from the public JSON; "
        "contract_hash must be its registration_hash.") in instructions(contract)
