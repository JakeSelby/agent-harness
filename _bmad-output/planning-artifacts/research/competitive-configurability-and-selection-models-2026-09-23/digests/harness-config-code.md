# Digest: bin/harness configuration and init

Claims in the standard shape. Source text treated as data.

- claim: load_config merges example defaults, then user config, then a project file named by HARNESS_PROJECT_CONFIG, then HARNESS_STANCE_* env keys.
  source: bin/harness load_config
  publisher: agent-harness repository at 3020251
  pub_date: 2026-09-23
  accessed: 2026-09-23
  confidence: high
  class: capability

- claim: A project file carrying any key other than stances is refused: 'project config may select stances only; user config owns identity, targets and permissions'.
  source: bin/harness load_config
  publisher: agent-harness repository at 3020251
  pub_date: 2026-09-23
  accessed: 2026-09-23
  confidence: high
  class: capability

- claim: Sync links ~/.claude/rules/harness to claude/rules as one link, so rules cannot be selected individually.
  source: bin/harness sync
  publisher: agent-harness repository at 3020251
  pub_date: 2026-09-23
  accessed: 2026-09-23
  confidence: high
  class: capability

- claim: STANCE_PRESETS has two entries, software (no overlay) and general (five stances off or light); they are the only bundle concept.
  source: bin/harness STANCE_PRESETS
  publisher: agent-harness repository at 3020251
  pub_date: 2026-09-23
  accessed: 2026-09-23
  confidence: high
  class: capability

- claim: init writes every stance key into the user config: the flag path copies the example stances plus the preset; the interactive path asks for all nine and writes each.
  source: bin/harness init paths
  publisher: agent-harness repository at 3020251
  pub_date: 2026-09-23
  accessed: 2026-09-23
  confidence: high
  class: capability

- claim: check_detectors fails lint for a rule file with neither a detector nor an OPT_OUT entry; its docstring reads 'A rule nobody can measure is a rule nobody can prune'.
  source: bin/harness check_detectors
  publisher: agent-harness repository at 3020251
  pub_date: 2026-09-23
  accessed: 2026-09-23
  confidence: high
  class: capability

- claim: rule_report groups hits by rule, by repository and by stance; it has no mode or switch grouping.
  source: bin/harness rule_report
  publisher: agent-harness repository at 3020251
  pub_date: 2026-09-23
  accessed: 2026-09-23
  confidence: high
  class: capability
