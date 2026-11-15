"""Kaggle CLI adapter; private script kernels, no credential-file reads."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from research_loops.compute.core import fetch_outputs, launch_source, new_receipt, raw_output, record, runner
from research_loops.domain import IntegrityError


STATUSES = {"queued": "queued", "new_script": "queued", "running": "running",
    "complete": "complete", "completed": "complete", "error": "failed", "failed": "failed",
    "cancel_requested": "cancelled", "cancel_acknowledged": "cancelled",
    "cancelled": "cancelled", "canceled": "cancelled"}


def parse_status(raw):
    # Kaggle CLI 2.x prints `<id> has status "KernelWorkerStatus.COMPLETE"`, then an
    # optional `Failure message:` line; only the first line carries the status.
    lines = raw.strip().splitlines()
    match = re.fullmatch(r"(?:[^\n]*\bhas status\s*:?\s*|(?:kernel\s+)?status\s*:\s*)?"
        r"[\"']?(?:KernelWorkerStatus\.)?([a-z_]+)[\"']?[.!]?",
        lines[0].strip() if lines else "", re.IGNORECASE)
    return STATUSES.get(match[1].lower(), "unknown") if match else "unknown"


class KaggleBackend:
    name = "kaggle"

    def __init__(self, *, owner=None, is_private=True, run=runner):
        if is_private is not True:
            raise IntegrityError("Kaggle compute kernels must be private")
        self.owner, self.run = owner, run

    def check(self):
        home = Path.home() / ".kaggle"
        # Iterating names avoids os._Environ.__contains__, which reads the value.
        credentials = ("KAGGLE_API_TOKEN" in set(os.environ) or (home / "access_token").is_file()
            or (home / "kaggle.json").is_file())
        cli = shutil.which("kaggle") is not None
        return dict(backend=self.name, ready=credentials and cli, credentials_present=credentials, cli_present=cli)

    def submit(self, job, smoke=False):
        owner = self.owner or os.environ.get("RLOOP_KAGGLE_OWNER", "")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", owner):
            raise IntegrityError("set --kaggle-owner or RLOOP_KAGGLE_OWNER")
        name = job.spec.name + ("-smoke" if smoke else "")
        receipt = new_receipt(job, self.name, smoke)
        remote_id = owner + "/" + name
        receipt = record(receipt, "queued", remote_id=remote_id)
        with tempfile.TemporaryDirectory(prefix="rloop-kaggle-") as folder:
            staging = Path(folder)
            (staging / job.spec.entry).write_text(launch_source(job.files[job.spec.entry],
                job.spec.entry, job.arguments(smoke), "/kaggle/working"), encoding="utf-8", newline="\n")
            metadata = dict(id=remote_id, title=name, code_file=job.spec.entry,
                kernel_type="script", language="python", is_private=True,
                enable_gpu=job.spec.needs_gpu, enable_internet=job.spec.needs_internet,
                dataset_sources=[], competition_sources=[], kernel_sources=[])
            (staging / "kernel-metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
            try:
                result = self.run(["kaggle", "kernels", "push", "-p", str(staging)], timeout=job.spec.max_runtime_s)
            except (OSError, subprocess.TimeoutExpired):
                return record(receipt, "failed", "Kaggle CLI submission failed or timed out")
        return record(receipt, "queued" if result.returncode == 0 else "failed", raw_output(result))

    def status(self, receipt):
        try:
            result = self.run(["kaggle", "kernels", "status", receipt.remote_id], timeout=60)
        except (OSError, subprocess.TimeoutExpired):
            return record(receipt, "unknown", "Kaggle CLI status failed or timed out")
        raw = raw_output(result)
        return record(receipt, parse_status(raw) if result.returncode == 0 else "unknown", raw)

    def fetch(self, receipt, out_dir):
        with tempfile.TemporaryDirectory(prefix="rloop-kaggle-output-") as folder:
            try:
                result = self.run(["kaggle", "kernels", "output", receipt.remote_id, "-p", folder], timeout=300)
            except (OSError, subprocess.TimeoutExpired):
                raise IntegrityError("Kaggle CLI output download failed or timed out") from None
            if result.returncode:
                raise IntegrityError("Kaggle CLI output download failed")
            return fetch_outputs(receipt, Path(folder), out_dir)
