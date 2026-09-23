# Digest: docs/benchmarks.md (at 3020251)

Method: read in full 2026-09-23. Repo-relative path; publisher is the agent-harness repository.

## Claims

- claim: The static tier counts what every managed session loads before the first prompt (global instructions, rules, selected stances, output style, one description per agent, skill and command); a bare session loads none of it, so the count is the harness's standing overhead.
  source: docs/benchmarks.md, "Static context figure"
  publisher: agent-harness
  pub_date: 2026-09-23
  accessed: 2026-09-23
  confidence: high
  class: method

- claim: Static tokens are characters divided by four, a trend estimate and not a billing figure; dollars price `session_start` as one cache write and `later_turn` as one cache read.
  source: docs/benchmarks.md
  publisher: agent-harness
  pub_date: 2026-09-23
  accessed: 2026-09-23
  confidence: high
  class: method

- claim: CI fails when the static estimate grows more than 5% over the committed figure unless `benchmarks/allow.json` carries a version-pinned entry with a reason.
  source: docs/benchmarks.md
  publisher: agent-harness
  pub_date: 2026-09-23
  accessed: 2026-09-23
  confidence: high
  class: method

- claim: Recorded trims (static estimate, not live): baseline at 0.12.0 7,524 total (5,198 always-loaded, 2,326 listings); after shortening descriptions (#430) 7,185; after trimming the output style (#430) 6,519.
  source: docs/benchmarks.md, "Recorded trims"
  publisher: agent-harness
  pub_date: 2026-09-23
  accessed: 2026-09-23
  confidence: medium
  class: measurement

- claim: Live replay runs pinned tasks headlessly against a signed-in otherwise-empty profile and against the harness, scoring each run with a held-back check; it is run by hand on a release candidate, never in CI; default schedule 4 tasks x 2 arms x 2 reps.
  source: docs/benchmarks.md, "Live replay"
  publisher: agent-harness
  pub_date: 2026-09-23
  accessed: 2026-09-23
  confidence: high
  class: method

- claim: Arms differ by environment only: same model, `--strict-mcp-config`, `--max-budget-usd 2`, same sandbox with network off; each arm's fence is proved by a capped lint pre-flight before any scored run; each run starts in a one-commit snapshot outside the home directory with a scrubbed environment.
  source: docs/benchmarks.md
  publisher: agent-harness
  pub_date: 2026-09-23
  accessed: 2026-09-23
  confidence: high
  class: method

- claim: Cost is the CLI's `total_cost_usd`, a list-price equivalent; each row also carries a cache-normalised cost (first-turn cache reads repriced as writes) and `cache_miss_ratio`; errored runs are counted apart from failures.
  source: docs/benchmarks.md
  publisher: agent-harness
  pub_date: 2026-09-23
  accessed: 2026-09-23
  confidence: high
  class: method

- claim: The publishable threshold is fixed in the script: the harness costs at most 85% of bare per passed task while passing no fewer than bare minus one, mean of reps; compare ratios across days, never dollars.
  source: docs/benchmarks.md
  publisher: agent-harness
  pub_date: 2026-09-23
  accessed: 2026-09-23
  confidence: high
  class: method

- claim: What is faked: single-shot prompts stand in for interactive sessions, two of the four tasks are synthetic, and a tagged run measures the tag's default configuration.
  source: docs/benchmarks.md
  publisher: agent-harness
  pub_date: 2026-09-23
  accessed: 2026-09-23
  confidence: high
  class: method

- claim: Status: the live tier has one uncontaminated result, 1.052 on a four-task set, above the 0.85 threshold, so no cost claim is published; two earlier figures in either direction were artifacts of the runner's sandbox and a test-suite defect; the static tier is the figure to rely on today.
  source: docs/benchmarks.md, "Status"
  publisher: agent-harness
  pub_date: 2026-09-23
  accessed: 2026-09-23
  confidence: high
  class: measurement

- claim: Limits: Claude Code only; the user's own personal file, memory, MCP servers and hook output are not counted, and MCP tool definitions alone can outweigh everything measured; only descriptions of agents and skills are counted.
  source: docs/benchmarks.md, "Limits"
  publisher: agent-harness
  pub_date: 2026-09-23
  accessed: 2026-09-23
  confidence: high
  class: method
