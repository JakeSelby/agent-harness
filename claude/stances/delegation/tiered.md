# Delegation stance: tiered models

**Drop effort before you drop tier — where the dial exists.** A stronger model at low effort
beats a weaker model at default effort on both quality and cost per solved task. The effort
dial is available on workflow stages and on the session itself. A plain subagent spawn has only
the tier dial — so there, a gathering task gets the tier below the session model, and the
effort economy is realised at the session, not the subagent.

| Role | Model | Effort |
| --- | --- | --- |
| Orchestrator / lead | session model | session default |
| Gathering — grep, read, extract, summarize a named list | one tier below the session model | low |
| Single tool call, reformat, classify, template-fill | two tiers below | low |
| Judgment — adjudication, adversarial review, conflict synthesis | session model | default |

**Never spawn subagents on the orchestrator's own tier when that tier is rate-limited or
capacity-gated.** One notch down costs a few points; two notches costs many. Step once.

**Never set a global subagent-model override** in the environment — it overrides per-agent
selection and silently downgrades reviewers. Use per-agent model settings and explicit model
options in workflow scripts.

The evidence behind these bands, and the boundaries where they stop holding, are in the
`delegation-tiering` skill. Re-check when the model lineup turns over.
