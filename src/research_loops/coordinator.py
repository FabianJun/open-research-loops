"""Offline vertical slice; this process is the sole database writer."""

import asyncio
import json
from pathlib import Path

from research_loops.data import datasets
from research_loops.domain import Contract, IntegrityError, WorkerContract, WorkerReport, Workspace, digest
from research_loops.evaluation import SubprocessEvaluator, evaluator_hash
from research_loops.fake import FakeBackend
from research_loops.paths import atomic_write
from research_loops.reporting import export, report
from research_loops.storage import Repository


def load_contract(example: Path) -> Contract:
    return Contract.model_validate_json((example / "contract.json").read_bytes())


def prepare(example: Path) -> tuple[Repository, Contract, str]:
    contract = load_contract(example)
    repo = Repository(example / ".rloop")
    data = datasets(contract)
    inputs = {key: digest(value) for key, value in data.items()}
    key = repo.register(contract.model_dump(mode="json"), evaluator_hash(), inputs)
    for name, value in data.items():
        path = repo.root / "private" / f"{name}.json"
        if not path.exists():
            atomic_write(path, value, exclusive=True)
        elif digest(path.read_bytes()) != inputs[name]:
            raise IntegrityError("registered input modified")
    return repo, contract, key


async def run(example: Path) -> None:
    repo, contract, key = prepare(example)
    try:
        evaluator = SubprocessEvaluator()
        for variant in (0, 1):
            run_id = f"agent-7-{variant:02d}"
            if repo.db.execute("SELECT 1 FROM runs WHERE id=?", (run_id,)).fetchone():
                continue
            assignment = WorkerContract(run_id=run_id, registration_hash=key, goal=contract.goal,
                prediction=contract.prediction, seed=7, variant=variant,
                input_hash=digest((repo.root / "private" / "training.json").read_bytes()))
            repo.dispatch(assignment)
            workspace = Workspace(root=repo.root / "runs" / run_id / "outbox")
            try:
                result = await asyncio.wait_for(FakeBackend().run(assignment, workspace, contract.limits), contract.limits.worker_seconds)
                repo.import_report(result, workspace)
                verdict = evaluator.evaluate(repo.artifact(run_id, "candidate"), (repo.root / "private" / "development.json").read_bytes(), contract.limits.evaluator_seconds)
                repo.verdict(run_id, verdict)
            except Exception as exc:
                repo.fail(run_id, "technical_error", str(exc))
                raise
        report(repo)
        export(repo)
    finally:
        repo.close()
