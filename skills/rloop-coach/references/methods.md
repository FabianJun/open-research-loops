# Research method cards

These are working explanations, grounded in this repository's records.
Suggestions are not claims that a method was tested here. Each “seen” entry
states what the record actually supports; missing evidence stays missing.

## Pre-registration

- **What:** agree the question, decision rule and prediction before scoring.
- **Why:** prevents hindsight from quietly changing what success meant.
- **How:** fix the metric, target, budget and stop rule in the contract; plan,
  then record the person's number with `rloop predict PROJECT --value X`.
- **When it does not fit:** exploratory checks whose question is still forming;
  label them exploratory, then register the confirmatory test separately.
- **Seen in this repository:** the [CNN rule](../../../experiments/grain-cnn/README.md)
  fixed the team comparison, target and one val scoring before the full run.

## Holdout barrier

- **What:** reserve final data for one agreed evaluation after selection.
- **Why:** keeps selection feedback separate from final evidence.
- **How:** develop without final inputs or scores; get explicit agreement,
  then use only `rloop run PROJECT --final`. Never tune on the holdout.
- **When it does not fit:** repeated exploratory use of the same data; that
  data is no longer a holdout, and a new untouched evaluation is needed.
- **Seen in this repository:** the [Phase 4b holdout gap](../../../docs/PHASE-4B-PILOT.md#final-holdout)
  was left uninvestigated because rescoring outside `--final` would break the barrier.

## Random or negative control

- **What:** a comparison expected not to carry the proposed useful signal.
- **Why:** checks whether the evaluator can distinguish useful work from noise.
- **How:** define an actual random procedure or known failing candidate and
  its expected behavior before testing; use the same evaluation conditions.
- **When it does not fit:** a label alone does not make a control; a live worker
  called “random” but following the same instructions is not a random baseline.
- **Seen in this repository:** [Phase 4b arms and follow-ups](../../../docs/PHASE-4B-PILOT.md)
  explicitly say the live random arm was a replicate, and propose a true control.

## Falsifier

- **What:** a result that would count against the stated hypothesis.
- **Why:** makes a failure informative instead of inviting a new success rule.
- **How:** write the disproof in the person's words, then bind it to the metric
  and threshold; separate technical failure from a negative scientific result.
- **When it does not fit:** a broad ambition without a measurable question;
  narrow the question first rather than inventing a threshold.
- **Seen in this repository:** the [Phase 4b rule and negative result](../../../docs/PHASE-4B-PILOT.md)
  used development `max_rel_error <= 0.10`; none of the eight runs reached it.

## Seed spread and noise floor

- **What:** inspect variation across independent seeds and the scale of noise
  before interpreting a small difference.
- **Why:** an apparent improvement can be smaller than ordinary run variation.
- **How:** register seeds, report the spread and an appropriate paired interval;
  consider sample size and dependence before claiming a meaningful improvement.
- **When it does not fit:** repeated identical deterministic outputs do not
  estimate training uncertainty; one seed cannot establish a spread.
- **Seen in this repository:** [LESSONS L06](../../../docs/LESSONS.md#patterns-and-failure-modes)
  records the single-seed limitation and the rule for seeds, margins and intervals.
  It supplies no universal numerical noise floor.

## Ablation

- **What:** remove or vary one component while holding the comparison fixed.
- **Why:** helps identify which component explains a difference.
- **How:** pre-register a full version and a version without the proposed
  component, matched for data, selection, seeds and budget.
- **When it does not fit:** many simultaneous changes, or removing a component
  makes the system invalid; use a suitable control instead.
- **Seen in this repository:** [Phase 4b](../../../docs/PHASE-4B-PILOT.md#development-results)
  lists multi-parameter candidates, not a controlled ablation. It motivates this
  follow-up but does not establish which component caused a score difference.

## Overfitting to development data

- **What:** repeated choices learn the development set, even without gradients.
- **Why:** separating selection from evaluation limits feedback that can make
  development gains look more general than they are. A hidden final set alone
  does not remove development overfit.
- **How:** bound iteration, choose checkpoints on internal-check data, freeze
  choices before development scoring, and reserve final evaluation separately.
- **When it does not fit:** inspecting training data is necessary for fitting;
  do not confuse that with evidence of generalisation.
- **Seen in this repository:** [CNN selection and result](../../../experiments/grain-cnn/README.md)
  separated internal-check selection from the once-scored val result. The
  internal score did not predict val well; this alone does not diagnose overfit.

## Fair comparison

- **What:** every method in a comparison gets the same tuning data, a stated
  tuning budget and the same evaluation images.
- **Why:** a baseline tuned on the scoring set looks better than it is, and a
  new method compared against it looks worse. Either way the gap misleads.
- **How:** before any scoring, write down where each method's numbers come
  from. Re-tune the baseline on your training data with a stated budget, or
  score its published setting next to yours on images neither has seen.
- **When it does not fit:** a baseline that cannot be re-run; then report its
  number as context only and say on which data it was chosen.
- **Seen in this repository:** the [CNN interpretation](../../../experiments/grain-cnn/README.md#interpretation-added-after-the-result)
  explains why its pre-registered bar was unfair: the team's 0.1259 was chosen
  on the same 40 val images, while the U-Net never saw them.

## Grouped cross-validation

- **What:** split the training data into folds; tune on some, check on the
  rest, rotate, and keep related samples in the same fold.
- **Why:** adapting a method is fine, as long as it happens on training data.
  Every training sample is checked once without being used for its own fit,
  and grouping stops near-copies from leaking across the split.
- **How:** pick the group key first (for example tiles cut from one
  micrograph), choose settings on out-of-fold predictions only, then freeze
  and train once on all training data.
- **When it does not fit:** very few groups; then folds are noisy, so report
  the spread across folds instead of trusting one winner.
- **Seen in this repository:** the [CNN interpretation](../../../experiments/grain-cnn/README.md#interpretation-added-after-the-result)
  names it as the step its single internal split lacked.

## Sample size and intervals

- **What:** show how much the score could move on another sample of the same
  size, and compare methods image by image.
- **Why:** with 40 images, a medians-based score can swing by several points;
  a single number hides that.
- **How:** bootstrap the per-sample errors (resample with replacement, many
  times, fixed seed) for an interval. To compare two methods, resample the
  same samples for both and look at the interval of the difference.
- **When it does not fit:** strongly dependent samples; resample whole groups
  instead, or the interval is too narrow.
- **Seen in this repository:** the [CNN interpretation](../../../experiments/grain-cnn/README.md#interpretation-added-after-the-result)
  gives a 95% interval of 0.119 to 0.231 for the U-Net's val score of 0.1639.

## Data licence check

- **What:** establish rights to use and transfer data separately from code rights.
- **Why:** a repository's licence does not automatically cover its dataset.
- **How:** record the source, version, licence and unresolved terms; agree what
  stays private before upload, publication or redistribution.
- **When it does not fit:** a metadata licence alone cannot settle ambiguous
  package rights; keep the uncertainty explicit instead of granting permission.
- **Seen in this repository:** [DECISIONS, Phase 4b](../../../docs/DECISIONS.md#phase-4b-authorization--2026-11-15)
  distinguishes CC BY metadata from unresolved package terms and forbids image redistribution.

## Receipts and reproducibility

- **What:** bind a reported result to saved inputs, versions, execution and output.
- **Why:** a plausible number without producing artifacts cannot be checked.
- **How:** keep hashes, data versions, configuration, run receipts and raw
  metrics; regenerate the report from saved evidence and retain failed attempts.
- **When it does not fit:** identical outputs alone do not prove sound science
  or legal data use; these require separate judgments.
- **Seen in this repository:** [Checkpoint B's failed attempts](../../../docs/CHECKPOINT-B-PILOT.md#attempt-log)
  remain in the record; its results link protocol changes and checks. [LESSONS](../../../docs/LESSONS.md)
  distinguishes reproducibility from validity.

## Smoke test

- **What:** a small end-to-end run before expensive execution.
- **Why:** catches loading, output and integration failures while repairs are cheap.
- **How:** choose a sample covering the data's variety: formats, sizes, channels
  and relevant edge cases; exercise loading, compute, output and retrieval.
- **When it does not fit:** a small convenient sample cannot establish full
  coverage, capacity or scientific performance; state what it did not test.
- **Seen in this repository:** the [CNN attempt log](../../../experiments/grain-cnn/README.md#attempt-log)
  says the smoke subset contained only RGB PNG, missing RGB JPG and grayscale
  PNG. The first full run failed in the loader before training. After repair,
  the U-Net scored 0.1639 on val against the team's 0.1259, a bar later
  found unfair (see fair comparison).

## Bounded iteration and stop rules

- **What:** limit attempts, time and resources before searching.
- **Why:** prevents chasing a positive result and hiding failed trials.
- **How:** agree caps and a stop condition; keep failures; an amendment does not
  reset spent allowances. Stop when the rule says to stop, even if negative.
- **When it does not fit:** an unworkable initial setup needs a labelled repair,
  not a silent scientific retry or extra budget.
- **Seen in this repository:** [Checkpoint B attempt O0](../../../docs/CHECKPOINT-B-PILOT.md#attempt-log)
  was refused because its earlier offline check had started the project clock.
  [CNN decisions](../../../docs/DECISIONS.md#cnn-feasibility-on-external-compute--2026-11-15)
  require a new go for a training loop or another holdout use.

## Parallel fan-out and diversity

- **What:** explore distinct approaches concurrently within one shared budget.
- **Why:** useful differences in hypotheses or starting points can broaden search.
- **How:** make worker approaches distinct, bound concurrency and total work,
  isolate tools and private data, and inspect duplicate candidates afterwards.
- **When it does not fit:** identical tasks on an easy problem can consume more
  resources without adding information; parallelism alone is not diversity.
- **Seen in this repository:** [Checkpoint B results](../../../docs/CHECKPOINT-B-PILOT.md#results)
  record sixteen identical planted answers and explicitly disclaim scientific
  value or diversity. [Phase 4b](../../../docs/PHASE-4B-PILOT.md#what-this-does-not-show)
  also reports limited diversity, not a vendor ranking.

Licensed under Apache-2.0.
