"""Compute adapters exercised offline with fake processes and synthetic outputs."""

from datetime import datetime, timedelta
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

from pydantic import ValidationError
import pytest
from typer.testing import CliRunner

from research_loops.cli import app
from research_loops.compute import load_backend
from research_loops.compute import core
from research_loops.compute.command import CommandConfig, substitute
from research_loops.compute.core import JobSpec, package, read_receipt
from research_loops.compute.kaggle import KaggleBackend, parse_status
from research_loops.compute.local import LocalBackend
from research_loops.compute.manual import ManualBackend
from research_loops.domain import IntegrityError, canonical, digest


def result(stdout="", returncode=0, stderr=""):
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)


@pytest.fixture
def job_dir(tmp_path):
    directory = tmp_path / "job with spaces"
    directory.mkdir()
    (directory / "entry.py").write_text('"""Synthetic job."""\nfrom __future__ import annotations\n'
        'import sys\nSEEN_ARGS = list(sys.argv)\n', encoding="utf-8")
    spec = dict(name="tiny-job", entry="entry.py", args=["--value", "two words; $(not-a-shell)"],
        smoke_args=["--smoke"], needs_gpu=True, needs_internet=False, max_runtime_s=20,
        outputs=["result.json", "labels.npz"],
        data=[dict(url="https://example.invalid/data.zip", size=100, sha256="a" * 64)])
    (directory / "job.json").write_text(json.dumps(spec), encoding="utf-8")
    return directory


@pytest.fixture
def command_config(tmp_path):
    path = tmp_path / "host.compute.local.toml"
    path.write_text('''submit = ["submit-tool", "{staging}", "{name}", "; no shell"]
status = ["status-tool", "{remote_id}"]
fetch = ["fetch-tool", "{remote_id}", "{out_dir}"]
remote_id_regex = 'JOB_ID=([a-z0-9-]+)'
[status_map]
'^WAITING$' = "queued"
'^ACTIVE$' = "running"
'^DONE$' = "complete"
'^BROKEN$' = "failed"
'^STOPPED$' = "cancelled"
''', encoding="utf-8")
    return path


def outputs(directory):
    directory.mkdir(parents=True, exist_ok=True)
    for name, data in (("result.json", b'{"ok":true}\n'), ("labels.npz", b"synthetic array bytes")):
        (directory / name).write_bytes(data)


@pytest.mark.parametrize("change", [
    {"unknown": 1}, {"is_private": False}, {"name": "Bad Name"}, {"entry": "../entry.py"},
    {"entry": "helper/entry.py"}, {"entry": "entry.sh"}, {"needs_gpu": 1},
    {"needs_internet": "true"}, {"max_runtime_s": True}, {"max_runtime_s": "20"},
    {"max_runtime_s": 0}, {"args": [1]}, {"args": ["--output-dir", "elsewhere"]},
    {"smoke_args": ["--output-dir=elsewhere"]}, {"outputs": []},
    {"outputs": ["../result.json"]}, {"outputs": ["A.json", "a.json"]},
    {"data": [{"url": "file:///data.zip", "size": 1, "sha256": "a" * 64}]},
    {"data": [{"url": "https://example.invalid", "size": 1, "sha256": "a" * 64, "extra": 1}]},
])
def test_compute_strict_contract(job_dir, change):
    spec = json.loads((job_dir / "job.json").read_bytes())
    with pytest.raises(ValidationError):
        JobSpec.model_validate({**spec, **change})


@pytest.mark.parametrize("name", [
    "mask.png", "image.JPG", "a.jpeg", "a.tif", "a.tiff", "a.bmp", "labels.npz", "a.npy",
    "data.zip", "data.tar.gz", "data.7z", "data.rar", "data.tar.xz", "data.whl", "image.png.txt",
    ".rloop/secret.py",
])
def test_compute_packaging_refuses_data(job_dir, name):
    path = job_dir / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"synthetic forbidden package input")
    with pytest.raises(IntegrityError, match="cannot be packaged"):
        package(job_dir)


