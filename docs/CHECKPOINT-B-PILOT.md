# Checkpoint B: the first live pilot

This is the record of the first runs against real models. It includes every attempt that failed for technical reasons. A failed attempt is kept, never overwritten, and each restart got a fresh project directory.

## Setup

The owner gave the go for a pilot with the cheaper models from both vendors, to keep the cost down.

| | Claude | OpenAI |
|---|---|---|
| Backend | `claude_agent` (Claude Agent SDK) | `openai_agents` (OpenAI Agents SDK) |
| Model | `claude-sonnet-5-5` | `gpt-6.1-terra` |
| Sign-in | the owner's Claude Code subscription (`claude_code`) | Sign in with ChatGPT (`chatgpt`) |
| Effort | high | high |

The run limits were the same for both backends:
- 8 worker runs, 1 at a time;
- at most 32 turns and 300 s per worker;
- 3600 s for the whole project.

There was no API key and no fallback. The example was `planted-signal` with the locked contract: the controls run first, then each worker proposes one bounded expression, and the protected evaluator scores it on development data the worker never sees.

## Attempt log

All times are UTC on 2026-11-15. "Inference" means a model was actually called.

C counts the Claude attempts and O the OpenAI ones.

| # | Directory | Backend | Inference | Outcome | Cause | Fix |
|---|---|---|---|---|---|---|
| C1 | `claude` | Claude | no | `technical_error` after 5 s | `CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST` in the worker environment turned subscription login off | eedb16e |
| C2 | `claude-r2` | Claude | yes, short | `technical_error` after 7 s: "SDK finished without a sealed tool submission" | The CLI denied every rloop tool. The custom transport built the CLI command without `--permission-prompt-tool stdio`, so the `can_use_tool` callback was never asked | 7dec791 |
| C3 | `claude-r3` | Claude | yes, one full run | run 00 `technical_error` after 128 s: "unknown report scope"; run 01 cancelled | The model set `report_id` to `<run_id>-report`. `submit_result` accepted that, but the import requires `report_id == run_id`, and the instructions never said so. The fake backends always used the run id, so no test caught it | 1db00de |
| O0 | `openai` | OpenAI | no | refused before dispatch: "control attempt/time allowance exhausted" | This directory had been used for the offline setup check at 01:30 with `project_seconds=300`. That started its project clock, and the later amendment to 3600 s does not extend a stored deadline, by design | fresh directory `openai-r2` |
| C4 | `claude-r4` | Claude | yes, one full run | run 00 `technical_error` after 146 s: "invalid candidate node"; run 01 `cancelled` | The model followed the protocol and sealed a submission with the right scope, but wrote its expression as `{"op", "args": [...]}` with `{"const"}` and `{"var"}` leaves. The evaluator only accepts binary `{"op", "left", "right"}` nodes with `{"feature"}` and `{"constant"}` leaves, and the instructions never stated that grammar | worker protocol v2: 51abbe8, 8d6b552 |
| O1 | `openai-r2` | OpenAI | yes, one full run | run 00 `technical_error` after 33 s: "SDK finished without a sealed tool submission"; run 01 `cancelled` | The model wrote a candidate in a third grammar (a list S-expression). Its hand-encoded base64 failed three times, then it gave up on `transcript.json`, which had to contain the exact public JSON, base64-encoded by hand. The adapter saved no trace on this path | worker protocol v2: 51abbe8, 8d6b552 |
| C5 | `claude-r5` | Claude | yes, 8 runs | 8/8 `completed`, all `supported`, development MSE 0, in 2 min 11 s | — | — |
| O2 | `openai-r3` | OpenAI | yes, 8 runs | 8/8 `completed`, all `supported`, development MSE 0, in 2 min 01 s | — | — |

`claude-debug` and `claude-debug2` were single-run diagnostic copies of C1 and C2. `openai-debug` was one of O1, run through a local wrapper that saved the SDK's item trace, because the adapter itself kept none when no submission was sealed. These runs were part of finding the causes and are not pilot results.

In C3 the model followed the whole protocol:
- it read the contract and the public training samples;
- it registered a prediction;
- it proposed `y = 2·x0 − 3·x2 + x1·x3`;
- it submitted.

That single run used 20,359 output tokens (18,286 of them thinking) at an estimated $0.30; on a subscription this is an estimate, not a charge. Its candidate was never imported, so it was never scored. It was not scored out of band either, because that would bypass the protected evaluator. A later check of its grammar alone (`validate_candidate`, no data) shows it would have been rejected anyway: it uses the same `args`/`const`/`var` form as C4.

