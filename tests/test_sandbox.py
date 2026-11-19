import asyncio
import json
import os
import shutil
import subprocess
import sys
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


def test_sandbox_refuses_linked_folders(monkeypatch, tmp_path):
    def linked(path):
        if os.name == "nt":
            import _winapi
            _winapi.CreateJunction(str(target), str(path))
        else:
            path.symlink_to(target, target_is_directory=True)
        return path

    target, workspace, public = tmp_path / "target", tmp_path / "workspace", tmp_path / "inputs"
    for folder in (target, workspace, public):
        folder.mkdir()
    link = linked(tmp_path / "linked")

    sandbox = ContainerSandbox("sha256:" + "a" * 64)
    with pytest.raises(IntegrityError, match="links forbidden"):
        sandbox.command("test", link, public)
    with pytest.raises(IntegrityError, match="links forbidden"):
        sandbox.command("test", workspace, link)

    def unexpected(*args, **kwargs):
        pytest.fail("launch preparation ran for a linked folder")

    monkeypatch.setattr(sandbox, "preflight", unexpected)
    monkeypatch.setattr(Path, "chmod", unexpected)
    siblings = set(tmp_path.iterdir())
    with pytest.raises(IntegrityError, match="links forbidden"):
        sandbox.tool_launch(task(), link)
    assert not list(target.iterdir())
    assert set(tmp_path.iterdir()) == siblings
    (tmp_path / "launch").mkdir()
    linked(tmp_path / "launch" / "public")
    with pytest.raises(IntegrityError, match="links forbidden"):
        sandbox.tool_launch(task(), tmp_path / "launch" / "outbox")
    assert not list(target.iterdir())
    assert not (tmp_path / "launch" / "outbox").exists()


def test_missing_runtime_blocks(monkeypatch):
    sandbox = ContainerSandbox("sha256:" + "a" * 64)
    def unavailable(*args, **kwargs):
        raise FileNotFoundError("runtime missing")
    monkeypatch.setattr(subprocess, "run", unavailable)
    with pytest.raises(IntegrityError, match="unavailable"):
        sandbox.available()


@pytest.fixture(scope="session")
def sandbox_image(tmp_path_factory):
    in_ci = "GITHUB_ACTIONS" in os.environ
    if in_ci and not sys.platform.startswith("linux"):
        pytest.skip("GitHub macOS and Windows runners provide no Linux OCI runtime; Linux CI runs the container contract")
    runtime = os.environ.get("RLOOP_TEST_RUNTIME", "docker")
    if not shutil.which(runtime):
        if in_ci:
            pytest.fail("Linux CI must provide its required OCI runtime")
        pytest.skip("Linux container integration requires docker/podman CLI; use Linux CI or Docker Desktop locally")
    # Probe only locally so an unreachable daemon still fails the container contract in CI.
    # With host-configured socket activation, any client call (probe or build) can start the engine. The tests start nothing themselves.
    if not in_ci:
        try:
            daemon_reachable = subprocess.run([runtime, "info"], capture_output=True, timeout=15).returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            daemon_reachable = False
        if not daemon_reachable:
            pytest.skip(
                f"{runtime} CLI found but its daemon is not reachable; "
                "start it to run the container tests locally (the tests do not start it)"
            )
    image = os.environ.get("RLOOP_SANDBOX_IMAGE")
    # Opt-in for offline local runs only. CI ignores it and keeps building and running the contract.
    if os.environ.get("RLOOP_TEST_NO_CONTAINER_BUILD") == "1" and not in_ci:
        if not image:
            pytest.skip("offline container tests require an already-local RLOOP_SANDBOX_IMAGE; no build or pull")
        local = subprocess.run([runtime, "image", "inspect", image], capture_output=True)
        if local.returncode != 0:
            pytest.skip("offline sandbox image is not local; no build or pull")
    if not image:
        output = tmp_path_factory.mktemp("image") / "iid"
        built = subprocess.run([runtime, "build", "--file", "Containerfile", "--iidfile", str(output), "."], capture_output=True)
        assert built.returncode == 0, built.stderr.decode(errors="replace")
        image = output.read_text().strip()
    return image


@pytest.mark.parametrize("github_actions", ["true", ""], ids=["ci", "empty-ci-value"])
@pytest.mark.parametrize("platform,exception,message", [
    ("darwin", pytest.skip.Exception, "no Linux OCI runtime"),
    ("win32", pytest.skip.Exception, "no Linux OCI runtime"),
    ("linux", pytest.fail.Exception, "Linux CI must provide its required OCI runtime"),
])
def test_ci_container_fixture_without_runtime(monkeypatch, tmp_path_factory, platform, exception, message, github_actions):
    monkeypatch.setenv("GITHUB_ACTIONS", github_actions)
    monkeypatch.setattr(sys, "platform", platform)
    monkeypatch.setattr(shutil, "which", lambda runtime: None)
    with pytest.raises(exception, match=message):
        sandbox_image.__wrapped__(tmp_path_factory)