@pytest.mark.parametrize("kind", ["is_symlink", "is_junction"])
def test_compute_packaging_refuses_links(job_dir, monkeypatch, kind):
    target = job_dir / "linked.py"
    target.write_text("pass\n", encoding="utf-8")
    original = getattr(Path, kind)
    monkeypatch.setattr(Path, kind, lambda self: self == target or original(self))
    with pytest.raises(IntegrityError, match="symlinks or junctions"):
        package(job_dir)


def test_compute_package_limit_before_read(job_dir, monkeypatch):
    oversized = job_dir / "large.py"
    oversized.write_bytes(b" " * 5_000_001)
    original = Path.read_bytes

    def guarded(path):
        assert path != oversized, "oversized file was read"
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", guarded)
    with pytest.raises(IntegrityError, match="5 MB"):
        package(job_dir)


def test_compute_package_total_limit(job_dir):
    (job_dir / "first.py").write_bytes(b" " * 2_600_000)
    (job_dir / "second.py").write_bytes(b" " * 2_600_000)
    with pytest.raises(IntegrityError, match="5 MB"):
        package(job_dir)


def test_compute_hash_and_output_exclusion(job_dir, monkeypatch):
    before = package(job_dir)
    spec = json.loads((job_dir / "job.json").read_bytes())
    (job_dir / "job.json").write_text(json.dumps(spec, indent=4), encoding="utf-8")
    outputs(job_dir / "out")
    original = Path.read_bytes

    def guarded(path):
        assert not path.is_relative_to(job_dir / "out"), "output data entered a package"
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", guarded)
    assert package(job_dir).sha256 == before.sha256
    (job_dir / "helper.py").write_text("pass\n", encoding="utf-8")
    assert package(job_dir).sha256 != before.sha256
    changed = package(job_dir).sha256
    (job_dir / "helper.py").rename(job_dir / "renamed.py")
    assert package(job_dir).sha256 != changed


def test_compute_local_round_trip(job_dir):
    calls = []

    def fake(argv, **kwargs):
        calls.append(argv)
        assert argv[0] == sys.executable
        assert argv[-2] == "--output-dir"
        assert argv[2:-2] == ["--value", "two words; $(not-a-shell)", "--smoke"]
        assert kwargs["timeout"] == 20 and "shell" not in kwargs
        assert Path(argv[1]).parent == kwargs["cwd"]
        assert kwargs["cwd"] != job_dir
        assert kwargs["env"]["RLOOP_OUTPUT_DIR"] == argv[-1]
        outputs(Path(argv[-1]))
        return result("finished")

    backend = LocalBackend(run=fake)
    job = package(job_dir)
    receipt = backend.submit(job, smoke=True)
    assert receipt.status == "complete" and len(calls) == 1
    assert [event.status for event in receipt.history] == ["queued", "running", "complete"]
    assert backend.check()["ready"]
    fetched = backend.fetch(receipt, job_dir / "out/fetched")
    assert fetched.job_sha256 == job.sha256
    assert fetched.job.data[0].sha256 == "a" * 64
    for name, fact in fetched.outputs.items():
        raw = (Path(fetched.fetched_dir) / name).read_bytes()
        assert fact.sha256 == digest(raw) and fact.size == len(raw)
    assert datetime.fromisoformat(fetched.created_at).utcoffset() == timedelta(0)
    assert read_receipt(fetched.path) == fetched
    assert backend.status(fetched).status == "complete"


@pytest.mark.parametrize("failure", ["timeout", "nonzero", "oserror"])
def test_compute_local_failure(job_dir, failure):
    def fake(argv, **kwargs):
        if failure == "timeout":
            raise subprocess.TimeoutExpired(argv, kwargs["timeout"])
        if failure == "oserror":
            raise FileNotFoundError("missing interpreter")
        return result("bad", returncode=2)

    receipt = LocalBackend(run=fake).submit(package(job_dir))
    assert receipt.status == "failed"
    assert read_receipt(receipt.path) == receipt


