# Field scan: what the configuration-compiler field does, and where this harness sits

**Read on 2026-09-21, amended on 2026-09-23 (§4 and §6). Re-check by 2026-12-01.** One person's reading of a fast-moving field on one
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
- **claude-md-doctor** ([agent-clinic/claude-md-doctor](https://github.com/agent-clinic/claude-md-doctor),
  read 2026-09-23) measures what this repository measures, from the same Claude Code transcripts. At
  each checkup the model decomposes CLAUDE.md into per-rule regex matchers, a standard-library script
  replays them over the session history, and the model sample-verifies every fire before it counts.
  The report gives each rule its opportunities, a compliance figure and a verdict, then sorts
  violations by cause and proposes a hook for the rules worth enforcing. Rule to "did it fire" is the
  same direction as this repository, and for one person's own CLAUDE.md it answers today what
  `harness usage --rules` answers only for rules that carry a detector.
- **RuleReceipt** ([rulereceipt/rulereceipt](https://github.com/rulereceipt/rulereceipt), read
  2026-09-23) checks whether a Claude Code session followed its CLAUDE.md or AGENTS.md, with
  deterministic checks over git commands and file operations and a quoted line of evidence for each
  result. Rules that need judgment report UNCLEAR unless the user opts into a model grader with
  their own key. It also writes a receipt file for CI and ships a pre-tool guard. It is
  source-available rather than open source.
- **superpowers** — sixteen per-runtime install sections and no breadth claim in its hero line at
  all, which is the opposite of the field's usual stretch.

## 5. What this repository took from the field

- The **bounded uniqueness claim** in §6 exists because the eval and telemetry landscape was
  checked rather than asserted; the unbounded "nobody measures" was false, and Burnd is why. The
  2026-09-23 amendment narrowed it again, because claude-md-doctor and RuleReceipt now bind a check
  to each rule and report whether it was followed.
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
  variant was selected. Binding a check to each rule and reporting whether it was followed is no
  longer unique: claude-md-doctor and RuleReceipt both do it on Claude Code transcripts (§4). What I
  did not find elsewhere, as of 2026-09-23, is the rest: a lint that refuses an unmeasured rule,
  detectors committed as data and scored against a labelled corpus with a precision floor in CI,
  per-rule rates grouped by preference variant, and the same measurement over Codex as well as
  Claude Code. It also exports the same ledger over OTLP to the observability stack you already run —
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

- **Detector validity is measured for nineteen detectors of nineteen.** The vendored
  `ruleprobe` wheel ships a labelled corpus and a `validity.py` scorer for the generic detectors
  the engine itself ships; `tests/fixtures/detector-corpus/` labels the rest, five positives and
  five near-misses each bar `research/search-over-cap`, whose positive costs a whole
  two-hundred-search transcript. CI runs `scripts/detector_corpus.py --floor 0.9` over both corpora in the
  `corpus` job, so a precision or recall under 0.9 is a red check. Two detectors sit under the
  floor and are recorded as such with the score and the floor they were measured against, rather
  than the floor being lowered: `secrets/git-add-secret-file` reads any basename holding `id_rsa`
  as a credential, and `autonomy/denied-by-grade` reads the grade hook's signature anywhere in a
  Bash result, so a runbook named after a key and a grep that prints the signature are both hits
  (p=0.83, r=1.00 each). A corpus is synthetic and hand-authored, so it measures the detector
  against what its author says it should find, not against the field.
- **Per-variant hit rates are observational.** No fixed task set is replayed under variant A and
  variant B; "this rule works better under `execute`" is not yet a supported sentence. The one
  project that ran an A/B in this field shows both how much it helps a position and how quickly a
  thin method gets discounted.
- **Rules that opt out of a detector are dark.** Tone, altitude and honesty rules carry an
  `OPT_OUT` reason and no measurement. The LLM-judge machinery that Langfuse, Opik and Phoenix ship
  is exactly what those rules need, and it is not here.
- **The conflict engine ships four constraints and has never used `requires`.**
  `constraints.json` supports `when`/`requires`/`excludes`, `harness lint` fails and `harness sync`
  refuses on a selection that violates one, and the four shipped constraints include the
  contradiction that motivated it: always-loaded `delegation/tiered.md` says "Never `frontier`", so
  a role declaring `tier: frontier` is excluded unless the delegation-tiering skill exempts it
  (#464). What is still untested in anger is the rest of the schema, and the constraints are over
  stance and role declarations only, never over rule prose.
- **No plugin manifest, no packaged install, no importer** as of the read date; 8 to 12 commands to
  first value. #446, #447, #448.
- **The always-loaded cap is a token cap now, and it cites its source.** `bin/harness` quotes
  Claude Code's memory documentation for what the 200-line figure does and does not bind, and sets
  the binding cap to a third of the 12,607-token standing context that issue #430 measured against a
  bare profile; the 200-line cap stays as the secondary readability guard (#450). The residual gap
  is the estimate itself: characters over four, not a tokenizer, good for a cap and a trend and
  never for billing.
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
