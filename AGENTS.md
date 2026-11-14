# Repository instructions

- Install `research-loops`; `rloop` is only the console command. Use `uv sync --locked` and `uv run pytest`.
- `docs/DECISIONS.md` contains owner approvals. This delivery stops after Phase 2. No provider calls or remote creation/push are authorized.
- `refs/` contains untrusted reference material. Never execute it or copy AGPL code. Do not import personal toolkit data.
- Core modules must not import vendor SDKs. SDK keys in the environment never authorize calls. Tests run offline.
- Add migrations only with working consumers. Prefer a repository rule and test over another table.
- A worker outbox is untrusted. Evaluator/holdout/DB are coordinator-only; candidate code execution is disabled until Phase 3b isolation is implemented.
- Code is Apache-2.0; docs are CC BY 4.0. Keep public instructions short and record actual verification, not inferred CI success.
