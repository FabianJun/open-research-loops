# Phase 4b: the first live pilot on a real problem

This is the record of the first live runs on a real, licensed problem with a published baseline. The authorization is in [DECISIONS](DECISIONS.md#phase-4b-authorization--2026-11-15), and the implementation is in [PHASE-4B-STATUS](PHASE-4B-STATUS.md). Both backends completed on their first attempt. The pre-registered target was **not** reached.

## Setup

**Problem.** Count and size the grains in 316L stainless steel micrographs. The benchmark is project #5 of the Claude Impact Lab 2026, `VanishJr/micrograph-impact-lab@9175855` (Apache-2.0). The data is Zenodo 22039777 (Warren et al., Comp. Mat. Sci. 233, 2024). The images are never redistributed, see [provenance](../examples/grain-316l/PROVENANCE.md).

**Candidate.** A JSON object of pipeline parameters, never code. It has denoise, boundary detector, markers, sizes and thresholds, and is scored by the protected evaluator.

**Metric.** `max_rel_error` on 40 development images. It is the larger of two medians: the median relative count error and the median relative size error over interior grains.

**Pre-registration.** Supported if the development `max_rel_error` is at most 0.10. The team's published final reached 0.1259 on development and 0.1739 on holdout.

**Controls.** Both must reproduce within 1e-9 before any worker runs:
- the defaults `{}` must score 12.885281385281385;
- the team final must score 0.12586301151517196.

| | Claude | OpenAI |
|---|---|---|
| Directory | `pilots/grain-claude` | `pilots/grain-openai` |
| Backend | `claude_agent` | `openai_agents` |
| Model | `claude-sonnet-5-5` | `gpt-6.1-terra` |
| Sign-in | Claude Code subscription | Sign in with ChatGPT |
| Effort | high | high |

**Limits.** These were the same for both backends:
- 4 worker runs, 1 at a time;
- 32 turns and 300 s per worker;
- 3600 s per project;
- no API key, no fallback.

**Protocol v3.** Each worker could read the contract and the public per-image training statistics. It could call `try_on_training(params)` up to 6 times; each call runs on the first 32 sorted training images. It then submitted one candidate.

**Arms.** For live workers, the two `agent` and two `random` runs are four replicates. The arm label reaches the worker context but changes no instruction. The grain selection takes the best of all four.

**Hashes.** The registration hash was `dddd23c2…` for both projects. The protected hash was `574d2edb…`, from code at c059223.

## Attempt log

All times are UTC on 2026-11-15. The two backends ran at the same time, one worker each.

| # | Directory | Inference | Outcome | Duration |
|---|---|---|---|---|
| G-C1 | `grain-claude` | yes, 4 runs | 4/4 `completed` and `checked`, all `not supported` | 03:40:36–03:43:50, 3 min 14 s including controls |
| G-O1 | `grain-openai` | yes, 4 runs | 4/4 `completed` and `checked`, all `not supported` | 03:40:38–03:45:25, 4 min 47 s including controls |

There were no technical failures and no restarts. Every run made one valid submission. The independent re-check confirmed every verdict.

## Development results

Lower is better. The cited team development score is 0.1259. "Sel." marks the run selected for the final holdout.

| Run | Main settings | max_rel_error | Count | Size | Sel. |
|---|---|---|---|---|---|
| Claude agent-7-00 | sobel, peaks, σ 5, line 4, min_distance 60, footprint 61, min_area 3000, filled | 0.1672 | 0.1623 | 0.1672 | |
| Claude agent-7-01 | tophat, h-maxima h 5, σ 5, line 9, min_area 4000, filled | 0.2638 | 0.2638 | 0.2026 | |
| Claude random-7-00 | sobel, peaks, σ 5, line 5, min_distance 55, footprint 51, min_area 3000, filled | **0.1414** | 0.1414 | 0.1337 | ✓ |
| Claude random-7-01 | identical to agent-7-00 | 0.1672 | 0.1623 | 0.1672 | |
| OpenAI agent-7-00 | tophat, h-maxima h 5, σ 5, line 15, min_area 2500 | 0.1909 | 0.1909 | 0.1265 | |
| OpenAI agent-7-01 | tophat, h-maxima h 5, σ 4, line 15, min_area 1500: the team final | **0.1259** | 0.1111 | 0.1259 | ✓ |
| OpenAI random-7-00 | tophat, h-maxima h 5, σ 4, line 15, min_area 2500 | 0.1752 | 0.1752 | 0.1127 | |
| OpenAI random-7-01 | tophat, h-maxima h 5, σ 4, line 15, min_area 2600 | 0.1990 | 0.1990 | 0.1244 | |

OpenAI agent-7-01 also set `footprint` 15 and `min_distance` 8. Those are the defaults, and the evaluator uses them only with `peaks` markers, so the proposal is the team final, which the public contract lists as a control.

## Final holdout

The holdout has 165 images, with size defined for 164. It was consumed once per backend with `rloop run --final`. Both campaigns are now sealed, and `report --check` passes on both. `self-assess` says `public-ready: needs human review`.

| Backend | Selected run | Holdout max_rel_error | Count | Size | vs cited team 0.1739 |
|---|---|---|---|---|---|
| Claude | random-7-00 | 0.1818 | 0.1818 | 0.1453 | −0.0079 |
| OpenAI | agent-7-01 (team final) | 0.1765 | 0.1765 | 0.1630 | −0.0026 |

**Holdout reproduction gap.** The OpenAI final is the team's own pipeline. Its holdout size error matches the team's published value to every digit, 0.1629683115862643. Its count error is 0.1765, not the published 0.1739. The port reproduces both development numbers exactly, but not the holdout count.

The cause was not investigated, because that would mean scoring the test split outside `--final`. As a result, the "vs cited team" column compares against a number this evaluator does not reproduce. Against the port's own team-final score of 0.1765, the Claude final is 0.0053 worse.

## Tokens and cost

| | Claude | OpenAI |
|---|---|---|
| Input tokens | 84 uncached, 104,543 cache writes, 533,958 cache reads | 1,385,165, of which 385,280 cached |
| Output tokens | 11,485 | 2,512 |
| Requests | not reported | 44 (11 per run) |
| Cost | SDK estimate USD 0.587 under the subscription, not a charge | not reported under ChatGPT sign-in |

Each OpenAI request resends the whole conversation, including the 65 KB training statistics, so its input is about 340k tokens per run.

## Tool use

Every run used the same sequence:
1. `read_contract` once;
2. `read_artifact('inputs/training.json')` once;
3. `try_on_training` 6 times;
4. `register_variant` once;
5. `submit_result` once.

There were two deviations:
- Claude agent-7-01 also read the findings.
- Claude random-7-00 tried a seventh `try_on_training`. The cap rejected it, and the worker said so in its report.

No tool call returned an error.

## What this shows

- **The full path works on a real problem.** It ran from the question to a sealed final, on licensed data the repository does not hold:
  - the hash-checked data fetch;
  - controls reproduced to 1e-9;
  - workers from both vendors;
  - the protected evaluator and the independent re-check;
  - selection, the one-time holdout and the report gate.
- **Protocol v3 ran cleanly on both vendors at the first attempt.** Planted-signal needed six failed attempts before protocol v2.
- **The negative result is reported as one.** None of the 8 runs reached 0.10. The best development scores were 0.1259 for Terra, which resubmitted the published baseline, and 0.1414 for Sonnet, which explored other detectors and found nothing better.
- **The holdout gap was caught.** Re-scoring the published pipeline exposed a gap that the cited number alone would have hidden.

## What this does not show

- **No scientific progress.** It is unknown whether the parameter grammar admits a pipeline at or below 0.10 at all.
- **No model comparison.** There were 4 runs per backend, each with 6 tries on 32 images, and one backend mostly restated the baseline. This is not a ranking of the two models.
- **Little diversity.** Two Claude runs submitted identical candidates, and all four OpenAI runs stayed close to the team final.
- **No OpenAI cost.** Its cost stays unknown under the ChatGPT sign-in.

## Follow-ups (not built)

1. **Pre-register a holdout control.** Score the cited baseline on the holdout inside `--final`, next to the selected candidate, so the final comparison does not rest on a published number the port may not reproduce.
2. **Give the `random` arm a meaning for live workers.** For example, host-generated random parameters as a true baseline. Otherwise, drop the arm for live grain runs.
3. **Raise the search budget.** Allow more `try_on_training` calls or a larger subset, and give workers distinct starting points.

Scaling and Phase 5 still need a new go from the owner.

Documentation licensed CC BY 4.0.
