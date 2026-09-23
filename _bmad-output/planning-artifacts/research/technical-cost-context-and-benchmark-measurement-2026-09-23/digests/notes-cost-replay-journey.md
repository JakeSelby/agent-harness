# Digest: maintainer notes (unpublished), 2026-09-22, cost replay journey

Usable measurement findings only. Where the same number is public, the public source is cited in research.md instead. Personal, spend and local-path material was dropped and is not described.

- claim: A re-baseline on a fixed fixture read 0.782 ("passed") over 24 runs at 3 reps (per task hook-ids 0.677, link-alias 0.740, codex-pre-allow 0.875, hook-inventory 1.530) and was later found contaminated: the bare arm's fence thrash, not a harness saving.
  source: maintainer notes (unpublished), 2026-09-22, cost replay journey
  publisher: maintainer
  pub_date: 2026-09-22
  accessed: 2026-09-23
  confidence: medium
  class: measurement

- claim: A run with the harness arm moved to a separate bench profile read 1.160 ("failed") over 16 runs and was later found contaminated; three follow-up ablations of personal-layer files (1.285, 1.738, 1.226) were chasing the same defect.
  source: maintainer notes (unpublished), 2026-09-22, cost replay journey
  publisher: maintainer
  pub_date: 2026-09-22
  accessed: 2026-09-23
  confidence: medium
  class: measurement

- claim: Root cause of the contamination: #498. The suite's sync tests wrote into whichever profile CLAUDE_CONFIG_DIR named, so every bench-profile arm was asked to pass a gate it structurally could not; a sandbox fence that did not admit each arm's profile and /tmp compounded it (fixed in #487/#489, pre-flight bar lowered to lint in #499/#500).
  source: maintainer notes (unpublished), 2026-09-22, cost replay journey
  publisher: maintainer
  pub_date: 2026-09-22
  accessed: 2026-09-23
  confidence: medium
  class: mechanism-failure

- claim: The first uncontaminated set read 1.052 (cache-normalised 1.044), status failed, 16 runs (4 tasks x 2 arms x 2 reps), 0 errors, both pre-flights passed; per task link-alias 0.859, codex-pre-allow 1.166, hook-ids 1.197, hook-inventory 1.417: about 5% more than bare, winning only on the long task.
  source: maintainer notes (unpublished), 2026-09-22, cost replay journey
  publisher: maintainer
  pub_date: 2026-09-22
  accessed: 2026-09-23
  confidence: medium
  class: measurement

- claim: Two harness cells were bimodal at n=2 (codex-pre-allow 6 vs 25 calls, hook-ids 10 vs 52), explained as strategy; the bare arm's link-alias thrash still traced to #498 through the held-back test file, so 0.859 on that task flatters the harness; hook-ids rep 1 (one inline script, 10 calls, where bare went by hand at 55) is the first measured harness advantage.
  source: maintainer notes (unpublished), 2026-09-22, cost replay journey
  publisher: maintainer
  pub_date: 2026-09-22
  accessed: 2026-09-23
  confidence: medium
  class: measurement

- claim: Spawn break-even counterfactual from 20 stored transcripts: 4.8 to 7.6 calls; hook-inventory runs 6 calls so delegation cannot pay there (a manifest defect); the other three run 17 to 45 and should have delegated and never did (a harness defect); zero Task/Agent blocks in all 20.
  source: maintainer notes (unpublished), 2026-09-22, cost replay journey
  publisher: maintainer
  pub_date: 2026-09-22
  accessed: 2026-09-23
  confidence: medium
  class: measurement

- claim: The live prefix over bare was remeasured at 13,640 tokens (against an earlier 12,607); the first-call cache-write field is warmth-contaminated (45,847 vs 27,977 on one profile).
  source: maintainer notes (unpublished), 2026-09-22, cost replay journey
  publisher: maintainer
  pub_date: 2026-09-22
  accessed: 2026-09-23
  confidence: medium
  class: measurement

- claim: Output tokens were 19.6% to 22.9% of spend across four arm-sets, so brevity rules were assessed as a 2-3% lever against a ~60% swing from turn count; the output-style A/B (a 1,515-token style) was planned, not run.
  source: maintainer notes (unpublished), 2026-09-22, cost replay journey
  publisher: maintainer
  pub_date: 2026-09-22
  accessed: 2026-09-23
  confidence: medium
  class: measurement

- claim: A plugin auto-sync moved the slash-command count from 75 to 84 between two runs on one profile, an uncontrolled change to the arm; a plugin-parity pre-flight was filed (#482).
  source: maintainer notes (unpublished), 2026-09-22, cost replay journey
  publisher: maintainer
  pub_date: 2026-09-22
  accessed: 2026-09-23
  confidence: medium
  class: mechanism-failure

- claim: 0.12 release position: the instrument ships, no number or hero change ships; the eight-task set (48 runs at 3 reps) is held pending the evaluation; the publish-or-stop outcome is either a claim carrying both halves (cheaper on long tasks, dearer on the shortest) or a published failure with the instrument findings as the paper.
  source: maintainer notes (unpublished), 2026-09-22, cost replay journey
  publisher: maintainer
  pub_date: 2026-09-22
  accessed: 2026-09-23
  confidence: medium
  class: method
