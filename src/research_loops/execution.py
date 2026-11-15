"""Trusted dispatch metadata and lazy backend selection; no SDK imports."""

from importlib.metadata import version
from pathlib import Path

from research_loops.domain import IntegrityError


def backend_record(backend) -> tuple[dict, int]:
    name = getattr(backend, "name", "fake")
    sdk = {"openai_agents": "openai-agents", "claude_agent": "claude-agent-sdk"}.get(name)
    reserve = backend.check_authorization() if hasattr(backend, "check_authorization") else 0
    return {"backend": name, "provider": getattr(backend, "provider", "offline"),
        "model": getattr(backend, "model", "deterministic-v1"), "sdk_version": version(sdk) if sdk else None,
        "cost_micro_usd": 0 if name == "fake" else None,
        "sandbox_image": getattr(getattr(backend, "sandbox", None), "image", None),
        "authorization_cap_micro_usd": reserve,
        "mode": "offline_seam" if getattr(backend, "offline", False) else ("offline" if name == "fake" else "checkpoint_b")}, reserve or 0


def load_backend(name: str, project: Path):
    import json
    path = project / "project.json"
    config = json.loads(path.read_bytes()) if path.is_file() else {}
    settings = config.get("sandbox", {"name": "none"})
    from research_loops.sandbox import NoneSandbox, ContainerSandbox
    if settings.get("name") == "container":
        sandbox = ContainerSandbox(settings.get("image", ""), runtime=settings.get("runtime", "docker"))
    elif settings.get("name") == "none":
        sandbox = NoneSandbox()
    else:
        raise IntegrityError("unknown sandbox")
    if name == "fake":
        if settings.get("name") == "container":
            from research_loops.adapters.mcp_fake import MCPFakeBackend
            return MCPFakeBackend(sandbox=sandbox)
        from research_loops.fake import FakeBackend
        return FakeBackend()
    # Gate before importing optional adapter modules or looking at credentials.
    from research_loops.authorization import authorize
    model = config.get("checkpoint_b", {}).get("model", "")
    provider = {"openai_agents": "openai", "claude_agent": "anthropic"}.get(name)
    if provider is None:
        raise IntegrityError("unknown backend")
    authorize(project, provider, model)
    if name == "openai_agents":
        from research_loops.adapters.openai_agents import OpenAIBackend
        return OpenAIBackend(model, project=project, sandbox=sandbox)
    from research_loops.adapters.claude_agent import ClaudeBackend
    return ClaudeBackend(model, project=project, sandbox=sandbox)
