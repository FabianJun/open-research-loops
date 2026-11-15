"""Strict job contracts, code-only packages, receipts and shared output checks."""

from dataclasses import dataclass
from datetime import datetime, timezone
import ast
import hashlib
from pathlib import Path
import re
import shutil
import stat
import subprocess
from typing import Literal, Protocol
from urllib.parse import urlsplit
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

from research_loops.domain import IntegrityError, canonical, digest
from research_loops.paths import atomic_write, confined


Status = Literal["queued", "running", "complete", "failed", "cancelled", "unknown"]
BACKENDS = Literal["local", "kaggle", "manual", "command"]
MAX_PACKAGE_BYTES = 5_000_000
FORBIDDEN = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".npz", ".npy",
    ".zip", ".tar", ".gz", ".gzip", ".tgz", ".bz", ".bz2", ".bzip2", ".tbz", ".tbz2",
    ".xz", ".txz", ".7z", ".rar", ".zst", ".lz", ".lzma", ".lz4", ".cab", ".iso",
    ".jar", ".war", ".whl", ".egg"}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


def filename(value):
    if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,254}", value)
            or value.endswith(".") or re.match(r"(?i)^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)", value)):
        raise ValueError("expected one plain filename")
    return value


class DataSource(StrictModel):
    url: str
    size: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("url")
    @classmethod
    def public_url(cls, value):
        parsed = urlsplit(value)
        if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("expected an HTTP(S) data URL without credentials")
        return value


class JobSpec(StrictModel):
    name: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=63)
    entry: str
    args: list[str]
    smoke_args: list[str]
    needs_gpu: bool
    needs_internet: bool
    max_runtime_s: int = Field(gt=0)
    outputs: list[str] = Field(min_length=1)
    data: list[DataSource]

    @field_validator("entry")
    @classmethod
    def python_file(cls, value):
        filename(value)
        if not value.endswith(".py"):
            raise ValueError("entry must be one Python file")
        return value

    @field_validator("outputs")
    @classmethod
    def output_names(cls, value):
        for item in value:
            filename(item)
        if len({item.casefold() for item in value}) != len(value):
            raise ValueError("outputs must be unique")
        return value

    @field_validator("args", "smoke_args")
    @classmethod
    def job_args(cls, value):
        if any("\x00" in item or item == "--output-dir" or item.startswith("--output-dir=") for item in value):
            raise ValueError("output directory is supplied by the backend; NUL arguments forbidden")
        return value


def no_links(path):
    path = Path(path).absolute()
    for part in (path, *path.parents):
        if part.is_symlink() or part.is_junction():
            raise IntegrityError("compute paths must not contain symlinks or junctions")
        if part.exists() and getattr(part.stat(), "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise IntegrityError("compute reparse points forbidden")
    return path


@dataclass(frozen=True)
class Job:
    root: Path
    spec: JobSpec
    files: dict[str, bytes]
    sha256: str

    def arguments(self, smoke):
        return [*self.spec.args, *(self.spec.smoke_args if smoke else [])]


def package(job_dir):
    root = no_links(job_dir)
    if any(".rloop" in part.casefold() for part in root.parts):
        raise IntegrityError(".rloop paths cannot be packaged")
    files, total = {}, 0

    def collect(folder):
        nonlocal total
        for path in sorted(folder.iterdir()):
            no_links(path)
            # Generated results and Python caches are never package inputs.
            if path.name in {"out", "__pycache__"} and path.is_dir():
                continue
            relative = path.relative_to(root).as_posix()
            if ".rloop" in path.name.casefold() or any(suffix.lower() in FORBIDDEN for suffix in path.suffixes):
                raise IntegrityError("data or archive path cannot be packaged: " + relative)
            if path.is_dir():
                collect(path)
            elif path.is_file() and stat.S_ISREG(path.stat().st_mode):
                total += path.stat().st_size
                if total > MAX_PACKAGE_BYTES:
                    raise IntegrityError("compute package exceeds 5 MB")
                files[relative] = path.read_bytes()
                if sum(map(len, files.values())) > MAX_PACKAGE_BYTES:
                    raise IntegrityError("compute package exceeds 5 MB")
            else:
                raise IntegrityError("only regular code/package files are allowed")

    collect(root)
    if "job.json" not in files:
        raise IntegrityError("job directory needs job.json")
    spec = JobSpec.model_validate_json(files["job.json"])
    if spec.entry not in files:
        raise IntegrityError("entry must be a file inside the job directory")
    files["job.json"] = (canonical(spec) + "\n").encode()
    # Path + digest + size binds filenames and contents without delimiter ambiguity.
    identity = dict(job=spec.model_dump(mode="json"), files={name: dict(sha256=digest(raw), size=len(raw))
        for name, raw in files.items() if name != "job.json"})
    return Job(root, spec, files, digest(canonical(identity).encode()))


def stage(job, destination):
    destination = no_links(destination)
    destination.mkdir(parents=True, exist_ok=True)
    for name, raw in job.files.items():
        target = confined(destination, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)


def launch_source(raw, entry, args, output_dir=None, preserve_argv=False):
    """Inject arguments after the docstring/future imports, preserving valid Python."""
    text = raw.decode("utf-8")
    tree = ast.parse(text)
    line = 0
    for index, node in enumerate(tree.body):
        if ((index == 0 and isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str))
                or isinstance(node, ast.ImportFrom) and node.module == "__future__"):
            line = node.end_lineno
        else:
            break
    header = ("\n# Generated by rloop compute; job arguments and host output location only.\n"
        "import os as _rloop_os\nimport sys as _rloop_sys\n"
        f"_rloop_sys.argv = {repr([entry, *args])}"
        + (" + _rloop_sys.argv[1:]" if preserve_argv else "") + "\n")
    if output_dir is not None:
        header += f"_rloop_os.environ['RLOOP_OUTPUT_DIR'] = {repr(output_dir)}\n"
    lines = text.splitlines(keepends=True)
    return "".join(lines[:line]) + header + "\n" + "".join(lines[line:])


