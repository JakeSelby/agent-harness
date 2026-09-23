# Digest: benchmarks/static.json (at 3020251), summarised not copied

- claim: The committed static figure is for harness 0.12.0: always-loaded 21 files, 343 lines, ~5,168 est. tokens; listings 33 files, ~2,326 tokens; total 54 files, ~7,494 tokens; worst case (longest variant of every dimension) ~7,553.
  source: benchmarks/static.json
  publisher: agent-harness
  pub_date: 2026-09-22
  accessed: 2026-09-23
  confidence: high
  class: measurement

- claim: The single largest always-loaded file is the output style (6,061 characters, ~1,515 tokens), about 3.9x the next-largest rule file (1,562 characters).
  source: benchmarks/static.json, `largest`
  publisher: agent-harness
  pub_date: 2026-09-22
  accessed: 2026-09-23
  confidence: high
  class: measurement

- claim: Priced per model from policy/prices.json, the whole static layer is cents per session start and a fraction of a cent per later turn (e.g. 0.0468 USD start / 0.0037 USD per turn at the listed Opus rates; 0.0187 / 0.0015 at Sonnet 5).
  source: benchmarks/static.json, `usd`
  publisher: agent-harness
  pub_date: 2026-09-22
  accessed: 2026-09-23
  confidence: medium
  class: measurement

- claim: Minor inconsistency: static.json's always-loaded 5,168 differs from the docs' "Baseline at 0.12.0" 5,198 (total 7,494 vs 7,524).
  source: benchmarks/static.json vs docs/benchmarks.md
  publisher: agent-harness
  pub_date: 2026-09-22
  accessed: 2026-09-23
  confidence: medium
  class: measurement
