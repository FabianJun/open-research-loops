"""Explicit user-invoked auth commands. Importing this module does not sign in."""

import typer

app = typer.Typer(no_args_is_help=True)


@app.command()
def preflight(backend: str = "claude_agent", auth_mode: str | None = None):
    """Report configured mode offline; never inspect credential files."""
    modes = {"claude_agent": ("claude_code", "api_key"), "openai_agents": ("chatgpt", "api_key")}
    if backend not in modes or (auth_mode and auth_mode not in modes[backend]):
        raise typer.BadParameter("unknown backend/auth mode")
    mode = auth_mode or modes[backend][0]
    typer.echo(f"{backend}: configured auth_mode={mode}. Login/entitlement not checked; no network or credential files read.")


@app.command("login-openai")
def login_openai(account: str | None = None):
    """Continue with ChatGPT in the system browser (user action required)."""
    from research_loops.openai_auth import ChatGPTAuth, AuthError, login
    try:
        typer.echo("Continue with ChatGPT. Complete sign-in in your system browser.")
        label = login(ChatGPTAuth(), account=account)
        typer.echo(f"Active account registration: {label}. No inference was requested.")
    except AuthError as exc:
        raise typer.BadParameter(str(exc)) from None


@app.command()
def accounts(select: str | None = None):
    """List opaque registration labels or select one; never display tokens."""
    from research_loops.openai_auth import TokenStore, AuthError
    try:
        store = TokenStore()
        if select:
            store.select(select)
        for label, active in store.accounts():
            typer.echo(f"{label}{' (active)' if active else ''}")
    except AuthError as exc:
        raise typer.BadParameter(str(exc)) from None


@app.command()
def models():
    """Fetch only models listed for the active ChatGPT account; no inference."""
    from research_loops.openai_auth import ChatGPTAuth, AuthError
    try:
        for model in ChatGPTAuth().models():
            typer.echo(f"{model['slug']}\t{model['display_name']}")
    except AuthError as exc:
        raise typer.BadParameter(str(exc)) from None
