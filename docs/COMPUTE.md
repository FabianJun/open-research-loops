# Compute jobs

Compute is separate from research worker backends. A job is trusted owner code
submitted explicitly with `rloop compute`; this is not the worker candidate
sandbox. Adapters implement one `ComputeBackend` Protocol and are loaded lazily
by `compute.load_backend`, following the worker factory in `execution.py`.
Adding a host requires an adapter/factory branch, or a private command config;
the experiment stays unchanged. No vendor SDK is imported by this subsystem.

| Backend | Needs | Offline verification | Live verification |
|---|---|---|---|
| `local` | Current Python and the job's dependencies | Fake runner, timeout/failure handling, argument/env contract and output hashes | No CNN training run |
| `kaggle` | Installed Kaggle CLI, credentials and a privately configured owner | Fake CLI: private metadata, generated entry, status parsing and fetch | Never submitted live |
| `manual` | A host/runtime and manual upload/download; suitable for free Colab | Bundle/notebook creation and synthetic incoming/fetch round trip | Never run on Colab |
| `command` | User-supplied TOML and installed host CLI/wrappers | Fake commands, whole-argument substitution, status and fetch | No host configuration verified live |

Verification: `uv run --locked pytest -q` passed with 421 passed, 1 skipped
(the existing real-data environment gate), and 43 existing dependency warnings.
`UV_OFFLINE=1` and an already cached Docker image kept this run offline; no
temporary pytest plugin or extra skips were used.

Free Colab uses `manual`; no official headless execution API was found for it.
Colab Enterprise has an official execution-job API on Vertex AI. It is paid,
needs a GCP project and a service account, and can be driven by a `command`
configuration once that configuration is verified. No Enterprise/vendor
template is shipped or claimed to work. This is supplied scope information,
not a fresh online API check.

## Job contract

A job directory contains `job.json` and a standalone Python entry. All fields
are required: `name` (lowercase slug), `entry` (one `.py` filename), `args` and
`smoke_args` (string lists), `needs_gpu`, `needs_internet`, positive integer
`max_runtime_s`, nonempty unique `outputs` (plain filenames), and `data`
(list of `{url, size, sha256}`). Unknown keys and coerced types are rejected.
`data` is informational provenance shown inside receipts; the job fetches and
verifies its data. The compute layer never downloads those URLs.

The entry accepts `--output-dir`, resolving its output directory in this order:
CLI argument, `RLOOP_OUTPUT_DIR`, `/kaggle/working` if it exists, `./out`.
Backend-owned `--output-dir` is excluded from job argument lists. `--smoke`
appends `smoke_args` to `args`. Local runs get a fresh working directory and a
timeout; resource declarations do not provide GPU isolation or a remote runtime
cap. Configure remote runtime limits at the host where supported.

```sh
uv run --locked rloop compute check --backend local
uv run --locked rloop compute submit experiments/grain-cnn --backend manual --smoke
uv run --locked rloop compute status <receipt-path>
uv run --locked rloop compute fetch <receipt-path> --out <output-directory>
```

`submit` prints one receipt path under `<job-dir>/out/receipts/`. `status` and
`fetch` select the backend from that receipt. Without `--out`, fetch writes to
`<job-dir>/out/fetched/<receipt-id>/`. Receipts hold the canonical job and its
data provenance, package SHA-256, backend/remote ID, UTC timestamps, raw status
text and status history, and SHA-256/size for every fetched expected output.
Statuses are `queued`, `running`, `complete`, `failed`, `cancelled`, `unknown`.
Fetch refuses missing expected files; extra host outputs are not copied.

Kaggle uses `--kaggle-owner` or `RLOOP_KAGGLE_OWNER`. Its CLI metadata exists
only in temporary staging and always requests a private script kernel; GPU
and internet settings come from the job. The generated entry preserves future
imports, sets `sys.argv`, and sets `RLOOP_OUTPUT_DIR=/kaggle/working`. Smoke
kernels have a separate name. The adapter only stages the single entry; helpers
must be inlined for Kaggle. Its credential check tests whether `KAGGLE_API_TOKEN`
is set or `~/.kaggle/access_token` / `~/.kaggle/kaggle.json` exists. It never opens
or prints credential values and never contacts Kaggle during `check`.

Manual bundles live under `out/manual/<receipt-id>/`. Follow `RUN.md`, or open
`run.ipynb` on Colab to upload the entry, run it and download zipped outputs.
Copy expected files into that bundle's `incoming/`; status then becomes complete.

For `command`, pass `--command-config /private/path/host.compute.local.toml`
to check/submit. This file is host-only and must be outside the job directory.
The receipt records its location and hash; later operations refuse a changed
configuration. Required TOML keys are `submit`, `status`, `fetch` (argument
lists), `remote_id_regex` (with a capture group), and `[status_map]` mapping
regexes to statuses. Unknown or ambiguous status text becomes `unknown` and is
kept verbatim. Every invocation uses `shell=False`; placeholders are whole
arguments: `{job_dir}`, `{staging}`, `{name}`, `{remote_id}`, `{out_dir}`.
Both directory aliases name the filtered package; `{out_dir}` names local
incoming storage. The staged entry includes the configured args/smoke args;
your host launcher supplies `--output-dir` or sets its output environment. The command adapter checks
executables, while the host CLI owns authentication; it cannot generically
verify credentials. The commented [SSH/scp example](../examples/compute/command.example.toml)
requires your own verified wrapper commands.

## Packaging and data

Every backend uses the same bounded package: files inside the job directory
only, no symlinks, junctions, special files or `.rloop` paths. Image/mask
extensions `.png .jpg .jpeg .tif .tiff .bmp`, arrays `.npz .npy`, and archives
(including zip, tar, gzip, 7z and wheels) are refused before staging. Total
package size is at most 5,000,000 bytes. Generated `out/` directories and Python
caches are excluded. The package hash binds canonical `job.json` plus each
packaged filename and its contents; JSON whitespace does not change identity.

Code goes out; dataset pixels never do. Images and masks are never redistributed.
Keep bundles, receipts, downloaded data and results out of git. `out/` and
`*.compute.local.toml` are ignored. Owner handles and credentials belong in
environment variables or private config, never tracked experiment files.
Tests use fake command runners and synthetic fixtures; they never read real
grain test-split files. No compute provider call or real training is part of
offline verification.
