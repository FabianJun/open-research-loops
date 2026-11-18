"""Deterministic evidence inventory, never a scientific score or certification."""

from collections import Counter
import json
from pathlib import Path
import re
import sqlite3

from research_loops.domain import Contract, IntegrityError, Verdict, canonical, content_hash, digest
from research_loops.evaluation import evaluator_hash
from research_loops.licensing import license_issues
from research_loops.reporting import report, verify_export
from research_loops.skills import resources
from research_loops.storage import Repository
from research_loops.verification import check
from research_loops.contracts import is_grain, parse_contract
from research_loops.grain_evaluator import parse_verdict

# Adapted rubric wording, CC BY 4.0, see NOTICE
QUESTIONS = {
    "Problem": "Is the intended problem worth solving, and what would refute the scientific claim?",
    "Loop": "Is the evaluator valid for that claim, and are the controls and search budget appropriate?",
    "Evidence": "Do the artifacts support the stated scope, uncertainty and interpretation?",
    "Honesty": "Are negative results, failures, selection effects and remaining limitations explained fairly?",
    "Reproducibility": "Can another researcher reproduce the procedure in their environment?",
    "License review": "Are all code, data, sources and redistribution permissions complete and compatible?",
    "Impact review": "Who could use the result, what would change, and what harms or misuse need attention?",
}


