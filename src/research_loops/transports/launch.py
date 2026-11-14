"""Run-scoped stdio launch descriptions and credential-free tool environments."""

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from research_loops.domain import WorkerContract, canonical
from research_loops.paths import atomic_write


def tool_environment() -> dict[str, str]:
    allowed = {"SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP", "LANG"}
    return {key: value for key, value in os.environ.items() if key.upper() in allowed}


@dataclass(frozen=True)
class Launch:
    command: str
    args: list[str]
    env: dict[str, str]
    cwd: str | None = None
    image: str | None = None


def local_launch(contract: WorkerContract, root: Path, *, adapter: bool = False) -> Launch:
    root = root.resolve()
    context = root.parent / "worker-context.json"
    value = canonical(contract).encode()
    if context.exists():
        if context.read_bytes() != value:
            raise ValueError("worker context cannot be replaced")
    else:
        atomic_write(context, value, exclusive=True)
    args = ["-I", "-m", "research_loops.transports.launcher", "--context", str(context),
        "--outbox", str(root), "--audit", str(root.parent / "tool-environment.json")]
    if adapter:
        args.append("--adapter")
    return Launch(sys.executable, args, tool_environment())
