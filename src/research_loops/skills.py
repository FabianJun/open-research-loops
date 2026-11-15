"""Portable skill discovery and collision-refusing personal-agent links."""

import os
from pathlib import Path
import subprocess
from typing import Literal

import typer

from research_loops.domain import IntegrityError, digest

NAMES = (
    "rloop-research-loop", "rloop-bounded-iteration", "rloop-evidence-gate",
    "rloop-challenge", "rloop-parallel-fanout", "rloop-handoff-report", "rloop-self-assess",
)
app = typer.Typer(no_args_is_help=True)


def resources() -> Path:
    """Wheel resources live beside the code; editable installs use the checkout."""
    package = Path(__file__).resolve().parent
    return package if (package / "skills").is_dir() else package.parents[1]


def home_directory() -> Path:
    """Single redirectable boundary; tests always replace this with a temp home."""
    return Path.home()


def skill_path(name: str) -> Path:
    if name not in NAMES:
        raise IntegrityError(f"unknown skill: {name}")
    return resources() / "skills" / name


def create_link(source: Path, target: Path) -> None:
    if os.name == "nt":
        # PowerShell literals keep spaces, quotes and shell metacharacters as data.
        literal = lambda path: "'" + str(path).replace("'", "''") + "'"
        subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
            "$ErrorActionPreference = 'Stop'; New-Item -ItemType Junction -Path "
            + literal(target) + " -Target " + literal(source) + " | Out-Null"], check=True, capture_output=True)
    else:
        target.symlink_to(source, target_is_directory=True)


def install(target: str = "both", *, dry_run: bool = False) -> list[str]:
    if target not in {"claude", "agents", "both"}:
        raise IntegrityError(f"unknown target: {target}")
    home = home_directory()
    locations = ("claude", "agents") if target == "both" else (target,)
    plan, conflicts, messages = [], [], []
    for location in locations:
        for name in NAMES:
            source = skill_path(name).resolve(strict=True)
            path = home / f".{location}" / "skills" / name
            if path.is_symlink() or path.is_junction():
                if path.resolve() == source:
                    messages.append(f"unchanged {path}")
                    continue
                conflicts.append(path)
            elif path.exists():
                conflicts.append(path)
            else:
                invalid_parent = next((p for p in path.parents if p.exists() and not p.is_dir()), None)
                if invalid_parent:
                    conflicts.append(invalid_parent)
                else:
                    plan.append((source, path))
    if conflicts:
        raise IntegrityError("conflicting paths; nothing changed:\n" + "\n".join(str(p) for p in dict.fromkeys(conflicts)))
    created, directories = [], []
    try:
        for source, path in plan:
            if not dry_run:
                missing = [p for p in path.parents if not p.exists()]
                for parent in reversed(missing):
                    parent.mkdir()
                    directories.append(parent)
                create_link(source, path)
                created.append(path)
            messages.append(f"{'would link' if dry_run else 'linked'} {path} -> {source}")
    except Exception:
        for path in reversed(created):
            path.rmdir() if path.is_junction() else path.unlink()
        for path in reversed(directories):
            path.rmdir()
        raise
    return messages


@app.command("list")
def list_skills() -> None:
    """List bundled skill names and exact-byte SHA-256 hashes."""
    for name in NAMES:
        typer.echo(f"{name}  sha256:{digest((skill_path(name) / 'SKILL.md').read_bytes())}")


@app.command("show")
def show_skill(name: str) -> None:
    """Print skill text and its SHA-256 for explicit agent injection."""
    try:
        data = (skill_path(name) / "SKILL.md").read_bytes()
    except IntegrityError as exc:
        raise typer.BadParameter(str(exc)) from None
    typer.echo(data.decode("utf-8"), nl=False)
    typer.echo(f"\nsha256:{digest(data)}")


@app.command("install")
def install_skills(target: Literal["claude", "agents", "both"] = "both", dry_run: bool = False) -> None:
    """Link skills into personal agent directories; refuse all collisions."""
    try:
        for message in install(target, dry_run=dry_run):
            typer.echo(message)
    except (IntegrityError, OSError, subprocess.CalledProcessError) as exc:
        raise typer.BadParameter(str(exc)) from None
