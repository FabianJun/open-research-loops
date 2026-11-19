# open-research-loops

Test your research idea with AI and see what really holds up.

## What it does
You set a research question and what would disprove it before any result exists. The agent writes the code and runs several attempts in parallel, a protected scoring program that the attempts cannot touch scores each one the same way, and you give the verdict. You get a report that tags each result as measured or simulated and keeps negative results; in coached mode you also get a research brief and your own method card.

## Interfaces
- Skill: eight skills under `skills/`, with `skills/rloop-coach/SKILL.md` for coached mode and `AGENTS.md` as the entry for agents.
- CLI: `rloop`, for example `rloop init`, `rloop status`, `rloop report` and `rloop pilot`.
- MCP: the six tools each parallel attempt may use, `read_contract`, `read_findings`, `read_artifact`, `register_variant`, `write_artifact` and `submit_result`, and nothing else (`docs/DESIGN.md`).
- Python: `research_loops`, distributed as `research-loops` from source.

## Works best with
Any agent app that can read files, run commands and search the web, plus uv and Python 3.12 or newer on Windows or Linux. The offline example runs in a terminal and calls no model. On Windows, Smart App Control can block the programs that setup creates.

## Who it suits
Researchers and students who want to test an idea with AI and keep honest evidence, without coding themselves.

## Status
ready

## Install
- Claude Code: paste a starter from the README; the agent clones the repository, runs `uv sync --locked` and follows `AGENTS.md`.
- Codex: paste a starter from the README; the agent clones the repository, runs `uv sync --locked` and follows `AGENTS.md`.
- Other apps: paste a starter from the README into any app that can clone a repository, run commands and read `AGENTS.md`.

## Licence
Apache-2.0 for code, `SKILL.md` and prompt files; CC BY 4.0 for texts and images. The adapted review rubric and the skill versions published before the licence change keep CC BY 4.0 (see NOTICE).

## Link
https://github.com/scaled-thinking/open-research-loops