@pytest.mark.parametrize("error", [
    None,
    subprocess.TimeoutExpired(["podman", "info"], 15),
    OSError("runtime unavailable"),
], ids=["nonzero-exit", "timeout", "os-error"])
def test_local_container_fixture_skips_unreachable_daemon(monkeypatch, tmp_path_factory, error):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setenv("RLOOP_TEST_RUNTIME", "podman")
    monkeypatch.setenv("RLOOP_TEST_NO_CONTAINER_BUILD", "1")
    monkeypatch.setenv("RLOOP_SANDBOX_IMAGE", "sha256:local-test")
    monkeypatch.setattr(shutil, "which", lambda runtime: runtime)
    calls = []

    def failed_info(argv, **kwargs):
        calls.append(argv)
        assert kwargs == {"capture_output": True, "timeout": 15}
        if error is not None:
            raise error
        return subprocess.CompletedProcess(argv, 1)

    monkeypatch.setattr(subprocess, "run", failed_info)
    with pytest.raises(pytest.skip.Exception, match="podman CLI found but its daemon is not reachable"):
        sandbox_image.__wrapped__(tmp_path_factory)
    assert calls == [["podman", "info"]]


def test_local_container_fixture_fails_build_after_daemon_probe(monkeypatch, tmp_path_factory):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("RLOOP_TEST_NO_CONTAINER_BUILD", raising=False)
    monkeypatch.delenv("RLOOP_SANDBOX_IMAGE", raising=False)
    monkeypatch.setattr(shutil, "which", lambda runtime: runtime)
    calls = []

    def failed_build(argv, **kwargs):
        calls.append(argv[1])
        if argv[1] == "info":
            return subprocess.CompletedProcess(argv, 0)
        return subprocess.CompletedProcess(argv, 1, stderr=b"build failed")

    monkeypatch.setattr(subprocess, "run", failed_build)
    with pytest.raises(AssertionError, match="build failed"):
        sandbox_image.__wrapped__(tmp_path_factory)
    assert calls == ["info", "build"]


@pytest.mark.parametrize("image,local", [(None, False), ("sha256:local-test", False), ("sha256:local-test", True)])
def test_offline_container_fixture_never_builds_or_pulls(monkeypatch, tmp_path_factory, image, local):
    from types import SimpleNamespace
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setenv("RLOOP_TEST_NO_CONTAINER_BUILD", "1")
    if image:
        monkeypatch.setenv("RLOOP_SANDBOX_IMAGE", image)
    else:
        monkeypatch.delenv("RLOOP_SANDBOX_IMAGE", raising=False)
    monkeypatch.setattr(shutil, "which", lambda runtime: "/local/docker")
    calls = []
    def run(argv, **kwargs):
        args = argv[1:]
        calls.append(args)
        if args == ["info"]:
            return SimpleNamespace(returncode=0)
        assert args == ["image", "inspect", image]
        return SimpleNamespace(returncode=0 if local else 1)
    monkeypatch.setattr(subprocess, "run", run)
    if local:
        assert sandbox_image.__wrapped__(tmp_path_factory) == image
    else:
        with pytest.raises(pytest.skip.Exception, match="no build or pull"):
            sandbox_image.__wrapped__(tmp_path_factory)
    assert calls == ([["info"], ["image", "inspect", image]] if image else [["info"]])


@pytest.mark.parametrize("github_actions", ["true", ""], ids=["ci", "empty-ci-value"])
@pytest.mark.parametrize("image", ["sha256:local-test", None], ids=["given-image", "build"])
def test_ci_container_fixture_ignores_offline_opt_in(monkeypatch, tmp_path_factory, image, github_actions):
    from types import SimpleNamespace

    monkeypatch.setenv("GITHUB_ACTIONS", github_actions)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(shutil, "which", lambda runtime: "/local/docker")
    monkeypatch.setenv("RLOOP_TEST_NO_CONTAINER_BUILD", "1")
    if image:
        monkeypatch.setenv("RLOOP_SANDBOX_IMAGE", image)
    else:
        monkeypatch.delenv("RLOOP_SANDBOX_IMAGE", raising=False)

    calls = []

    def failed_build(argv, **kwargs):
        calls.append(argv)
        return SimpleNamespace(returncode=1, stderr=b"fake")

    monkeypatch.setattr(subprocess, "run", failed_build)
    if image:
        assert sandbox_image.__wrapped__(tmp_path_factory) == image
        assert not calls
    else:
        with pytest.raises(AssertionError, match="fake"):
            sandbox_image.__wrapped__(tmp_path_factory)
        assert [argv[1] for argv in calls] == ["build"]


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
