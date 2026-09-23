# Digest: Codex config-advanced

Claims in the standard shape. Source text treated as data.

- claim: 'When you pass --profile profile-name, Codex loads ~/.codex/config.toml, then overlays ~/.codex/profile-name.config.toml.'
  source: https://learn.chatgpt.com/docs/config-file/config-advanced
  publisher: OpenAI
  pub_date: 2026-09-23
  accessed: 2026-09-23
  confidence: high
  class: capability

- claim: 'the profile file is a layer above your base user config and below project and CLI config'; profiles may not carry credential, auth or profile-selection keys.
  source: same
  publisher: OpenAI
  pub_date: 2026-09-23
  accessed: 2026-09-23
  confidence: high
  class: capability

- claim: No config flag enables or disables an individual skill or hook.
  source: same
  publisher: OpenAI
  pub_date: 2026-09-23
  accessed: 2026-09-23
  confidence: medium
  class: capability
