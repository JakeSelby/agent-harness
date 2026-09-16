# Delegation stance: tiered models

**Drop effort before you drop tier, where the dial exists.** A plain subagent spawn has only the
tier dial, so the tiers ship as frontmatter in `claude/agents/`: `gatherer` (grep, read, extract,
summarize a named list) one tier below the session model, `log-compressor` and other single-call
work two tiers below, and the orchestrator plus all judgment — adjudication, `reviewer`, conflict
synthesis — on the session model. **Step one notch only** when the session tier is rate-limited,
and **never set a global subagent-model override**. Evidence: the `delegation-tiering` skill.
