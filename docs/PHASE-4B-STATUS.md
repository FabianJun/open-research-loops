# Phase 4b offline implementation

The grain domain has a parameter-only candidate, protected watershed evaluation,
independent SciPy truth/metric checking, two controls before dispatch, deterministic
split manifests, host-only archive ingestion, and protocol v3 training feedback.
No live approval was created and no provider, sign-in or real pilot was run.
The authorized live pilot runs separately.

Planted-signal retains its original contract, generated data, registration,
worker protocol v2, six tools and committed example report. A manifest compatibility
record preserves its numerical evaluator identity only while **all** protected
file hashes match that record. Runtime verification still checks the full new
manifest. A later protected edit changes the identity unless a new owner-authorized
compatibility record explicitly covers it.

Verification on Windows, Python 3.12.13:

- `uv sync --locked --all-extras`: installed the locked optional dependencies.
- `uv run --locked pytest`: 293 passed, 1 skipped, 142.64 seconds. The local
  container tests ran; only the opt-in real archive test was skipped here.
- `uv run --locked python scripts/check_example_report.py`: passed, fresh report
  byte-identical to the committed planted-signal fixture.
- `uv build --wheel`, then `uv run --isolated --no-project --with
  ./dist/research_loops-0.1.0-py3-none-any.whl python scripts/check_wheel.py`:
  isolated wheel run, evaluation, migrations, report/export and final passed.
- Local opt-in check, launched with `uv run --locked python -I -m pytest
  tests/test_grain_real.py -s -q` and `RLOOP_GRAIN_ARCHIVE` set to the supplied
  scratch archive: 1 passed in 115.16 seconds; measured computation 115.016 seconds.
  Both controls matched exactly: `12.885281385281385` and `0.12586301151517196`.
  Size, MD5 and SHA-256 verified before reading validation members. Only `val`
  members were opened. The real `test` members were never opened or evaluated.

The exact SciPy stack and attribution are in the example's PROVENANCE.md.
Deprecation warnings from the pinned stack are retained; in particular the old
strictly-smaller `min_size` behavior is needed for source compatibility.

The archive has PNG and JPEG images with PNG masks. A PNG-only extraction rule
would omit 26 of the 40 validation images and cannot reproduce the benchmark.
The narrow JPEG image allowlist was accepted, since the PNG-only rule in the
delivery prompt did not match the archive. The implementation ran no real
fetch; the archive was fetched separately for the live pilot ([record](PHASE-4B-PILOT.md)). Synthetic fixtures cover extraction, final consumption and tool isolation.
The minimal OCI image remains for planted-signal; grain uses the host declarative
tool service and never executes candidate code.

The current team scoring code uses all truth grains when `exclude_edge=false`
and interior truth grains otherwise. The older defaults artifact has NaN for an
undefined size; the current scoring code excludes undefined sizes. The main
control numbers reproduce under that current code.

Authorization-only commit `7f1cdbe1e47ee066b4c41dabc59c8184ca819775` was pushed
alone. CI run `43672496642` completed successfully on Ubuntu and Windows.
The protected hash moves from
`9c1a922e6006f18059367ade09c49733ebb430507337af960bef394ef8766d7e` to
`574d2edbce7a6211f57ef0ab8f4392f8cd86329fc2940fa53b2899c0d8edb945`.
`check_protected.py --base origin/main` passes against that trusted authorization.
The implementation `c059223` was pushed after that; CI run `43673161341`
passed on Ubuntu and Windows.

Documentation licensed CC BY 4.0.
