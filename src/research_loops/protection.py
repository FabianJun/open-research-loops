"""Evaluator anchor validation and trusted-base amendment policy."""

import json
from pathlib import Path

from research_loops.domain import IntegrityError, content_hash, digest


def verify_anchor() -> dict:
    root = Path(__file__).parent
    manifest = json.loads((root / "evaluator-manifest.json").read_bytes())
    for name, expected in manifest["files"].items():
        if "/" in name or "\\" in name or digest((root / name).read_bytes()) != expected:
            raise IntegrityError("protected evaluator anchor differs from package files")
    return manifest


def authorize_change(base: dict, current: dict, trusted_decisions: list[dict]) -> None:
    if base == current:
        return
    for decision in trusted_decisions:
        if (decision.get("old") == content_hash(base) and decision.get("new") == content_hash(current)
            and decision.get("authority") == "scaled-thinking" and decision.get("reason", "").strip()):
            return
    raise IntegrityError("protected spec/anchor changed without a human decision in the trusted base")
