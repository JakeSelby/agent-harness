# Digest: docs/usage.md (at 3020251), sections "What it cost", "What the hit rate tells you", "Whether the prefix held", "Usage feed", subagent rows

- claim: Tokens mislead as a measure of spend: cache reads dominate the count at a fraction of base input, and routing to a cheaper model can spend more tokens and fewer dollars, so every grouping carries a list-price `usd` column that is not an invoice.
  source: docs/usage.md, "What it cost"
  publisher: agent-harness
  pub_date: 2026-09-23
  accessed: 2026-09-23
  confidence: high
  class: method

- claim: Unpriced is not free: unknown model, multi-model rows with no breakdown and partial rows are counted in an `unpriced` footer and contribute nothing, because an understated figure is worse than an absent one.
  source: docs/usage.md
  publisher: agent-harness
  pub_date: 2026-09-23
  accessed: 2026-09-23
  confidence: high
  class: method

- claim: The price table reproduced a recorded session's CLI-reported total_cost_usd of 0.60097775 exactly (0.000% deviation against a 2% tolerance); `harness doctor` warns when the newest price `as_of` is over 90 days old.
  source: docs/usage.md
  publisher: agent-harness
  pub_date: 2026-09-23
  accessed: 2026-09-23
  confidence: high
  class: measurement

- claim: Across 137 sessions on one machine the cache hit rate was flat by subagent count: 97.0% at zero subagents, 97.2% at 1-6, 97.3% at 7-50, 97.1% at 51 or more, so the expected fall in hit rate from fan-out did not appear.
  source: docs/usage.md, "What the hit rate tells you"
  publisher: agent-harness
  pub_date: 2026-09-23
  accessed: 2026-09-23
  confidence: medium
  class: measurement

- claim: Prefix-held is reported as `miss = cache_write / (cache_read + cache_write)` with subagent tokens subtracted; a session that spawned anything reports no step, and a row with no cache fields reports `unknown`, never zero; it measures and never enforces.
  source: docs/usage.md, "Whether the prefix held"
  publisher: agent-harness
  pub_date: 2026-09-23
  accessed: 2026-09-23
  confidence: high
  class: method

- claim: A subagent's figure must be summed from its own transcript: the tool response reports only the last response, measured at 3,143 output tokens against 10,575 actually spent.
  source: docs/usage.md, "Usage feed"
  publisher: agent-harness
  pub_date: 2026-09-23
  accessed: 2026-09-23
  confidence: high
  class: measurement

- claim: Subagent rows carry `requested_type` and `rerouted` (how often a spawn hook moved a spawn) and the role's soft budget, so an overrun is a subtraction on one row; per-role budgets are re-seeded from the p75 of a window and a role at n<30 has not earned a re-seed.
  source: docs/usage.md
  publisher: agent-harness
  pub_date: 2026-09-23
  accessed: 2026-09-23
  confidence: high
  class: method
