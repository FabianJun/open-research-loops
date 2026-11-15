# Grain CNN feasibility

Does a small trained U-Net beat the fixed classical pipeline on the 40-image
grain-316l val split, using the identical count/size metric with
`exclude_edge=False`? Background: [Phase 4b pilot](../../docs/PHASE-4B-PILOT.md).

Pre-registered rule: one full run with the fixed configuration in
`train_unet.py`. The result **beats the team pipeline** if val
`max_rel_error < 0.12586301151517196`, and **meets the Phase 4b target** if
`max_rel_error <= 0.10`. Val is scored once. No configuration change after
seeing the val score in this experiment.

The seed-0 split of sorted training stems gives 551 fit and 60 internal-check
images. Each epoch uses one random crop per fit image. Checkpoint selection
uses internal `max_rel_error` at fixed `t=0.5, a=0`; ties keep the earliest
epoch. The requested 25 post-processing settings are then compared only on
internal-check predictions from that checkpoint; ties prefer lower t, then
lower a. All other training choices are fixed in the script and recorded in
`run.json`. Val masks are never opened by training; val images are decoded
only after all choices are fixed. Full-image inference uses reflection padding
to a multiple of 16, cropped back to 300x400.

## Run on any host

The [compute adapters](../../docs/COMPUTE.md) handle submission, status and
output retrieval. The experiment itself is independent of the host. Kaggle is
the free GPU host we use first. These are manual commands for the owner;
building and testing launches no real training or download. Local and other
hosts need Python, PyTorch, numpy, scipy, scikit-image and Pillow already installed.
From the repository root, set `RLOOP_KAGGLE_OWNER` privately for Kaggle:

```sh
uv run --locked rloop compute check --backend kaggle
uv run --locked rloop compute submit experiments/grain-cnn --backend kaggle
uv run --locked rloop compute status <receipt-path>
uv run --locked rloop compute fetch <receipt-path> --out experiments/grain-cnn/out/full
uv run --locked python experiments/grain-cnn/score_local.py <project-dir> experiments/grain-cnn/out/full/val_labels.npz
```

`<project-dir>` must already contain `.rloop/data/val.json` and verified image
and mask files under `.rloop/data/Grain/val`. The scorer uses the evaluator's
manifest and hash checks. It prints the score and writes
`val_labels.score.json` beside the predictions (negative `difference_to_team` is an improvement),
refusing to overwrite an existing score file. Do not score smoke outputs against
the full val manifest: they intentionally contain only two stems.

Submit prints its receipt path under `out/receipts/`. For free Colab, use
`--backend manual`: upload the generated bundle, follow `RUN.md` or `run.ipynb`,
then copy the returned files into its `incoming/` before fetching. For another
CLI host, use `--backend command --command-config /private/path/host.compute.local.toml`.
Configuration and owner handles stay outside tracked experiment files.

An optional `--smoke` submission runs one epoch, eight fit, four internal-check
and two val images. Fetch into `out/smoke/`. Kaggle smoke kernels get a separate
name; each local/manual/command submission gets a fresh run directory. Run the
full configuration only once under the pre-registration above.

Use `--backend local` with an existing PyTorch environment, or execute directly:

```sh
python experiments/grain-cnn/train_unet.py --smoke --archive /path/to/Grain.zip --output-dir experiments/grain-cnn/out/smoke
```

Omit `--archive` to download the pinned Zenodo archive. Both paths check size,
md5 and sha256 before extraction. Only train/val members are opened or extracted.
Output resolution is `--output-dir`, then `RLOOP_OUTPUT_DIR`, then
`/kaggle/working` if it exists, then `./out`. Use fresh output directories.
Training also saves `best.pt`; the portable job fetches only `val_labels.npz`
and `run.json`. Temporary
extracted data and its downloaded archive are cleaned up on exit, including
Python exceptions. A supplied `--archive` is retained.

## Data and result

Images and masks are never redistributed. Outputs, including derived label
maps and weights, bundles and receipts, stay out of git. Packaging excludes
`out/` and refuses dataset/array/archive inputs. Keep fetched outputs private.
No real holdout split is read or scored.
Code is Apache-2.0; this README is CC BY 4.0. The copied metric's upstream
attribution is in the script docstring and repository NOTICE.

Result: **not run yet**.