def test_compute_kaggle_staging(job_dir, monkeypatch):
    original = {path.name: path.read_bytes() for path in job_dir.iterdir()}
    captured = {}

    def fake(argv, **kwargs):
        assert argv[:4] == ["kaggle", "kernels", "push", "-p"]
        staging = Path(argv[4])
        captured["staging"] = staging
        metadata = json.loads((staging / "kernel-metadata.json").read_bytes())
        assert metadata["is_private"] is True
        assert metadata["enable_gpu"] is True and metadata["enable_internet"] is False
        assert metadata["id"] == "private-owner/tiny-job-smoke"
        assert metadata["kernel_type"] == "script" and metadata["language"] == "python"
        assert metadata["code_file"] == "entry.py" and metadata["dataset_sources"] == []
        source = (staging / "entry.py").read_text(encoding="utf-8")
        assert "private-owner" not in source
        namespace = {}
        exec(compile(source, "entry.py", "exec"), namespace)
        assert namespace["SEEN_ARGS"] == ["entry.py", "--value", "two words; $(not-a-shell)", "--smoke"]
        import os
        assert os.environ["RLOOP_OUTPUT_DIR"] == "/kaggle/working"
        return result("submitted")

    monkeypatch.setenv("RLOOP_OUTPUT_DIR", "before")
    monkeypatch.setattr(sys, "argv", ["before"])
    monkeypatch.setenv("RLOOP_KAGGLE_OWNER", "private-owner")
    receipt = KaggleBackend(run=fake).submit(package(job_dir), smoke=True)
    assert receipt.remote_id == "private-owner/tiny-job-smoke"
    assert not captured["staging"].exists()
    for name, raw in original.items():
        assert (job_dir / name).read_bytes() == raw
    assert not (job_dir / "kernel-metadata.json").exists()
    assert receipt.path.is_relative_to(job_dir / "out")
    with pytest.raises(IntegrityError, match="private"):
        KaggleBackend(is_private=False)


@pytest.mark.parametrize("raw, expected", [
    ('user/job has status "complete"', "complete"), ("Kernel status: RUNNING", "running"),
    ("queued", "queued"), ("error", "failed"), ("cancelled", "cancelled"),
    ("canceled", "cancelled"), ("Completed", "complete"),
    ("completed request but status not available", "unknown"), ("unexpected reply", "unknown"),
    ('user/job has status "KernelWorkerStatus.COMPLETE"', "complete"),
    ('user/job has status "KernelWorkerStatus.RUNNING"', "running"),
    ('user/job has status "KernelWorkerStatus.NEW_SCRIPT"', "queued"),
    ('user/job has status "KernelWorkerStatus.CANCEL_ACKNOWLEDGED"', "cancelled"),
    ('user/job has status "KernelWorkerStatus.ERROR"\nFailure message: "boom"', "failed"),
    ('user/job has status "KernelWorkerStatus.SOMETHING_NEW"', "unknown"),
])
def test_compute_kaggle_status_mapping(raw, expected):
    assert parse_status(raw) == expected


def test_compute_kaggle_status_and_fetch(job_dir):
    def fake(argv, **kwargs):
        if argv[2] == "status":
            return result("an unfamiliar status response")
        if argv[2] == "output":
            outputs(Path(argv[-1]))
        return result()

    backend = KaggleBackend(owner="private-owner", run=fake)
    receipt = backend.submit(package(job_dir))
    updated = backend.status(receipt)
    assert updated.status == "unknown"
    assert updated.history[-1].raw == "an unfamiliar status response"
    fetched = backend.fetch(updated, job_dir / "out/fetched")
    assert set(fetched.outputs) == {"result.json", "labels.npz"}


