"""Offline coordinator: sole writer, frozen inputs, bounded execution and recovery."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

from research_loops.data import datasets
from research_loops.domain import Contract, IntegrityError, Verdict, WorkerContract, WorkerReport, Workspace, canonical, digest
from research_loops.evaluation import SubprocessEvaluator, evaluator_hash
from research_loops.fake import FakeBackend, oracle
from research_loops.grounding import public_context
from research_loops.paths import atomic_write
from research_loops.processes import process_identity
from research_loops.reporting import export, report
from research_loops.scheduler import fanout
from research_loops.storage import Repository


def load_contract(example: Path) -> Contract:
    return Contract.model_validate_json((example / "contract.json").read_bytes())


def private(repo: Repository, key: str, split: str) -> bytes:
    inputs = json.loads(repo.db.execute("SELECT inputs FROM registrations WHERE hash=?", (key,)).fetchone()[0])
    data = (repo.root / "private" / key / f"{split}.json").read_bytes()
    if digest(data) != inputs[split]:
        raise IntegrityError("registered input modified")
    return data


def prepare(example: Path, *, amendment_reason: str | None = None) -> tuple[Repository, Contract, str]:
    contract = load_contract(example)
    repo = Repository(example / ".rloop")
    try:
        method_hash = digest(Path(__file__).with_name("fake.py").read_bytes())
        current = repo.db.execute("SELECT current_registration FROM project").fetchone()[0]
        if current:
            previous = repo.db.execute("SELECT * FROM registrations WHERE hash=?", (current,)).fetchone()
            if previous["evaluator_hash"] != evaluator_hash():
                raise IntegrityError("protected evaluator changed; a trusted human evaluator decision is required")
            same_method = json.loads(previous["inputs"]).get("proposal_method") == method_hash
            if previous["payload"] == canonical(contract) and same_method:
                # Ordinary run/resume does not even open or regenerate the final labels.
                private(repo, current, "training")
                private(repo, current, "development")
                return repo, contract, current
            if not amendment_reason:
                raise IntegrityError("registration changed; explicitly plan an amendment with a reason")
            if repo.db.execute("SELECT final_ticket FROM project").fetchone()[0]:
                raise IntegrityError("sealed campaign cannot amend registration")
        data = datasets(contract)
        inputs = {name: digest(value) for name, value in data.items()}
        inputs["proposal_method"] = method_hash
        key = repo.register(contract.model_dump(mode="json"), evaluator_hash(), inputs, supersedes=current, reason=amendment_reason)
        for name, value in data.items():
            path = repo.root / "private" / key / f"{name}.json"
            if not path.exists():
                atomic_write(path, value, exclusive=True)
            elif digest(path.read_bytes()) != inputs[name]:
                raise IntegrityError("registered input modified")
        return repo, contract, key
    except BaseException:
        repo.close()
        raise


def evaluate_saved(root: Path, run_id: str, candidate: bytes, dataset: bytes, seconds: float) -> Verdict:
    # All inputs are captured by the coordinator: evaluator threads get no DB handle.
    receipt = root / "evaluation_receipts" / f"{run_id}.json"
    if receipt.exists():
        value = json.loads(receipt.read_bytes())
        if value["state"] == "completed":
            return Verdict.model_validate(value["verdict"])
        if value["state"] == "intent":
            raise IntegrityError("unresolved evaluator launch intent; automatic replay blocked")
        if process_identity(value["pid"]) == value["creation"]:
            raise IntegrityError("prior evaluator is still alive; recovery blocked")
        raise IntegrityError("interrupted evaluator; explicit new attempt required")
    atomic_write(receipt, canonical({"state": "intent"}).encode(), exclusive=True)
    def started(identity):
        atomic_write(receipt, canonical({"state": "running", **identity}).encode())
    verdict = SubprocessEvaluator().evaluate(candidate, dataset, seconds, started=started)
    atomic_write(receipt, canonical({"state": "completed", "verdict": verdict.model_dump(mode="json")}).encode())
    return verdict


def reconcile(repo: Repository, contract: Contract, key: str) -> None:
    # The project lock proves the previous in-process fake workers are gone.
    # An evaluator can outlive its parent on Linux; check creation identity first.
    ticket_text = repo.db.execute("SELECT final_ticket FROM project").fetchone()[0]
    final_receipt = repo.root / "private" / "final-receipt.json"
    if ticket_text and final_receipt.exists():
        ticket = json.loads(ticket_text)
        if ticket["state"] == "started":
            saved = json.loads(final_receipt.read_bytes())
            if saved["ticket"] != ticket:
                raise IntegrityError("final recovery receipt differs from consumed ticket")
            repo.final_result(ticket, Verdict.model_validate(saved["verdict"]))
    for row in repo.runs():
        if row["execution_status"] != "running":
            continue
        if row["registration_hash"] != key:
            repo.fail(row["id"], "interrupted", "registration superseded; comparison flagged")
            continue
        root = repo.root / "runs" / row["id"] / "outbox"
        sealed = root / "report.json"
        if not row["report_hash"] and sealed.exists():
            repo.import_report(WorkerReport.model_validate_json(sealed.read_bytes()), Workspace(root=root))
        elif not row["report_hash"]:
            journal = root / "journal.jsonl"
            if journal.exists():
                with repo.db:
                    repo.event("partial_outbox", row["id"], {"journal_hash": digest(journal.read_bytes()), "text": journal.read_text(encoding="utf-8")})
            repo.fail(row["id"], "interrupted", "worker died before sealing a report")
            continue
        receipt = repo.root / "evaluation_receipts" / f"{row['id']}.json"
        if receipt.exists():
            value = json.loads(receipt.read_bytes())
            if value["state"] == "intent":
                raise IntegrityError("unresolved launch intent; recovery blocked")
            if value["state"] == "running":
                if process_identity(value["pid"]) == value["creation"]:
                    raise IntegrityError("prior evaluator is still alive; recovery blocked")
                repo.fail(row["id"], "interrupted", "evaluator died without a sealed receipt")
                continue
        verdict = evaluate_saved(repo.root, row["id"], repo.artifact(row["id"], "candidate"), private(repo, key, "development"), contract.limits.evaluator_seconds)
        repo.verdict(row["id"], verdict)
        repo.promote_claim(row["id"])


async def run(example: Path, *, final: bool = False, resume_only: bool = False, backend=None) -> None:
    repo, contract, key = prepare(example)
    try:
        reconcile(repo, contract, key)
        if final:
            final_evaluation(repo, contract, key)
        elif not resume_only:
            if repo.db.execute("SELECT final_ticket FROM project").fetchone()[0]:
                raise IntegrityError("campaign sealed; no more worker dispatch")
            await campaign(repo, contract, key, backend or FakeBackend())
    finally:
        try:
            report(repo)
            export(repo)
        finally:
            repo.close()


async def campaign(repo: Repository, contract: Contract, key: str, backend) -> None:
    if not repo.db.execute("SELECT pilot FROM project").fetchone()[0]:
        evaluator = SubprocessEvaluator()
        dev = private(repo, key, "development")
        repo.reserve_control()
        positive = evaluator.evaluate(canonical(oracle()).encode(), dev, contract.limits.evaluator_seconds)
        repo.reserve_control()
        negative = evaluator.evaluate(b'{"constant":0}', dev, contract.limits.evaluator_seconds)
        rows = json.loads(dev)["rows"]
        repo.pilot({"positive_control": positive.supported, "negative_control": not negative.supported,
            "nonconstant": len({row["y"] for row in rows}) > 1, "baseline": positive.baseline_mse > 0})
    repo.require_pilot()
    assignments = [WorkerContract(run_id=f"{key[:8]}-{arm}-{seed}-{variant:02d}", registration_hash=key,
        goal=contract.goal, prediction=contract.prediction, seed=seed, variant=variant, arm=arm,
        input_hash=digest(private(repo, key, "training")))
        for arm in ("agent", "random") for seed in contract.seeds for variant in range(contract.variants_per_seed)]
    existing = {row["id"] for row in repo.runs()}

    async def execute(assignment):
        public_context(assignment.model_dump(mode="json"))
        repo.dispatch(assignment)
        root = repo.root / "runs" / assignment.run_id / "outbox"
        try:
            deadline = repo.db.execute("SELECT deadline FROM project").fetchone()[0]
            remaining = max(0.001, deadline - time.time())
            result = await asyncio.wait_for(backend.run(assignment, Workspace(root=root), contract.limits), min(remaining, contract.limits.worker_seconds))
            repo.import_report(result, Workspace(root=root))
            remaining = max(0.001, deadline - time.time())
            candidate, dataset = repo.artifact(assignment.run_id, "candidate"), private(repo, key, "development")
            verdict = await asyncio.to_thread(evaluate_saved, repo.root, assignment.run_id, candidate, dataset, min(remaining, contract.limits.evaluator_seconds))
            repo.verdict(assignment.run_id, verdict)
            repo.promote_claim(assignment.run_id)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            repo.fail(assignment.run_id, "timed_out", "worker deadline or batch cancellation")
            raise
        except Exception as exc:
            repo.fail(assignment.run_id, "technical_error", f"{type(exc).__name__}: {exc}")
            raise
    pending = [item for item in assignments if item.run_id not in existing]
    if pending:
        await fanout("best_of_n", pending, execute, contract.limits.concurrency, pilot_ready=True)
    from research_loops.selection import select
    select(repo, contract, key)


def final_evaluation(repo: Repository, contract: Contract, key: str) -> None:
    from research_loops.selection import select
    selection = select(repo, contract, key)
    ticket = repo.consume_final(selection["winner"])
    deadline = repo.db.execute("SELECT deadline FROM project").fetchone()[0]
    seconds = min(contract.limits.evaluator_seconds, max(0.001, deadline - time.time()))
    verdict = SubprocessEvaluator().evaluate(repo.artifact(ticket["run_id"], "candidate"), private(repo, key, "final"), seconds)
    atomic_write(repo.root / "private" / "final-receipt.json", canonical({"ticket": ticket, "verdict": verdict.model_dump(mode="json")}).encode(), exclusive=True)
    repo.final_result(ticket, verdict)
