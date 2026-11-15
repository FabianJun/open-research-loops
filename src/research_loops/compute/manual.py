"""Manual bundle for free Colab and hosts without a verified headless adapter."""

import json
import shlex

from research_loops.compute.core import fetch_outputs, new_receipt, no_links, record, stage


def notebook(entry, args):
    source = {
        "upload": "from google.colab import files\nfiles.upload()  # Upload the bundled entry (and any helper files).\n",
        "run": "%run " + shlex.join([entry, "--output-dir", "/content/out", *args]) + "\n",
        "download": ("import shutil\nfrom google.colab import files\n"
            "shutil.make_archive('/content/results', 'zip', '/content/out')\n"
            "files.download('/content/results.zip')\n"),
    }
    return dict(nbformat=4, nbformat_minor=5,
        metadata=dict(colab={}, kernelspec=dict(name="python3", display_name="Python 3")),
        cells=[dict(id=name, cell_type="code", metadata={}, execution_count=None, outputs=[],
            source=text.splitlines(keepends=True)) for name, text in source.items()])


class ManualBackend:
    name = "manual"

    def check(self):
        return dict(backend=self.name, ready=True, credentials_required=False)

    def submit(self, job, smoke=False):
        receipt = new_receipt(job, self.name, smoke)
        bundle = receipt.run_dir
        stage(job, bundle)
        (bundle / "incoming").mkdir()
        command = shlex.join(["python", job.spec.entry, "--output-dir", "out", *job.arguments(smoke)])
        instructions = ("# Run on your chosen host\n\nUpload the entry and any helper files to a host with its dependencies.\n"
            "For Colab, select a GPU runtime if this job needs one and open run.ipynb.\n\n"
            f"Run from the bundle directory:\n\n```sh\n{command}\n```\n\n"
            "Copy these files from out/ into this bundle's incoming/ directory:\n\n"
            + "".join(f"- {name}\n" for name in job.spec.outputs)
            + "\nThen run rloop compute fetch with the saved receipt. Keep data and outputs private.\n")
        (bundle / "RUN.md").write_text(instructions, encoding="utf-8", newline="\n")
        (bundle / "run.ipynb").write_text(json.dumps(notebook(job.spec.entry, job.arguments(smoke)), indent=2) + "\n",
            encoding="utf-8")
        return record(receipt, "queued", remote_id=receipt.receipt_id)

    def status(self, receipt):
        incoming = no_links(receipt.run_dir / "incoming")
        complete = all((incoming / name).is_file() and not (incoming / name).is_symlink()
            and not (incoming / name).is_junction() for name in receipt.job.outputs)
        return record(receipt, "complete" if complete else "queued")

    def fetch(self, receipt, out_dir):
        return fetch_outputs(receipt, receipt.run_dir / "incoming", out_dir)
