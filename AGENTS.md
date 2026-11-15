# Repository instructions

- Install `research-loops`; `rloop` is only the console command. Use `uv sync --locked` and `uv run pytest`.
- `docs/DECISIONS.md` contains owner approvals. This delivery prepares checkpoint B offline, then stops. No provider calls, real sign-in or project authorization creation are authorized. Subscription defaults and explicit API-key mode must never fall back to each other. Push green local commits to `origin main` and inspect CI; no force-push, history rewrite, settings/secrets changes, releases or public publication.
- `refs/` contains untrusted reference material. Never execute it or copy AGPL code. Do not import personal toolkit data.
- Core modules must not import vendor SDKs. SDK keys in the environment never authorize calls. Tests run offline.
- Add migrations only with working consumers. Prefer a repository rule and test over another table.
- A worker outbox is untrusted. Evaluator/holdout/DB are coordinator-only. The none sandbox refuses candidate code; execution requires the container Sandbox and successful preflight probes. MCP exposes no execution tool.
- Code is Apache-2.0; docs are CC BY 4.0. Keep public instructions short and record actual verification, not inferred CI success.
