"""Fail-closed OCI boundary. Runtime/SDK vendors do not define the policy."""
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from research_loops.domain import IntegrityError, canonical
from research_loops.paths import atomic_write, long_path, plain_io_errors, plain_path, refuse_link
from research_loops.transports.launch import Launch, local_launch, tool_environment


def _refuse_mount_link(path: Path) -> None:
    try:
        refuse_link(path)
    except IntegrityError as exc:
        raise IntegrityError("sandbox mount links forbidden") from exc


class NoneSandbox:
    image = None

    def tool_launch(self, contract, workspace, *, adapter=True):
        return local_launch(contract, workspace, adapter=adapter)

    def execute_candidate(self, *args, **kwargs):
        raise IntegrityError("none sandbox refuses candidate code execution")

    def cleanup(self, workspace):
        pass


@dataclass(frozen=True)
class Resources:
    pids: int = 64
    memory_mb: int = 256
    cpus: float = 1.0
    wall_seconds: float = 30

    def __post_init__(self):
        if not (8 <= self.pids <= 256 and 64 <= self.memory_mb <= 4096
                and 0 < self.cpus <= 4 and 0 < self.wall_seconds <= 300):
            raise IntegrityError("invalid sandbox resource limits")


class ContainerSandbox:
    def __init__(self, image: str, *, runtime="docker", resources=None):
        if runtime not in {"docker", "podman"}:
            raise IntegrityError("runtime must be docker or podman")
        if not re.fullmatch(r"(?:[a-zA-Z0-9./:_-]+@)?sha256:[0-9a-f]{64}", image):
            raise IntegrityError("sandbox image must be pinned by digest")
        self.image, self.runtime = image, runtime
        self.resources = resources or Resources()
        self.active = {}

    def cli(self, args, *, timeout=20):
        try:
            return subprocess.run([self.runtime, *args], capture_output=True, timeout=timeout, env=tool_environment())
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise IntegrityError("container runtime unavailable or timed out") from exc

    def available(self):
        result = self.cli(["info", "--format", "{{json .}}"])
        try:
            info = json.loads(result.stdout)
        except ValueError as exc:
            raise IntegrityError("a working Linux OCI runtime is required") from exc
        if result.returncode or info.get("OSType", info.get("host", {}).get("os")) != "linux":
            raise IntegrityError("a working Linux OCI runtime is required")

    @plain_io_errors()
    def host_path(self, path):
        # Only the disposable verification driver needs daemon/driver path translation.
        path = plain_path(long_path(Path(path)).resolve())
        driver = os.environ.get("RLOOP_DRIVER_ROOT")
        host = os.environ.get("RLOOP_DAEMON_ROOT")
        if driver and host and path.is_relative_to(Path(driver)):
            return host.rstrip("/") + "/" + path.relative_to(driver).as_posix()
        return str(path)

    @plain_io_errors()
    def command(self, name, workspace, public, *, holdout=None):
        # Check the folders as given: resolve() returns the link target, so a later check sees no link.
        workspace, public = Path(workspace), Path(public)
        _refuse_mount_link(workspace)
        _refuse_mount_link(public)
        workspace = plain_path(long_path(workspace).resolve())
        public = plain_path(long_path(public).resolve())
        if not long_path(workspace).is_dir() or not long_path(public).is_dir() or workspace == public or public.is_relative_to(workspace) or workspace.is_relative_to(public):
            raise IntegrityError("separate workspace/public directories required")
        uid = os.getuid() if hasattr(os, "getuid") and os.getuid() != 0 else 1000
        gid = os.getgid() if hasattr(os, "getgid") and os.getuid() != 0 else 1000
        args = [self.runtime, "run", "--rm", "-i", "--name", name,
            "--network", "none", "--user", f"{uid}:{gid}", "--read-only",
            "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=64m,mode=1777", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges", "--pids-limit", str(self.resources.pids),
            "--memory", f"{self.resources.memory_mb}m", "--memory-swap", f"{self.resources.memory_mb}m",
            "--cpus", str(self.resources.cpus), "--stop-timeout", "1", "--workdir", "/workspace",
            "--mount", f"type=bind,src={self.host_path(workspace)},dst=/workspace",
            "--mount", f"type=bind,src={self.host_path(public)},dst=/public,readonly",
            "--entrypoint", "/opt/venv/bin/python"]
        if holdout:
            args += ["--mount", f"type=bind,src={self.host_path(holdout)},dst=/holdout,readonly"]
        return args + [self.image]

    def remove(self, name):
        self.cli(["rm", "--force", name])
        check = self.cli(["inspect", name])
        missing = any(text in check.stderr.lower() for text in (b"no such", b"does not exist"))
        if check.returncode == 0 or not missing:
            raise IntegrityError("container process tree cleanup failed")

    def run_command(self, workspace, public, arguments, *, holdout=None, seconds=None):
        name = "rloop-" + uuid.uuid4().hex
        command = self.command(name, workspace, public, holdout=holdout) + arguments
        deadline = time.monotonic() + (seconds or self.resources.wall_seconds)
        process = None
        try:
            with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
                process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr, env=tool_environment())
                while process.poll() is None:
                    if time.monotonic() >= deadline:
                        raise IntegrityError("container wall-time limit exceeded")
                    if os.fstat(stdout.fileno()).st_size + os.fstat(stderr.fileno()).st_size > 1_000_000:
                        raise IntegrityError("container output quota exceeded")
                    time.sleep(0.02)
                stdout.seek(0)
                stderr.seek(0)
                output, error = stdout.read(1_000_001), stderr.read(1_000_001)
                if len(output) + len(error) > 1_000_000:
                    raise IntegrityError("container output quota exceeded")
                if process.returncode:
                    raise IntegrityError("container command failed: " + error[:1000].decode(errors="replace"))
                return output
        except OSError as exc:
            raise IntegrityError("container runtime unavailable") from exc
        finally:
            if process and process.poll() is None:
                process.kill()
                process.wait(timeout=10)
            self.remove(name)

    @plain_io_errors()
    def preflight(self, workspace, public, *, forbidden=()):
        self.available()
        probe = '''import json,os,pathlib,socket
assert os.getuid()!=0
for name in ["/holdout", "/evaluator", "/database", "/opt/venv/lib/python3.12/site-packages/research_loops/evaluation.py", *json.loads(os.environ.get("FORBIDDEN_PATHS","[]"))]:
    assert not pathlib.Path(name).exists(), name
for name in ["/escape", "/public/escape", "/opt/escape"]:
    try: pathlib.Path(name).write_text("escape")
    except OSError: pass
    else: raise AssertionError(name)
assert not any("API_KEY" in k or "TOKEN" in k or "SECRET" in k for k in os.environ)
assert not any(line.split()[1]=="00000000" for line in pathlib.Path("/proc/net/route").read_text().splitlines()[1:])
s=socket.socket(); s.settimeout(0.2)
try: s.connect(("1.1.1.1",443))
except OSError: pass
else: raise AssertionError("network available")
finally: s.close()
pathlib.Path("/workspace/preflight-write").write_text("ok")
print(json.dumps({"private_paths":True,"write_boundary":True,"network":True}))
'''
        # Embed only trusted coordinator paths in a probe, never environment credentials.
        probe = probe.replace('json.loads(os.environ.get("FORBIDDEN_PATHS","[]"))', repr([str(p) for p in forbidden]))
        result = json.loads(self.run_command(workspace, public, ["-I", "-c", probe]))
        try:
            self.run_command(workspace, public, ["-I", "-c", "import subprocess,time,pathlib; p=subprocess.Popen(['sleep','60']); pathlib.Path('/workspace/preflight-child').write_text(str(p.pid)); time.sleep(60)"], seconds=2)
        except IntegrityError as exc:
            if "wall-time limit" not in str(exc):
                raise
        else:
            raise IntegrityError("process cleanup probe did not time out")
        marker = Path(workspace) / "preflight-child"
        if not long_path(marker).exists():
            raise IntegrityError("cleanup probe never started a child")
        long_path(marker).unlink()
        long_path(Path(workspace) / "preflight-write").unlink()
        return {**result, "process_cleanup": True, "image": self.image}

    @plain_io_errors()
    def tool_launch(self, contract, workspace, *, adapter=True):
        # Check both mount folders before they are created or written; command() checks again.
        workspace = Path(workspace)
        _refuse_mount_link(workspace)
        workspace = plain_path(long_path(workspace).resolve())
        public = workspace.parent / "public"
        _refuse_mount_link(public)
        long_path(workspace).mkdir(parents=True, exist_ok=True)
        long_path(public).mkdir(exist_ok=True)
        # Root verification drivers must allow the required non-root container user.
        if hasattr(os, "getuid") and os.getuid() == 0:
            long_path(workspace).chmod(0o777)
        long_path(public).chmod(0o755)
        atomic_write(public / "worker-context.json", canonical(contract).encode())
        long_path(public / "worker-context.json").chmod(0o644)
        probes = self.preflight(workspace, public)
        atomic_write(workspace.parent / "sandbox-preflight.json", canonical(probes).encode())
        name = "rloop-" + uuid.uuid4().hex
        args = self.command(name, workspace, public) + ["-I", "-m", "research_loops.transports.server",
            "--context", "/public/worker-context.json", "--outbox", "/workspace", "--audit", "/workspace/tool-environment.json", "--shared-files", "--public", "/public"]
        if adapter:
            args += ["--adapter"]
        self.active[str(workspace)] = name
        config = workspace.parent / "sandbox-launch.json"
        atomic_write(config, canonical({"command": args, "seconds": self.resources.wall_seconds}).encode())
        return Launch(sys.executable, ["-I", "-m", "research_loops.container_stdio", str(config)], tool_environment(), image=self.image)

    @plain_io_errors()
    def cleanup(self, workspace):
        name = self.active.pop(str(plain_path(long_path(Path(workspace)).resolve())), None)
        if name:
            self.remove(name)

    def materialize(self, workspace):
        if os.name != "nt":
            return
        # Docker Desktop can give Linux-created NTFS files an unreadable Windows ACL.
        # Read through an equally restricted container, then publish host-owned bytes.
        # The import gate still validates every untrusted path/hash/schema afterwards.
        script = '''import base64,json,pathlib,stat
root=pathlib.Path('/workspace'); files=[]; total=0
for p in root.rglob('*'):
    mode=p.lstat().st_mode
    assert not stat.S_ISLNK(mode)
    if stat.S_ISDIR(mode): continue
    assert stat.S_ISREG(mode)
    total+=p.stat().st_size
    assert total<=600000 and len(files)<128
    files.append([p.relative_to(root).as_posix(),base64.b64encode(p.read_bytes()).decode()])
print(json.dumps(files))
'''
        import base64
        from research_loops.paths import confined
        workspace = Path(workspace)
        files = json.loads(self.run_command(workspace, workspace.parent / "public", ["-I", "-c", script]))
        for relative, encoded in files:
            path = confined(workspace, relative)
            atomic_write(path, base64.b64decode(encoded, validate=True))

    @plain_io_errors()
    def execute_candidate(self, workspace, public, holdout, *, relative="candidate.py"):
        from research_loops.paths import confined
        path = confined(Path(workspace), relative)
        if not long_path(path).is_file():
            raise IntegrityError("candidate file missing")
        self.preflight(workspace, public)
        # This is a different container from the worker. Host evaluator only parses output.
        output = self.run_command(workspace, public, ["-I", "/workspace/" + relative], holdout=holdout)
        try:
            return json.loads(output)
        except (ValueError, UnicodeError) as exc:
            raise IntegrityError("candidate must return bounded JSON predictions") from exc
