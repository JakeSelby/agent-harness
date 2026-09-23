# Digest: PRs #362, #368, #599 (issue), #609 on the benchmark instruments

- claim: #362 added the zero-token static count, committed ~7,500 estimated tokens for 0.11.1 and the 5% CI growth gate.
  source: https://github.com/JakeSelby/agent-harness/pull/362
  publisher: agent-harness (GitHub)
  pub_date: 2026-09-21
  accessed: 2026-09-23
  confidence: high
  class: method

- claim: #368 added the live replay runner storing the harness as a same-day ratio to bare "so a cost claim can be measured before it is published"; no live run at merge.
  source: https://github.com/JakeSelby/agent-harness/pull/368
  publisher: agent-harness (GitHub)
  pub_date: 2026-09-21
  accessed: 2026-09-23
  confidence: high
  class: method

- claim: #599 asked for pinned-tag replay and named the constraint that a tagged sync must never touch the real profile, "the exact contamination class #498 caused".
  source: https://github.com/JakeSelby/agent-harness/issues/599
  publisher: agent-harness (GitHub)
  pub_date: 2026-09-23
  accessed: 2026-09-23
  confidence: high
  class: method

- claim: #609 shipped repeatable `--tag`: each ref is snapshotted, synced into a signed-in isolated profile, measured as its own schedule with its own history row, then the sync is removed from its own manifest; a leftover stops the run before the next tag; no per-tag result is recorded in the PR.
  source: https://github.com/JakeSelby/agent-harness/pull/609
  publisher: agent-harness (GitHub)
  pub_date: 2026-09-23
  accessed: 2026-09-23
  confidence: high
  class: method
