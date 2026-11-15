"""Host-only working mode; never part of a contract or worker projection."""

import json
from pathlib import Path
from typing import Literal

from research_loops.domain import IntegrityError, canonical
from research_loops.paths import atomic_write

Mode = Literal["autonomous", "coached"]


def validate_mode(value: object) -> Mode:
    if not isinstance(value, str) or value not in ("autonomous", "coached"):
        raise IntegrityError("mode must be autonomous or coached")
    return value


def working_mode(project: Path) -> Mode:
    path = project / "project.json"
    config = json.loads(path.read_bytes()) if path.exists() else {}
    return validate_mode(config.get("mode", "autonomous"))


def initialize_mode(project: Path, mode: Mode | None) -> Mode:
    """Keep an existing mode unless explicitly changed, like the owner setting."""
    path = project / "project.json"
    config = json.loads(path.read_bytes()) if path.exists() else {}
    value = validate_mode(mode if mode is not None else config.get("mode", "autonomous"))
    config["mode"] = value
    atomic_write(path, canonical(config).encode())
    return value
