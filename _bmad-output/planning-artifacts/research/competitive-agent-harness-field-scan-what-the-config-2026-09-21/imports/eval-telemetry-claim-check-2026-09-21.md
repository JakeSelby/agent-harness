# Adversarial check: "no other project measures whether your instruction-file rules fire"

Date: 2026-09-21. Method: GitHub API (`readme`, `git/trees`, `contents`, code search) over 7 external
repos. No web search. Everything below is from source or README text read this session; anything not
read is marked **could not verify**.

## Verdict

**True in a narrower form.** As stated it is an unbounded universal ("no other project") that I
checked against 7 repos, and one of them — `burnd` — measures *skill* firing and also emits CLAUDE.md
text, so a hostile reader has a foothold. The narrower form survives.

Defensible public sentence:

> agent-harness is the only agent-config project we know of that binds a named detector to each rule
> file, fails its own lint when a rule has neither a detector nor a written opt-out reason, and
> reports per-rule hit rate from the agent's own transcripts — broken down by repository and by which
> preference variant was active.

## Evidence per repo

### langfuse/langfuse
Ingestion is SDK/API-first (Python + JS SDKs, integrations). **Accepts OTLP**: the repo carries a
public OTel ingestion path (`web/src/pages/api/public/otel/otlp-proto/`, `web/src/server/otel/
processOtelIngestion.ts`, `worker/src/queues/otelIngestionQueue.ts`), so agent-harness could feed it.
Scoring exists — "LLM-as-a-judge, Code evaluators, user feedback collection, manual labeling, and
custom evaluation pipelines via APIs/SDKs" — but scores attach to traces/observations/dataset runs.
**No concept of a rule or instruction file.** No coding-agent transcript reader.

### comet-ml/opik
Same shape: SDK tracing, feedback scores annotated on traces/spans, LLM-as-a-judge metrics, datasets
and experiments, "online evaluation rules" (server-side judges over production traces, not
instruction-file rules), PyTest CI integration. OTLP: the repo carries OTel integrations in both
SDKs (`sdks/python/src/opik/integrations/otel/`, `sdks/typescript/.../opik-otel/`) and an nginx OTel
template (`apps/opik-frontend/nginx/templates/20-otel.conf.template`), so it can receive OTel-shaped
data; the exact ingest endpoint was not read this session. No transcript reader,
no rule-file binding.

### Arize-ai/phoenix
OpenTelemetry/OpenInference-native by construction ("vendor, language, and framework agnostic"), so
OTLP in is a given. Ingestion still requires instrumenting the app. Evals are LLM-graded response and
retrieval quality over spans/datasets. No rule-file concept, no agent-transcript reader.

### lob-labs/cc-cost
Closest on *input*: pure-Python, parses `~/.claude/projects/**.jsonl`, zero instrumentation. Purpose
is cost. `--diagnose` heuristics, verbatim from `cc_cost.py::diagnose`:
1. cache hit rate `< 30%` with `turns > 5` → "Cache hit rate is X% (target: 80%+). You are paying
   ~10× more than necessary on prompt input…";
2. cache hit rate `< 60%` with `turns > 5` → "Some context is hot, but you're still re-reading
   non-cached chunks";
3. mean output `> 1500` tokens/turn → "Output costs 5× input… Add to system prompt: 'Keep responses
   concise. Skip preambles and summaries.'";
4. Bash `> 60%` of calls and `> 20` calls → "Each Bash call re-pays the prompt — group commands…";
5. `Read` calls `> 30` → "If you're re-reading the same files, bundle context…";
6. exactly one distinct tool used → "All N tool calls were `<tool>`…".
Nothing ties to CLAUDE.md. The recommendations are prose advice, not measurements of a rule.

### garvitsurana/burnd → actually **garvitsurana271/burnd** (the briefed path 404s)
The real neighbour. TypeScript CLI over the same JSONL. Detector files under
`src/cli/src/detectors/`: `long-bash-output`, `model-substitution`, `one-shot-failure`,
`project-cost-outlier`, `repeated-read`, `retry-storm`, `skill-firing`, `thrash`, `tired-coding`,
`tool-overuse`; plus an `openclaw/detectors/` set (`agent-cost-outlier`, `cache-underuse`,
`expensive-model`, `high-output-ratio`, `late-night`, `provider-switching`). Registry in
`detectors/index.ts` also computes a per-user baseline (session-cost p50/p75/p90, inferred focus
window) so outliers are relative to that user.

Two overlaps worth naming honestly:

1. **It does measure firing — of skills, as a cost leak.** `skill-firing.ts`: flags a session where
   the `Skill` tool was called `>= 5` times *and* `> 20%` of tool calls, titled "Skill is firing too
   often". Its own comment: "Heavy skill firing usually means a skill description is too broad".
2. **It touches CLAUDE.md.** Every insight carries a field typed in `detectors/types.ts`:
   `claudeMdPatch: string | null` — "The single CLAUDE.md line (or short block) that fixes this leak.
   Copy-pasteable directly into a project's CLAUDE.md." e.g. `tool-overuse.ts` emits "Prefer Read over
   cat/head/tail. Prefer Edit over sed/awk…".