class FileFact(StrictModel):
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size: int = Field(ge=0)


class Event(StrictModel):
    at: str
    status: Status
    raw: str | None = None


class Receipt(StrictModel):
    receipt_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    backend: BACKENDS
    job_dir: str
    job: JobSpec
    job_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    smoke: bool
    remote_id: str | None = None
    created_at: str
    updated_at: str
    status: Status = "queued"
    history: list[Event]
    options: dict[str, str] = Field(default_factory=dict)
    fetched_at: str | None = None
    fetched_dir: str | None = None
    outputs: dict[str, FileFact] = Field(default_factory=dict)

    @property
    def path(self):
        return confined(no_links(self.job_dir), f"out/receipts/{self.receipt_id}.json")

    @property
    def run_dir(self):
        return confined(no_links(self.job_dir), f"out/{self.backend}/{self.receipt_id}")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def save(receipt):
    atomic_write(receipt.path, (canonical(receipt) + "\n").encode())
    return receipt


def new_receipt(job, backend, smoke, options=None):
    now = utc_now()
    return save(Receipt(receipt_id=uuid.uuid4().hex, backend=backend, job_dir=str(job.root), job=job.spec,
        job_sha256=job.sha256, smoke=smoke, created_at=now, updated_at=now,
        history=[Event(at=now, status="queued")], options=options or {}))


def record(receipt, status, raw=None, **updates):
    now = utc_now()
    value = receipt.model_dump(mode="json")
    value.update(status=status, updated_at=now, **updates)
    value["history"].append(dict(at=now, status=status, raw=raw))
    return save(Receipt.model_validate(value))


def read_receipt(path):
    path = no_links(path)
    receipt = Receipt.model_validate_json(path.read_bytes())
    if path.resolve() != receipt.path.resolve():
        raise IntegrityError("receipt must remain in its job's out/receipts directory")
    return receipt


def runner(argv, **kwargs):
    return subprocess.run(argv, shell=False, capture_output=True, text=True, **kwargs)


def raw_output(result):
    return (result.stdout or "") + (result.stderr or "")


def fetch_outputs(receipt, source, out_dir):
    source = no_links(source)
    destination = no_links(out_dir)
    # Verify all expected files before copying any. Extra remote files are ignored.
    selected = {}
    for name in receipt.job.outputs:
        path = confined(source, name)
        if not path.is_file():
            raise IntegrityError("expected compute output missing: " + name)
        selected[name] = path
    destination.mkdir(parents=True, exist_ok=True)
    facts = {}
    for name, path in selected.items():
        target = confined(destination, name)
        if path.resolve() != target.resolve():
            shutil.copyfile(path, target)
        with target.open("rb") as stream:
            sha256 = hashlib.file_digest(stream, "sha256").hexdigest()
        facts[name] = dict(sha256=sha256, size=target.stat().st_size)
    now = utc_now()
    return record(receipt, "complete", fetched_at=now, fetched_dir=str(destination), outputs=facts)


class ComputeBackend(Protocol):
    def check(self) -> dict: ...
    def submit(self, job: Job, smoke: bool) -> Receipt: ...
    def status(self, receipt: Receipt) -> Receipt: ...
    def fetch(self, receipt: Receipt, out_dir: Path) -> Receipt: ...
