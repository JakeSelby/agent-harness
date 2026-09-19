# Delegation stance: tiered models

**Gather with subagents without waiting to be asked** — locating files, reading, grepping,
extracting, summarizing — in every repo and mode. Keep judgment in the session.

**Drop effort before you drop tier, where the dial exists.** The tiers ship as frontmatter in
`claude/agents/`: `gatherer` (grep, read, extract, summarize a named list) one tier below the
session model, `log-compressor` and single-call work two tiers below, the orchestrator and all
judgment — adjudication, `reviewer`, synthesis — on the session model. The `tier-spawns`
hook puts a spawn naming no agent one tier down (session model in a framework repo): **name
judgment agents**. **One notch** when rate-limited; **no global override**. Why: `delegation-tiering`.
