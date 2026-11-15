"""Project-owner identity in coordinator-only project configuration."""

import getpass
import json
import subprocess
from pathlib import Path

from research_loops.domain import IntegrityError, canonical
from research_loops.paths import atomic_write


def owner_name(record: dict) -> str:
    """Validate an already recorded identity; never resolve a missing owner here."""
    owner = record.get("owner") if isinstance(record, dict) else None
    value = owner.get("name") if isinstance(owner, dict) else None
    if not isinstance(value, str) or not value.strip():
        raise IntegrityError("a nonempty project owner must be recorded in project.json")
    return value.strip()


def resolve_owner(name: str | None, directory: Path) -> dict:
    if name is not None:
        source = "argument"
    else:
        try:
            result = subprocess.run(["git", "-C", str(directory), "config", "user.name"],
                capture_output=True, text=True, check=False)
            name = result.stdout.strip() if result.returncode == 0 else ""
        except OSError:
            name = ""
        source = "git"
        if not name:
            name, source = getpass.getuser(), "os"
    owner_name({"owner": {"name": name}})
    return {"name": name.strip(), "source": source}


def initialize_owner(project: Path, name: str | None) -> dict:
    """Preserve a recorded owner on repeated init unless explicitly replaced."""
    path = project / "project.json"
    config = json.loads(path.read_bytes()) if path.exists() else {}
    if name is None and "owner" in config:
        owner_name(config)
        return config["owner"]
    # Use the nearest existing directory so new project paths inherit Git config.
    directory = project.resolve()
    while not directory.exists():
        directory = directory.parent
    config["owner"] = resolve_owner(name, directory)
    atomic_write(path, canonical(config).encode())
    return config["owner"]
