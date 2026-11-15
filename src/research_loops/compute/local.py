"""Run a trusted entry with the current interpreter, without a shell."""

import os
import subprocess
import sys

from research_loops.compute.core import fetch_outputs, new_receipt, record, runner, stage


class LocalBackend:
    name = "local"

    def __init__(self, *, run=runner):
        self.run = run

    def check(self):
        return dict(backend=self.name, ready=True, credentials_required=False)

    def submit(self, job, smoke=False):
        receipt = new_receipt(job, self.name, smoke)
        work, output = receipt.run_dir / "work", receipt.run_dir / "outputs"
        stage(job, work)
        output.mkdir(parents=True)
        receipt = record(receipt, "running", remote_id=receipt.receipt_id)
        env = {**os.environ, "RLOOP_OUTPUT_DIR": str(output)}
        try:
            result = self.run([sys.executable, str(work / job.spec.entry), *job.arguments(smoke),
                "--output-dir", str(output)], cwd=work, env=env, timeout=job.spec.max_runtime_s)
        except subprocess.TimeoutExpired:
            return record(receipt, "failed", "local job exceeded max_runtime_s")
        except OSError:
            return record(receipt, "failed", "local interpreter could not start")
        return record(receipt, "complete" if result.returncode == 0 else "failed", result.stdout + result.stderr)

    def status(self, receipt):
        return record(receipt, receipt.status)

    def fetch(self, receipt, out_dir):
        return fetch_outputs(receipt, receipt.run_dir / "outputs", out_dir)
