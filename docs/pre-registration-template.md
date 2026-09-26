# Pre-registration template

Copy this file for each proof run, fill every section, and commit the copy before the run's first
trial. Name the copy for the date and the question, for example
`benchmarks/preregistrations/2026-10-01-harness-vs-bare.md`, and push it before the first trial so
its date is on a remote others can read. This is item 1 of the [evidence standard](evidence-standard.md),
which says how the order is checked.

Replace each `<...>` with a value. A section that does not apply says "none" and why; a blank or a
leftover `<...>` fails the check. SM-2's values are filled in as defaults; change one only by
recording the change and its reason here, before the first trial.

After the first trial the sections above the deviation log are frozen. A change after that point is
an appended entry in the deviation log, never an edit above it.

---

## Run

- **Question:** <one sentence: what this run decides>
- **Author role:** <maintainer, contributor>
- **Date registered:** <YYYY-MM-DD>
- **Task manifest:** `benchmarks/tasks.json` at commit `<sha>`
- **Arms:** <harness at tag or commit, bare>
- **Model, CLI and effort:** `<exact model ID>`, `<CLI version>`, `<effort>`

## Hypotheses

- **Primary:** the harness lowers Cost-of-Pass against bare, with an expected ratio of 0.85, and does
  not lower the pass rate by more than the non-inferiority margin δ.
- **Secondary:** <each further hypothesis, with its direction, or "none">
- **Exploratory:** <each analysis that will be reported but supports no claim, or "none">

## Primary metric

- **Metric:** Cost-of-Pass ratio, harness over bare, pooled across the set: the total cost of every
  attempt divided by the total number of passes, per arm.
- **Interval:** paired, task-clustered 95% interval, by <task-clustered paired bootstrap with N
  resamples and seed S, or the delta method>.
- **Undefined case:** if either arm passes nothing, the result is reported as a pass-rate result only.

## Guardrails

- **Pass rate:** non-inferiority margin δ = 0.125 on the paired, task-clustered pass-rate difference
  (harness minus bare).
- **Fallback rate:** <the share of trials on an unpinned model above which the run is reported as
  compromised>
- **Spend:** <the per-trial budget and the whole-run cap>
- **Other:** <each further guardrail metric and its bound, or "none">

## Sample size

- **Tasks:** <k>, of which <n> are long multi-turn tasks.
- **Trials per task and arm:** <m>, five or more.
- **α and power:** α 0.05 two-sided, joint power 0.8 on both tests of the decision rule, assuming a
  true ratio of 0.85 and equal pass rates.
- **Minimum detectable effect:** <at most 15%>
- **Variance source:** <the pilot rows or earlier run the power analysis used, with its
  intra-cluster correlation>
- **Power calculation:** <the command or formula that produced k and m, and its output>

## Stopping rule

- **Fixed sample:** the run stops when every task has <m> trials per arm, and no result is read
  before then. <Or: the sequential design, its looks and its spending function.>
- **Early stop for harm or cost:** <the condition, or "none">
- **Stop condition for the claim:** a saving claim needs the hypothesis supported on the whole set
  and a win on the long-task subset, a win meaning the subset's ratio interval lies wholly below 1.0.
  Without that win the instrument findings are published as the result.

## Multiplicity

- **Decision rule:** both conditions must hold, so the two tests form one joint test and need no
  correction.
- **Further confirmatory tests:** <each one, with its correction, such as Holm across the family, or
  "none">
- **Everything else:** exploratory, labelled so, and supports no claim.

## Decision rule

The hypothesis is supported only when both hold:

- the paired, task-clustered 95% interval on the Cost-of-Pass ratio lies wholly below 1.0;
- the lower bound of the paired, task-clustered 95% interval on the pass-rate difference (harness
  minus bare) is above −δ.

The result is published with its intervals, whatever it shows.

## Exclusions

- **Analysis population:** every assigned trial, crashes, timeouts and fallbacks included.
- **Pre-stated exclusions:** <each rule that removes a trial, decided now, or "none">

## Deviation log

Append a dated entry for every change after the first trial: what changed, why, and which figures
it touches. Never edit an entry.

- <YYYY-MM-DD: none yet>
