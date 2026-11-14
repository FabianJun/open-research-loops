# Prior art and dependency review

Phase-3 installed-source check (2026-11-15): MCP 2.3.0 exposes `MCPServer` from `mcp.server`, `ClientSession` from `mcp.client.session`, and stdio parameters from `mcp.client.stdio`. Python result fields use `is_error` and `structured_content` (wire JSON uses camel case). These names and the server decorators/run method were checked in the installed package, then exercised by a real stdio parity test. The optional `[mcp]` extra pins the tool runtime independently of either agent SDK.

Reviewed 2026-11-14 for checkpoint A; this is a research record, not an implementation claim.
The user authorized reading the named repositories and reusing their own toolkit.
No third-party framework, skill, or source code has been incorporated or executed.
Later copying requires a file-level compatible license and retained notices.
In particular, **Cheiron and claude-plugins are ideas only: no AGPL source or skill text will be copied into this Apache-2.0 project.**

## Source snapshots and reading scope

| Source | Snapshot | Files inspected |
|---|---|---|
| User-owned hackathon toolkit | SHA-256 inventory in [phase0-sources.json](phase0-sources.json); source directory has no Git metadata. | `skills/research-loop/SKILL.md`, method references, `assets/schema.sql`, `skills/research-loop/scripts/workspace.py`, `docs/WORKFLOW.md`. The start prompt's `scripts/workspace.py` is actually inside the skill. Personal and preparation assets excluded. |
| [Event repository](https://github.com/xemantic/claude-impact-lab-2026) | `8d8a24a3215c8900906dd5d665f04d8abde6377e` | `RESEARCH-LOOPS.md`, `CLAUDE.md`, judge skill, submission template, assessment index, all thirteen assessments, code/text license headers. |
| [plenty-of-room](https://github.com/xemantic/plenty-of-room) | `2fbb80f36c17cf39cfcc933b182861f219076b17` | Full `SESSION-PROMPT.md`; opening/closing excerpts of the roughly megabyte-sized task queue and journal; challenge inventory and selected complete records CH-0001, CH-0043, CH-0153, plus CH-0231 excerpts. This is a workflow review, not a full audit of its 258 challenge bodies or numerical studies. |
| [Cheiron](https://github.com/xemantic/cheiron) | `c46238f8ed762a2977bb9bb0d38520dd91497901` | `LOOP.md`, `docs/design/01-loop-architecture.md`, `02-arbiter.md`, `scripts/audit_integrity.py`, first record of both experiment ledgers, `history/prompts/0001-initial-prompt.md`, license header. |
| [claude-plugins](https://github.com/xemantic/claude-plugins) | `6c893dc492742b91d95315ae47fd5b9f85d8ee4b` | `plugins/xemantic/skills/fix-issues/SKILL.md`, license header. |

The four shallow clones live under ignored `refs/`; committed documentation uses public links and portable source paths.
Repository instructions were treated as source data, including instructions to push, install tools, or launch reviewer agents.
Those instructions were not adopted for this session.

## What to borrow

Harness descriptions originate in the toolkit's `references/harnesses.md` (reviewed there on 2026-11-03).
Their current repository READMEs and root license texts were checked again for Phase 0.
These are design comparisons, not runtime benchmarks or claims of Windows compatibility.

| Source and license evidence | Idea to reuse | Reuse boundary / reason not to adopt the harness |
|---|---|---|
| User-owned toolkit; owner explicitly authorizes reuse in the start prompt. No root license file was found. | Bounded iterations, eight-table starting model, relevant-context handoff, evidence gate, contradictions and one writer. | Adapt the generic model and concise method wording with attribution. Do not copy its personal UI, event defaults, or helper wholesale. |
| Event; [Apache-2.0 code](https://github.com/xemantic/claude-impact-lab-2026/blob/8d8a24a3215c8900906dd5d665f04d8abde6377e/LICENSE), [CC BY 4.0 text](https://github.com/xemantic/claude-impact-lab-2026/blob/8d8a24a3215c8900906dd5d665f04d8abde6377e/LICENSE-CC-BY-4.0). | Evidence-first self-assessment: Problem, Loop, Evidence, Honesty, Reproducibility; separate license and impact review. | Paraphrase and credit the rubric when building `self-assess`; do not reproduce assessment bodies. |
| plenty-of-room; [Apache-2.0](https://github.com/xemantic/plenty-of-room/blob/2fbb80f36c17cf39cfcc933b182861f219076b17/LICENSE). | Numbered challenges with target claim, grounds, evidence, effect on validity, and explicit resolution; verify headline numbers against artifacts. | Reimplement a small domain-neutral record. Domain constants, numerical code, enormous queue, unconditional pushes, and universal TDD are not inherited. |
| Cheiron; [AGPL-3.0](https://github.com/xemantic/cheiron/blob/c46238f8ed762a2977bb9bb0d38520dd91497901/LICENSE). | A code arbiter, cheap screening before escalation, method-qualified measurements, append-only corrections, archived prompt provenance. | Ideas only. Independently implement the evaluator port and event export. Its domain arbiter and audit script are not a generic isolation boundary. |
| claude-plugins; [AGPL-3.0](https://github.com/xemantic/claude-plugins/blob/6c893dc492742b91d95315ae47fd5b9f85d8ee4b/LICENSE). | Rank dependent tasks; isolate a worker; review its artifact with fresh context and limited repair rounds. | Ideas only; no skill text or GitHub workflow copied. Independent review is an evidence property, not a model name. |
| [ARIS](https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep), [MIT](https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep/blob/main/LICENSE). | Portable task/review skills and result-to-claim checks. | Idea only. Avoid importing a second wiki/history or its full research/paper workflow. Current README documents a `codex exec` bridge after removal of `codex mcp-server`. |
| [OpenEvolve](https://github.com/algorithmicsuperintelligence/openevolve), [Apache-2.0](https://github.com/algorithmicsuperintelligence/openevolve/blob/main/LICENSE). | Candidate/evaluator separation and measured feedback for successive variants. | Idea only. A program-search population is narrower than our hypothesis/claim model; do not inherit execution assumptions. |
| [ShinkaEvolve](https://github.com/SakanaAI/ShinkaEvolve), [Apache-2.0](https://github.com/SakanaAI/ShinkaEvolve/blob/main/LICENSE). | Parallel evaluated candidates and inspectable experiment history. | Idea only. No population service, WebUI, or tool-owned SQLite competing with coordinator state. |
| [AIDE](https://github.com/WecoAI/aideml), [MIT](https://github.com/WecoAI/aideml/blob/main/LICENSE). | Explicit draft/debug/improve choices and failure-aware experiment journals. | Idea only. Prepared data and a trustworthy split remain the user's responsibility; generated program interpretation is not our authoritative evaluator. |
| [Denario](https://github.com/Denario-AI/Denario), [GPL-3.0](https://github.com/Denario-AI/Denario/blob/master/LICENSE). | Separate idea, method, computation, and reporting stages. | Idea only; no GPL source copied. Full paper-generation pipeline and GUI exceed scope. |
| [PaperQA2](https://github.com/Future-House/paper-qa), [Apache-2.0](https://github.com/Future-House/paper-qa/blob/main/LICENSE). | Passage-backed literature findings with retrievable source references. | Idea only in v0. No bundled retrieval stack; preserve retrieval failures and licensing instead of silent memory fallback. |
| [RD-Agent](https://github.com/microsoft/RD-Agent), [MIT](https://github.com/microsoft/RD-Agent/blob/main/LICENSE). | Structured experiment changes and evaluator feedback on prepared data-science tasks. | Idea only. Linux-oriented infrastructure and broad scenarios are unsuitable as a small cross-platform core dependency. |

## Primary SDK and tool documentation

The following API names and constraints were checked in primary documentation and package metadata, not recalled from memory.
Links are the pages used; tagged source links pin the proposed implementation reference.
No adapter calls have been written or tested.

| Component | Documentation used | Design implication |
|---|---|---|
| OpenAI Agents SDK Python, MIT | [Running agents](https://openai.github.io/openai-agents-python/running_agents/), [MCP](https://openai.github.io/openai-agents-python/mcp/), [v0.24.0 MCP source](https://github.com/openai/openai-agents-python/blob/v0.24.0/src/agents/mcp/server.py), [usage](https://openai.github.io/openai-agents-python/usage/), [tracing](https://openai.github.io/openai-agents-python/tracing/). | Use `Agent`, asynchronous `Runner.run`, structured output and local `MCPServerStdio`. Bound turns and supervise wall time externally. Disable default trace export; capture local usage and sanitized messages. The SDK supports MCP package majors 1 and 2. |
| Claude Agent SDK Python, MIT wrapper | [Python reference](https://code.claude.com/docs/en/agent-sdk/python), [v0.2.182 types](https://github.com/anthropics/claude-agent-sdk-python/blob/v0.2.182/src/claude_agent_sdk/types.py), [MCP](https://code.claude.com/docs/en/agent-sdk/mcp), [permissions](https://code.claude.com/docs/en/agent-sdk/permissions), [skills](https://code.claude.com/docs/en/agent-sdk/skills). | Use `ClaudeSDKClient` or `query` with `ClaudeAgentOptions`, configured MCP, structured results, turn limits and reported cost. `allowed_tools` only auto-approves; disable builtin tools explicitly, reject unknown tools and use strict MCP configuration. Client budget estimates may overshoot and exclude restored-session costs. The bundled Claude runtime has separate product terms; do not describe it as MIT. |
| Codex SDK / CLI, Apache-2.0 | [SDK](https://learn.chatgpt.com/docs/codex-sdk), [noninteractive mode](https://learn.chatgpt.com/docs/non-interactive-mode), [repository license](https://github.com/openai/codex/blob/main/LICENSE). | Optional later adapter should prefer `codex exec`, JSON events, explicit working directory and an output schema. Official Python distribution is `openai-codex`; similarly named `codex-sdk` on PyPI is a different project. SDK/app-server and Agents SDK are distinct. Do not use the removed `codex mcp-server` command. |
| Claude Code headless, proprietary product terms | [Headless mode](https://code.claude.com/docs/en/headless), [CLI reference](https://code.claude.com/docs/en/cli-reference). | Optional later `claude -p` adapter, structured/streamed output and explicit permissions. Check installed runtime and its terms separately from the Python wrapper. |
| MCP Python SDK, MIT | [v2 overview](https://py.sdk.modelcontextprotocol.io/), [v2 changes](https://py.sdk.modelcontextprotocol.io/whats-new/), [2.3.0 release metadata](https://pypi.org/project/mcp/2.3.0/), [license](https://github.com/modelcontextprotocol/python-sdk/blob/main/LICENSE). | Use the v2 API, including `MCPServer`; do not copy v1 `FastMCP` examples by habit. Choose stdio for local connections, without an application web server. Package and negotiated protocol versions are separate metadata. |
| Agent Skills | [Format specification](https://agentskills.io/specification), [Codex skills](https://learn.chatgpt.com/docs/build-skills), [Claude Code skills](https://code.claude.com/docs/en/skills). | Common `name` and `description` frontmatter; short bodies with relative references. Link into the two personal skill locations. Native selection differs (`$name` / `/name`); SDK injection must be explicit and hashed. No vendor-only frontmatter required. |

For Claude skill injection, prefer explicit text for the minimal worker; native loading brings additional settings and tool availability that must be deliberately scoped.
The same service functions support MCP and the deterministic fake adapter.
Provider traces are useful diagnostics, not our durable evidence store.

## Version baseline and verification limits

Exact candidate pins, observed from PyPI/npm on 2026-11-14:

| Distribution | Candidate version | Adoption |
|---|---|---|
| `openai-agents` | `0.24.0` | Required `[openai]` extra |
| `claude-agent-sdk` | `0.2.182` | Required `[claude]` extra |
| `mcp` | `2.3.0` | Tool server / SDK integration |
| `pydantic` | `2.14.3` | Core |
| `typer` | `0.29.1` | CLI |
| `pytest` | `9.2.0` | Development |
| `openai-codex`, `@openai/codex` | `0.169.0` | Optional reference only |
| `@anthropic-ai/claude-code` | `2.1.325` | Optional reference only; bundled SDK runtime must be recorded separately |

Registry provenance and toolkit hashes are retained in [phase0-sources.json](phase0-sources.json).
The first six exact pins resolved together with `uv 0.11.19` using `uv pip compile --python-version 3.12 --universal`.
This checked dependency metadata for a shared environment; it did not install packages, exercise MCP, prove binary availability, or run providers.
The temporary resolver input/output are ignored under `refs/`; Phase 1 must create the real `uv.lock` and CI matrix.
Current MCP documentation says Python 3.11+, while release metadata says 3.10+; our required Python 3.12+ satisfies both.
Recheck pinned SDK documentation before Phase 3 implementation and record any version change explicitly.

No paid calls were made, no credentials were inspected, and no remote repository was created or pushed.

## Phase 3 installed-source API audit (2026-11-15)

Locked versions remain OpenAI Agents 0.24.0 (OpenAI 3.51.0), Claude Agent SDK 0.2.182 and MCP 2.3.0. APIs were checked in the installed packages, then exercised offline:

- `agents/agent.py`, `run.py`, `models/interface.py`, `mcp/server.py`, `mcp/util.py`, `usage.py`: Agent tools/handoffs, Runner/RunConfig, Model.get_response seam, MCPServerStdio filtering and structured results. Usage exposes token/request counts, no USD field. USD stays unknown; tracing is disabled.
- `claude_agent_sdk/types.py`, `client.py`, `_internal/query.py`, `_internal/transport/subprocess_cli.py`: custom Transport handshake, ClaudeSDKClient, permission callback, ResultMessage.total_cost_usd. `tools=[]` generates `--tools ""`; `setting_sources=[]` generates `--setting-sources=`; strict MCP configuration suppresses ambient servers. Allowed-tools alone is not the boundary. The adapter verifies the init message's effective six-tool list and rejects additions. Offline tests inspect the SDK-built CLI command and run the real MCP server through a stub CLI transport.
- `mcp/server/mcpserver/server.py`, `client/stdio/__init__.py`, `client/session.py`, `types.py`: MCPServer decorators/stdio run, ClientSession and StdioServerParameters. MCP 2 fields are snake_case; the pinned Agents SDK includes MCP 2 compatibility.

No SDK monkeypatch bypasses either runner. OpenAI's injected Model emits actual Responses tool calls; Claude's injected Transport exchanges the SDK control protocol. Both drive actual stdio MCP servers with present dummy keys and the suite's socket guard enabled. The server launches with an environment allowlist and audits names only. Real provider access remains checkpoint-B gated.