All three runs that reached the model (C3, C4, O1) inferred the planted signal from the public training samples, and all three failed at the protocol, not at the science. C4 used 23,132 output tokens (21,001 of them thinking), an estimated $0.35; much of that went into base64 and into copying the exact prompt, which the host already knows. O1 used about 33,000 tokens.

## Results

C5 and O2 ran in parallel from 02:30 UTC on worker protocol v2, each in a fresh directory, with the same contract and the same limits as the earlier attempts.
- Worker protocol v2 is 51abbe8 plus 8d6b552. CI failed on 51abbe8 alone: the committed example report still carried the old registration ids. 8d6b552 refreshed that fixture. CI run 43667767136 then passed on Ubuntu and Windows, with 226 tests.
- v2 changed the trusted base, so the registration hash moved from `ddc65dc8…` to `c6330680…`. The earlier attempts keep their old hash.

| # | Runs | Verdict | Development MSE | Tokens | Cost |
|---|---|---|---|---|---|
| C5, Claude | 8/8 `completed` | 8 `supported` | 0 | 13,906 output (8,916 of them thinking); 64 input, 42,109 cache write, 103,522 cache read | estimated $0.318 for all 8, $0.035–0.051 per run |
| O2, OpenAI | 8/8 `completed` | 8 `supported` | 0 | 69,782 input, 1,923 output (494 of them reasoning), 40 requests | not reported under Sign in with ChatGPT |

`rloop report --check` passed for both directories (exit 0). The two control evaluations ran first.

The adapter traces show the same short path in all 16 runs:
- four tool calls: `read_contract`, `read_artifact` (the training samples), `register_variant`, `submit_result`;
- the first submission was valid every time, with no grammar error, no tool error and no retry;
- every run submitted the same tree, `y = 2·x0 − 3·x2 + x1·x3`, which is the planted signal. Identical candidates evaluate identically, so all 16 point to one evidence object (`53782a68…`).

Compared with the failed attempts, C5 used 13,906 output tokens for eight runs, where the single failed C4 run used 23,132. O2 used about 9,000 tokens per run, where O1 used about 33,000.

**What this shows.** The whole path works with real models from both vendors, on subscription sign-in and without API keys: locked contract, controls, pre-registration, MCP-only tools, host-written transcript and scope, protected evaluator, import and report gate.

**What it does not show.** It shows no scientific value. `planted-signal` is a sanity task with a known answer that the public training samples make easy to find. Sixteen identical answers also mean that parallel runs added no diversity on this task. That is expected for a sanity task, and it is the open question for a real problem. The Claude cost is the SDK's estimate, and subscription use is not billed per token; the OpenAI cost is unknown.

**Open follow-ups:**
- The report still uses the wording of the fake backend for real runs: the header "Planted signal — simulated", the line "Fake proposals demonstrate execution and evidence handling…", and the tag `[simulated]` on "Attempted variants". The label should come from the backend that actually ran.
- Scaling beyond this pilot (for example to 48 worker runs) needs a new go from the owner.

## What the failures taught

- **Fakes hide the contract the model never saw.** Every scope field a model has to fill in must be stated in its instructions and checked where the model can still correct it (at `submit_result`), not only later at import. Since 1db00de a wrong `report_id` is rejected at submit time with a message the model can act on.
- **The model supplies the science; the host supplies everything it already knows.** Three different expression grammars came back from two vendors, because the instructions never named one. Scope ids, hashes and the transcript envelope are known to the trusted host, and asking a model to copy them (in base64, by hand) cost most of its tokens and lost O1 entirely. Worker protocol v2 states the grammar, validates the candidate at submit time with an error the model can act on, and lets the host write the transcript and the report scope.
- **A failure must leave evidence.** O1 could only be diagnosed with a separate debug run, because no trace was saved when no submission was sealed. In v2 the adapter keeps the trace on that path too.
- **A failure must name its cause.** The batch error first surfaced as "unhandled errors in a TaskGroup", and the cancelled sibling run was labelled `timed_out`. Since 1db00de the CLI prints the underlying error, and siblings are recorded as `cancelled`.
- **The project clock is part of the evidence.** A directory used for an offline check has spent its project time, and an amendment will not give it back. Live pilots start in a fresh directory.
