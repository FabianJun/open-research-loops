"""Offline coordinator: sole writer, frozen inputs, bounded execution and recovery."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from pathlib import Path

from research_loops.data import datasets
from research_loops.domain import Contract, IntegrityError, Verdict, WorkerContract, Workspace, canonical, digest
from research_loops.reports import WorkerReport
from research_loops.evaluation import SubprocessEvaluator, evaluator_hash
from research_loops.fake import FakeBackend, oracle
from research_loops.grounding import public_context
from research_loops.paths import atomic_write
from research_loops.processes import process_identity
from research_loops.reporting import export, report
from research_loops.scheduler import fanout
from research_loops.storage import Repository
from research_loops.authorization import LimitReached
from research_loops.contracts import GrainWorkerContract, is_grain, parse_contract
from research_loops.grain_evaluator import parse_verdict
from research_loops.cancellation import Cancellation, RunCancelled


def load_contract(example: Path) -> Contract:
    return parse_contract((example / "contract.json").read_bytes())


def proposal_method(contract):
    return Path(__file__).with_name("grain_worker.py" if is_grain(contract) else "fake.py")


def data_root(repo, contract, split):
    if not is_grain(contract):
        return None
    return repo.root / "data" / "Grain" / {"training": "train", "development": "val", "final": "test"}[split]


def training_projection(repo, contract, key):
    if not is_grain(contract):
        return private(repo, key, "training")
    data = (repo.root / "inputs" / "training.json").read_bytes()
    inputs = json.loads(repo.db.execute("SELECT inputs FROM registrations WHERE hash=?", (key,)).fetchone()[0])
    if digest(data) != inputs["public_training"]:
        raise IntegrityError("public grain statistics modified")
    return data


def private(repo: Repository, key: str, split: str) -> bytes:
    inputs = json.loads(repo.db.execute("SELECT inputs FROM registrations WHERE hash=?", (key,)).fetchone()[0])
    data = (repo.root / "private" / key / f"{split}.json").read_bytes()
    if digest(data) != inputs[split]:
        raise IntegrityError("registered input modified")
    return data


def prepare(example: Path, *, amendment_reason: str | None = None) -> tuple[Repository, Contract, str]:
    from research_loops.settings import working_mode
    working_mode(example)
    contract = load_contract(example)
    repo = Repository(example / ".rloop")
    try:
        method_hash = digest(proposal_method(contract).read_bytes())
        current = repo.db.execute("SELECT current_registration FROM project").fetchone()[0]
        if current:
            previous = repo.db.execute("SELECT * FROM registrations WHERE hash=?", (current,)).fetchone()
            if previous["evaluator_hash"] != evaluator_hash(contract.name):
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
        if is_grain(contract):
            try:
                data = {name: (repo.root / "data" / f"{split}.json").read_bytes()
                    for name, split in (("training", "train"), ("development", "val"), ("final", "test"))}
            except FileNotFoundError:
                raise IntegrityError("grain data missing; run rloop data fetch PROJECT --archive PATH") from None
        else:
            data = datasets(contract)
        inputs = {name: digest(value) for name, value in data.items()}
        if is_grain(contract):
            inputs["public_training"] = digest((repo.root / "inputs" / "training.json").read_bytes())
        inputs["proposal_method"] = method_hash
        key = repo.register(contract.model_dump(mode="json"), evaluator_hash(contract.name), inputs, supersedes=current, reason=amendment_reason)
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


def evaluate_saved(root: Path, run_id: str, candidate: bytes, dataset: bytes, seconds: float, *, data_root=None) -> Verdict:
    # All inputs are captured by the coordinator: evaluator threads get no DB handle.
    receipt = root / "evaluation_receipts" / f"{run_id}.json"
    if receipt.exists():
        value = json.loads(receipt.read_bytes())
        if value["state"] == "completed":
            return parse_verdict(value["verdict"])
        if value["state"] == "intent":
            raise IntegrityError("unresolved evaluator launch intent; automatic replay blocked")
        if process_identity(value["pid"]) == value["creation"]:
            raise IntegrityError("prior evaluator is still alive; recovery blocked")
        raise IntegrityError("interrupted evaluator; explicit new attempt required")
    atomic_write(receipt, canonical({"state": "intent"}).encode(), exclusive=True)
    def started(identity):
        atomic_write(receipt, canonical({"state": "running", **identity}).encode())
    verdict = SubprocessEvaluator().evaluate(candidate, dataset, seconds, started=started, data_root=data_root)
    atomic_write(receipt, canonical({"state": "completed", "verdict": verdict.model_dump(mode="json")}).encode())
    return verdict


def reconcile(repo: Repository, contract: Contract, key: str, cancellation=None) -> None:
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
            repo.final_result(ticket, parse_verdict(saved["verdict"]))
    for row in repo.runs():
        if cancellation:
            cancellation.check()
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
        if cancellation:
            cancellation.check()
        verdict = evaluate_saved(repo.root, row["id"], repo.artifact(row["id"], "candidate"), private(repo, key, "development"), contract.limits.evaluator_seconds, data_root=data_root(repo, contract, "development"))
        repo.verdict(row["id"], verdict)
        repo.promote_claim(row["id"])


async def run(example: Path, *, final: bool = False, resume_only: bool = False, pilot_only: bool = False, worker_runs: int | None = None, backend=None) -> None:
    if backend is not None and hasattr(backend, "check_authorization"):
        backend.check_authorization()
    repo, contract, key = prepare(example)
    job_id = uuid.uuid4().hex
    cancellation = Cancellation(repo.root, job_id)
    job_status = "completed"
    try:
        with repo.db:
            repo.event("job_started", job_id, {})
        cancellation.check()
        reconcile(repo, contract, key, cancellation)
        cancellation.check()
        if final:
            final_evaluation(repo, contract, key, cancellation)
        elif not resume_only:
            if repo.db.execute("SELECT final_ticket FROM project").fetchone()[0]:
                raise IntegrityError("campaign sealed; no more worker dispatch")
            task = asyncio.create_task(campaign(repo, contract, key, backend or FakeBackend(),
                pilot_only=pilot_only, worker_runs=worker_runs, cancellation=cancellation))
            try:
                while not task.done():
                    await asyncio.wait({task}, timeout=0.05)
                    cancellation.check()
                await task
            finally:
                if not task.done():
                    task.cancel()
                # Await worker cleanup and any evaluator that already started.
                # A cancelled thread await must not close the ledger underneath it.
                try:
                    await task
                except (asyncio.CancelledError, RunCancelled):
                    pass
    except RunCancelled:
        job_status = "cancelled"
        for row in repo.runs():
            if row["execution_status"] == "running":
                repo.fail(row["id"], "cancelled", "job cancellation requested")
    except asyncio.CancelledError:
        job_status = "cancelled"
        raise
    except BaseException:
        job_status = "technical_error"
        raise
    finally:
        try:
            with repo.db:
                repo.event("job_finished", job_id, {"execution_status": job_status})
            report(repo)
            export(repo)
        finally:
            repo.close()


async def campaign(repo: Repository, contract: Contract, key: str, backend, *, pilot_only: bool = False, worker_runs: int | None = None, cancellation=None) -> None:
    def check_cancel():
        if cancellation:
            cancellation.check()
    check_cancel()
    if is_grain(contract) and type(backend) is FakeBackend:
        from research_loops.grain_worker import GrainFakeBackend
        backend = GrainFakeBackend()
    approval = backend.check_authorization() if hasattr(backend, "check_authorization") else None
    limits = contract.limits
    if approval:
        if any(row["execution_status"] == "limit_reached"
                and json.loads(row["execution_metadata"]).get("provider") == approval.provider for row in repo.runs()):
            raise LimitReached("pilot previously reached a provider/run limit; owner review required")
        limits = limits.model_copy(update={
            "concurrency": min(limits.concurrency, approval.run_limits.max_parallel_workers),
            "worker_seconds": min(limits.worker_seconds, approval.run_limits.max_wall_seconds_per_worker)})
        requested = worker_runs or (2 if pilot_only else len(contract.seeds) * contract.variants_per_seed * 2)
        if requested > approval.run_limits.max_worker_runs:
            raise LimitReached("requested worker runs exceed checkpoint B allowance")
    stopped = False
    technical_failure = False
    deadline_failure = False
    if is_grain(contract) and not repo.db.execute("SELECT pilot FROM project").fetchone()[0]:
        from research_loops.grain_worker import controls
        controls(repo, contract, key)
        check_cancel()
    if not repo.db.execute("SELECT pilot FROM project").fetchone()[0]:
        evaluator = SubprocessEvaluator()
        dev = private(repo, key, "development")
        repo.reserve_control()
        positive = evaluator.evaluate(canonical(oracle()).encode(), dev, contract.limits.evaluator_seconds)
        check_cancel()
        repo.reserve_control()
        negative = evaluator.evaluate(b'{"constant":0}', dev, contract.limits.evaluator_seconds)
        check_cancel()
        rows = json.loads(dev)["rows"]
        repo.pilot({"positive_control": positive.supported, "negative_control": not negative.supported,
            "nonconstant": len({row["y"] for row in rows}) > 1, "baseline": positive.baseline_mse > 0})
    repo.require_pilot()
    suffix = "" if getattr(backend, "name", "fake") == "fake" else "-" + backend.name
    assignment_class = GrainWorkerContract if is_grain(contract) else WorkerContract
    assignments = [assignment_class(run_id=f"{key[:8]}-{arm}-{seed}-{variant:02d}{suffix}", registration_hash=key,
        goal=contract.goal, prediction=contract.prediction, seed=seed, variant=variant, arm=arm,
        input_hash=digest(training_projection(repo, contract, key)))
        for arm in ("agent", "random") for seed in contract.seeds for variant in range(contract.variants_per_seed)]
    existing = {row["id"] for row in repo.runs()}
    if pilot_only:
        assignments = assignments[:2]
    if worker_runs is not None:
        if not 1 <= worker_runs <= len(assignments):
            raise IntegrityError("worker runs exceed registered assignments")
        assignments = assignments[:worker_runs]

    async def execute(assignment):
        nonlocal stopped, technical_failure, deadline_failure
        check_cancel()
        if stopped:
            raise LimitReached("pilot stopped after provider limit")
        public_context(assignment.model_dump(mode="json"))
        from research_loops.execution import backend_record
        metadata, reserve = backend_record(backend)
        repo.dispatch(assignment, reserve, execution_metadata=metadata)
        root = repo.root / "runs" / assignment.run_id / "outbox"
        try:
            public = root.parent / "public"
            public.mkdir(mode=0o755, parents=True, exist_ok=True)
            data = training_projection(repo, contract, key)
            training = public / "training.json"
            if training.exists():
                if training.read_bytes() != data:
                    raise IntegrityError("public training projection changed")
            else:
                atomic_write(training, data, exclusive=True)
            training.chmod(0o644)
            if is_grain(contract):
                from research_loops.grain_worker import prepare_training_tool
                prepare_training_tool(repo, contract, key, root.parent)
            deadline = repo.db.execute("SELECT deadline FROM project").fetchone()[0]
            remaining = max(0.001, deadline - time.time())
            result = await asyncio.wait_for(backend.run(assignment, Workspace(root=root), limits), min(remaining, limits.worker_seconds))
            check_cancel()
            repo.import_report(result, Workspace(root=root))
            check_cancel()
            remaining = max(0.001, deadline - time.time())
            candidate, dataset = repo.artifact(assignment.run_id, "candidate"), private(repo, key, "development")
            evaluation = asyncio.create_task(asyncio.to_thread(evaluate_saved, repo.root, assignment.run_id, candidate, dataset, min(remaining, contract.limits.evaluator_seconds), data_root=data_root(repo, contract, "development")))
            try:
                verdict = await asyncio.shield(evaluation)
            except asyncio.CancelledError:
                await evaluation
                raise
            repo.verdict(assignment.run_id, verdict)
            repo.promote_claim(assignment.run_id)
        except LimitReached:
            stopped = True
            repo.fail(assignment.run_id, "limit_reached", "provider or worker allowance reached; no retry or fallback")
            raise
        except asyncio.TimeoutError:
            deadline_failure = True
            if approval:
                stopped = True
                repo.fail(assignment.run_id, "limit_reached", "worker/project wall-time allowance reached")
                raise LimitReached("worker/project wall-time allowance reached") from None
            repo.fail(assignment.run_id, "timed_out", "worker deadline")
            raise
        except RunCancelled:
            repo.fail(assignment.run_id, "cancelled", "job cancellation requested")
            raise
        except asyncio.CancelledError:
            if technical_failure:
                repo.fail(assignment.run_id, "cancelled", "batch cancelled after a sibling run failed")
            else:
                repo.fail(assignment.run_id, "timed_out" if deadline_failure else "cancelled", "worker deadline" if deadline_failure else "job cancellation requested" if cancellation and cancellation.requested() else "batch cancellation")
            raise
        except Exception as exc:
            technical_failure = True
            if isinstance(exc, IntegrityError):
                reason = f"IntegrityError: {exc}"[:300]
            elif approval:
                reason = f"{type(exc).__name__}: SDK failure (details suppressed)"
            else:
                reason = f"{type(exc).__name__}: {exc}"
            repo.fail(assignment.run_id, "technical_error", reason)
            raise
    pending = [item for item in assignments if item.run_id not in existing]
    if pending:
        try:
            await fanout("best_of_n", pending, execute, limits.concurrency, pilot_ready=True)
        except* LimitReached:
            raise LimitReached("pilot stopped at a run/provider limit; review saved report") from None
        except* RunCancelled:
            raise RunCancelled() from None
    check_cancel()
    if not pilot_only and worker_runs is None:
        from research_loops.selection import select
        select(repo, contract, key)


def final_evaluation(repo: Repository, contract: Contract, key: str, cancellation=None) -> None:
    from research_loops.selection import select
    selection = select(repo, contract, key)
    if cancellation:
        cancellation.check()
    ticket = repo.consume_final(selection["winner"])
    deadline = repo.db.execute("SELECT deadline FROM project").fetchone()[0]
    seconds = min(contract.limits.evaluator_seconds, max(0.001, deadline - time.time()))
    verdict = SubprocessEvaluator().evaluate(repo.artifact(ticket["run_id"], "candidate"), private(repo, key, "final"), seconds, data_root=data_root(repo, contract, "final"))
    atomic_write(repo.root / "private" / "final-receipt.json", canonical({"ticket": ticket, "verdict": verdict.model_dump(mode="json")}).encode(), exclusive=True)
    repo.final_result(ticket, verdict)
