"""Command-line entry point."""

import asyncio
from pathlib import Path

import typer

from research_loops import __version__

app = typer.Typer(no_args_is_help=True)
from research_loops.auth_cli import app as auth_app
app.add_typer(auth_app, name="auth")
from research_loops.skills import app as skills_app
app.add_typer(skills_app, name="skills")
data_app = typer.Typer(no_args_is_help=True)
app.add_typer(data_app, name="data")


@data_app.command("fetch")
def data_fetch(project: Path, archive: Path | None = None) -> None:
    """Verify and safely ingest host-only grain data; omit --archive to download."""
    from research_loops.grain_data import fetch
    from research_loops.domain import IntegrityError, canonical
    try:
        typer.echo(canonical(fetch(project, archive)))
    except (IntegrityError, OSError) as exc:
        raise typer.BadParameter(str(exc)) from None


@app.callback()
def main() -> None:
    """Bounded offline research loops."""


def failure_message(exc: Exception) -> str:
    from research_loops.domain import IntegrityError
    if isinstance(exc, ExceptionGroup):
        return "\n".join(failure_message(child) for child in exc.exceptions)
    if isinstance(exc, IntegrityError):
        return f"{type(exc).__name__}: {exc}"[:300]
    return f"{type(exc).__name__}: SDK failure (details suppressed)"


@app.command()
def run(example: Path, backend: str = "fake", final: bool = False) -> None:
    """Run a registered domain (fake backend by default)."""
    from research_loops.execution import load_backend
    from research_loops.coordinator import run as execute
    from research_loops.domain import IntegrityError
    try:
        selected = load_backend(backend, example)
        asyncio.run(execute(example, final=final, backend=selected))
    except (IntegrityError, ExceptionGroup) as exc:
        raise typer.BadParameter(failure_message(exc)) from None
    typer.echo(str(example / ".rloop" / "report.md"))


@app.command()
def pilot(example: Path, backend: str = typer.Option(...), workers: int = 8) -> None:
    """Run bounded public-input workers after controls; never consume final data."""
    from research_loops.execution import load_backend
    from research_loops.coordinator import run as execute
    from research_loops.domain import IntegrityError
    try:
        asyncio.run(execute(example, backend=load_backend(backend, example), worker_runs=workers))
    except (IntegrityError, ExceptionGroup) as exc:
        raise typer.BadParameter(failure_message(exc)) from None
    typer.echo(str(example / ".rloop" / "report.md"))


@app.command()
def init(example: Path, question: str = "Can we recover a planted nonlinear signal?", owner: str | None = None) -> None:
    """Create a simulated scaffold and complete its first offline pilot."""
    from research_loops.domain import Contract, canonical
    from research_loops.paths import atomic_write
    from research_loops.coordinator import run as execute
    from research_loops.domain import IntegrityError
    from research_loops.owner import initialize_owner
    try:
        initialize_owner(example, owner)
    except IntegrityError as exc:
        raise typer.BadParameter(str(exc), param_hint="--owner") from exc
    if not (example / "contract.json").exists():
        contract = Contract(goal=question, falsifier="The candidate fails the locked planted-signal criteria.",
            prediction="Uncertain; the negative control should fail and the planted oracle should pass.")
        atomic_write(example / "contract.json", canonical(contract).encode(), exclusive=True)
    from research_loops.coordinator import load_contract
    from research_loops.contracts import is_grain
    if is_grain(load_contract(example)):
        typer.echo("Grain project initialized; fetch verified data before run.")
        return
    asyncio.run(execute(example, pilot_only=True))
    typer.echo(f"Simulated fake pilot complete: {example / '.rloop' / 'report.md'}")


@app.command()
def plan(example: Path, reason: str | None = None) -> None:
    """Register a plan; amendments require an explicit reason."""
    from research_loops.coordinator import prepare
    repo, _, key = prepare(example, amendment_reason=reason)
    repo.close()
    typer.echo(key)


@app.command()
def resume(example: Path) -> None:
    """Reconcile saved processes/outboxes without dispatching new work."""
    from research_loops.coordinator import run as execute
    asyncio.run(execute(example, resume_only=True))
    typer.echo("Reconciled; completed work was not rerun.")


@app.command()
def status(example: Path) -> None:
    """Show saved run states."""
    from research_loops.storage import Repository
    repo = Repository(example / ".rloop")
    try:
        for row in repo.runs():
            typer.echo(f"{row['id']}: {row['execution_status']} / {row['scientific_outcome']}")
    finally:
        repo.close()


@app.command()
def report(example: Path, check: bool = False) -> None:
    """Regenerate a report, or check the saved copy."""
    from research_loops.reporting import report as generate
    from research_loops.storage import Repository
    repo = Repository(example / ".rloop")
    try:
        typer.echo(generate(repo, check=check))
    finally:
        repo.close()


@app.command()
def export(example: Path) -> None:
    """Append review events without rewriting earlier lines."""
    from research_loops.reporting import export as generate
    from research_loops.storage import Repository
    repo = Repository(example / ".rloop")
    try:
        typer.echo(str(generate(repo)))
    finally:
        repo.close()


@app.command()
def self_assess(project: Path, write: bool = False) -> None:
    """Print an offline evidence review; optionally save self-assessment.md."""
    from research_loops.assessment import assess
    from research_loops.paths import atomic_write
    from research_loops.domain import IntegrityError
    try:
        value = assess(project)
        if write:
            atomic_write(project / ".rloop" / "self-assessment.md", value.encode())
    except (IntegrityError, OSError) as exc:
        raise typer.BadParameter(str(exc)) from None
    typer.echo(value, nl=False)


@app.command()
def version() -> None:
    """Print the installed framework version."""
    typer.echo(__version__)


if __name__ == "__main__":
    app()
