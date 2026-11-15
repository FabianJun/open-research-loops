"""Database-derived, deterministic report and append-only review export."""

import html
import json
from pathlib import Path

from research_loops.domain import IntegrityError, canonical, content_hash
from research_loops.grounding import number
from research_loops.paths import atomic_write
from research_loops.storage import Repository


def render(repo: Repository) -> str:
    metadata = [json.loads(row["execution_metadata"]) for row in repo.runs()]
    live = any(item["backend"] != "fake" for item in metadata)
    tag = "measured" if live else "simulated"
    title = "# Planted signal — live model workers" if live else "# Planted signal — simulated"
    scope = ("Real model workers on a known-answer sanity task: this tests the loop and evidence handling, not scientific discovery."
        if live else "Fake proposals demonstrate execution and evidence handling, not new scientific discovery.")
    lines = [title, "", scope, "",
        "| Run | Execution | Scientific outcome | Verification | Development MSE |", "|---|---|---|---|---|"]
    for row in repo.runs():
        verdict = json.loads(row["verdict"]) if row["verdict"] else None
        if verdict:
            if repo.artifact(row["id"], "evaluation") != canonical(verdict).encode():
                raise IntegrityError("database verdict differs from sealed raw evaluation")
            repo.artifact(row["id"], "candidate")
            repo.artifact(row["id"], "transcript")
        score = format(verdict["mse"], ".12g") if verdict else "unavailable"
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
    lines.append("")
    return "\n".join(lines)


def report(repo: Repository, *, check: bool = False) -> str:
    value = render(repo)
    target = repo.root / "report.md"
    if check:
        if not target.exists() or target.read_text(encoding="utf-8") != value:
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


def verify_export(repo: Repository) -> tuple[int, int]:
    path = repo.root / "events.jsonl"
    existing = path.read_bytes()
    full = export_bytes(repo)
    if existing and (not existing.endswith(b"\n") or not full.startswith(existing)):
        raise IntegrityError("divergent or torn export; preserve file and diagnose before recovery")
    return len(existing.splitlines()), len(full.splitlines())


def export(repo: Repository) -> Path:
    path = repo.root / "events.jsonl"
    existing = path.read_bytes() if path.exists() else b""
    full = export_bytes(repo)
    if existing and (not existing.endswith(b"\n") or not full.startswith(existing)):
        raise IntegrityError("divergent or torn export; preserve file and diagnose before recovery")
    if existing != full:
        with path.open("ab") as stream:
            stream.write(full[len(existing):])
            stream.flush()
            import os
            os.fsync(stream.fileno())
    return path