@pytest.mark.parametrize("credential", ["env", "access_token", "kaggle.json", "none"])
def test_compute_kaggle_check_never_reads_credentials(tmp_path, monkeypatch, credential):
    import os
    import research_loops.compute.kaggle as module
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(module.shutil, "which", lambda _: "kaggle")
    monkeypatch.delenv("KAGGLE_API_TOKEN", raising=False)
    if credential == "env":
        monkeypatch.setenv("KAGGLE_API_TOKEN", "secret-never-read")
    elif credential != "none":
        path = tmp_path / ".kaggle" / credential
        path.parent.mkdir()
        path.write_text("secret-never-read", encoding="utf-8")

    def forbidden(*args, **kwargs):
        pytest.fail("credential file was opened")

    original = type(os.environ).__getitem__

    def env_guard(self, name):
        if name == "KAGGLE_API_TOKEN":
            pytest.fail("credential value was read")
        return original(self, name)

    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(type(os.environ), "__getitem__", env_guard)
    check = KaggleBackend().check()
    assert check["credentials_present"] == (credential != "none")
    assert "secret-never-read" not in canonical(check)


def test_compute_manual_round_trip(job_dir):
    backend = ManualBackend()
    receipt = backend.submit(package(job_dir), smoke=True)
    bundle = receipt.run_dir
    assert bundle == job_dir / "out/manual" / receipt.receipt_id
    assert (bundle / "entry.py").read_bytes() == (job_dir / "entry.py").read_bytes()
    instructions = (bundle / "RUN.md").read_text(encoding="utf-8")
    assert "python entry.py --output-dir out" in instructions and "--smoke" in instructions
    nb = json.loads((bundle / "run.ipynb").read_bytes())
    assert len(nb["cells"]) == 3 and nb["nbformat"] == 4
    assert "%run entry.py --output-dir /content/out" in "".join(nb["cells"][1]["source"])
    assert "--smoke" in "".join(nb["cells"][1]["source"])
    assert backend.status(receipt).status == "queued"
    outputs(bundle / "incoming")
    updated = backend.status(receipt)
    assert updated.status == "complete"
    fetched = backend.fetch(updated, job_dir / "out/fetched")
    assert fetched.outputs["labels.npz"].sha256 == digest(b"synthetic array bytes")


def test_compute_command_round_trip(job_dir, command_config):
    calls = []

    def fake(argv, **kwargs):
        calls.append(argv)
        assert "shell" not in kwargs
        if argv[0] == "submit-tool":
            assert argv[1] != str(job_dir) and argv[2:] == ["tiny-job", "; no shell"]
            source = (Path(argv[1]) / "entry.py").read_text(encoding="utf-8")
            assert "--smoke" in source and "/kaggle/working" not in source
            return result("JOB_ID=remote-123")
        if argv[0] == "status-tool":
            assert argv[1] == "remote-123"
            return result("ACTIVE")
        assert argv == ["fetch-tool", "remote-123", argv[2]]
        outputs(Path(argv[2]))
        return result()

    backend = load_backend("command", config=command_config, run=fake)
    receipt = backend.submit(package(job_dir), smoke=True)
    assert receipt.remote_id == "remote-123" and receipt.status == "queued"
    assert backend.values(receipt)["job_dir"] == backend.values(receipt)["staging"]
    assert backend.status(receipt).status == "running"
    # Later invocations recover the private config path from the receipt.
    fetched = load_backend("command", run=fake).fetch(receipt, job_dir / "out/fetched")
    assert fetched.status == "complete" and len(fetched.outputs) == 2
    assert len(calls) == 3
    command_config.write_text(command_config.read_text(encoding="utf-8") + "\n# changed\n", encoding="utf-8")
    with pytest.raises(IntegrityError, match="config changed"):
        backend.status(receipt)


def test_compute_command_launcher_preserves_host_arguments(job_dir, command_config, monkeypatch):
    def fake(argv, **kwargs):
        source = (Path(argv[1]) / "entry.py").read_text(encoding="utf-8")
        namespace = {}
        exec(compile(source, "entry.py", "exec"), namespace)
        assert namespace["SEEN_ARGS"] == ["entry.py", "--value", "two words; $(not-a-shell)",
            "--smoke", "--output-dir", "/remote/output"]
        return result("JOB_ID=remote-1")

    monkeypatch.setattr(sys, "argv", ["entry.py", "--output-dir", "/remote/output"])
    load_backend("command", config=command_config, run=fake).submit(package(job_dir), smoke=True)


