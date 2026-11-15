"""User-configured CLI adapter: argument lists only, never shell interpolation."""

from pathlib import Path
import re
import shutil
import subprocess
import tomllib

from pydantic import Field, field_validator

from research_loops.compute.core import (Status, StrictModel, fetch_outputs, launch_source, new_receipt,
    no_links, raw_output, record, runner, stage)
from research_loops.domain import IntegrityError, digest


PLACEHOLDERS = {"{job_dir}", "{staging}", "{name}", "{remote_id}", "{out_dir}"}


class CommandConfig(StrictModel):
    submit: list[str] = Field(min_length=1)
    status: list[str] = Field(min_length=1)
    fetch: list[str] = Field(min_length=1)
    remote_id_regex: str
    status_map: dict[str, Status] = Field(min_length=1)

    @field_validator("submit", "status", "fetch")
    @classmethod
    def whole_arguments(cls, values):
        if values[0] in PLACEHOLDERS:
            raise ValueError("command executable must be literal")
        for value in values:
            if "\x00" in value or (("{" in value or "}" in value) and value not in PLACEHOLDERS):
                raise ValueError("placeholders must be whole arguments")
        return values

    @field_validator("remote_id_regex")
    @classmethod
    def capture_id(cls, value):
        try:
            groups = re.compile(value).groups
        except re.error:
            raise ValueError("invalid remote id regex") from None
        if groups < 1:
            raise ValueError("remote_id_regex needs a capture group")
        return value

    @field_validator("status_map")
    @classmethod
    def status_regexes(cls, value):
        try:
            for pattern in value:
                re.compile(pattern)
        except re.error:
            raise ValueError("invalid status regex") from None
        return value


def substitute(template, values):
    return [values[arg[1:-1]] if arg in PLACEHOLDERS else arg for arg in template]


class CommandBackend:
    name = "command"

    def __init__(self, *, config=None, run=runner):
        self.config_path = no_links(config) if config is not None else None
        self.run = run

    def configuration(self, receipt=None):
        path = self.config_path or (Path(receipt.options["command_config"]) if receipt else None)
        if path is None:
            raise IntegrityError("command backend requires --command-config")
        raw = no_links(path).read_bytes()
        if receipt and digest(raw) != receipt.options["command_config_sha256"]:
            raise IntegrityError("command config changed since submission")
        return path, raw, CommandConfig.model_validate(tomllib.loads(raw.decode("utf-8")))

    def check(self):
        if self.config_path is None:
            return dict(backend=self.name, ready=False, config_present=False, credentials="managed by command")
        _, _, config = self.configuration()
        available = all(shutil.which(args[0]) is not None for args in (config.submit, config.status, config.fetch))
        return dict(backend=self.name, ready=available, config_present=True, credentials="managed by command")

    def values(self, receipt, out_dir=None):
        staging = receipt.run_dir / "staging"
        # Both directory aliases refer to the filtered package, never the source tree.
        return dict(job_dir=str(staging), staging=str(staging), name=receipt.job.name,
            remote_id=receipt.remote_id or "", out_dir=str(out_dir or receipt.run_dir / "incoming"))

    def submit(self, job, smoke=False):
        path, raw, config = self.configuration()
        if path.is_relative_to(job.root):
            raise IntegrityError("keep private command config outside the job directory")
        receipt = new_receipt(job, self.name, smoke,
            dict(command_config=str(path), command_config_sha256=digest(raw)))
        stage(job, receipt.run_dir / "staging")
        # A generated launcher carries both the job's arguments and smoke selection.
        entry = receipt.run_dir / "staging" / job.spec.entry
        source = launch_source(job.files[job.spec.entry], job.spec.entry, job.arguments(smoke), preserve_argv=True)
        entry.write_text(source, encoding="utf-8", newline="\n")
        try:
            result = self.run(substitute(config.submit, self.values(receipt)), timeout=job.spec.max_runtime_s)
        except (OSError, subprocess.TimeoutExpired):
            return record(receipt, "failed", "command submission failed or timed out")
        raw = raw_output(result)
        match = re.search(config.remote_id_regex, raw) if result.returncode == 0 else None
        if match is None:
            return record(receipt, "failed", raw)
        remote_id = match.groupdict().get("remote_id") or match[1]
        if not remote_id or any(char in remote_id for char in ("\n", "\r", "\x00")):
            return record(receipt, "failed", "invalid remote id in command output")
        return record(receipt, "queued", raw, remote_id=remote_id)

    def status(self, receipt):
        _, _, config = self.configuration(receipt)
        try:
            result = self.run(substitute(config.status, self.values(receipt)), timeout=60)
        except (OSError, subprocess.TimeoutExpired):
            return record(receipt, "unknown", "command status failed or timed out")
        raw = raw_output(result)
        matches = {status for pattern, status in config.status_map.items() if re.search(pattern, raw)}
        status = matches.pop() if result.returncode == 0 and len(matches) == 1 else "unknown"
        return record(receipt, status, raw)

    def fetch(self, receipt, out_dir):
        _, _, config = self.configuration(receipt)
        incoming = receipt.run_dir / "incoming"
        incoming.mkdir(parents=True, exist_ok=True)
        try:
            result = self.run(substitute(config.fetch, self.values(receipt, incoming)), timeout=300)
        except (OSError, subprocess.TimeoutExpired):
            raise IntegrityError("command output download failed or timed out") from None
        if result.returncode:
            raise IntegrityError("command output download failed")
        return fetch_outputs(receipt, incoming, out_dir)
