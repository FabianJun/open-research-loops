"""Statistics-only grain reports, bound to stored evaluator evidence."""

import json

from research_loops.domain import IntegrityError, canonical, content_hash
from research_loops.grain_data import LICENSE_CAVEAT, TEAM_SOURCE


def render(repo):
    from research_loops.reporting import run_summaries
    rows = repo.runs()
    metadata = [json.loads(r["execution_metadata"]) for r in rows]
    live = any(m["backend"] != "fake" for m in metadata)
    lines = ["# Grain 316L — " + ("live model workers" if live else "offline fake workers"), "",
        "Real benchmark with a published baseline. " + ("Real model workers proposed parameters." if live else "Fake workers demonstrate the loop; their proposals are simulated."),
        "Supported iff development max_rel_error <= 0.10.", "",
        "| Run | Backend | Execution | Outcome | Verification | Development max_rel_error | Count | Size | Improvement vs cited team development |",
        "|---|---|---|---|---|---|---|---|---|"]
    for row, meta, summary in zip(rows, metadata, run_summaries(repo), strict=True):
        verdict = json.loads(row["verdict"]) if row["verdict"] else None
        if verdict:
            if repo.artifact(row["id"], "evaluation") != canonical(verdict).encode():
                raise IntegrityError("database verdict differs from sealed raw evaluation")
            repo.artifact(row["id"], "candidate")
            repo.artifact(row["id"], "transcript")
        def metric(key):
            value = summary["development_metrics"].get(key)
            return format(value, ".12g") if value is not None else "undefined"
        evidence = f"[evidence](objects/{content_hash(verdict)})" if verdict else "none"
        improvement = format(.12586301151517196 - verdict["max_rel_error"], ".12g") if verdict else "unavailable"
        outcome = ("supported" if verdict["supported"] else "not supported") if verdict else "unevaluated"
        lines.append(f"| {row['id']} | {meta['backend']} | {row['execution_status']} | {outcome} | {row['verification_status']} | {metric('max_rel_error')} ({evidence}) | {metric('median_count_rel_error')} | {metric('median_size_rel_error')} | {improvement} |")
    lines += ["", "[cited] " + TEAM_SOURCE + ". Development: max_rel_error 0.12586301151517196, count 0.1111111111111111, size 0.12586301151517196 (40 images, size defined for 39).",
        "[cited] Team holdout benchmark: max_rel_error 0.17391304347826086, count 0.17391304347826086, size 0.1629683115862643 (165 images, size defined for 164). This is cited, not recomputed.",
        "[interpretation] Improvement is cited team error minus candidate error; positive is better.",
        "[cited] " + LICENSE_CAVEAT, "", "Controls (absolute reproduction tolerance 1e-9):"]
    controls = repo.db.execute("SELECT payload FROM events WHERE kind='grain_controls' ORDER BY seq DESC LIMIT 1").fetchone()
    if controls:
        for c in json.loads(controls[0])["controls"]:
            lines.append(f"[measured] {c['name']} {canonical(c['params'])}: {c['measured']!r}; expected {c['expected']!r}; reproduction {'passed' if c['reproduced'] else 'FAILED'}.")
    else:
        lines.append("Controls have no completed reproduction evidence; workers remain blocked.")
    state = repo.db.execute("SELECT * FROM project").fetchone()
    lines += ["", f"[measured] Attempted variants: {len(rows)}; control/final starts: {state['control_attempts']}."]
    if live:
        known = [m["cost_micro_usd"] for m in metadata if m["cost_micro_usd"] is not None]
        lines.append(f"[measured] SDK-reported cost estimate: USD {sum(known) / 1_000_000:.6f} across {len(known)} run(s); unknown for {len(rows)-len(known)} run(s). Subscription estimates are not charges.")
    else:
        lines.append("[measured] External model cost: USD 0.000000 (offline fake only).")
    if state["selection"]:
        selection = json.loads(state["selection"])
        lines += ["[measured] Selection: " + selection["winner"] + ".", "[interpretation] " + selection["limitation"]]
    if state["final_ticket"]:
        ticket = json.loads(state["final_ticket"])
        lines.append("[measured] Final ticket: " + ticket["state"] + "; campaign sealed.")
        if "verdict" in ticket:
            v = ticket["verdict"]
            lines.append(f"[measured] Final holdout max_rel_error {v['max_rel_error']!r}; count {v['median_count_rel_error']!r}; size {v['median_size_rel_error']!r}; improvement vs cited team holdout {(.17391304347826086-v['max_rel_error'])!r}.")
    else:
        lines.append("Final holdout unspent; no measured final result.")
    return "\n".join(lines) + "\n"