@pytest.mark.parametrize("failure", ["nonzero", "missing_id", "timeout"])
def test_compute_remote_submission_failure(job_dir, command_config, failure):
    def fake(argv, **kwargs):
        if failure == "timeout":
            raise subprocess.TimeoutExpired(argv, kwargs["timeout"])
        return result("no remote id", returncode=3 if failure == "nonzero" else 0)

    backend = load_backend("command", config=command_config, run=fake)
    receipt = backend.submit(package(job_dir))
    assert receipt.status == "failed" and read_receipt(receipt.path).status == "failed"
    if failure != "missing_id":
        kaggle = KaggleBackend(owner="private-owner", run=fake).submit(package(job_dir))
        assert kaggle.status == "failed"


def test_compute_command_check_and_private_config(job_dir, command_config, monkeypatch):
    import research_loops.compute.command as module
    monkeypatch.setattr(module.shutil, "which", lambda name: "/fake/" + name)
    assert load_backend("command", config=command_config).check()["ready"]
    assert not load_backend("command").check()["ready"]
    private = job_dir / "host.toml"
    private.write_bytes(command_config.read_bytes())
    with pytest.raises(IntegrityError, match="outside the job"):
        load_backend("command", config=private).submit(package(job_dir))


@pytest.mark.parametrize("field,value", [("remote_id_regex", "["), ("remote_id_regex", "no capture"),
    ("status_map", {"[": "running"}), ("status_map", {"ok": "success"})])
def test_compute_command_bad_regexes_and_statuses(command_config, field, value):
    import tomllib
    config = tomllib.loads(command_config.read_text(encoding="utf-8"))
    config[field] = value
    with pytest.raises(ValidationError):
        CommandConfig.model_validate(config)


@pytest.mark.parametrize("bad", ["--flag={name}", "{staging}/entry.py", "{unrecognized}"])
def test_compute_command_whole_argument_policy(command_config, bad):
    import tomllib
    config = tomllib.loads(command_config.read_text(encoding="utf-8"))
    config["submit"] = ["tool", bad]
    with pytest.raises(ValidationError, match="whole arguments"):
        CommandConfig.model_validate(config)
    assert substitute(["tool", "{name}", "; $(literal)"], {"name": "spaces ; & $(data)"}) == [
        "tool", "spaces ; & $(data)", "; $(literal)"]


@pytest.mark.parametrize("raw, code, expected", [
    ("DONE", 0, "complete"), ("WAITING", 0, "queued"), ("BROKEN", 0, "failed"),
    ("STOPPED", 0, "cancelled"), ("unfamiliar", 0, "unknown"), ("DONE", 2, "unknown"),
])
def test_compute_command_status(job_dir, command_config, raw, code, expected):
    def fake(argv, **kwargs):
        return result("JOB_ID=remote-1") if argv[0] == "submit-tool" else result(raw, code)

    backend = load_backend("command", config=command_config, run=fake)
    receipt = backend.submit(package(job_dir))
    updated = backend.status(receipt)
    assert updated.status == expected and updated.history[-1].raw == raw


@pytest.mark.parametrize("name", ["local", "kaggle", "manual", "command"])
def test_compute_missing_outputs_fail(job_dir, command_config, name):
    def fake(argv, **kwargs):
        return result("JOB_ID=remote-1")

    options = dict(run=fake) if name != "manual" else {}
    if name == "kaggle":
        options["owner"] = "private-owner"
    if name == "command":
        options["config"] = command_config
    backend = load_backend(name, **options)
    receipt = backend.submit(package(job_dir))
    with pytest.raises(IntegrityError, match="expected compute output missing"):
        backend.fetch(receipt, job_dir / "out/fetched")
    assert not (job_dir / "out/fetched").exists()
    assert not read_receipt(receipt.path).outputs


