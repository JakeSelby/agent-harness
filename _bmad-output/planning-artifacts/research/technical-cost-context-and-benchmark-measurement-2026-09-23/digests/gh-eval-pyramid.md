# Digest: issues #509 to #514, the tiered evaluation pyramid (all open)

- claim: #509: price every rule, stance variant, skill and agent description individually in the static tier and print per-file deltas in CI, since a rule edit's cost side is fully determined by its text.
  source: https://github.com/JakeSelby/agent-harness/issues/509
  publisher: agent-harness (GitHub)
  pub_date: 2026-09-22
  accessed: 2026-09-23
  confidence: high
  class: method

- claim: #510: replay stored transcripts through the detector registry offline, one row per run per detector, to read mechanism directly at zero model spend rather than inferring it from cost.
  source: https://github.com/JakeSelby/agent-harness/issues/510
  publisher: agent-harness (GitHub)
  pub_date: 2026-09-22
  accessed: 2026-09-23
  confidence: high
  class: method

- claim: #511: run every hook against a recorded tool-call corpus under every stance variant as a deterministic decision matrix; a cost difference on a task whose matrix row did not change is not the hooks.
  source: https://github.com/JakeSelby/agent-harness/issues/511
  publisher: agent-harness (GitHub)
  pub_date: 2026-09-22
  accessed: 2026-09-23
  confidence: high
  class: method

- claim: #512: a micro-task tier on a cheap model reporting "mechanism fired" beside pass/fail, in a separate series never mixed with production rows; acceptance is a full micro set under 2 USD reported and 15 minutes.
  source: https://github.com/JakeSelby/agent-harness/issues/512
  publisher: agent-harness (GitHub)
  pub_date: 2026-09-22
  accessed: 2026-09-23
  confidence: high
  class: method

- claim: #514: per-rule attribution is structurally blocked: ARMS is a hard-coded two-tuple, nothing enumerates the instruction surface, no row records which entry an ablation removed, reps default to 2 against observed per-task spread up to 1.86x so a 2-3% effect is noise, cost_per_passed folds two variables, and the prefix figure is warmth-contaminated (45,847 vs 27,977 on one profile with identical totals).
  source: https://github.com/JakeSelby/agent-harness/issues/514
  publisher: agent-harness (GitHub)
  pub_date: 2026-09-22
  accessed: 2026-09-23
  confidence: high
  class: method
