# Grain counting and sizing on 316L steel

Real benchmark with a published baseline, adapted from Claude Impact Lab 2026
project #5. Supported means development `max_rel_error <= 0.10`.
Defaults and the team final configuration must reproduce before any worker runs.
Read [PROVENANCE.md](PROVENANCE.md), including the unresolved package license.
No images or masks are distributed, reported or exported.

From the checkout root, with a previously obtained, verified archive:

```powershell
uv sync --locked --all-extras
Copy-Item -Recurse examples/grain-316l grain-demo
uv run rloop init grain-demo --owner "Your Name"
uv run rloop data fetch grain-demo --archive C:/local/Grain.zip
uv run rloop plan grain-demo
uv run rloop run grain-demo --backend fake
uv run rloop report grain-demo --check
uv run rloop self-assess grain-demo --write
```

The fake run demonstrates mechanics with simulated proposals. It makes no model
request and does not spend the holdout. Public training information contains
derived statistics only. Protocol v3 adds `try_on_training(params)`, capped at six
calls on the first 32 sorted training names; one candidate seals each run.

The archive contains both PNG and JPEG images, paired with PNG masks. Original
bytes are retained for manifest hashes; images are never converted. Fetch without
`--archive` implements Zenodo download; that online path was not used in delivery.

The live pilot runs under
[Phase 4b authorization](../../docs/DECISIONS.md#phase-4b-authorization--2026-11-15),
in a fresh project per backend, with its existing explicit checkpoint-B gate.
This implementation creates no live approval. Only `rloop run PROJECT --final`
spends the selected candidate's one-use final ticket. The offline sequence above
does not run it. Grain uses the host declarative tool service; the minimal OCI
worker image intentionally contains no protected evaluator or grain pixels.

Documentation licensed CC BY 4.0.
