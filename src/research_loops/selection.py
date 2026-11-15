"""Locked development selection and explicitly descriptive bootstrap intervals."""

import json
import random

from research_loops.domain import Contract, IntegrityError, canonical
from research_loops.storage import Repository


def select(repo: Repository, contract: Contract, key: str) -> dict:
    from research_loops.contracts import is_grain
    if is_grain(contract):
        return select_grain(repo, contract, key)
    saved = repo.db.execute("SELECT selection FROM project").fetchone()[0]
    if saved:
        return json.loads(saved)
    by_arm = {"agent": [], "random": []}
    rows = [row for row in repo.runs() if row["registration_hash"] == key]
    expected = len(contract.seeds) * contract.variants_per_seed * 2
    if len(rows) != expected:
        raise IntegrityError("selection requires the complete registered denominator")
    for row in rows:
        if row["execution_status"] == "completed" and row["verification_status"] == "checked":
            by_arm[json.loads(row["assignment"])["arm"]].append(row)
    def winner(candidates):
        if not candidates:
            raise IntegrityError("no checked candidate in arm")
        best = min(json.loads(row["verdict"])["mse"] for row in candidates)
        tied = [row for row in candidates if json.loads(row["verdict"])["mse"] <= best + contract.keep_margin]
        return min(tied, key=lambda row: (json.loads(row["report"])["candidate"]["sha256"], row["id"]))
    agent, baseline = winner(by_arm["agent"]), winner(by_arm["random"])
    a, b = json.loads(agent["verdict"]), json.loads(baseline["verdict"])
    differences = [x - y for x, y in zip(b["squared_errors"], a["squared_errors"], strict=True)]
    rng = random.Random(contract.bootstrap_seed)
    means = sorted(sum(rng.choices(differences, k=len(differences))) / len(differences) for _ in range(contract.bootstrap_resamples))
    count = len(means)
    value = {"winner": agent["id"], "random_winner": baseline["id"], "attempts": len(rows),
        "keep_margin": contract.keep_margin, "seeds": list(contract.seeds), "bootstrap_seed": contract.bootstrap_seed,
        "bootstrap_resamples": contract.bootstrap_resamples, "paired_improvement_interval": [means[int(count * .025)], means[min(count - 1, int(count * .975))]],
        "limitation": "Descriptive development comparison after adaptive selection; not a generalization guarantee."}
    with repo.db:
        repo.db.execute("UPDATE project SET selection=?", (canonical(value),))
        repo.event("selection", agent["id"], value)
    return value


def select_grain(repo, contract, key):
    saved = repo.db.execute("SELECT selection FROM project").fetchone()[0]
    if saved:
        return json.loads(saved)
    rows = [r for r in repo.runs() if r["registration_hash"] == key]
    if len(rows) != len(contract.seeds) * contract.variants_per_seed * 2:
        raise IntegrityError("selection requires the complete registered denominator")
    candidates = [r for r in rows if r["execution_status"] == "completed" and r["verification_status"] == "checked"]
    if not candidates:
        raise IntegrityError("no checked grain candidates")
    best = min(json.loads(r["verdict"])["max_rel_error"] for r in candidates)
    tied = [r for r in candidates if json.loads(r["verdict"])["max_rel_error"] <= best + contract.keep_margin]
    winner = min(tied, key=lambda r: (json.loads(r["report"])["candidate"]["sha256"], r["id"]))
    value = dict(winner=winner["id"], attempts=len(rows), keep_margin=contract.keep_margin, seeds=list(contract.seeds),
        limitation="Adaptive development selection on a real benchmark with a published baseline; the final holdout is consumed once.")
    with repo.db:
        repo.db.execute("UPDATE project SET selection=?", (canonical(value),))
        repo.event("selection", winner["id"], value)
    return value
