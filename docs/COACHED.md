# Work with a coach who also builds

Choose coached mode when you want to learn research design while getting the
experiment done. Your own coding agent handles code, evaluators, compute,
Kaggle and CI. On research method it explains and suggests; you decide. Your
question, hypothesis and conclusions stay yours.

Coaching pattern adapted from PresentTogether, MIT, same author.

## Start with your agent

Paste the [coached starter prompt](../README.md#two-ways-to-work) into an agent
that can read files and run programs. It follows [rloop-coach](../skills/rloop-coach/SKILL.md).
You do not need to type commands yourself. If its tools cannot do a step, it
explains the limit and proposes a practical next action.

For the offline planted-signal scaffold, the agent uses:

```console
rloop init my-question --mode coached
# Agree contract.json first: the question, metric, target, controls and limits.
rloop plan my-question
rloop predict my-question --value 0.1 --note "My reason, in my words"
rloop run my-question
rloop report my-question
```

The number above is an illustrative prediction of development MSE, not a grain
result. Changing the scaffold's question does not create a new domain evaluator.
New research needs its own suitable data, contract and evaluator.

Autonomous is the default: `rloop init my-question` still runs the fake pilot
immediately. Coached init creates a scaffold and waits so you can predict first.
The mode lives in host-only `project.json`, never the worker contract. Repeated
init keeps the recorded mode unless `--mode` is explicit. To change it later,
edit `mode` in `project.json` to exactly `autonomous` or `coached`, as with other
host settings, or repeat init with an explicit mode. Switching to autonomous
through init also runs its usual fake pilot. An omitted mode in an older
project means autonomous; unknown values are refused.

Both modes allow one numerical prediction per project after `plan` and before
any scoring starts, including controls. A project already scored by autonomous
init is too late: use a fresh project and register its contract with `plan`
before predicting. The textual prediction in the contract is separate. The
ledger records the number, optional note, UTC time, metric and registration.
An amendment cannot unlock a second prediction. Reports compare it to the best
checked development result under that registration, showing actual minus
predicted and both UTC timestamps. A pending result stays unavailable; a final
holdout score is never substituted. With no prediction, coached reports say
“no prediction recorded”; autonomous reports keep their existing format.

The mode guides how you work together. It is not a security barrier, and the
tool cannot verify who wrote a prediction or its rationale. It never grants
provider, compute, publication or holdout permission.

## The route

🗣️ marks the four moments where your view comes before the agent's. There is
one such question per reply. Elsewhere it does the work and names the current
step. If you already gave an answer, it confirms it and moves on.

| Step | What the agent does | Your part | What you learn |
|---|---|---|---|
| 1. Question and rights 🗣️ | Checks licences, data use and what stays private. | Your question in one sentence, and what would disprove it. | A question you can test. |
| 2. Metric, target and falsifier | Makes the agreed rule executable. | Decide if it answers your question. | What a score can establish. |
| 3. Baselines and controls | Prepares defaults, published/team comparison and random or negative control; checks each was tuned on the same data. | Judge a fair comparison. | Detecting an uninformative test. |
| 4. Approach 🗣️ | After your idea, offers safe, unusual and cheap no-GPU options; recommends one. | Your first idea, then your choice. | Choosing an approach for a reason. |
| 5. Pre-register 🗣️ | Records rule, budget, stop rule and your number before scoring. | Predict a number and explain why. | Expectation versus hindsight. |
| 6. Compute and cost | Picks the simplest host; states cost first; smoke-tests the data's variety. | Approve costs or new services when needed. | What a small test covers. |
| 7. Evaluate once 🗣️ | Scores the frozen candidate, shows uncertainty and limits. | Your verdict: what does it mean? | Weighing evidence against the rule. |
| 8. Reflect | Two or three questions, one at a time; a personal method card; proposed profile updates. | Explain the method in your words. | Reusing it next time. |

Controls are prepared at step 3 and scored only after pre-registration. Once
the agreed evaluation is done, tuning needs a follow-up plan. Final holdout use
always needs your explicit agreement and `rloop run --final`.

**Every method has a name.** Each suggestion explains what it is called, why
it works, how to use it and when it does not fit, with a [method card](../skills/rloop-coach/references/methods.md).
The agent keeps agreed research decisions in a short project `BRIEF.md`, so
another agent can continue. Your private profile never goes into that brief.

## Your private competence profile

The agent offers this once in your first session: rate six areas 1–4 or skip.
It never blocks the experiment. Areas are Research design, Statistics and
evaluation, ML training, Agent orchestration, Reproducibility and Compute.

| Level | Meaning | Support in that area |
|---|---|---|
| 1 New | Has not met it yet | A full first explanation using your project, a starting hint and an understanding check. |
| 2 Knows the terms | Has heard of it, not applied it | A short explanation, options and a recommendation. |
| 3 Applies with support | Has used it with help | Method name and a one-line reason; your call first. |
| 4 Applies and judges | Uses it independently and can explain it | Method name only; you lead and may challenge it. |

Support adapts separately for each area and fades with understanding. No
rating starts at level 1. All four 🗣️ moments remain at every level.
“Shorter”, “explain more” and “just do it” override for this session. For
“just do it”, the agent acts and gives a one-sentence reason, within permissions.

The plain Markdown file is `~/.competence-profiles/research-loops.md`, on Windows
under `%USERPROFILE%\.competence-profiles\`. Only your coaching agent reads and
writes it; there is no profile CLI command. On creation it tells you where the
file is and that you can read, edit or delete it at any time. If home is not
writable, it keeps the profile in the conversation and offers text you can save.

At reflection, or when you ask, it proposes changes from things you actually
showed: a reasoned decision or prediction, a method you applied, a diagnosis.
A lucky guess does not count. Each proposal names the area, old and new level,
and one evidence line. Changes are at most one level per area per session,
including decreases with a clear, kind reason. Nothing changes without your
yes; you can edit the proposal. Confirmed changes update the table and append
a history line. You can set any rating yourself at any time; this is recorded
as “set by the person”. Session-end progress uses that history in one or two
lines in the conversation. [Exact format and observable descriptors](../skills/rloop-coach/references/competence-profile.md).

It is a coaching aid, never a grade. It is outside every repository, never
committed, uploaded, sent to services, workers or sub-agents, or copied or quoted
into project files, reports, briefs, method cards, logs, receipts, the ledger,
issues or commit messages. For students it is shared with nobody unless they
choose to share it themselves. Deleting it simply returns coaching to the default.

## What you might be asked to do

Give your research judgment, try a result, confirm a profile change, or sign in
through a provider's own page. Never paste passwords or keys into chat. Before
money or paid compute, you see the resources and cost. Publishing, a new service
receiving data or code, any holdout use, and deleting need explicit agreement.
The agent handles commands and technical repairs.

## Feedback that helps

| You notice | The agent looks at |
|---|---|
| “Too good to be true.” | Leakage, holdout barrier and double scoring. |
| “All runs give the same answer.” | Worker diversity and prompts. |
| “I don't see why it is better.” | An ablation. |
| “The difference is tiny.” | Seed spread, noise floor and sample size. |
| “Isn't the other number adapted to these images?” | Fair comparison: same tuning data and budget for every method. |
| “Can we still adjust it?” | Yes, on training data with grouped cross-validation, under a new plan; scored data stays untouched. |
| “Are these images enough?” | A bootstrap interval and a paired comparison. |

You keep an evidence-linked result, including negative results, a research
brief and a [personal method card](../skills/rloop-coach/references/method-card-template.md).
The profile stays private; the methods are yours to use next time.

Documentation licensed CC BY 4.0.
