<div align="center">

<img src="docs/assets/social-preview.jpg" width="100%" alt="open-research-loops: parallel AI research loops that keep their evidence honest. Risograph print in red, teal and blue: eight thin threads loop through separate experiments side by side, the ones that hold pass through the eye of a red needle and leave as one tidy blue braid, two stop short in tied-off knots.">

**Parallel AI research loops that keep their evidence honest.**

For researchers and students working with a coding agent. No coding needed.

[![tests](https://github.com/scaled-thinking/open-research-loops/actions/workflows/tests.yml/badge.svg)](https://github.com/scaled-thinking/open-research-loops/actions/workflows/tests.yml)
[![you decide: question and verdict](https://img.shields.io/badge/you_decide-question_and_verdict-c4432b)](#two-ways-to-work)
[![your agent: any capable coding agent](https://img.shields.io/badge/your_agent-any_capable_coding_agent-2f5bea)](#two-ways-to-work)
[![evidence: checked, negatives kept](https://img.shields.io/badge/evidence-checked%2C_negatives_kept-0e7c7b)](#measured-not-promised)
![python 3.12+](https://img.shields.io/badge/python-3.12%2B-59636e)
[![licence: Apache-2.0 · CC BY 4.0](https://img.shields.io/badge/licence-Apache--2.0_%C2%B7_CC_BY_4.0-59636e)](#names-and-licences)
![status: pre-alpha](https://img.shields.io/badge/status-pre--alpha-59636e)

[Two ways to work](#two-ways-to-work) · [Quickstart](#quickstart) · [How it works](#how-it-works) · [Why this exists](#why-this-exists) · [Backends](#backends) · [Measured, not promised](#measured-not-promised)

<br/>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/loop-dark.svg">
  <img alt="The loop: your question and locked contract, then fan out agent workers that only use MCP tools, import and hash their outputs, evaluate them with a protected plain-code evaluator, and render an evidence-tagged report. Findings feed the next round; the holdout never does. Legend: person icon for your decisions, checkbox for your agent and the workers it starts, check for route and evidence; infrastructure is neutral." src="docs/assets/loop-light.svg" width="100%">
</picture>

</div>

You set the question and what would disprove it, before any result exists. Your agent writes the
code and runs the workers in parallel. Every thread then passes the same needle, a protected
evaluator: what holds joins the report, and what fails stays in it as a negative result.

The runtime enforces each step as a rule, and every rule answers a failure found in the published
assessments of thirteen research-loop projects ([why this exists](#why-this-exists)).

## Two ways to work

Your own coding agent, any capable one, handles code, evaluators, compute and CI. The workers it
starts are separate sessions on one of the [backends](#backends). Pick a mode and paste its starter
into your agent.

### Autonomous

You delegate. The agent proposes a bounded plan and works within your permissions.

```text
Mode: autonomous
Use open-research-loops and follow AGENTS.md. Handle the technical work,
propose a bounded research plan and work within my permissions.
My question: …
```

### Coached

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/competence-dark.svg">
  <img alt="Competence-enhancing AI makes you more capable, not more dependent: it explains, you decide, and you keep what you learn." src="docs/assets/competence-light.svg" width="100%">
</picture>

You learn research design while the experiment gets done. The agent explains and suggests; you
decide on the method.

```text
Mode: coached
Use open-research-loops and skills/rloop-coach/SKILL.md. Coach me on research
design and do the technical work. Explain the methods; let me decide.
Reply in my language. My question: …
```

The agent starts with `rloop init PROJECT --mode coached`, agrees the contract with you and records
your predicted number with `rloop predict` before anything is scored.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/route-dark.svg">
  <img alt="One route, two roles. Five stages: your question (step 1), a fair test (steps 2–3), plan and predict (steps 4–5), run once (steps 6–7), reflect (step 8). At each stage you decide: your question and what disproves it, what the score means and what counts as fair, your idea and choice and predicted number, the budget then your verdict before the agent interprets, and your method card in your own words. Your agent does the technical work: it checks licences, data rights, privacy and your academic rules where applicable first, makes the rule executable and prepares fair baselines, offers safe, unusual and no-GPU options, states cost first and tests before scoring the frozen candidate once with a protected evaluator, then asks short questions and drafts your method card. You leave with a checked result, a research brief and your own method card." src="docs/assets/route-light.svg" width="100%">
</picture>

Your view comes first at four moments (question, first idea, prediction, verdict), one question per
reply; elsewhere the agent gets on with the work and names the step. Say “shorter”, “explain more”
or “just do it” at any time.

The brief is the project's `BRIEF.md`; an optional competence profile stays on your machine. Every
method has a [card](skills/rloop-coach/references/methods.md) with its reason, steps and limits.

**A real example, negative result included.** A small U-Net was scored once against a team's
grain-counting pipeline: val error **0.1639** against **0.1259**, lower is better, so no win. In
review, the owner identified two problems: the team's number was tuned on the same 40 val images,
and 40 images leave a wide 95% interval of 0.119 to 0.231. A coached agent raises a **fair
comparison** and **sample size and intervals** before the run
([what happened](experiments/grain-cnn/README.md#interpretation-added-after-the-result)).

All eight steps, the levels and the private profile: [COACHED](docs/COACHED.md).

## Quickstart

You need [uv](https://docs.astral.sh/uv/) and Python 3.12+ on Windows or Linux. Nothing here calls a
model provider.

```console
git clone https://github.com/scaled-thinking/open-research-loops
cd open-research-loops
uv sync --locked
uv run rloop init my-pilot --question "Can we recover a planted nonlinear signal?"
```

In under two seconds, `init` registers a contract, runs the controls, scores two simulated candidates
with the protected evaluator and writes `my-pilot/.rloop/report.md`. Every statement in it carries a
provenance tag such as `[measured]` or `[simulated]`.

> [!NOTE]
> The planted-signal example is **simulated**: its fake workers know the answer on purpose, so it
> shows that the machinery works, not that agents can do research. In the
> [live pilot](docs/CHECKPOINT-B-PILOT.md), real models from two vendors found the same planted
> answer from the public training samples. A real question needs its own data, contract and evaluator.

The full example campaign, the report format and every offline command: [GUIDE](docs/GUIDE.md).

## How it works

Workers never touch the database or the evaluator. Each writes to a private outbox; the coordinator
validates, hashes and imports those bytes, and the protected evaluator scores exactly what was
imported. A worker sees six MCP tools and nothing else, optionally inside a container without network.

The full sequence, the evidence gate, worker isolation and the code map:
[HOW-IT-WORKS](docs/HOW-IT-WORKS.md).

## Why this exists

Thirteen submissions to the *Claude Impact Lab x Foresight Institute — AI Research Loops for Open
Science Problems* hackathon (Berlin, November 2026) pointed agent loops at open science problems.
Their published assessments show the same failures again and again, and those failures are about
the loop, not the science. `rloop` turns each one into a rule the runtime enforces.

| What the assessments found | What `rloop` enforces |
|---|---|
| A planner loosened its own success threshold | Goal, falsifier, thresholds, seeds and evaluator hash are registered and immutable before the first dispatch |
| A later prompt included test scores; truth files sat in public view | Workers see an allowlisted public projection. Evaluator, holdout and database never enter their view. The final evaluation is a one-use ticket |
| A stale verdict was picked by file modification time | Imports are hash-checked and content-addressed; selection uses immutable IDs, never mtimes |
| Planted defects were too easy to catch; a review target was constant | Controls run first. A failed or uninformative control blocks the pilot |
| Variants went uncommitted; single seeds; intervals dropped | Every proposal, variant and retry gets a durable attempt ID. Seeds, keep margin and intervals appear in the report |
| An orchestrator changed a protected spec together with its hash | Hash anchors sit outside worker authority. A change needs a recorded human decision and creates a new version |
| Headline numbers had no saved artifacts behind them | Reports render from the database, every statement carries a provenance tag, and CI fails when a committed report drifts |

Each lesson with a link to its assessment: [LESSONS](docs/LESSONS.md).

## Backends

These backends run the workers, not your own agent.

| Backend | Install | Signs in with | Status |
|---|---|---|---|
| `fake` | base package | nothing; deterministic and offline | Default. Drives the example and CI |
| `claude_agent` | `uv sync --extra claude` (Claude Agent SDK) | your own Claude Code login | Live pilot passed: 8/8 supported ([record](docs/CHECKPOINT-B-PILOT.md)) |
| `openai_agents` | `uv sync --extra openai` (OpenAI Agents SDK) | Sign in with ChatGPT for open-source apps (preview): `rloop auth login-openai` | Live pilot passed: 8/8 supported ([record](docs/CHECKPOINT-B-PILOT.md)) |

- **Subscription sign-in by default.** An API key in the environment never authorizes a call;
  API-key mode is an explicit choice.
- **The owner approves each live run.** The authorization in `project.json` names the owner,
  provider, exact model, auth mode, effort and four run limits. `rloop init --owner NAME` sets the
  owner (default: Git `user.name`, then the OS login). Without an authorization, `rloop pilot`
  refuses before any SDK or tool starts.
- **No silent fallback.** A rate or usage limit stops the pilot and cancels its siblings: no retry,
  no switch to another model, account or auth mode.
- **Honest cost.** Token usage is recorded and cost is estimated; an unknown cost stays unknown,
  never zero.

```console
$ uv run rloop auth preflight --backend claude_agent        # offline check, reads no credentials
$ uv run rloop auth login-openai                            # browser sign-in, Sign in with ChatGPT
$ uv run rloop auth models                                  # models your account lists; no automatic fallback
$ uv run rloop pilot pilots/claude --backend claude_agent --workers 8
```

Step-by-step handoff with example configs: [CHECKPOINT-B-PREP](docs/CHECKPOINT-B-PREP.md). Training
jobs run separately through `rloop compute` on a local, Kaggle, manual (for example Colab) or
command-configured host: [COMPUTE](docs/COMPUTE.md).

## Measured, not promised

| What | Result |
|---|---|
| First live pilot, planted-signal, 8 worker runs per backend | `claude-sonnet-5-5`: **8/8 supported** in 2 min 11 s, estimated USD 0.32 in total. `gpt-6.1-terra`: **8/8 supported** in 2 min 01 s, about 72k tokens, cost not reported under ChatGPT sign-in. Every first submission was valid |
| First real problem, grain counting on 316L micrographs, 4 worker runs per backend | Controls reproduced to 1e-9; 8/8 completed and re-checked on the first attempt. Best development `max_rel_error`: Terra **0.126**, the published baseline resubmitted; Sonnet **0.141**. Pre-registered target 0.10 **not reached**. Holdout: 0.176 and 0.182 |
| Grain U-Net, one pre-registered training run | Val `max_rel_error` **0.1639**, scored once; team pipeline 0.1259. **No win** ([record](experiments/grain-cnn/README.md)) |
| Offline test suite, network blocked in the test process | CI: Ubuntu **463 passed, 1 skipped**; Windows **457 passed, 7 skipped** (container tests skip there). Includes real worker and evaluator containers, and both SDK adapters against stubs with real MCP subprocesses |

Commands and raw results: [Phase 2](docs/PHASE-2-STATUS.md), [Phase 3](docs/PHASE-3-STATUS.md), the
[pilot record](docs/CHECKPOINT-B-PILOT.md) with every live attempt (six failed before the worker
protocol fix) and the [Phase 4b record](docs/PHASE-4B-PILOT.md).

## Roadmap

- **Done:** the offline core and its integrity gates, MCP workers on two vendor SDKs in an OCI
  sandbox, live pilots on both, portable agent skills, a first real problem, compute jobs and coached
  mode.
- **Planned:** a provider comparison on real work.
- **Not yet:** a positive scientific result, a PyPI release.

## Documentation

| Document | Read it for |
|---|---|
| [GUIDE](docs/GUIDE.md) | Offline commands from install to the grain benchmark |
| [COACHED](docs/COACHED.md) | Coached mode: the route, levels, competence profile |
| [HOW-IT-WORKS](docs/HOW-IT-WORKS.md) | One loop step by step, the evidence gate, worker isolation, the code map |
| [LESSONS](docs/LESSONS.md) | What the thirteen assessments showed, and the rule each lesson became |
| [DESIGN](docs/DESIGN.md) | Architecture, contracts, information flow, database, threat model |
| [REQUIREMENTS](docs/REQUIREMENTS.md) | Every requirement traced to a design section and an acceptance check |
| [DECISIONS](docs/DECISIONS.md) | Owner decisions per checkpoint |
| [CHECKPOINT-B-PILOT](docs/CHECKPOINT-B-PILOT.md) | Every live attempt on both vendors, what failed, why, and what fixed it |
| [COMPUTE](docs/COMPUTE.md) | Training jobs on local and hosted compute |
| [PRIOR-ART](docs/PRIOR-ART.md) | Credited sources, SDK references, pinned versions |

## Names and licences

The distribution is `research-loops`, the import is `research_loops`, the command is `rloop`. It is
not on PyPI yet; install from source as shown above. The unrelated PyPI package `rloop`, a Rust
asyncio event loop, is never a dependency.

Code is licensed under [Apache-2.0](LICENSE), documentation under [CC BY 4.0](LICENSE-CC-BY-4.0); see
[NOTICE](NOTICE). The core is an independent implementation. Ideas from the event's material and
other projects are credited in [PRIOR-ART](docs/PRIOR-ART.md); no AGPL code is included.
