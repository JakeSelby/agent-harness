# Digest: docs/telemetry.md (runtime sections) @3020251

- source: docs/telemetry.md (runtime sections) @3020251
- publisher: agent-harness
- pub_date: 2026-09-23
- accessed: 2026-09-23

- {claim: "Claude Code reports a dollar figure per API call; Codex counts tokens, turn cost, tool calls and API calls.", source: "docs/telemetry.md (runtime sections) @3020251", publisher: "agent-harness", pub_date: 2026-09-23, accessed: 2026-09-23, confidence: medium, class: platform-capability}
- {claim: "Claude Code resolves OTLP headers at run time through otelHeadersHelper (re-run about every 29 minutes); Codex takes [otel] header values only as literals in config.toml, so the harness writes none and Codex native export needs an unauthenticated endpoint.", source: "docs/telemetry.md (runtime sections) @3020251", publisher: "agent-harness", pub_date: 2026-09-23, accessed: 2026-09-23, confidence: high, class: platform-capability}
- {claim: "Codex metrics_exporter defaults to a first-party sink that drops token usage, turn cost, tool-call and API-call metrics client-side, so exporter alone sends no token metrics (from config reference and source read, unverified by a run).", source: "docs/telemetry.md (runtime sections) @3020251", publisher: "agent-harness", pub_date: 2026-09-23, accessed: 2026-09-23, confidence: medium, class: platform-capability}
- {claim: "Codex has no config key for metric labels; OTEL_RESOURCE_ATTRIBUTES from the process environment is honoured but sync cannot set it and a desktop-launched Codex may inherit no shell env.", source: "docs/telemetry.md (runtime sections) @3020251", publisher: "agent-harness", pub_date: 2026-09-23, accessed: 2026-09-23, confidence: medium, class: platform-capability}
- {claim: "harness.usd is a list-price API equivalent fixed at export time from policy/prices.json, not an invoice; a Claude Code session figure includes its subagents, while Codex subagent and role-worker rows are priced alone.", source: "docs/telemetry.md (runtime sections) @3020251", publisher: "agent-harness", pub_date: 2026-09-23, accessed: 2026-09-23, confidence: high, class: harness-design}
- {claim: "Claude Code attaches user.email, account ids, organization.id and session.id to its datapoints; the harness sets none of the OTEL_METRICS_INCLUDE_* switches.", source: "docs/telemetry.md (runtime sections) @3020251", publisher: "agent-harness", pub_date: 2026-09-23, accessed: 2026-09-23, confidence: high, class: platform-capability}
