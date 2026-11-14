"""Command-line entry point."""

import typer

from research_loops import __version__

app = typer.Typer(no_args_is_help=True)


@app.command()
def version() -> None:
    """Print the installed framework version."""
    typer.echo(__version__)
