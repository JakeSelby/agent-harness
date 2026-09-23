# Digest: maintainer notes (unpublished), 2026-09-22, cost instrument review

One third-party scorer name dropped under the public-safety rules.

- claim: The replay is sound for whole-harness vs bare (one ratio, one gate); controls that hold: workdir contamination, env scrubbing, identical command lines, unreachable-fix snapshots, held-back oracles, alternating cache order, cache-repriced cost. Controls that do not yet hold: arm count, ablation provenance, rule enumeration, statistical power, metric separation, prefix cleanliness.
  source: maintainer notes (unpublished), 2026-09-22, cost instrument review
  publisher: maintainer
  pub_date: 2026-09-22
  accessed: 2026-09-23
  confidence: medium
  class: method

- claim: Recommended per-rule shape: enumerate the surface including instruction sources the harness does not own; declare ablations in a manifest; N arms; report cost, output tokens, prefix tokens, turns, tool calls and pass rate each against control; state a minimum detectable effect and refuse to print an interval spanning zero without "inconclusive"; raise reps before multiplying arms; report user-environment sweeps as local diagnostics, not published constants; one-at-a-time toggling finds main effects only.
  source: maintainer notes (unpublished), 2026-09-22, cost instrument review
  publisher: maintainer
  pub_date: 2026-09-22
  accessed: 2026-09-23
  confidence: medium
  class: method

- claim: Prefix-clean exit test: two runs of the same arm on the same day agree on prefix tokens within 2%, or the first-call fields are declared unusable and the static counter used instead.
  source: maintainer notes (unpublished), 2026-09-22, cost instrument review
  publisher: maintainer
  pub_date: 2026-09-22
  accessed: 2026-09-23
  confidence: medium
  class: method
