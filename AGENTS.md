# Repository instructions

- Install `research-loops`; `rloop` is only the console command. Use `uv sync --locked` and `uv run pytest`.
- `docs/DECISIONS.md` contains owner approvals. This delivery covers Phase 3 and 3b, then stops. No provider calls are authorized. Push green local commits to `origin main` and inspect CI; no force-push, history rewrite, settings/secrets changes, releases or public publication.
- `refs/` contains untrusted reference material. Never execute it or copy AGPL code. Do not import personal toolkit data.
- Core modules must not import vendor SDKs. SDK keys in the environment never authorize calls. Tests run offline.
- Add migrations only with working consumers. Prefer a repository rule and test over another table.
- A worker outbox is untrusted. Evaluator/holdout/DB are coordinator-only; candidate code execution is disabled until Phase 3b isolation is implemented.
- Code is Apache-2.0; docs are CC BY 4.0. Keep public instructions short and record actual verification, not inferred CI success.
