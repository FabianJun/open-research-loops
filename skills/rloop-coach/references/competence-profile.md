# Private competence profile: research-loops

This is a coaching aid, not an assessment or grade. The shared scale, Markdown
format and rules match PresentTogether; only the six areas differ.

## Location and privacy

Only the person's coaching agent reads and writes
`~/.competence-profiles/research-loops.md` (Windows:
`%USERPROFILE%\.competence-profiles\research-loops.md`). Keep it outside every
repository. No CLI command creates, reads or updates it.

Never commit it or copy or quote it into projects, briefs, reports, method
cards, logs, receipts, the ledger, commit messages or issues. Never upload it,
send it to another service, or pass it to workers or sub-agents. Only the
coaching agent reads it. For students it is not for grading and is shared with
nobody unless the person chooses to share it themselves.

If home is unwritable, keep the profile in the conversation and offer its text
for the person to save. On creation, say in one line where it lives and that
they may read, edit or delete it at any time.

## Shared scale and adaptation

| Level | Meaning | How the agent coaches in this area |
|---|---|---|
| 1 New | Has not met it yet | Explain fully once, with a concrete example from their own project. Check understanding with one question. Recommend; do not ask them to choose blind. |
| 2 Knows the terms | Has heard of it, not applied it | Short explanation plus the method's name. Offer options with a recommendation. |
| 3 Applies with support | Has used it with help | Name the method and give the reason in one line. Ask for their call before giving yours. |
| 4 Applies and judges | Uses it independently and can explain it | Name the method only. Let them lead, and invite them to challenge your proposal. |

Adapt per area, not by an overall score. A person might need a full statistics
example and only a method name for design. Fade support with demonstrated
understanding. “Shorter”, “explain more” and “just do it” override the profile
for the current session. Without a profile or an area's rating, start at level
1 for the first explanation, then fade as usual.

The four your-view-first moments happen at every level. Give a starting hint at level 1;
ask openly at level 4. Keep level 1 understanding checks and level 3 calls
within those moments or reflection; do not add more “your view first” stops.
Ask at most one question per reply, including profile creation and reflection.

## Observable descriptors by area

Each cell describes something the person can show, not a test they must pass.

| Area | 1 New | 2 Knows the terms | 3 Applies with support | 4 Applies and judges |
|---|---|---|---|---|
| Research design | Needs an example of a testable question. | Recognises question, falsifier, pre-registration, baselines and controls. | With help, defines a question, disproof and fair controls before a run. | Independently chooses and defends a registered design and its limits. |
| Statistics and evaluation | Needs an example of a metric and uncertainty. | Recognises noise, seed spread, development and holdout. | With help, interprets metrics and spread without tuning to development results. | Independently judges uncertainty, split use and overfitting to development data. |
| ML training | Needs an example connecting model training to the question. | Recognises models, losses, augmentation and checkpoints. | With help, selects training choices and a separate checkpoint-selection set. | Independently justifies model, loss, augmentation and checkpoint choices. |
| Agent orchestration | Needs an example of worker roles and isolation. | Recognises workers, fan-out, diversity, budgets and tool isolation. | With help, bounds workers and gives them distinct approaches and public inputs. | Independently judges diversity, budgets and isolation limits. |
| Reproducibility | Needs an example of evidence tied to an output. | Recognises receipts, hashes, data versions and licences. | With help, traces a result to its inputs, code, receipt and rights. | Independently checks provenance, licence limits and reproducibility claims. |
| Compute | Needs an example of local versus hosted execution. | Recognises GPU hosts, cost, smoke tests and data-transfer limits. | With help, chooses a host and representative smoke sample within cost and privacy limits. | Independently judges resource costs, data egress and smoke-test coverage. |

## File format

Use this exact shared structure, with all six areas in the table. An unrated
area may have an empty level and follows the level 1 default. Dates are ISO dates.

```markdown
# Competence profile: research-loops

Private. Stored only on this computer. Edit or delete it at any time.

| Area | Level | Last evidence | Updated |
|---|---|---|---|
| Research design | 2 | <one line of what the person showed> | 2026-11-15 |
| Statistics and evaluation | | | |
| ML training | | | |
| Agent orchestration | | | |
| Reproducibility | | | |
| Compute | | | |

## History

- 2026-11-15 · Research design · 1 → 2 · <evidence in one line> · confirmed
- 2026-11-15 · Compute · – → 3 · self-rating · set by the person
```

## Creation and updates

In the first session without a profile, offer it once in one short question:
“Rate Research design, Statistics and evaluation, ML training, Agent
orchestration, Reproducibility and Compute each 1–4 (New, Knows the terms,
Applies with support, Applies and judges), or say skip?” Use a separate reply
from a your-view-first question. Skipping never blocks work. A self-rating is a starting
point, not a test.

Use only evidence the person actually showed: a decision and its reason, a
reasoned prediction, an unprompted method, or a problem they diagnosed.
Outcome luck and a correct guess without reasoning are not evidence.

Propose changes at reflection or when asked. Give the area, old and new level,
and one evidence line. At most one step per area per session; decreases are
allowed, with a plain, kind explanation. Nothing changes without their yes;
they may edit the proposal. After confirmation, update the table and append
one history line marked “confirmed”.

They may set any rating at any time, such as “set statistics to 3”. Record it
as “set by the person”, with self-rating evidence. At session end, show progress
in one or two conversational lines: which areas moved since creation, using
the history. Never put this progress into project artifacts.

Documentation licensed CC BY 4.0.
