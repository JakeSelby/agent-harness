# Teardown — eval-telemetry-claim-check-2026-09-21.md

- claim: the unbounded claim "no other project measures whether your instruction-file rules fire" was checked against 7 external repos via the GitHub API and survives only in a narrower form.
  source: eval-telemetry-claim-check-2026-09-21.md
  publisher: internal research import
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: telemetry
  via: eval-telemetry-claim-check-2026-09-21.md
- claim: the defensible public sentence is that agent-harness is the only agent-config project known to bind a named detector to each rule file, fail its own lint when a rule has neither a detector nor a written opt-out, and report per-rule hit rate broken down by repository and active preference variant.
  source: eval-telemetry-claim-check-2026-09-21.md
  publisher: internal research import
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: telemetry
  via: eval-telemetry-claim-check-2026-09-21.md
- claim: Langfuse ingests via SDK/API and accepts OTLP through a public OTel path, so agent-harness could export to it, but it has no concept of a rule or instruction file and no coding-agent transcript reader.
  source: langfuse/langfuse:web/src/pages/api/public/otel/otlp-proto/, worker/src/queues/otelIngestionQueue.ts
  publisher: Langfuse
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: telemetry
  via: eval-telemetry-claim-check-2026-09-21.md
- claim: Opik's "online evaluation rules" are server-side judges over production traces, not instruction-file rules, and it has no transcript reader or rule-file binding.
  source: comet-ml/opik:sdks/python/src/opik/integrations/otel/
  publisher: Comet ML
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: medium
  class: telemetry
  via: eval-telemetry-claim-check-2026-09-21.md
- claim: Opik's exact OTLP ingest endpoint was not read this session, so its receive path is inferred from the presence of OTel integrations and an nginx OTel template.
  source: comet-ml/opik:apps/opik-frontend/nginx/templates/20-otel.conf.template
  publisher: Comet ML
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: low
  class: telemetry
  via: eval-telemetry-claim-check-2026-09-21.md
- claim: Arize Phoenix is OpenTelemetry/OpenInference-native so OTLP ingest is a given, but ingestion still requires instrumenting the application and it has no rule-file concept or agent-transcript reader.
  source: Arize-ai/phoenix
  publisher: Arize AI
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: medium
  class: telemetry
  via: eval-telemetry-claim-check-2026-09-21.md
- claim: lob-labs/cc-cost parses `~/.claude/projects/**.jsonl` in pure Python with zero instrumentation, the same zero-instrumentation input shape agent-harness uses, but for cost.
  source: lob-labs/cc-cost:cc_cost.py
  publisher: lob-labs
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: telemetry
  via: eval-telemetry-claim-check-2026-09-21.md
- claim: cc-cost's `--diagnose` emits six prose heuristics (cache hit rate under 30% and under 60%, mean output over 1500 tokens/turn, Bash over 60% of calls, Read over 30 calls, single-tool sessions) and none of them ties to CLAUDE.md.
  source: lob-labs/cc-cost:cc_cost.py::diagnose
  publisher: lob-labs
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: telemetry
  via: eval-telemetry-claim-check-2026-09-21.md
- claim: the briefed repo path garvitsurana/burnd 404s; the real repository is garvitsurana271/burnd.
  source: https://api.github.com/repos/garvitsurana271/burnd
  publisher: GitHub
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: traction
  via: eval-telemetry-claim-check-2026-09-21.md
- claim: burnd is the nearest neighbour — a TypeScript CLI over the same Claude Code JSONL with ten named detectors plus a second openclaw detector set, and a per-user baseline (session-cost p50/p75/p90) so outliers are relative to that user.
  source: garvitsurana271/burnd:src/cli/src/detectors/index.ts
  publisher: garvitsurana271/burnd
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: telemetry
  via: eval-telemetry-claim-check-2026-09-21.md
- claim: burnd does measure firing — `skill-firing.ts` flags a session where the Skill tool was called at least 5 times and more than 20% of tool calls, commenting "Heavy skill firing usually means a skill description is too broad".
  source: garvitsurana271/burnd:src/cli/src/detectors/skill-firing.ts
  publisher: garvitsurana271/burnd
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: telemetry
  via: eval-telemetry-claim-check-2026-09-21.md
  contradicts: the unbounded claim no other project
- claim: every burnd insight carries a `claudeMdPatch: string | null` field described as "The single CLAUDE.md line (or short block) that fixes this leak. Copy-pasteable directly into a project's CLAUDE.md."
  source: garvitsurana271/burnd:src/cli/src/detectors/types.ts
  publisher: garvitsurana271/burnd
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: telemetry
  via: eval-telemetry-claim-check-2026-09-21.md
- claim: burnd's direction is inverted — leak to proposed rule text, never returning to ask whether the proposed rule changed anything; no detector is bound to a rule file, there is no per-rule hit rate and no coverage gate.
  source: garvitsurana271/burnd:src/cli/src/detectors/
  publisher: garvitsurana271/burnd
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: telemetry
  via: eval-telemetry-claim-check-2026-09-21.md
- claim: letta-evals' "rule-based grading" means graders over outputs in a Dataset → Target → Extractor → Grader → Reward → Result flow; nothing reads an instruction file or a live transcript.
  source: letta-ai/letta-evals
  publisher: Letta
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: medium
  class: validation
  via: eval-telemetry-claim-check-2026-09-21.md
