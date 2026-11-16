"""Allowlisted machine projections; no settings, worker text or raw evaluations."""

import json

from research_loops.cancellation import Cancellation, active_job
from research_loops.reporting import run_summaries


def status(repo) -> dict:
    runs = run_summaries(repo)
    job = active_job(repo)
    state = repo.db.execute("SELECT current_registration,final_ticket FROM project").fetchone()
    last = repo.db.execute("SELECT payload FROM events WHERE kind='job_finished' ORDER BY seq DESC LIMIT 1").fetchone()
    project_state = ("running" if job or any(row["execution_status"] == "running" for row in runs)
        else "sealed" if state["final_ticket"] else json.loads(last[0])["execution_status"] if last
        else "completed" if runs else "ready" if state["current_registration"] else "unregistered")
    paths = {kind: f".rloop/report.{suffix}" for kind, suffix in (("markdown", "md"), ("html", "html"))
        if (repo.root / f"report.{suffix}").is_file()}
    return {"schema": "rloop.status/1", "project_state": project_state,
        "cancel_requested": bool(job and Cancellation(repo.root, job).requested()),
        "runs": [{key: row[key] for key in ("id", "execution_status", "scientific_outcome", "started_at", "finished_at", "prediction_registered")}
            | {"report_paths": paths or None} for row in runs]}


def report(repo) -> dict:
    summary = status(repo)
    runs = run_summaries(repo)
    if not any(row["execution_status"] != "running" for row in runs):
        return {"schema": "rloop.report/1", "error": {"code": "not_ready", "message": "No finished run exists yet."}}
    state = repo.db.execute("SELECT control_attempts,spent_micro_usd,reserved_micro_usd,selection FROM project").fetchone()
    selection = json.loads(state["selection"]) if state["selection"] else None
    return {"schema": "rloop.report/1", "project_state": summary["project_state"],
        "cancel_requested": summary["cancel_requested"], "runs": runs,
        "attempted_variants": len(runs), "control_final_evaluation_starts": state["control_attempts"],
        "spent_micro_usd": state["spent_micro_usd"], "reserved_micro_usd": state["reserved_micro_usd"],
        "selected_run_id": selection["winner"] if selection else None}
