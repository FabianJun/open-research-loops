"""Checkpoint B is an explicit project record, never inferred from API keys."""

import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

from research_loops.domain import IntegrityError


def authorize(project: Path | None, provider: str, model: str) -> int:
    path = project / "project.json" if project else None
    if path is None or not path.is_file():
        raise IntegrityError("provider calls are not authorized: checkpoint B project configuration required")
    try:
        value = json.loads(path.read_bytes())["checkpoint_b"]
        cap = Decimal(str(value["usd_cap"]))
        if value.get("approved_by") != "scaled-thinking" or value["provider"] != provider or value["model"] != model or not model.strip() or not cap.is_finite() or cap < Decimal("0.000001"):
            raise ValueError("provider/model/cap mismatch")
        return int(cap * 1_000_000)
    except (ValueError, KeyError, TypeError, InvalidOperation) as exc:
        raise IntegrityError("invalid checkpoint B provider, model or USD cap") from exc
