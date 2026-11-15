# Provenance

- Dataset: Zenodo record 22039777, DOI
  [10.5281/zenodo.22039777](https://doi.org/10.5281/zenodo.22039777).
  Creators: WUT-AI-AI4Mat. Metadata license: CC BY 4.0.
- Underlying images: Warren, P. et al., “Grain and grain boundary segmentation
  using machine learning with real and generated datasets”, Computational
  Materials Science 233, 112739 (2024), [arXiv:2307.05911](https://arxiv.org/abs/2307.05911).
- License caveat: the deposit README says a final license has not yet been
  selected inside the package. The contract's CC-BY-4.0 declaration refers to
  metadata; it does not resolve image redistribution rights. Images and masks
  must never enter Git, reports, exports, journals or tool results.
- `Grain.zip`: 100439005 bytes; MD5
  `b6c9d5d98b5c0001e12e4ee9a0582b86`; SHA-256
  `30ca8e80392519bb790d6093b5deb86df4d4aedf8cbe9beedbf329106d54d9d0`.
  `train` (611 images) is worker training; `val` (40) is development;
  `test` (165) is final holdout. The original archive includes `.jpg` images,
  as well as `.png` images; all masks are PNGs. Paths and hashes, not roots,
  are registered. Roots stay host-only. No archive is bundled.
- Pipeline and metric: [VanishJr/micrograph-impact-lab](https://github.com/VanishJr/micrograph-impact-lab/tree/91758551f37d54d94130ab69cd00a8ee68ac0d40),
  commit `91758551f37d54d94130ab69cd00a8ee68ac0d40`, Apache-2.0,
  Claude Impact Lab 2026 project #5, “micrograph”. Read only; never executed
  or imported. `watershed.segment`, grain measurement and the 316L metric were
  ported with lazy imports, stricter parameter validation and statistics-only
  outputs. Defect detection, overlays, labels and unrelated measurements were
  omitted. NOTICE records this reuse. Independent truth uses SciPy labeling
  and `sqrt(4A/pi)`, without the port's scikit-image measurements.
- Source-code detail: count truth is `n_all` when `exclude_edge=false`,
  `n_interior` otherwise. This differs from the initial interior-only summary.
  The baseline artifact contains NaN for an undefined true size; the current
  source excludes undefined sizes. The reproduction gate uses the requested
  main metric, not that older artifact's size aggregation.
- Cited development controls: defaults `12.885281385281385`; team final
  `0.12586301151517196` (count `0.1111111111111111`, size
  `0.12586301151517196`, 39 defined sizes). Source: the team's
  `results/baseline/316L/execute.json` and `results/final.json`.
- Cited final holdout: `0.17391304347826086` (count
  `0.17391304347826086`, size `0.1629683115862643`, 164 defined sizes).
  Source: `results/final.json`; not recomputed during implementation.
- Python 3.12 pins from the team's `uv.lock`: scikit-image 0.26.0,
  SciPy 1.18.1, NumPy 2.5.4, Pillow 13.0.0, imageio 2.38.1.

Documentation licensed CC BY 4.0.