- claim: inspect_ai has a rich internal transcript but no importer for Claude Code JSONL was found; replicating the rule report there means building agent-harness's detectors inside Inspect as a custom solver and scorer.
  source: UKGovernmentBEIS/inspect_ai:src/inspect_ai/log/_transcript.py
  publisher: UK AI Safety Institute (BEIS)
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: medium
  class: validation
  via: eval-telemetry-claim-check-2026-09-21.md
- claim: fastxyz/skill-optimizer runs eval cases against a SKILL.md with deterministic local graders emitting `{ "pass": true, "score": 1, "evidence": [...] }` and instructs "do not use an LLM judge unless the eval explicitly requires one".
  source: fastxyz/skill-optimizer:SKILL.md:126
  publisher: fastxyz
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: validation
  via: eval-telemetry-claim-check-2026-09-21.md
- claim: skill-optimizer measures quality under synthetic cases rather than whether a skill fired in real work; whether its workbench scores description-match separately could not be verified.
  source: fastxyz/skill-optimizer:README
  publisher: fastxyz
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: low
  class: validation
  via: eval-telemetry-claim-check-2026-09-21.md
- claim: the uniqueness chain has four load-bearing links, and only links 2-4 (detector bound by name to a rule file, enforced coverage lint, hit rate per rule grouped by repo and preference variant) are unshared; reading the on-disk transcript with zero instrumentation is shared with cc-cost and burnd.
  source: eval-telemetry-claim-check-2026-09-21.md
  publisher: internal research import
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: telemetry
  via: eval-telemetry-claim-check-2026-09-21.md
- claim: the per-variant axis is the hardest link to refute because no project checked has any notion of alternative instruction variants, so none can report per-variant firing.
  source: eval-telemetry-claim-check-2026-09-21.md
  publisher: internal research import
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: medium
  class: preference-variants
  via: eval-telemetry-claim-check-2026-09-21.md
  contradicts: LynxPrompt is the only project
- claim: the claim stops being true if burnd adds a detector keyed to CLAUDE.md headings reporting a per-rule fire rate — it already has the parser, the CLAUDE.md vocabulary and the field.
  source: eval-telemetry-claim-check-2026-09-21.md
  publisher: internal research import
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: medium
  class: telemetry
  via: eval-telemetry-claim-check-2026-09-21.md
- claim: agent-harness detector validity is unmeasured — no labelled corpus, no golden run, so no detector's precision or recall is known, and a hit rate can move because the detector got luckier.
  source: eval-telemetry-claim-check-2026-09-21.md
  publisher: internal research import
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: validation
  via: eval-telemetry-claim-check-2026-09-21.md
- claim: per-variant hit rate is observational, not experimental — there is no fixed task set replayed under variant A and variant B, so "this rule works better" is unsupported and no regression gate would catch a rule edit making behaviour worse.
  source: eval-telemetry-claim-check-2026-09-21.md
  publisher: internal research import
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: validation
  via: eval-telemetry-claim-check-2026-09-21.md
- claim: rules carrying an OPT_OUT are unmeasured, and the comparators' LLM-as-judge machinery (Langfuse, Opik, Phoenix) could score exactly those non-pattern-matchable rules — tone, altitude, honesty.
  source: eval-telemetry-claim-check-2026-09-21.md
  publisher: internal research import
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: medium
  class: validation
  via: eval-telemetry-claim-check-2026-09-21.md
- claim: agent-harness is behind on operator surface — local JSONL only, no off-by-default OTLP export to Langfuse/Phoenix/Opik, and no cost or outlier dimension where burnd has per-user percentile baselines and dollar savings estimates.
  source: eval-telemetry-claim-check-2026-09-21.md
  publisher: internal research import
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: telemetry
  via: eval-telemetry-claim-check-2026-09-21.md
- claim: whether the rule report can drill from a miss down to the offending turn could not be verified.
  source: eval-telemetry-claim-check-2026-09-21.md
  publisher: internal research import
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: low
  class: telemetry
  via: eval-telemetry-claim-check-2026-09-21.md
- claim: the positioning call is to lead with the narrow uniqueness sentence then immediately add the complementarity clause about OTLP export, and never to state the unbounded negative in public copy — say "the only one we know of".
  source: eval-telemetry-claim-check-2026-09-21.md
  publisher: internal research import
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: telemetry
  via: eval-telemetry-claim-check-2026-09-21.md

## Leads

- garvitsurana271/burnd — the only real competitor on this axis; watch `detectors/types.ts` for a rule-keyed detector appearing.
- An off-by-default OTLP exporter targeting Langfuse/Phoenix/Opik is the cheapest complementarity move and the import names it as the missing operator surface.
- A labelled detector corpus with a golden run is the weakest joint in the uniqueness claim; letta-evals, inspect_ai and skill-optimizer all model the discipline.
- inspect_ai as a possible runner/viewer/stats layer for a replayed-transcript regression gate.
- Anthropic exposing rule attribution inside Claude Code would make the whole detector layer redundant — a strategic watch item.

## Not found

- Any project besides agent-harness binding a detector by name to a specific rule file.
- Any instruction-set coverage gate analogue in any of the seven repos.
- Opik's exact OTLP ingest endpoint.
- Whether skill-optimizer scores description-match / trigger activation separately.
- Whether the agent-harness rule report drills from a miss to the offending turn.
