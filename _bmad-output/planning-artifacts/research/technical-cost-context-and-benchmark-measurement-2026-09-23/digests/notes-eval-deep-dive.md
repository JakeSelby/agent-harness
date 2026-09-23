# Digest: maintainer notes (unpublished), 2026-09-21, evaluation harness deep dive (method claims only)

Private material mixed in this note (spend figures, local paths) was dropped and is not described.

- claim: Pyramid tiers and cost per rule change: static token accounting (seconds, 0 USD); deterministic hook and policy tests (minutes, 0 USD); offline detector replay over a stored corpus (seconds per transcript, 0 USD); micro-task with an oracle on a cheap model (2-4 runs, priced); probe on the production model (2-4 runs); full live set (48 runs).
  source: maintainer notes (unpublished), 2026-09-21, evaluation harness deep dive
  publisher: maintainer
  pub_date: 2026-09-21
  accessed: 2026-09-23
  confidence: medium
  class: method

- claim: Questions split into model-invariant (hook decisions, detector hits, skill triggering, prefix cost), priceable on a cheap model, and model-bound (strategy choice, delegation judgment, thrash), which only the production model answers.
  source: maintainer notes (unpublished), 2026-09-21, evaluation harness deep dive
  publisher: maintainer
  pub_date: 2026-09-21
  accessed: 2026-09-23
  confidence: medium
  class: method

- claim: Nine stance dimensions give 3·2·4·6·3·3·2·3·3 = 23,328 variant permutations, so the recommended unit is per-rule plus pairwise checks on dimensions that share text, not the grid; a run's priced decomposition must reconcile to total_cost_usd within 5%.
  source: maintainer notes (unpublished), 2026-09-21, evaluation harness deep dive
  publisher: maintainer
  pub_date: 2026-09-21
  accessed: 2026-09-23
  confidence: medium
  class: method
