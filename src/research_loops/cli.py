"""Command-line entry point."""

import asyncio
from pathlib import Path

import typer

from research_loops import __version__

app = typer.Typer(no_args_is_help=True)


@app.callback()
def main() -> None:
    """Bounded offline research loops."""


@app.command()
def run(example: Path, backend: str = "fake", final: bool = False) -> None:
    """Run the offline planted-signal example."""
    if backend != "fake":
        from research_loops.execution import load_backend
        from research_loops.domain import IntegrityError
        try:
            selected = load_backend(backend, example)
        except IntegrityError as exc:
            raise typer.BadParameter(str(exc)) from exc
    else:
        selected = None
    from research_loops.coordinator import run as execute
    asyncio.run(execute(example, final=final, backend=selected))
    typer.echo(str(example / ".rloop" / "report.md"))


@app.command()
def init(example: Path, question: str = "Can we recover a planted nonlinear signal?") -> None:
    """Create a simulated scaffold and complete its first offline pilot."""
    from research_loops.domain import Contract, canonical
    from research_loops.paths import atomic_write
    from research_loops.coordinator import run as execute
    if not (example / "contract.json").exists():
        contract = Contract(goal=question, falsifier="The candidate fails the locked planted-signal criteria.",
            prediction="Uncertain; the negative control should fail and the planted oracle should pass.")
        atomic_write(example / "contract.json", canonical(contract).encode(), exclusive=True)
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
def version() -> None:
    """Print the installed framework version."""
    typer.echo(__version__)


if __name__ == "__main__":
    app()
