"""Database-derived, deterministic report and append-only review export."""

import html
import json
from pathlib import Path

from research_loops.domain import IntegrityError, canonical, content_hash
from research_loops.grounding import number
from research_loops.paths import atomic_write, long_path, plain_io_errors
from research_loops.storage import Repository


def run_summaries(repo) -> list[dict]:
    """Facts shared by the Markdown run table and the machine report."""
    predictions = {json.loads(row[0])["registration_hash"] for row in
        repo.db.execute("SELECT payload FROM events WHERE kind='prediction'")}
    finished = {row["record_id"]: row["created"] for row in repo.db.execute(
        "SELECT record_id,created FROM events WHERE kind IN "
        "('verdict','technical_error','timed_out','interrupted','cancelled','limit_reached') ORDER BY seq")}
    summaries = []
    for row in repo.runs():
        verdict = json.loads(row["verdict"]) if row["verdict"] else {}
        metric = "max_rel_error" if "max_rel_error" in verdict else "mse"
        summaries.append({"id": row["id"], "execution_status": row["execution_status"],
            "scientific_outcome": row["scientific_outcome"], "verification_status": row["verification_status"],
            "started_at": row["created"], "finished_at": finished.get(row["id"]),
            "prediction_registered": row["registration_hash"] in predictions,
            "backend": json.loads(row["execution_metadata"])["backend"],
            "development_metrics": {name: verdict[name] for name in
                (metric, "median_count_rel_error", "median_size_rel_error") if name in verdict}})
    return summaries


def render(repo: Repository) -> str:
    from research_loops.prediction import section
    from research_loops.settings import working_mode
    working_mode(repo.root.parent)
    registration = repo.db.execute("SELECT payload FROM registrations WHERE hash=(SELECT current_registration FROM project)").fetchone()
    if registration and json.loads(registration[0]).get("name") == "grain-316l":
        from research_loops.grain_reporting import render as grain_render
        extra = section(repo)
        return grain_render(repo) + ("\n".join(extra) + "\n" if extra else "")
    metadata = [json.loads(row["execution_metadata"]) for row in repo.runs()]
    live = any(item["backend"] != "fake" for item in metadata)
    tag = "measured" if live else "simulated"
    title = "# Planted signal — live model workers" if live else "# Planted signal — simulated"
    scope = ("Real model workers on a known-answer sanity task: this tests the loop and evidence handling, not scientific discovery."
        if live else "Fake proposals demonstrate execution and evidence handling, not new scientific discovery.")
    lines = [title, "", scope, "",
        "| Run | Execution | Scientific outcome | Verification | Development MSE |", "|---|---|---|---|---|"]
    for row, summary in zip(repo.runs(), run_summaries(repo), strict=True):
        verdict = json.loads(row["verdict"]) if row["verdict"] else None
        if verdict:
            if repo.artifact(row["id"], "evaluation") != canonical(verdict).encode():
                raise IntegrityError("database verdict differs from sealed raw evaluation")
            repo.artifact(row["id"], "candidate")
            repo.artifact(row["id"], "transcript")
        score = format(summary["development_metrics"]["mse"], ".12g") if verdict else "unavailable"
        if verdict:
            number(verdict["mse"], score)
        evidence = f"[evidence](objects/{content_hash(verdict)})" if verdict else "none"
        lines.append(f"| {row['id']} | {row['execution_status']} | {row['scientific_outcome'] or 'unevaluated'} | {row['verification_status']} | {score} ({evidence}) |")
    state = repo.db.execute("SELECT * FROM project").fetchone()
    unknown = sum(item["cost_micro_usd"] is None for item in metadata)
    cost_text = (f"[measured] External model cost: unknown for {unknown} run(s); known settled USD {state['spent_micro_usd'] / 1_000_000:.6f}."
        if unknown else f"[measured] External model cost: USD {state['spent_micro_usd'] / 1_000_000:.6f}"
        + (" (offline fake only)." if all(item["backend"] == "fake" for item in metadata) else " (SDK reported)."))
    if any(item["backend"] != "fake" for item in metadata):
        known = [item["cost_micro_usd"] for item in metadata if item["cost_micro_usd"] is not None]
        cost_text = (f"[measured] SDK-reported cost estimate: USD {sum(known) / 1_000_000:.6f} across {len(known)} run(s); "
            f"unknown for {unknown} run(s). Subscription estimates are not charges.")
    lines += ["", f"[{tag}] Attempted variants: {len(repo.runs())}.",
        f"[measured] Control/final evaluation starts: {state['control_attempts']}.",
        cost_text,
        f"[measured] Reserved micro-USD: {state['reserved_micro_usd']}.", "[cited] Synthetic dataset license: CC0-1.0."]
    selection = json.loads(state["selection"]) if state["selection"] else None
    if selection:
        lines += ["", f"[{tag}] Selection: " + selection["winner"] + ".",
            "[assumed] Registered seeds: " + canonical(selection["seeds"]) + "; keep margin: " + format(selection["keep_margin"], ".12g") + ".",
            f"[{tag}] Paired bootstrap development MSE improvement interval: " + canonical(selection["paired_improvement_interval"]) + ".",
            "[interpretation] " + selection["limitation"]]
    ticket = json.loads(state["final_ticket"]) if state["final_ticket"] else None
    if ticket:
        lines += ["", "[measured] Final ticket: " + ticket["state"] + "; campaign sealed."]
        if "verdict" in ticket:
            lines += [f"[{tag}] Final MSE: " + format(ticket["verdict"]["mse"], ".12g") + "."]
    for row in repo.db.execute("SELECT * FROM challenges ORDER BY id"):
        resolved = repo.db.execute("SELECT 1 FROM events WHERE kind='challenge_resolution' AND record_id=?", (row["id"],)).fetchone()
        lines.append(f"[interpretation] Challenge {row['id']} to {row['claim_id']}: {'resolved' if resolved else 'contested'}; {row['grounds']}")
    lines += section(repo)
    lines.append("")
    return "\n".join(lines)


