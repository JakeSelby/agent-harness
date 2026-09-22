# Field scan: what the configuration-compiler field does, and where this harness sits

**Read on 2026-09-21. Re-check by 2026-12-01.** One person's reading of a fast-moving field on one
date. Release cadence among the projects below runs daily to weekly, so treat every "ships" and
"does not ship" here as a dated observation, not a standing fact. The method, the sources and the
raw claim ledger are in the research run under
[`_bmad-output/planning-artifacts/research/`](../_bmad-output/planning-artifacts/research/), and
corrections are welcome as an [Idea issue](https://github.com/JakeSelby/agent-harness/issues/new/choose).

## 1. Why this page exists

Comparisons age badly and get written by the party with the most to gain. This one names its date,
its method and its own gaps first, and puts what to use *instead* of this repository above what this
repository does well. If that order looks odd, it is the point: the page is meant to be useful to
someone choosing a tool, including when the right answer is not this one.

## 2. How the field was read

Four public curated lists were pulled with `gh api <repo>/readme` and their relevant categories
enumerated: `RyanAlberts/best-of-Agent-Harnesses` ("Coding harness configs and SDKs", "Personal
agent runtimes", "Evaluation and benchmarking harnesses", "Observability and eval-ops"),
`hesreallyhim/awesome-claude-code` ("Configuration", "Linting"), `jamesmurdza/awesome-ai-devtools`
("Configuration & Context Management") and `ai-for-developers/awesome-ai-coding-tools` ("Developer
Productivity Tools"). Twenty repositories were then read from their file trees, not their READMEs,
and every comparative claim below names a file path or a URL a reader can open. Eight issue trackers
were read for what users praise, complain about and ask for. Star counts are recorded as context and
never used as a ranking. This repository appears in none of the four lists as of the read date.

The category this repository competes in, named precisely: **tools that hold coding-agent
configuration — rules, skills, subagents, commands, hooks — as one source and generate each
runtime's native files from it.** Three adjacent categories get conflated with it and are
structurally different: skill packs shipped as-is for one runtime; read-only linters of context
files; and governance planes that gate actions at runtime.

## 3. What to use instead of this

For most people, most of the time:

- **[rulesync](https://github.com/dyoshikawa/rulesync)** if you run more than two runtimes. It
  compiles to fifty-two targets, and the target list is derived rather than hand-kept — one tuple per
  feature, unioned in `src/types/tool-targets.ts` ("no separately-maintained literal to drift"). It
  imports and converts in both directions, ships on npm, and cut three releases in four days in the
  week this was written. This repository compiles to two runtimes and has no importer yet.
- **[ctxlint](https://github.com/YawLabs/ctxlint)** alongside whatever you pick. Ninety rules in
  four JSON catalogs, token thresholds you can tune (`error: 8000`, `tierAggregate: 4000`), and
  contradiction detection across files on eight tool-choice axes (`src/core/checks/contradictions.ts`).
  It reads and never writes, so it composes with everything here. This repository's conflict
  engine ships with a schema and no constraints.
- **[planning-with-files](https://github.com/OthmanAdi/planning-with-files)** if long-running plans
  are your problem. It solves one axis better than this repository solves nine, and its `.mode`
  precedence — "Root `.mode` is a FLOOR, not a default that slug scope replaces"
  (`scripts/inject-plan.sh`) — is a better idea than this repository's override precedence.
- **[gsd-core](https://github.com/open-gsd/gsd-core)** if you want a cost and quality dial today,
  across sixteen runtime families, with a team behind it. `MODEL_PROFILES` offer `quality | balanced
  | budget | adaptive`, and review depth auto-downgrades past a file threshold
  (`src/code-review-depth.cts`).

## 4. What the field got right, by name

- **rulesync** — the derived target list, bidirectional `import`/`convert`, and a `doctor` with
  eighteen typed diagnostic codes. Also the most honest breadth table in the set: it marks end-of-life
  targets as "frozen-compatibility" rather than dropping or hiding them.
- **planning-with-files** — the only project positioned on evidence. Its README leads with "3 out
  of 3 blind A/B wins", links the method, and discloses its limits in the same breath ("Treat it as
  the project's own measurement, not an independent comparison"). Its ongoing seven-arm benchmark
  publishes a result *against itself* and carries a "What this test does not measure" section
  ([`docs/evals.md`](https://github.com/OthmanAdi/planning-with-files/blob/main/docs/evals.md)).
  That is the bar for an evidence claim in this field, and this page holds itself to it below.
- **wshobson/agents** — a capability matrix generated from code rather than maintained as prose:
  `tools/adapters/capabilities.py` produces
  [`docs/harnesses.md`](https://github.com/wshobson/agents/blob/main/docs/harnesses.md), fourteen
  capabilities by six harnesses, with a second "graceful degradation" table naming the exact rewrite
  per pattern per runtime. Also a name-collision check this repository lacked.
- **gstack** — `bin/gstack-developer-profile` keeps declared *and inferred* values on five
  preference dimensions and flags drift between them with `--check-mismatch`. This repository has
  declared stances and measured rules; it does not yet infer what your effective stance is.
- **agents-md-cookbook** — the only sourced size cap in the field: `CODEX_BYTE_CAP = 32768`,
  citing that Codex truncates AGENTS.md at 32 KiB (`rules/byte-cap.ts`). Six projects enforce a cap
  and no two numbers agree — 200 lines, 150, 400, 8,000 tokens, 32 KiB — and only this one says why.
- **Burnd** ([garvitsurana271/burnd](https://github.com/garvitsurana271/burnd)) — the nearest
  neighbour to what this repository measures. It reads the same Claude Code transcripts, flags heavy
  skill firing ("usually means a skill description is too broad"), and attaches a `claudeMdPatch` — "the single CLAUDE.md line (or short
  block) that fixes this leak" — to every insight. It runs the other direction from this
  repository (leak → suggested rule, rather than rule → did it fire), and it is credited here because
  the direction is the only difference.
- **superpowers** — sixteen per-runtime install sections and no breadth claim in its hero line at
  all, which is the opposite of the field's usual stretch.

## 5. What this repository took from the field

- The **bounded uniqueness claim** in §6 exists because the eval and telemetry landscape was
  checked rather than asserted; the unbounded "nobody measures" was false, and Burnd is why.
- A **generated compatibility matrix** with a degradation table, on wshobson's model, replaces two
  hand-maintained authorities that had drifted apart (`compatibility/catalog.json` marked clients
  qualified while `adapters/*/capabilities.json` marked every stance unqualified).
- A **plugin manifest, a packaged install path and an importer** — the three things every
  high-adoption neighbour ships and this repository did not — are 0.13 work, with rulesync's
  `import` as the reference.
- **Floor semantics for stances**, from planning-with-files, are scheduled and not yet adopted.
- The **field's vocabulary**: of eight project hero lines, only one uses the word "harness", and
  there it names the target runtimes. The most common noun is "skill", then "config", then "rules".
  This repository's front door now leads with rules.

## 6. What is here that I did not find elsewhere

Stated as narrowly as the evidence allows. Each line names the file that implements it.

- **Rules that are measured, and a lint that refuses an unmeasured one.** Every rule file names a
  deterministic detector over the agent's own transcript or carries a one-line reason nothing in a
  transcript can decide it; `check_detectors` in `bin/harness` fails the commit otherwise.
  `harness usage --rules` reports hit rate per rule, grouped by repository and by which preference
  variant was selected. This is the only project I know of that binds a detector to each rule file,
  fails lint on an unmeasured rule, and reports per-rule hit rate by repository and by preference
  variant. It also exports the same ledger over OTLP to the observability stack you already run —
  Langfuse, Phoenix and Opik all accept it — adding the one thing those platforms cannot see, which
  rule fired.
- **An ownership journal for the files it manages.** `lib/harness_core/reconcile.py` records prior
  and applied content per owned field, refuses an unmanaged path ("adopt explicitly before replacing
  it"), exits non-zero on conflict, and `harness uninstall` restores prior values only while the
  current value still matches what was last applied. rulesync's equivalent covers hooks only, opt-in.
- **Shell commands graded 0 to 3 before they run.** `claude/hooks/grade-bash.py` decomposes
  compounds, substitutions and heredocs and grades reversibility; the autonomy stance sets which grade
  stops and asks. Comparable tools pattern-match the command string.
- **One policy coordinator per lifecycle event across two runtimes**, fail-closed
  (`lib/harness_core/lifecycle.py`): a Claude Code spawn and a Codex spawn resolve to the same
  delegation policy.
- **Preferences as nine user-extensible axes.** Three other projects ship one to three switchable
  behavioural axes; this repository generalises the idea, and only three of its nine axes bind to
  enforcement today (autonomy, delegation, cost). The rest are prose that swaps cleanly. That
  boundary is stated in the product copy, not buried here.

## 7. What this deliberately does not do

- No model routing, no API gateway, no agent loop. Claude Code and Codex remain responsible for
  model access, native permissions and client behaviour.
- No fifty-two targets. Six runtimes at equal depth is the ceiling this repository is aiming for, and
  only after the measurement loop is closed. Users of every project in this field ask for new
  runtimes more than anything else; that demand is real, and it is rulesync's to serve.
- No always-on daemon, no hosted service, no team surface. Everything is local files.
- No claim that a rule produced the same behaviour on two runtimes. Nobody in the field has shown
  that, this repository included.

## 8. Honest gaps

The section that decides whether the rest is credible.

- **Detector validity is unmeasured.** No labelled corpus, so a hit rate may be measuring the
  detector rather than the behaviour. A labelled corpus with per-detector precision and recall is
  0.13 work (#455). Until it lands, read every figure from `usage --rules` with that caveat.
- **Per-variant hit rates are observational.** No fixed task set is replayed under variant A and
  variant B; "this rule works better under `execute`" is not yet a supported sentence. The one
  project that ran an A/B in this field shows both how much it helps a position and how quickly a
  thin method gets discounted.
- **Rules that opt out of a detector are dark.** Tone, altitude and honesty rules carry an
  `OPT_OUT` reason and no measurement. The LLM-judge machinery that Langfuse, Opik and Phoenix ship
  is exactly what those rules need, and it is not here.
- **The conflict engine is empty.** `constraints.json` supports `when`/`requires`/`excludes` and
  ships zero constraints, while the repository holds a contradiction it would catch: always-loaded
  `delegation/tiered.md` says "Never `frontier`" and two roles declare `tier: frontier`. #464.
- **No plugin manifest, no packaged install, no importer** as of the read date; 8 to 12 commands to
  first value. #446, #447, #448.
- **The 200-line always-loaded cap cites no source.** It will be sourced or restated in tokens
  against the repository's own measured standing context (#450).
- **Two runtimes.** "Across AI agents" is not an honest headline yet, and it is not the headline.
- **Two things the instrument caught about this repository itself**, recorded as the worked example
  rather than hidden: #429, a shipped delegation stance measured as never firing in nineteen headless
  runs; #324, a shipped hook measured as not moving the metric it was built to move. No other project
  in the field can produce a finding of that shape about itself, and both were filed as bugs.

## 9. Corrections welcome

This page is versioned and dated. If a project named here ships something that changes a line, or
if a claim does not match what you find in the file it cites, open an
[Idea issue](https://github.com/JakeSelby/agent-harness/issues/new/choose) with the path. The
research run that produced this page carries a staleness map; its earliest re-check is
2026-12-01, and a refresh replaces this page rather than amending it.
