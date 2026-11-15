"""One pre-run numerical prediction in the existing coordinator event ledger."""

import json
import math

from research_loops.domain import IntegrityError
from research_loops.settings import working_mode
from research_loops.storage import Repository


def record(repo: Repository, value: float, note: str | None = None) -> None:
    if not math.isfinite(value):
        raise IntegrityError("prediction must be a finite number")
    with repo.db:
        state = repo.db.execute("SELECT * FROM project").fetchone()
        if not state["current_registration"]:
            raise IntegrityError("register the contract with rloop plan before predicting")
        if repo.db.execute("SELECT 1 FROM events WHERE kind='prediction'").fetchone():
            raise IntegrityError("a prediction is already recorded for this project")
        # Refuse during scoring too: an interrupted evaluation must not let someone
        # see a score and then backfill a prediction before reconciliation.
        if (state["control_attempts"] or state["final_ticket"]
                or repo.db.execute("SELECT 1 FROM runs WHERE verdict IS NOT NULL").fetchone()
                or any((repo.root / "evaluation_receipts").glob("*.json"))):
            raise IntegrityError("prediction refused: scoring has already started")
        contract = json.loads(repo.db.execute("SELECT payload FROM registrations WHERE hash=?",
            (state["current_registration"],)).fetchone()[0])
        repo.event("prediction", "project", {"value": value, "note": note,
            "registration_hash": state["current_registration"],
            "metric": "max_rel_error" if contract["name"] == "grain-316l" else "mse",
            "scope": "best checked development result; lower is better"})


def section(repo: Repository) -> list[str]:
    saved = repo.db.execute("SELECT * FROM events WHERE kind='prediction' ORDER BY seq").fetchall()
    if not saved:
        return (["", "## Prediction vs result", "", "no prediction recorded"]
            if working_mode(repo.root.parent) == "coached" else [])
    if len(saved) != 1:
        raise IntegrityError("multiple project predictions in ledger")
    event = saved[0]
    prediction = json.loads(event["payload"])
    metric = prediction["metric"]
    candidates = [(json.loads(row["verdict"])[metric], row["id"])
        for row in repo.runs() if row["registration_hash"] == prediction["registration_hash"]
        and row["verdict"] and row["verification_status"] == "checked"
        and row["execution_status"] == "completed"]
    lines = ["", "## Prediction vs result", "",
        f"[hypothesis] Predicted development {metric}: {prediction['value']:.12g}; recorded {event['created']} (UTC).",
        "[assumed] Scope: best checked development result under registration "
        + prediction["registration_hash"] + "; lower is better. This is not the final holdout score."]
    if not candidates:
        return lines + ["[measured] Actual value, difference and result timestamp: unavailable; no matching checked result yet."]
    actual, run_id = min(candidates)
    result = repo.db.execute("SELECT * FROM events WHERE kind='verdict' AND record_id=? ORDER BY seq LIMIT 1", (run_id,)).fetchone()
    if not result or result["seq"] <= event["seq"] or result["created"] < event["created"]:
        raise IntegrityError("prediction must precede the scored result")
    return lines + [f"[measured] Actual development {metric}: {actual:.12g} ({run_id}); scored {result['created']} (UTC).",
        f"[measured] Difference (actual minus predicted): {actual - prediction['value']:.12g}.",
        "[measured] Prediction recorded before result (timestamps and ledger order)."]
