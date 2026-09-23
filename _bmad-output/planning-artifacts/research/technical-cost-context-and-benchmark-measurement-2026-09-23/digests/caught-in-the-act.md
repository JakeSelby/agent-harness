# Digest: docs/caught-in-the-act.md (at 3020251)

- claim: Across 19 headless replay runs (first live set plus two probes) there were zero `Agent` tool calls in either arm; on `hook-inventory`, the case the delegation stance names, the harness arm read all 18 files itself in 10 API calls against bare's 11.
  source: docs/caught-in-the-act.md
  publisher: agent-harness
  pub_date: 2026-09-23
  accessed: 2026-09-23
  confidence: high
  class: measurement

- claim: The delegation stance is where the harness claims its cost saving (work removed from the thread, not context trimmed), and nothing was changed in it after the finding; #429 stays open as a two-answer question.
  source: docs/caught-in-the-act.md
  publisher: agent-harness
  pub_date: 2026-09-23
  accessed: 2026-09-23
  confidence: high
  class: mechanism-failure

- claim: `brief-guard` shipped and worked, yet the brief-without-cap detector read 3.2 hits per 100 turns before, 3.6 during and 3.2 after, on one machine's ledger, because the ledger reads the tool input as the model wrote it and the hook's `updatedInput` lands in a separate entry; the metric was renamed `model-wrote-no-cap`.
  source: docs/caught-in-the-act.md
  publisher: agent-harness
  pub_date: 2026-09-23
  accessed: 2026-09-23
  confidence: high
  class: mechanism-failure

- claim: Detector validity is measured for 17 of 17 detectors against a synthetic labelled corpus with a 0.9 floor in CI; two detectors are recorded under the floor at p=0.83; per-variant rates are observational; opted-out rules have no hit rate.
  source: docs/caught-in-the-act.md, "What the instrument cannot show yet"
  publisher: agent-harness
  pub_date: 2026-09-23
  accessed: 2026-09-23
  confidence: high
  class: method
