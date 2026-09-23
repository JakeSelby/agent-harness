# Digest: docs/spikes/README.md and two 2026-09-22 spike records (at 3020251)

- claim: A spike record is history: it is judged against a number written down before the experiment and is not revised when a later measurement disagrees.
  source: docs/spikes/README.md
  publisher: agent-harness
  pub_date: 2026-09-23
  accessed: 2026-09-23
  confidence: high
  class: method

- claim: In-run budget nudge, status failed (do not build): on 89 budgeted subagent rows (2026-09-21 to 09-23, one machine), 2 of 89 (2.2%) ended over budget, both `builder`; excess 118,056 tokens, 4.5% of 2,594,799; the median run finished at 0.17 of budget. Exit criterion was >=10% fire rate, >=10 tool calls of runway, >=10% of output; two of three missed.
  source: docs/spikes/2026-09-22-in-run-budget-nudge.md
  publisher: agent-harness
  pub_date: 2026-09-22
  accessed: 2026-09-23
  confidence: high
  class: measurement

- claim: The reconstructed pre-budget sample (235 runs, today's budget applied retrospectively) had 51 of 235 (21.7%) over budget, 8.9% excess, and at the 1.0x crossing the median firing run had 1 tool call left (23 of 51 had none), so a nudge would arrive after the last tool call.
  source: docs/spikes/2026-09-22-in-run-budget-nudge.md
  publisher: agent-harness
  pub_date: 2026-09-22
  accessed: 2026-09-23
  confidence: high
  class: measurement

- claim: The spike reads budgets in briefs as coinciding with overruns falling from 21.7% to 2.2% (observational, not a controlled comparison) and names a re-run bar: >=200 budgeted rows with >=10% over budget, >=10% excess and >=10 tool calls of median runway.
  source: docs/spikes/2026-09-22-in-run-budget-nudge.md
  publisher: agent-harness
  pub_date: 2026-09-22
  accessed: 2026-09-23
  confidence: medium
  class: measurement

- claim: Deferred rule text, status open, nothing run: seven action-gated files are 5,012 characters (~1,253 tokens, 36% of a 3,524-token rules-and-stances layer); the build bar is >=900 tokens traceable to a hook-visible act, compliance no lower than resident minus one over >=20 paired runs, and a measured live prefix fall of >=700 tokens read from first-assistant cache_creation, not from static.json.
  source: docs/spikes/2026-09-22-deferred-rule-text.md
  publisher: agent-harness
  pub_date: 2026-09-23
  accessed: 2026-09-23
  confidence: high
  class: method