But the direction is inverted. burnd goes leak → proposed rule text, and never returns to ask whether
the rule it proposed changed anything. No detector is bound to a rule *file*; there is no per-rule hit
rate, no coverage gate, and `skill-firing.ts` sets `claudeMdPatch: null` explicitly because that fix
lives in SKILL.md. Over-firing is the only firing it scores, and only when firing costs money.

### letta-ai/letta-evals
"Rule-based grading" = graders over *outputs*. Flow is `Dataset → Target → Extractor → Grader →
Reward → Result`; graders are `kind: tool` (e.g. `contains`), rubric files, or custom Python, run
against dataset rows. Nothing reads an instruction file or a live transcript.

### UKGovernmentBEIS/inspect_ai
Scorers operate on runs Inspect itself orchestrates. It has a rich internal transcript
(`src/inspect_ai/log/_transcript.py`, `_transcript_store.py`, `solver/_transcript.py`) but that is its
own event record; I found no importer for Claude Code JSONL. You *could* replicate the rule report by
writing a dataset of past sessions plus a custom solver that replays a stored transcript and a scorer
that pattern-matches it — that is building agent-harness's detectors inside Inspect's harness, using
Inspect for the runner, viewer and stats rather than getting the rule report from it. Real work, not a
config change.

### fastxyz/skill-optimizer
Docker + OpenRouter workbench running eval cases against a SKILL.md with deterministic local graders
emitting `{ "pass": true, "score": 1, "evidence": ["answer matched"] }` (SKILL.md line 126); "do not
use an LLM judge unless the eval explicitly requires one". That measures **quality under synthetic
cases** — did the skill produce the right outcome when invoked — not whether it fired in real work. I
found no trigger/activation measurement in the README (grep for trigger/activate/describe returned
nothing); **could not verify** whether the workbench scores description-match separately.

## Narrowest true uniqueness chain

Every link is load-bearing; drop one and a comparator matches.

1. Reads the agent's own on-disk transcript, zero instrumentation of the app — shared with cc-cost and
   burnd, so not unique alone.
2. Each detector is bound **by name to a specific rule file**, not to a cost pattern or a tool —
   burnd's detectors are named for leaks (`retry-storm`, `tool-overuse`); none maps to a rule.
3. Coverage is **enforced**: lint fails a rule file with neither a detector nor a written OPT_OUT
   reason, so the measured set can't silently drift from the shipped set. No comparator has any
   analogue of instruction-set coverage.
4. The output is **hit rate per rule, grouped by repository and by selected preference variant**. The
   variant axis is the hardest link to refute: no project checked has a notion of alternative
   instruction variants at all, so none can report per-variant firing.

It stops being true the moment any of: burnd adds a detector keyed to CLAUDE.md headings that reports
a per-rule fire rate (it already has the parser, the CLAUDE.md vocabulary and the field); a Langfuse or
Opik cookbook ships a Claude Code JSONL importer plus per-rule scores; skill-optimizer adds real-session
trigger measurement; or Anthropic exposes rule-attribution in Claude Code itself, which would make the
whole detector layer redundant.

## Three things agent-harness is genuinely behind on

1. **Detector validity is unmeasured.** There is no labelled corpus and no golden run, so nobody knows
   a detector's precision or recall. A hit rate can move because the rule fired more or because the
   detector's pattern got luckier. letta-evals, inspect_ai and skill-optimizer all run against fixed
   datasets with ground truth; that discipline is absent here, and it is the weakest joint in the whole
   claim — "measures whether rules fire" is only as true as the detectors are accurate.
2. **No counterfactual.** Per-variant hit rate is observational, not experimental. There is no fixed
   task set replayed under variant A and variant B, so "this rule works better" is not supported.
   Opik gates on PyTest in CI and inspect_ai gives reproducible scored task runs; agent-harness has no
   equivalent regression gate that would catch a rule edit making behaviour worse.
3. **Rules with an OPT_OUT are simply dark, and nothing judges them.** The lint forces an honest
   admission, which is good, but the comparators all have LLM-as-judge machinery (Langfuse, Opik,
   Phoenix) that could score exactly the non-pattern-matchable rules — tone, altitude, honesty — that
   agent-harness currently writes off. Also behind on operator surface: local JSONL plus an off-by-
   default OTLP export against Langfuse/Phoenix/Opik UIs, and no cost or outlier dimension at all,
   where burnd has per-user percentile baselines and dollar savings estimates. Whether the rule report
   can drill from a miss down to the offending turn: **could not verify**.

## Positioning call

**Both, in a fixed order.** Lead with the narrow uniqueness sentence, because it is the only thing
here nobody else does and it is defensible verbatim; follow immediately with the complementarity
clause — "and it exports OTLP to the observability stack you already run" — because the audience most
likely to read the claim already runs Langfuse or Phoenix and will otherwise hear a competing product
rather than an additional signal. Uniqueness alone invites a refutation attempt; complementarity alone
buries the only novel mechanism. Never state the unbounded negative ("no other project") in public
copy: say "the only one we know of" and keep this file as the receipt.
