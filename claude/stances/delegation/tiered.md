# Delegation stance: tiered models

**Drop effort before you drop tier, where the dial exists.** The tiers ship as frontmatter in
`claude/agents/`: `gatherer` (grep, read, extract, summarize a named list) one tier below the
session model, `log-compressor` and single-call work two tiers below, the orchestrator and all
judgment — adjudication, `reviewer`, conflict synthesis — on the session model. A spawn with no
agent gets one tier below from the `tier-spawns` hook, so **name judgment agents**. **Step one
notch only** when rate-limited, **no global subagent-model override**. See `delegation-tiering`.
