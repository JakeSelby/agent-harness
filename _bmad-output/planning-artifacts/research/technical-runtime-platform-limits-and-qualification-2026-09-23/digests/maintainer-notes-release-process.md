# Digest: maintainer notes (unpublished), 2026-09-21, release-process cost analysis

- source: maintainer notes (unpublished), 2026-09-21, release-process cost analysis
- publisher: agent-harness maintainer
- pub_date: 2026-09-21
- accessed: 2026-09-23

- {claim: "Codex targets took 49 and 61 minutes and 224 and 239 tool calls against 20-30 minutes and 86-112 calls for Claude targets, because no runner drove them.", source: "maintainer notes (unpublished), 2026-09-21, release-process cost analysis", publisher: "agent-harness maintainer", pub_date: 2026-09-21, accessed: 2026-09-23, confidence: medium, class: cost-measurement}
- {claim: "Lifecycle acceptance on 2 systems x 2 Pythons costs about 2 minutes each and no model tokens.", source: "maintainer notes (unpublished), 2026-09-21, release-process cost analysis", publisher: "agent-harness maintainer", pub_date: 2026-09-21, accessed: 2026-09-23, confidence: medium, class: cost-measurement}
- {claim: "A scripted-case worker should land near 60K tokens per Claude target and about 120K for both Codex targets, taking a round from about 1M to about 0.2M orchestrator tokens and from 60 to 20-25 minutes (estimate).", source: "maintainer notes (unpublished), 2026-09-21, release-process cost analysis", publisher: "agent-harness maintainer", pub_date: 2026-09-21, accessed: 2026-09-23, confidence: low, class: cost-measurement}
- {claim: "Three runner plumbing faults found in round 1 (credential hang, vacuous pass, missing credential doc) were deterministic and catchable without a model turn.", source: "maintainer notes (unpublished), 2026-09-21, release-process cost analysis", publisher: "agent-harness maintainer", pub_date: 2026-09-21, accessed: 2026-09-23, confidence: medium, class: harness-design}
