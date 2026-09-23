# Digest: docs/telemetry.md (at 3020251), fan-out and double-counting sections

- claim: A Claude Code session's figure already includes its subagents, so a session row and its subagent rows must never be summed; filter on `kind` first. A Codex subagent is the reverse: its tokens are in no row but its own.
  source: docs/telemetry.md, "The dollar figure" and "De-duplicating an at-least-once stream"
  publisher: agent-harness
  pub_date: 2026-09-23
  accessed: 2026-09-23
  confidence: high
  class: method

- claim: Exported dollars are a list-price equivalent fixed at export time and re-stamped on replay; read the newest record per row key, ordered on the export stamp only.
  source: docs/telemetry.md
  publisher: agent-harness
  pub_date: 2026-09-23
  accessed: 2026-09-23
  confidence: high
  class: method