@plain_io_errors()
def report(repo: Repository, *, check: bool = False) -> str:
    value = render(repo)
    target = repo.root / "report.md"
    if check:
        if not long_path(target).exists() or long_path(target).read_text(encoding="utf-8") != value:
            raise IntegrityError("saved report differs from database regeneration")
    else:
        atomic_write(target, value.encode())
        atomic_write(repo.root / "report.html", ("<!doctype html><meta charset=utf-8><title>Research loop</title><pre>" + html.escape(value) + "</pre>").encode())
    return value


def export_bytes(repo: Repository) -> bytes:
    """Expected event chain, shared by append and read-only assessment."""
    expected = []
    previous = "0" * 64
    for row in repo.db.execute("SELECT * FROM events ORDER BY seq"):
        payload = dict(row)
        payload["payload"] = json.loads(payload["payload"])
        envelope = {"schema_version": 1, "previous": previous, "event": payload}
        envelope["hash"] = content_hash(envelope)
        previous = envelope["hash"]
        expected.append((canonical(envelope) + "\n").encode())
    return b"".join(expected)


@plain_io_errors()
def verify_export(repo: Repository) -> tuple[int, int]:
    path = repo.root / "events.jsonl"
    existing = long_path(path).read_bytes()
    full = export_bytes(repo)
    if existing and (not existing.endswith(b"\n") or not full.startswith(existing)):
        raise IntegrityError("divergent or torn export; preserve file and diagnose before recovery")
    return len(existing.splitlines()), len(full.splitlines())


@plain_io_errors()
def export(repo: Repository) -> Path:
    path = repo.root / "events.jsonl"
    existing = long_path(path).read_bytes() if long_path(path).exists() else b""
    full = export_bytes(repo)
    if existing and (not existing.endswith(b"\n") or not full.startswith(existing)):
        raise IntegrityError("divergent or torn export; preserve file and diagnose before recovery")
    if existing != full:
        with long_path(path).open("ab") as stream:
            stream.write(full[len(existing):])
            stream.flush()
            import os
            os.fsync(stream.fileno())
    return path
