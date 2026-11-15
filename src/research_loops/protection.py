"""Evaluator anchor validation and trusted-base amendment policy."""

import json
from pathlib import Path

from research_loops.domain import IntegrityError, content_hash, digest
from research_loops.owner import owner_name


def verify_anchor() -> dict:
    root = Path(__file__).parent
    manifest = json.loads((root / "evaluator-manifest.json").read_bytes())
    for name, expected in manifest["files"].items():
        if "/" in name or "\\" in name or digest((root / name).read_bytes()) != expected:
            raise IntegrityError("protected evaluator anchor differs from package files")
    return manifest


def authorize_change(base: dict, current: dict, trusted_decisions: list[dict]) -> None:
    if base["anchor"] == current["anchor"]:
        return
    owner = owner_name(base)
    for decision in trusted_decisions:
        authority = decision.get("authority")
        if (decision.get("old") == content_hash(base) and decision.get("new") == content_hash(current)
            and isinstance(authority, str) and authority.strip() == owner
            and decision.get("reason", "").strip()):
            return
    raise IntegrityError("protected spec/anchor changed without a human decision in the trusted base")
