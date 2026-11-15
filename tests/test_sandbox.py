import asyncio
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from research_loops.domain import IntegrityError, Limits, Workspace
from research_loops.sandbox import ContainerSandbox, NoneSandbox
from test_mcp import task


def test_none_refuses_code():
    with pytest.raises(IntegrityError, match="refuses candidate code"):
        NoneSandbox().execute_candidate("anything")


def test_requires_digest_and_runtime():
    with pytest.raises(IntegrityError, match="digest"):
        ContainerSandbox("image:latest")
    with pytest.raises(IntegrityError, match="runtime"):
        ContainerSandbox("sha256:" + "a" * 64, runtime="bash")


@pytest.mark.parametrize("runtime", ["docker", "podman"])
def test_shared_oci_flags(runtime, tmp_path):
    workspace, public = tmp_path / "workspace", tmp_path / "public"
    workspace.mkdir()
    public.mkdir()
    sandbox = ContainerSandbox("sha256:" + "a" * 64, runtime=runtime)
    command = sandbox.command("test", workspace, public)
    assert command[:4] == [runtime, "run", "--rm", "-i"]
    for flag, value in [("--network", "none"), ("--cap-drop", "ALL"), ("--security-opt", "no-new-privileges"),
                        ("--pids-limit", "64"), ("--memory", "256m"), ("--cpus", "1.0")]:
        assert command[command.index(flag) + 1] == value
    assert "--read-only" in command and "--tmpfs" in command
    assert not command[command.index("--user") + 1].startswith("0:")
    assert sum(arg.startswith("type=bind,") for arg in command) == 2
    assert any(arg.endswith("dst=/public,readonly") for arg in command)


def test_missing_runtime_blocks(monkeypatch):
    sandbox = ContainerSandbox("sha256:" + "a" * 64)
    def unavailable(*args, **kwargs):
        raise FileNotFoundError("runtime missing")
    monkeypatch.setattr(subprocess, "run", unavailable)
    with pytest.raises(IntegrityError, match="unavailable"):
        sandbox.available()


@pytest.fixture(scope="session")
def sandbox_image(tmp_path_factory):
    if os.name == "nt" and os.environ.get("GITHUB_ACTIONS"):
        pytest.skip("GitHub Windows runners cannot run Linux containers; Linux CI runs the container contract")
    runtime = os.environ.get("RLOOP_TEST_RUNTIME", "docker")
    if not shutil.which(runtime):
        if os.environ.get("GITHUB_ACTIONS"):
            pytest.fail("Linux CI must provide its required OCI runtime")
        pytest.skip("Linux container integration requires docker/podman CLI; use Linux CI or Docker Desktop locally")
    image = os.environ.get("RLOOP_SANDBOX_IMAGE")
    if not image:
        output = tmp_path_factory.mktemp("image") / "iid"
        built = subprocess.run([runtime, "build", "--file", "Containerfile", "--iidfile", str(output), "."], capture_output=True)
        assert built.returncode == 0, built.stderr.decode(errors="replace")
        image = output.read_text().strip()
    return image


@pytest.fixture
def container(sandbox_image):
    return ContainerSandbox(sandbox_image, runtime=os.environ.get("RLOOP_TEST_RUNTIME", "docker"))


def folders(tmp_path):
    workspace, public = tmp_path / "workspace", tmp_path / "public"
    workspace.mkdir(mode=0o777)
    workspace.chmod(0o777)
    public.mkdir(mode=0o755)
    (public / "input.json").write_text("[1,2]")
    return workspace, public


@pytest.mark.container
def test_real_preflight_and_candidate_boundary(container, tmp_path):
    workspace, public = folders(tmp_path)
    forbidden = tmp_path / "private"
    forbidden.mkdir()
    (forbidden / "secret").write_text("private")
    probes = container.preflight(workspace, public, forbidden=[forbidden])
    assert all(probes[name] for name in ("private_paths", "write_boundary", "network", "process_cleanup"))
    # Evaluator container gets holdout read-only; the host never loads candidate code.
    (workspace / "candidate.py").write_text('''import json,pathlib
data=json.loads(pathlib.Path('/holdout/input.json').read_text())
try: pathlib.Path('/holdout/changed').write_text('bad')
except OSError: pass
else: raise AssertionError('holdout writable')
print(json.dumps([x*2 for x in data]))
''')
    holdout = tmp_path / "holdout"
    holdout.mkdir()
    (holdout / "input.json").write_text("[1,2]")
    assert container.execute_candidate(workspace, public, holdout) == [2, 4]
    assert not (holdout / "changed").exists()


@pytest.mark.container
@pytest.mark.parametrize("name", ["fake", "openai_agents", "claude_agent"])
def test_shared_container_isolation(name, container, tmp_path):
    from test_backends import backend
    if name == "fake":
        from research_loops.adapters.mcp_fake import MCPFakeBackend
        worker = MCPFakeBackend(sandbox=container)
    else:
        worker = backend(name)
        worker.sandbox = container
    workspace = Workspace(root=tmp_path / "run" / "outbox")
    report = asyncio.run(worker.run(task(), workspace, Limits(worker_seconds=60)))
    assert report.sandbox_image == container.image
    assert report.cost_micro_usd == (0 if name == "fake" else None)
    assert not container.active
    probes = json.loads((workspace.root.parent / "sandbox-preflight.json").read_bytes())
    assert probes["process_cleanup"] and probes["network"]
    audit = json.loads((workspace.root / "tool-environment.json").read_bytes())
    assert not any("API_KEY" in key or "SECRET" in key or "TOKEN" in key for key in audit["environment_keys"])
    assert (workspace.root / "report.json").is_file()


def test_probe_failure_blocks_launch(monkeypatch, tmp_path):
    sandbox = ContainerSandbox("sha256:" + "a" * 64)
    def refusal(*args, **kwargs):
        raise IntegrityError("probe failed")
    monkeypatch.setattr(sandbox, "preflight", refusal)
    with pytest.raises(IntegrityError, match="probe failed"):
        sandbox.tool_launch(task(), tmp_path / "outbox")
    assert not sandbox.active


def test_cleanup_refuses_unknown_daemon_state(monkeypatch):
    from types import SimpleNamespace
    sandbox = ContainerSandbox("sha256:" + "a" * 64)
    monkeypatch.setattr(sandbox, "cli", lambda *args, **kwargs: SimpleNamespace(returncode=1, stderr=b"Cannot connect to daemon"))
    with pytest.raises(IntegrityError, match="cleanup failed"):
        sandbox.remove("rloop-disposable")


@pytest.mark.container
def test_container_pilot_records_digest(container, example):
    from research_loops.adapters.mcp_fake import MCPFakeBackend
    from research_loops.coordinator import run
    from research_loops.storage import Repository
    path = example / "contract.json"
    contract = json.loads(path.read_bytes())
    contract.setdefault("limits", {})["worker_seconds"] = 60
    path.write_text(json.dumps(contract))
    asyncio.run(run(example, backend=MCPFakeBackend(sandbox=container), pilot_only=True))
    repo = Repository(example / ".rloop")
    try:
        assert len(repo.runs()) == 2
        for row in repo.runs():
            assert row["execution_status"] == "completed"
            assert json.loads(row["execution_metadata"])["sandbox_image"] == container.image
            assert json.loads(row["report"])["sandbox_image"] == container.image
    finally:
        repo.close()
