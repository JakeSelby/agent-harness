# Digest: spot-checks against code and deterministic commands (at 3020251)

Method: verification at `normal`, primary-source check of load-bearing figures. Read `scripts/cost_bench.py` (verdict, THRESHOLD, GROWTH_LIMIT) and `bin/harness` (cap constants and their comment); ran `python3 scripts/cost_bench.py static` and `python3 bin/harness lint` on 2026-09-23. No model called, nothing written.

- claim: `THRESHOLD = 0.85`; `verdict()` fails a run whose harness pass count is below bare minus one "whatever the dollars say", returns `inconclusive` when no ratio exists, else passed iff ratio <= 0.85; `GROWTH_LIMIT = 0.05`.
  source: scripts/cost_bench.py
  publisher: agent-harness
  pub_date: 2026-09-23
  accessed: 2026-09-23
  confidence: high
  class: method

- claim: Recomputed at 3020251 the static figure is ~6,751 est. tokens (always-loaded 4,680, 272 lines; listings 2,071), about 10% under the committed 0.12.0 figure of 7,494.
  source: `python3 scripts/cost_bench.py static` run 2026-09-23
  publisher: agent-harness
  pub_date: 2026-09-23
  accessed: 2026-09-23
  confidence: high
  class: measurement

- claim: `harness lint` enforces two caps on instructions, rules and the longest stance variant: 200 lines and 4,202 tokens; at 3020251 the layer is 199 of 200 lines and ~3,858 of 4,202 tokens, so the line cap is the one that binds.
  source: `python3 bin/harness lint` run 2026-09-23; bin/harness ALWAYS_LOADED_* constants
  publisher: agent-harness
  pub_date: 2026-09-23
  accessed: 2026-09-23
  confidence: high
  class: measurement

- claim: The token cap is derived from a live measurement: issue #430 put the harness's live standing context at 12,607 tokens against a bare profile, stable to +/-15 across eight task pairs, and the always-loaded layer may hold a third of that.
  source: bin/harness, comment above MEASURED_STANDING_CONTEXT_TOKENS
  publisher: agent-harness
  pub_date: 2026-09-23
  accessed: 2026-09-23
  confidence: high
  class: measurement
