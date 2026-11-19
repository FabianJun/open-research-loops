"""Trusted dispatch metadata and lazy backend selection; no SDK imports."""

from importlib.metadata import version
from pathlib import Path

from research_loops.paths import long_path, plain_io_errors
from research_loops.domain import IntegrityError


def backend_record(backend) -> tuple[dict, int]:
    name = getattr(backend, "name", "fake")
    sdk = {"openai_agents": "openai-agents", "claude_agent": "claude-agent-sdk"}.get(name)
    approval = backend.check_authorization() if hasattr(backend, "check_authorization") else None
    reserve = approval.cap_micro_usd if approval else None
    record = {"backend": name, "provider": getattr(backend, "provider", "offline"),
        "model": getattr(backend, "model", "deterministic-v1"), "sdk_version": version(sdk) if sdk else None,
        "cost_micro_usd": 0 if name == "fake" else None,
        "sandbox_image": getattr(getattr(backend, "sandbox", None), "image", None),
        "authorization_cap_micro_usd": reserve,
        "mode": "offline_seam" if getattr(backend, "offline", False) else ("offline" if name == "fake" else "checkpoint_b")}
    if name != "fake":
        record.update(auth_mode=getattr(backend, "auth_mode", None), effort=getattr(backend, "effort", None),
            cost_is_estimate=True, usage=None, run_limits=approval.run_limits.model_dump() if approval else None)
    return record, reserve or 0


@plain_io_errors()
def load_backend(name: str, project: Path):
    import json
    path = project / "project.json"
    config = json.loads(long_path(path).read_bytes()) if long_path(path).is_file() else {}
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
    provider = {"openai_agents": "openai", "claude_agent": "anthropic"}.get(name)
    if provider is None:
        raise IntegrityError("unknown backend")
    value = config.get("checkpoint_b", {})
    if "backends" in value:
        value = value["backends"].get(provider, {})
    model = value.get("model", "")
    approval = authorize(project, provider, model)
    if name == "openai_agents":
        from research_loops.adapters.openai_agents import OpenAIBackend
        return OpenAIBackend(model, project=project, sandbox=sandbox, auth_mode=approval.auth_mode, effort=approval.effort)
    from research_loops.adapters.claude_agent import ClaudeBackend
    return ClaudeBackend(model, project=project, sandbox=sandbox, auth_mode=approval.auth_mode, effort=approval.effort)