def test_compute_runner_never_uses_shell(monkeypatch):
    captured = {}

    def fake(argv, **kwargs):
        captured.update(kwargs)
        assert argv == ["fake", "two words; $(data)"]
        return result()

    monkeypatch.setattr(subprocess, "run", fake)
    core.runner(["fake", "two words; $(data)"], timeout=10)
    assert captured["shell"] is False


def test_compute_cli_manual_and_unknown(job_dir):
    cli = CliRunner()
    check = cli.invoke(app, ["compute", "check", "--backend", "manual"])
    assert check.exit_code == 0 and json.loads(check.stdout)["ready"]
    submit = cli.invoke(app, ["compute", "submit", str(job_dir), "--backend", "manual", "--smoke"])
    assert submit.exit_code == 0, submit.output
    receipt_path = Path(submit.stdout.strip())
    receipt = read_receipt(receipt_path)
    assert receipt.smoke
    outputs(receipt.run_dir / "incoming")
    status = cli.invoke(app, ["compute", "status", str(receipt_path)])
    assert status.exit_code == 0 and json.loads(status.stdout)["status"] == "complete"
    fetch = cli.invoke(app, ["compute", "fetch", str(receipt_path)])
    assert fetch.exit_code == 0 and json.loads(fetch.stdout)["outputs"]["result.json"]["size"] == 12
    custom = cli.invoke(app, ["compute", "fetch", str(receipt_path), "--out", str(job_dir / "out/custom")])
    assert custom.exit_code == 0 and (job_dir / "out/custom/result.json").is_file()
    unknown = cli.invoke(app, ["compute", "check", "--backend", "not-a-backend"])
    assert unknown.exit_code != 0 and "unknown compute backend" in unknown.output


@pytest.mark.parametrize("backend, option", [("kaggle", "--kaggle-owner"), ("command", "--command-config")])
def test_compute_cli_backend_options(job_dir, backend, option, monkeypatch):
    import research_loops.compute.cli as module
    captured = {}

    class Fake:
        def submit(self, job, smoke):
            captured.update(sha256=job.sha256, smoke=smoke)
            return SimpleNamespace(path=job_dir / "out/receipt.json")

    def fake_loader(name, **options):
        captured.update(name=name, options=options)
        return Fake()

    monkeypatch.setattr(module, "load_backend", fake_loader)
    value = "private-owner" if backend == "kaggle" else str(job_dir.parent / "private.compute.local.toml")
    response = CliRunner().invoke(app, ["compute", "submit", str(job_dir), "--backend", backend, option, value])
    assert response.exit_code == 0, response.output
    assert captured["name"] == backend and len(captured["sha256"]) == 64
    assert captured["options"] == ({"owner": value} if backend == "kaggle" else {"config": Path(value)})


@pytest.mark.parametrize("name", ["local", "kaggle", "manual", "command"])
def test_compute_cli_receipt_dispatch(job_dir, command_config, name, monkeypatch):
    import research_loops.compute.cli as module

    def fake(argv, **kwargs):
        if argv[0] == "kaggle" and argv[2] == "output":
            outputs(Path(argv[-1]))
        if argv[0] == "fetch-tool":
            outputs(Path(argv[-1]))
        return result("JOB_ID=remote-1")

    options = dict(run=fake) if name != "manual" else {}
    if name == "kaggle":
        options["owner"] = "private-owner"
    if name == "command":
        options["config"] = command_config
    backend = load_backend(name, **options)
    receipt = backend.submit(package(job_dir))
    if name in {"local", "manual"}:
        outputs(receipt.run_dir / ("outputs" if name == "local" else "incoming"))
    selected = []

    def loader(backend_name):
        selected.append(backend_name)
        return backend

    monkeypatch.setattr(module, "load_backend", loader)
    cli = CliRunner()
    response = cli.invoke(app, ["compute", "status", str(receipt.path)])
    assert response.exit_code == 0, response.output
    response = cli.invoke(app, ["compute", "fetch", str(receipt.path)])
    assert response.exit_code == 0, response.output
    assert selected == [name, name]
    assert set(json.loads(response.stdout)["outputs"]) == {"result.json", "labels.npz"}
