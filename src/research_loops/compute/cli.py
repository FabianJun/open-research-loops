"""CLI for explicit compute submissions and receipt-driven status/fetch."""

from pathlib import Path

import typer
from pydantic import ValidationError

from research_loops.compute import load_backend
from research_loops.compute.core import package, read_receipt
from research_loops.domain import IntegrityError, canonical


app = typer.Typer(no_args_is_help=True)


def selected(backend, kaggle_owner=None, command_config=None):
    if backend == "kaggle":
        if command_config is not None:
            raise IntegrityError("--command-config requires the command backend")
        return load_backend(backend, owner=kaggle_owner)
    if backend == "command":
        if kaggle_owner is not None:
            raise IntegrityError("--kaggle-owner requires the Kaggle backend")
        return load_backend(backend, config=command_config)
    if kaggle_owner is not None or command_config is not None:
        raise IntegrityError("backend options must match the selected backend")
    return load_backend(backend)


def execute(function):
    try:
        return function()
    except (IntegrityError, ValidationError, OSError, ValueError) as exc:
        # Never render pydantic input values (a private TOML may contain secrets).
        detail = "invalid compute contract/configuration" if isinstance(exc, ValidationError) else str(exc)
        raise typer.BadParameter(detail) from None


@app.command()
def check(backend: str = typer.Option(...), kaggle_owner: str | None = None,
        command_config: Path | None = None):
    """Check local prerequisites without contacting a host or opening credentials."""
    typer.echo(canonical(execute(lambda: selected(backend, kaggle_owner, command_config).check())))


@app.command()
def submit(job_dir: Path, backend: str = typer.Option(...), smoke: bool = False,
        kaggle_owner: str | None = None, command_config: Path | None = None):
    """Package code only and submit a trusted job to the explicitly chosen host."""
    receipt = execute(lambda: selected(backend, kaggle_owner, command_config).submit(package(job_dir), smoke))
    typer.echo(str(receipt.path))


@app.command()
def status(receipt: Path):
    """Refresh status using the backend recorded in a saved receipt."""
    def refresh():
        saved = read_receipt(receipt)
        return load_backend(saved.backend).status(saved)
    typer.echo(canonical(execute(refresh)))


@app.command()
def fetch(receipt: Path, out: Path | None = None):
    """Fetch every expected output and record its SHA-256 and size."""
    def download():
        saved = read_receipt(receipt)
        destination = out or Path(saved.job_dir) / "out/fetched" / saved.receipt_id
        return load_backend(saved.backend).fetch(saved, destination)
    typer.echo(canonical(execute(download)))