def assess(project: Path, *, repository_root: Path | None = None) -> str:
    facts = {key: [] for key in QUESTIONS}
    failures = []
    licenses = []
    root = project / ".rloop"

    def checked(dimension, label, source, action):
        try:
            detail = action()
            facts[dimension].append(f"{label}: {detail}. Source: `{source}`.")
        except (IntegrityError, OSError, ValueError, KeyError, TypeError, sqlite3.Error) as exc:
            failures.append(label)
            facts[dimension].append(f"{label}: FAIL ({exc}). Source: `{source}`.")

    def require(condition, message):
        if not condition:
            raise IntegrityError(message)

    # Reuse repository queries/artifact checks without its writable startup or migrations.
    repo = Repository.__new__(Repository)
    repo.root = root
    try:
        repo.db = sqlite3.connect((root / "state.sqlite").resolve().as_uri() + "?mode=ro", uri=True)
        repo.db.row_factory = sqlite3.Row
        repo.db.execute("PRAGMA query_only=ON")
        repo.db.execute("BEGIN")
        state = repo.db.execute("SELECT * FROM project").fetchone()
        runs = repo.runs()
        events = [dict(row) for row in repo.db.execute("SELECT * FROM events ORDER BY seq")]
        registrations = [dict(row) for row in repo.db.execute("SELECT * FROM registrations ORDER BY hash")]
        require(bool(state) and bool(registrations), "project has no saved registration")

        def database_check():
            require(repo.db.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "SQLite integrity check failed")
            require(not repo.db.execute("PRAGMA foreign_key_check").fetchall(), "foreign key check failed")
            return "SQLite integrity and foreign keys pass"
        checked("Evidence", "Database integrity", ".rloop/state.sqlite", database_check)

        contracts = {}
        inputs_by_key = {}
        for registration in registrations:
            key = registration["hash"]
            source = f".rloop/state.sqlite:registrations[{key}]"

            def registration_check():
                contract = json.loads(registration["payload"])
                inputs = json.loads(registration["inputs"])
                licenses.extend([contract.get("license", "undeclared")])
                parsed = parse_contract(contract)
                value = {"contract": contract, "evaluator_hash": registration["evaluator_hash"], "inputs": inputs}
                require(content_hash(value) == key, "registration content hash differs")
                contracts[key], inputs_by_key[key] = contract, inputs
                require(any(e["kind"] == "registration" and e["record_id"] == key and json.loads(e["payload"]) == value
                    for e in events), "registration event anchor missing or different")
                require(registration["evaluator_hash"] == evaluator_hash(parsed.name), "evaluator package anchor differs")
                for split in ("training", "development", "final"):
                    data = (root / "private" / key / f"{split}.json").read_bytes()
                    require(digest(data) == inputs[split], f"{split} input hash differs")
                from research_loops.coordinator import proposal_method
                require(inputs["proposal_method"] == digest(proposal_method(parsed).read_bytes()), "proposal method hash differs")
                return "exists; content hash, event anchor, evaluator anchor, saved splits and proposal method verified"
            checked("Problem", f"Registration {key}", source, registration_check)

        def current_contract():
            key = state["current_registration"]
            require(key in contracts, "current registration missing")
            require(canonical(parse_contract((project / "contract.json").read_bytes())) == canonical(contracts[key]),
                "working contract differs from current registration")
            return "matches current saved registration"
        checked("Problem", "Working contract", "contract.json; .rloop/state.sqlite:project.current_registration", current_contract)
        grain = contracts.get(state["current_registration"], {}).get("name") == "grain-316l"
        facts["Problem"].append("Task: grain-316l is a real benchmark with a published baseline. Source: `research_loops/contracts.py:GrainContract`." if grain else
            "Task: planted-signal is a known-answer sanity check, not an open scientific discovery. Source: `research_loops/domain.py:Contract.name`.")
        if grain:
            from research_loops.grain_data import LICENSE_CAVEAT
            facts["License review"].append(LICENSE_CAVEAT + " Source: `examples/grain-316l/PROVENANCE.md`.")

        def controls_first():
            ready, starts, dispatches = False, 0, 0
            for event in events:
                if event["kind"] == "registration":
                    ready, starts = False, 0
                elif event["kind"] == "control_start":
                    starts += 1
                elif event["kind"] == "pilot":
                    payload = json.loads(event["payload"])
                    require(starts >= 2 and set(payload) == {"positive_control", "negative_control", "nonconstant", "baseline"}
                        and all(value is True for value in payload.values()), "control gate evidence missing or failed")
                    ready = True
                    if grain:
                        evidence = next((json.loads(e["payload"])["controls"] for e in reversed(events)
                            if e["kind"] == "grain_controls" and e["seq"] < event["seq"]), [])
                        require(len(evidence) == 2 and all(c["reproduced"] and abs(c["measured"] - c["expected"]) <= 1e-9 for c in evidence), "grain reproduction controls missing or failed")
                elif event["kind"] == "dispatch":
                    require(ready, "worker dispatched before passing controls")
                    dispatches += 1
            require(dispatches == len(runs), "dispatch/run counts differ")
            return f"controls precede all {dispatches} worker dispatches (recorded gate evidence)"
        checked("Loop", "Controls ran first", ".rloop/state.sqlite:events(control_start,pilot,dispatch)", controls_first)

        statuses = Counter(row["execution_status"] for row in runs)
        outcomes = Counter(row["scientific_outcome"] or "unevaluated" for row in runs)
        for label, counts, defaults in (
            ("Execution status", statuses, ("planned", "running", "completed", "technical_error", "timed_out", "cancelled", "interrupted", "limit_reached")),
            ("Scientific outcome", outcomes, ("supported", "negative", "inconclusive", "unevaluated")),
        ):
            facts["Honesty"].append(label + ": " + ", ".join(f"{key}={counts[key]}" for key in sorted(set(defaults) | set(counts)))
                + ". Source: `.rloop/state.sqlite:runs`.")
        facts["Loop"].append(f"Control/final evaluation starts: {state['control_attempts']}. Source: `.rloop/state.sqlite:project.control_attempts`.")

        def artifacts_check():
            artifacts = list(repo.db.execute("SELECT * FROM artifacts ORDER BY id"))
            for artifact in artifacts:
                require(bool(re.fullmatch(r"[0-9a-f]{64}", artifact["hash"])), "invalid object hash")
                data = repo.artifact(artifact["run_id"], artifact["kind"])
                require(len(data) == artifact["size"], "object size differs")
            return f"all {len(artifacts)} saved artifact hashes and sizes verified"
        checked("Evidence", "Saved objects", ".rloop/state.sqlite:artifacts; .rloop/objects/", artifacts_check)

        def verdicts_check():
            count = 0
            for run in runs:
                require(run["registration_hash"] in contracts, "run registration is not verified")
                if run["report"]:
                    require(digest(run["report"].encode()) == run["report_hash"], "worker report hash differs")
                if not run["verdict"]:
                    require(run["scientific_outcome"] is None, "outcome has no verdict")
                    continue
                verdict = parse_verdict(run["verdict"])
                require(repo.artifact(run["id"], "evaluation") == canonical(verdict).encode(), "verdict lacks matching evidence object")
                request = json.loads((root / "private" / run["registration_hash"] / "development.json").read_bytes())
                if request.get("domain") == "grain-316l":
                    request = {"domain": "grain-316l", "manifest": request, "data_root": str(root / "data" / "Grain" / "val")}
                request["candidate"] = json.loads(repo.artifact(run["id"], "candidate"))
                check(request, verdict)
                require(run["scientific_outcome"] == ("supported" if verdict.supported else "negative"), "outcome differs from verdict")
                require(run["execution_status"] == "completed" and run["verification_status"] == "checked", "verdict execution/verification status differs")
                count += 1
            return f"every reported verdict has its evidence object; {count} saved verdicts independently re-checked"
        checked("Evidence", "Verdict evidence", ".rloop/state.sqlite:runs; .rloop/objects/; .rloop/private/*/development.json", verdicts_check)

        def final_check():
            if not state["final_ticket"]:
                return "not consumed; no final result claimed"
            ticket = json.loads(state["final_ticket"])
            require(ticket["state"] == "completed" and "verdict" in ticket, "final evaluation unfinished")
            run = next((row for row in runs if row["id"] == ticket["run_id"]), None)
            require(run is not None and run["registration_hash"] in inputs_by_key, "final run registration missing")
            require(ticket["split_hash"] == inputs_by_key[run["registration_hash"]]["final"], "final split hash differs")
            receipt = json.loads((root / "private" / "final-receipt.json").read_bytes())
            require(receipt["verdict"] == ticket["verdict"] and receipt["ticket"] == {k: v for k, v in ticket.items() if k != "verdict"} | {"state": "started"}, "final receipt differs")
            request = json.loads((root / "private" / run["registration_hash"] / "final.json").read_bytes())
            if request.get("domain") == "grain-316l":
                # Rechecking saved final truth would spend holdout information
                # again. Verify the sealed receipt/ticket only after final use.
                return "saved final receipt and one-use ticket match; grain holdout was not reopened"
            request["candidate"] = json.loads(repo.artifact(run["id"], "candidate"))
            check(request, parse_verdict(ticket["verdict"]))
            return "saved final receipt matches ticket; independent arithmetic re-check passes"
        checked("Evidence", "Final evidence", ".rloop/state.sqlite:project.final_ticket; .rloop/private/final-receipt.json", final_check)

        checked("Reproducibility", "Report check", ".rloop/report.md; .rloop/state.sqlite; .rloop/objects/",
            lambda: (report(repo, check=True), "report --check would pass")[1])
        checked("Reproducibility", "Export prefix", ".rloop/events.jsonl; .rloop/state.sqlite:events",
            lambda: "verified %d saved events of %d database events" % verify_export(repo))
    except (IntegrityError, OSError, ValueError, KeyError, TypeError, sqlite3.Error) as exc:
        failures.append("project evidence")
        facts["Evidence"].append(f"Project evidence: FAIL ({exc}). Source: `.rloop/state.sqlite`.")
    finally:
        if hasattr(repo, "db"):
            repo.db.close()

    checked("License review", "Repository licenses", "LICENSE; LICENSE-CC-BY-4.0; research_loops/licensing.py:license_issues",
        lambda: license_result(repository_root or resources(), licenses, failures))
    facts["License review"].append("Declared dataset/source licenses: " + (", ".join(sorted(set(licenses))) or "unavailable")
        + ". Source: `.rloop/state.sqlite:registrations.payload.license`. Dataset redistribution still requires human license review.")
    facts["Impact review"].append("No impact certification is computed. Source: `research_loops/assessment.py` (review policy).")
    lines = ["# Self-assessment", "", "Offline evidence inventory; no scores. No experiments were dispatched.", ""]
    for dimension, question in QUESTIONS.items():
        lines += [f"## {dimension}", "", "Machine-checked facts:", ""]
        lines += [f"- {fact}" for fact in facts[dimension]] or ["- No machine-checked facts available."]
        lines += ["", "Open questions requiring human judgment:", "", f"- {question}", ""]
    lines += ["public-ready: " + ("no" if failures else "needs human review"), ""]
    return "\n".join(lines)


def license_result(root: Path, licenses: list[str], failures: list[str]) -> str:
    issues = license_issues(root, licenses)
    if issues:
        failures.append("license issues")
        return "; ".join(issues)
    return "no issues detected by license_issues; legal and project redistribution review remains open"
