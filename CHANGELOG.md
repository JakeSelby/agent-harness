# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- A `jev` decision provider answers the `decide`/`record`/`learn` contract over the network, in
  the standard library alone, because the vendor SDK needs Python 3.10 and five packages where
  this repository's floor is 3.9. It validates a question pack of `choice`, `boolean` and `score`
  answers before anything is sent, refusing a `choice` question that offers no explicit `unknown`
  option: the service cannot abstain, so a pack without one leaves a model that cannot answer no
  way to say so but to guess. A request is bounded at 64k tokens, and its state plus the longest
  question at 32k; a response that is malformed, incomplete or carries a field nobody asked for is
  an error and never a judgment with the bad parts dropped; a budget of requests and tokens is
  checked before each call and charged after it. A judgment may turn an `allow` into an `ask` and
  may never widen a decision, and every path with no usable answer — no key, a timeout, an
  exhausted budget, an unparseable body, an unexpected exception — returns the deterministic
  provider's decision unchanged with the reason in `rule_matches`. Each call records the status,
  the requested and returned model ids, the pack hash, the request hash, the usage and the latency
  to the decision ledger, and never the state. Answers are not deterministic across identical
  requests, so nothing here promises otherwise. The endpoint must be `https` and the opener holds
  no handler for any other scheme, because a bearer key goes out with every request; a request is
  charged to its budget as it is sent rather than when it succeeds, so a refusing endpoint cannot
  be retried without limit; and `harness decide` suppresses the ledger row, because a reporting
  command changes nothing. The client is inert unless a caller constructs it with `live=True`; the
  opt-in configuration, per-decision-point modes and the sentinel file are #137. The endpoint, the
  default model id, the token ceilings, the response shape and the HTTP status mapping are taken
  from the vendor's documentation and have not been verified against the live service from this
  repository, which is what the one opt-in live request in the acceptance criteria is for (#136).
- `telemetry.completion_claim`, off by default, records the agent's completion claim on a
  `stop-gate` decision row: the last 2 KiB of the turn's final assistant message, read from the
  transcript at Stop because the Stop payload carries no assistant text, with the hash over the
  uncapped message. Verifying what an agent said it had done against the gate result needs the
  two on one row, and until now the row held only the gate. It is its own switch, and off,
  because it is the only field in the decision log that holds assistant prose; with it off the
  row is byte for byte what it was. The claim is the turn's own: the scan stops at the user
  prompt that opened it, so a turn that ended in a tool call claims nothing rather than
  repeating the previous turn's words. The read is a bounded tail, so it costs the same on a
  transcript of any size, and where there is no claim the row carries a null one beside a
  `completion_claim_miss` naming why — a runtime that supplied no path reads differently from
  evidence that is gone (#387).
- Every replay-benchmark row records `cache_miss_ratio` beside its cache-normalised cost: the
  share of the run's prefix the provider re-wrote rather than served, summed over every turn the
  run opened. The arithmetic is the one `harness usage --by prefix` applies to a ledger row, and
  is imported from that module rather than restated, but the two figures answer different
  questions and a fan-out run will differ: the replay counts a subagent thread's fresh prefix as
  part of what the run cost, where the session figure subtracts it. `benchmarks/history.jsonl`
  and `history.md` carry each arm's mean of it, so a candidate that buys fewer tokens by
  re-writing its prefix more often is visible in the history rather than hidden inside the
  dollars. A run whose CLI output carries no per-turn cache figures, or any one of whose turns
  reports its usage without them, is `null`, never zero, since zero is a run that held its whole
  prefix (#497).
### Changed

- `claude/settings.template.json` no longer carries a hooks block. Dispatch has been
  single-coordinator for some time — a sync registers one command per lifecycle event and
  `runtime_template()` takes that registration from `lib/harness_core/lifecycle.py` — so the
  eleven per-policy entries the file still listed were replaced unread at every sync, and an
  entry added there by hand would have been silently discarded. `docs/how-it-works.md` now
  describes the model: why one process per event rather than one per policy, where precedence is
  decided, and how the coordinator fails closed. Two places that still described registration as
  conditional are corrected with it: `docs/preferences.md` said the `plan-ceremony` stance decides
  whether the plan-card validator is registered, where it decides whether the validator runs, and
  `claude/OWNERSHIP.json` now says in the manifest itself that a hook id's `stance` and `variant`
  name when a policy acts, never whether it is registered. No installed settings file changes,
  because what sync wrote was already the coordinator registration (#521).
### Added

- The compatibility matrix carries a `tier restriction` row saying, per client surface, whether
  the delegation stance's model-tier ceiling is enforced, advisory or absent, and names the file
  behind each state. It is derived from a `tier_restriction` entry in
  `adapters/<runtime>/capabilities.json` rather than written into the rendered docs: the Claude
  Code CLI and VS Code surfaces read `enforced`, because `claude/hooks/tier-agent-spawns.py`
  rewrites a spawn asking for the strongest class by name. Every Codex surface reads `advisory`:
  the coordinator runs there and a Codex `Agent` call still passes the role, marker, evasion and
  brief checks, but the tier rewrite sits behind a `runtime == "claude-code"` gate in
  `lib/harness_core/lifecycle.py`. The plugin-marketplace install reads `advisory` because it
  installs no hooks at all. The generated note states what `enforced` does not cover — the
  session's own model, which the harness never writes; a `delegation` variant other than
  `tiered`; and a class table mapping fewer than two models — and the `delegation-tiering` skill
  now links to the row instead of restating it (#520).
### Changed

- The delegation rule now states that subagents never message a peer, and the builder role says
  what a blocked builder does instead: stop, finish what does not depend on the answer, and return
  the question under **Deviations** for the caller. A delivered message bills as a typed prompt on
  the receiver and again on the sender when the reply lands, and turn count is what the delegation
  arithmetic is sensitive to, while the measured coordination wins in the literature all come from
  mediating writes at write time rather than from agents conversing; `delegation-tiering` carries
  that reasoning with the three papers cited. Session-to-session `SendMessage` between
  human-facing sessions is unchanged (#539).

### Fixed

- An assistant transcript record that carries no message id is deduplicated by its `requestId`
  rather than counted once per line. Every such record used to open a slot of its own, so a
  runtime or version that writes one id-less response several times — as the streaming lines of
  one API call — inflated the session total and its turn count without any bound. A request id
  names one call, so it deduplicates unscoped by file: the same call written into both a session
  file and a subagent file is one response, and a call whose other records do carry a message id
  joins their slot, in whichever order the files are read, instead of being billed twice. A
  record with neither id is unknown rather than a duplicate and is left undeduplicated; session
  and subagent rows carry `idless_records` counting how many such records their totals include,
  the session's own and those of the subagent files folded into them, so a row without the field
  is known to have been deduplicated whole. Rows from transcripts whose records all carry message
  ids are unchanged (#519).
- The Remote Control sessions read checks that its capped page arrived newest-first. The endpoint
  takes no sort parameter, and its page is ordered by `last_event_at` rather than `updated_at`, so
  the order is asserted on arrival and a page that is not descending is refused: under the
  fifty-row cap the rows such a page dropped are unknown rather than merely old, and the session a
  host lost minutes ago is exactly the one another order would hide. `harness remote-control
  status` prints `not checked (page order unknown)` for a refusal, which no longer reads like an
  account with nothing lost, and both it and `doctor` now say `in the newest 50` when the account
  has more sessions than one page (#526).
- The repository's own copy states the figures its code holds. The landing copy said nineteen
  detectors where the registry holds seventeen, six from the vendored engine and eleven written
  for these rules, and a new test derives that count from the rule pack and fails when `README.md`
  or `product.json` drifts from it. `docs/field-scan.md` and `docs/caught-in-the-act.md` no longer
  say the conflict engine is empty (four constraints ship and lint fails on them), that the
  always-loaded cap cites no source (it quotes the memory documentation and the measured standing
  context) or that there is no labelled corpus: the vendored wheel ships one, it scores six of the
  seventeen detectors, and the remaining eleven and the precision floor in CI are #522.
  `benchmarks/static.json` and the `harness lint` context line each name the set they count, which
  differ, and `benchmarks/oracles/hook_ids.py` says its module count is the count at the task's
  pinned `parent_sha` rather than at HEAD. The always-loaded line ratchet is now the line cap
  itself: the binding cap is tokens, the line cap is the secondary guard, and a third budget four
  lines below it only obscured which one binds (#516).

- A model id the price table does not list is unpriced, where an unlisted variant of a listed
  family used to inherit that family's rate. Inheritance under-bills a premium variant by a
  multiple and prints a known-low figure as a known one — `gpt-5.5-pro` is $30/$180 where
  `gpt-5.5` is $5/$30 — which was the one place the ledger broke its own rule that an unknown is
  never zero. Ids now resolve by exact match after normalisation, which additionally drops a
  release suffix (a date stamp, a reseller's `-v1:0`, an `@date`), so every dated and cloud
  reseller spelling still reaches its family entry and no recorded row changes price. To price a
  variant, add it to `policy/prices.json` or override it under `prices` in `config.json`; until
  then it is counted in the `unpriced` footer and carries no `harness.usd` attribute (#517).

## [0.12.0] — 2026-09-22

### Added

- `harness remote-control` supervises each host through Claude Code's ten-minute give-up: `heal`
  keeps the bridge pointer naming the live environment, stops a host with one `SIGTERM` at nine
  minutes unreachable so launchd's relaunch takes the preserving path, and recreates the session
  worktrees a give-up already deleted. `status` lists sessions left active but disconnected on
  this Mac's environments and prints the manual reattach command for each — it never runs one,
  because a `--session-id` host registers the lost environment a second time and the client then
  routes new chats to it. `doctor` reports each host's process, environment, pointer freshness and
  disconnected sessions. Workspace trust is now read for the exact folder, as Claude Code reads
  it, and an untrusted folder fails `install` with the fix instead of looping launchd (#483).

- `harness remote-control install|status|uninstall` keeps one Claude Code Remote Control server
  per `remote_control.folders` entry running under launchd on macOS, so a new session can be
  started from the mobile app with no terminal open. A folder whose workspace trust was never
  accepted is reported and skipped, never trusted on the user's behalf.

- `harness usage --by prefix` reports whether each session held its cached prefix: the cache-miss
  ratio `cache_write / (cache_read + cache_write)` from the ledger rows it already has, with each
  subagent row's counts subtracted from its parent because the runtime folds them in, and the
  slice at which the ratio rose most sharply. A session whose subagent rows are missing, a row with
  no cache fields, and a runtime that never reports cache writes all report `unknown` rather than a
  figure. It measures and does not enforce; Codex exports no per-turn cache figures, which its
  capabilities file now records (#415).

- A `/close-out` workflow ends a finished session in one invocation: it sweeps for work still
  open — dirty checkouts, `harness worktree audit`, this session's pull requests and their
  checks, running background work, parked decisions — delegates the merge to `/land` and the
  progress file to `/handoff`, batches the follow-ups it found for filing on an explicit
  go-ahead, messages the sessions whose work this one changed where the client can reach
  them, and archives only when the invocation asked it to. It never clears or compacts
  first, because archiving ends the session and both only spend context the close-out is
  still using (#426).

- Qualification evidence is written per case as the case finishes, so a round killed part-way costs
  one case rather than the whole round. `scripts/native_acceptance.py` appends each finished case to
  a durable log outside the checkout, `--progress` names that log and `--from-progress` rebuilds a
  record from it without launching a client. The evidence schema already unions cases across several
  records per client and already rejects a linked `failed` or `unverified`, so a partial record stays
  a valid input and neither behaviour changes (#339).

- The landing copy now names the decision log: the `Live usage feed` feature in `product.json` and
  the matching README line say that a decision log on this machine records what a hook decided and
  what settled it, and that only `harness usage` reads it. A new `landing-copy` check enforces the
  rule that produced the gap: a pull request touching `bin/`, `lib/`, `adapters/`, `primitives/` or
  `policy/` must also change `product.json`, or carry a `Landing copy:` line in its body saying why
  no copy change is needed. A docs-only, tests-only or CI-only pull request never fires it (#390).
- `audit --live` reports a parent only GitHub records as `run refresh` rather than `run apply`, so a
  sub-issue added after its mapping cannot be detached by the next projection; `refresh` adopts it (#388).

- The `issue-ownership` check now refuses a pull request whose delivery issue has no BMad ID in the
  issue map, and `scripts/bmad_issue_sync.py new` files an issue and reserves its ID in one step (#378).

- `scripts/bmad_issue_sync.py audit --live` compares the committed issue map with GitHub, read-only:
  title and open/closed drift, a missing Planning block, and an accepted issue that has no BMad ID.
  `refresh` copies GitHub's title and state back into the map, and a `bmad traceability` workflow
  runs the audit daily and on issue events (#218).

- Release upkeep is written down and checked. `AGENTS.md` and `docs/releasing.md` now say when a
  release is proposed (cut by milestone, or when a user-visible unreleased change is seven days
  old, with a regression fix released at once as a patch), how it is numbered by what changed
  rather than by changelog section, and the exact `gh api` commands that close the released
  milestone and open the next. The seven release surfaces now mark the reference site and the
  personal-site card as verify only, because each repository deploys itself. A new
  `scripts/sync_about.py` compares the GitHub About panel with `product.json`: `--check` names
  every differing field and exits non-zero, `--apply` writes them through `gh repo edit`, and
  topics compare as a set. `--apply` stays a local step needing the owner's approval, because
  editing repository settings needs administration access and no such scope exists for a
  workflow's `GITHUB_TOKEN`. `scripts/release_preflight.py` runs that comparison and looks up
  every `on_the_way` entry that names an issue, blocking the release with "promote or remove"
  when one has closed. Both checks sit behind one `gh auth status` probe: without an
  authenticated `gh`, which is the case in the tag workflow, they are skipped with a named
  warning rather than silently, and a `gh` failure after a good probe blocks the release.

- A local, append-only decision log, `~/.local/state/agent-harness/decisions.jsonl`, beside the
  usage ledger: one record each time a hook makes a judgment, and a second record when the
  session settles it. `grade-bash` records the permission answer it gave a command and joins
  `ran` when the command's PostToolUse arrives, or `not_run` when the session ends without one —
  not "denied", because a refusal, an interrupt and a crash look the same from a hook. `stop-gate`
  records `blocked`, `released` or `skipped` with the gate's own result; `tier-agent-spawns`
  records the band an unnamed spawn was routed to, `brief-guard` what it wrote into the brief,
  and `evasion_deny` a refused re-spawn. A row holds the text the hook judged, capped at 2 KiB,
  with the hash taken over the uncapped text; it holds no tool output and no assistant prose.
  Nothing is exported, nothing is model-visible, and a write that fails is counted and swallowed
  rather than allowed to change a decision. `telemetry.decisions: false` turns it off entirely.
  Read it with `harness usage --by decision`, which prints counts, the outcomes seen per point
  and the unlabelled share. Band routing happens on Claude Code alone, so Codex writes no
  `tier-agent-spawns` row and its capabilities file names the gap.

- Subagent rows in the usage ledger now carry `budget_output_tokens` and `budget_tool_calls`,
  the soft budget the role they ran as carries, so an overrun is a subtraction on one row rather
  than a join against whatever the cost table says today. A role nothing prices records `null`,
  because a zero would say the spawn was budgeted nothing.

- Plan mode now investigates at the permission posture you selected instead of below it. Under
  `bypass` or `auto` in Claude Code, the PreToolUse coordinator approves the commands native plan
  mode prompts on — a script run, a `python3 -c`, a scratch redirect, a test run, anything graded
  0 or 1 — and asks about grade 2, because a push or a mutating API call is execution rather than
  planning. Grade 3, the confirm marker, `manual`, `inherit` and Codex are all unchanged, and a
  stricter autonomy stance still wins. A new config key, `plan_allow_tools`, lists tool-name globs
  (such as `mcp__notes__read_*`) approved in plan mode under the same posture gate; it is empty
  by default, because a hook payload carries no read-only hint for an MCP tool and nothing is
  inferred.

- `product.json` now holds the landing copy as validated data: a `hero` of title, subtitle and proof
  line, six `capabilities` groups of a pitch and three to six features each with a repository
  relative `doc` path, and an `on_the_way` list of at most five items, each naming an issue, a
  client the compatibility catalog calls `planned`, or a document. The hero title is the existing
  `headline`, which `github_description` already leads with, so the page, the README and the GitHub
  About description share one source. `tests/test_release.py` fails when a `doc` path is missing, a group
  or feature count leaves its range, a feature line runs past 170 characters, any string carries an
  em dash, or the README and the data disagree.

- Every usage row names the `harness_version` that wrote it, read from the same `VERSION` file
  `harness --version` prints, so a change in spend can be read against a release. A rescanned
  row carries `null` rather than today's version, and a role-run worker's row carries the
  version stamped into its `status.json` when the run started.

- A session row records the `effort` that covered the most output tokens and an `effort_source`
  naming where it was read: `transcript` for Claude Code, which writes `effort` on every
  assistant record, and `turn_context` for Codex. Effort changes mid-session — 14 of 112 Claude
  Code transcripts and 4 of 44 Codex rollouts on one machine — so the row weighs it by output
  rather than taking the first value seen, and records `null` when the transcript names none.

- A session row carries per-day slices in `days`: four token figures and a turn count per UTC
  date, cut from the same deduplicated map the row's totals are summed over and dropped whole
  if they do not add up to it. `harness usage --by day` sums the slices when a row has them and
  falls back to its end date when it does not, and `--days` then windows on the slice date, so
  a session that ran for a fortnight contributes only its in-window days instead of landing on
  the day it ended. Five such sessions were 68% of all output tokens on the machine measured.

- `harness usage --by stance --stance <dimension>` groups tokens by that dimension's variant.
  Rows with no recorded stance, and rows a rescan stamped, are counted under `(unknown)` rather
  than dropped. `--rules --by stance` keeps the hit report unchanged, and `--by stance` with
  neither is refused with a usage error rather than guessed at.

- `harness usage` reports dollars. `policy/prices.json` lists USD per million tokens for input,
  output, cache read and cache write per model id, each entry carrying the `as_of` date it was
  read and the provider pricing page it was read from; a model whose price could not be
  confirmed from a primary source is absent rather than guessed. Ids resolve by longest prefix
  after normalisation, so a dated, Bedrock-style or `[1m]` id reaches its family. Every token
  grouping gains a `usd` column and an `unpriced` footer, `--by role` gains p50 and p75 dollars,
  and a row with an unknown model, two models or partial tokens is unpriced rather than $0. A
  `prices` block in `config.json` merges over the file per model id. Checked against a recorded
  Claude Code session whose runtime reported `total_cost_usd = 0.60097775`: the table reproduces
  it exactly.

- A session row records a per-model token breakdown in `by_model`, checked against its own
  totals before it is written and dropped whole if it disagrees: cut from the deduplicated
  message map for Claude Code, and from the snapshot deltas under each `turn_context.model` for
  Codex. A row that carries one is priced model by model, which is the only way the sessions
  that switched model — the largest ones — can be priced at all. On a 60-day rescan, unpriced
  runs went from 26 of 143 to 0, and the share of output tokens that was unpriced from 73.7% to
  0%.

- A usage row records the cache-write tier split Claude Code reports — `cache_write_5m` and
  `cache_write_1h` beside the `cache_write` total — because Anthropic prices a 5-minute write at
  1.25x base input and a 1-hour write at 2x. The keys are additive, so an existing row stays
  readable and is charged whole at the 5-minute rate.

- `harness doctor` names the newest `as_of` in the price table and warns when it is over 90 days
  old, since prices go stale silently while the report keeps printing dollars.

- Ledger rows can be exported to any OTLP/HTTP endpoint, off by default. A `telemetry` block in
  `config.json` turns it on; with it off no network code runs and the hook behaves as before.
  Each row becomes one OTLP/JSON log record on `POST <endpoint>/v1/logs`, sent from the detached
  `SessionEnd` worker after the row is already in the ledger: one attempt, a two-second timeout,
  no retry, and a failure recorded in `usage.errors.jsonl` rather than in the session's exit
  status. The body is the row; the attributes are its flat scalars plus a stable
  `harness.row_key`, the harness version and one `harness.<dimension>` per recorded stance.

- Request headers are read from a named environment variable or a file outside every git work
  tree that no other user can read; a header value written into `config.json` is refused by
  name, and no value is ever printed, logged or written to an error record — a failure names
  the endpoint's scheme and host only.

- `harness usage export --since <date> [--until] [--dry-run]` replays a window of rows in
  batches, prints what was sent and what failed, and exits non-zero if any batch failed.
  Delivery is at-least-once, so [docs/telemetry.md](docs/telemetry.md) gives the
  de-duplication query on `harness.row_key` and states the model: the ledger is the record, a
  backend is a rebuildable copy, and replay is the recovery path when a backend's retention
  expires or it is rebuilt.

- `harness doctor` names the export mode, the endpoint's scheme and host, and the names — never
  the values — of the headers it resolved.

- A `/land` workflow picks up where `/build` stops. It verifies the required checks — and the
  issue-ownership check where a repository runs one — on the head that will actually merge,
  squash-merges with the remote branch deleted, fast-forwards the shared checkout, removes the
  managed worktree, deletes the local branch with `git branch -d`, audits for stale checkouts,
  then reads the repository's own release rule and either says no release is due or posts a
  release card for approval. It never forces a removal, never uses `git branch -D`, and stops on
  dirty or unmerged state with the reason; merging stays approval-gated and it never tags or
  deploys. Projections for both runtimes are generated from the shared source as usual.

- `"native": true` in the `telemetry` block makes `harness sync` turn on each runtime's **own**
  OpenTelemetry export to the same endpoint, off by default. Claude Code gets the telemetry
  switch, both OTLP exporters, `http/protobuf`, the endpoint and an `OTEL_RESOURCE_ATTRIBUTES`
  carrying `harness.version` and one `harness.<dimension>` per resolved stance, plus an
  `otelHeadersHelper` pointing at a harness-owned script that reads the configured header source
  at run time — so no header value is written into a settings file. Codex gets `[otel]` with
  both `exporter` and an explicit `metrics_exporter`, because its default metrics sink drops
  token, cost, tool and API metrics client-side; it is given no header, since `[otel]` takes a
  literal header map, and [docs/telemetry.md](docs/telemetry.md) states that gap rather than
  papering over it.

- Ownership is per variable: a variable you set in `env` is never read, changed or removed, a
  managed key already holding a value the harness did not write is reported and left alone, and
  turning the key off restores what each key held before. Labels are frozen at sync time, so a
  stance switched without a re-sync mislabels native data until the next one — the ledger row
  stays authoritative. `harness doctor` reports the state, the endpoint's host, whether the
  labels are current, and that both runtimes attach their own user and organization identifiers.

- [docs/telemetry.md](docs/telemetry.md) ends with a reference recipe for one backend that was
  set up and measured end to end — the ClickStack all-in-one image — as a worked example of "any
  OTLP/HTTP endpoint" rather than a requirement: the run command with its three persistent
  volumes, the two manual steps before a single record is accepted (create the first user, then
  send the ingestion key as a bare `authorization` header), the 30-day TTL every table ships
  with and the `ALTER TABLE … MODIFY TTL` that raises it, and why Codex cannot reach a backend
  that needs a header. It contains no command that creates an account, stores a password or
  removes a container or a volume, and it names the licence of every part of the image.

- A dashboard definition ships beside it as
  [docs/telemetry/clickstack-dashboard-native-cost.json](docs/telemetry/clickstack-dashboard-native-cost.json):
  ten tiles of this repository's own SQL over the standard OpenTelemetry tables, reading the
  native Claude Code cost and token metrics down to agent, model, effort and stance variant. The
  instance-specific connection id is a placeholder, with the one-line lookup beside it.

- `scripts/cost_bench.py replay` runs a pinned task set headlessly against two profiles — a
  signed-in, otherwise empty Claude Code profile and the installed harness — on one shared command
  line and a scrubbed environment, and scores each run with a check the agent never sees.
  `benchmarks/tasks.json` pins the tasks, `benchmarks/oracles/` holds the held-back checks, and
  `--verify-tasks` proves every check and refuses a fixture whose own gate is red or whose solving
  commit is still reachable. It calls a model and spends real usage, so it is run by hand on a
  release candidate and never in CI, and no result is published with this release: the runner
  ships, the number does not. Reading and limits: `docs/benchmarks.md`.

- `scripts/cost_bench.py static` measures what the harness adds to every Claude Code session against
  a bare one: files, lines, characters, an estimated token count and its price per model from
  `policy/prices.json`. `benchmarks/static.json` holds the figure for the last release and CI fails
  when the estimate grows more than 5% over it without an entry in `benchmarks/allow.json`. No model
  is called. Reading and limits: `docs/benchmarks.md`.

- An exported ledger row carries `harness.usd` and `harness.price_as_of`, so a dashboard reads
  dollars instead of re-implementing the price table in its own query language. The figure is a
  list-price API equivalent fixed at export time, computed by the code `harness usage` prices
  with: the rates, the id normalisation and the session/subagent join moved to
  `policy/hooks/pricing.py`, which the CLI and the standalone export hook each load rather than
  either one holding a second copy. A session row's figure already includes its subagents,
  exactly as the report totals them. An unpriced row carries neither attribute — never a zero —
  and a missing price file or a malformed `prices` override costs an export its dollars and
  nothing else.

- Qualification freezes on a release branch instead of on `main`. `compatibility/freeze.json` names
  the frozen commit and branch, and a new `harness freeze` reports drift between that commit and a
  given ref over the runtime source paths, exits non-zero on drift, and refuses a merge that would
  change those paths on the frozen branch. `docs/releasing.md` gains the freeze procedure and the
  triage rule that a round runs to completion and collects defects rather than fixing one mid-round,
  because any source-path change invalidates every evidence record for the round (#332).

- Two deterministic pre-qualification checks that spend no model turns. A documentation-link check
  resolves every relative path and heading anchor across the repository's Markdown, and a credential
  probe names the variable a client would authenticate with or fails immediately with the reason,
  instead of the 300-second hang a session-credentials-only home used to produce. Both are additive
  and neither writes to `compatibility/evidence/` or appears in a catalog record, because a green
  deterministic check is not native qualification (#401).

### Changed

- The credential probe's docstring records why its green line is a fixed string that never
  names the variable it found: a clean CodeQL scan with no dismissals was judged worth more than
  the name on stdout, and a caller that needs it calls `reachable` directly (#409).

- `telemetry.native` takes `true`, `false` or a list of runtime names, so a collector that
  authenticates can be fed natively from Claude Code while Codex, which takes header values only
  as literals in its configuration file, is left alone. `true` keeps its meaning, an unknown name
  stops `sync`, and `docs/telemetry.md` says which runtime can reach an authenticated endpoint (#405).

- The README's install command clones the `stable` branch, so a new install starts from the latest
  release instead of the development trunk.

- The README's first screen is the headline, a terminal capture of `harness sync --dry-run` on a
  fresh home, the description and the six capability groups, one linked line per feature, plus the
  "On the way" list. Release status and the generated compatibility block now follow the install
  section, so a first-time reader meets what the harness does before which clients are qualified.

- `harness usage --by role` marks a role with fewer than 30 runs `n<30` in a new `sample`
  column. A p90 over eight runs is the second-largest of eight, and the budget re-seeding
  procedure in `docs/usage.md` now says not to re-seed from a marked row.

- The fan-out warning in [docs/usage.md](docs/usage.md) now carries what was measured against
  it. Across 137 sessions on one machine the cache hit rate was 97.0%, 97.2%, 97.3% and 97.1%
  at 0, 1–6, 7–50 and 51-or-more subagents, so the falling hit rate it describes is a thing to
  check in your own data rather than an expectation.

### Fixed

- The test suite no longer writes the harness into a real profile. `claude_dir()` honours
  `CLAUDE_CONFIG_DIR`, so a suite run in a shell that had it set installed links and rendered
  files into whatever profile it named instead of the run's own temporary home. Every test now
  clears it through one shared isolation helper, and the sandbox fence that hid the leak is no
  longer what keeps a caller's profile intact.

- The usage feed says `spend unknown` once and names the agent it could not read, feeds a
  cumulative line for every round of an agent resumed with a follow-up message rather than only
  its first, and states once per session what its token figure measures so it cannot be read as
  the task notification's `subagent_tokens` (#306).
- `harness sync` installs the Claude Code output style from the `voice` stance instead of
  unconditionally: `scannable` installs `Scannable`, `answer-card` and `off` install none, a style
  you chose yourself survives, and a harness-installed style is removed when the variant changes.
  Ownership comes from the reconciliation journal rather than the style's name, so a style you
  picked before installing is left alone even when the harness ships one by that name. The Codex
  projection is unchanged; `scannable` was already the only variant it gave presentation material
  to, so the two runtimes now mean the same thing by each variant (#394).
- `harness usage` no longer prints the partial-totals warning above a USD report whose own
  footer already counts those runs as unpriced; a report with no unpriced run still warns that
  a column is short (#407).
- `.agent-harness/evidence/`, `task.json` and `sync.lock` are ignored repository-wide, so captured
  replay transcripts can never be staged or reach the lint, and the stop gate no longer goes red in
  a checkout whose own change is clean; a test pins the rules (#432).

- Three defects in the native acceptance runner, recorded during 0.11.0 qualification and none of
  them in the harness runtime. `orchestrator_text()` now reads a session's transcript whether or not
  a subagent directory was written, so a session that spawned none no longer returns an empty string
  and lets a `cost-posture` assertion pass vacuously. The runner's cited qualification runbook is
  written rather than a dead link. The three AWS session variables — the key id, the secret key and
  the session token — now reach the client, so a container holding only session credentials can
  authenticate. The bypass classification a `permission-controls` driver needs — telling a model's
  own refusal apart from a policy block by reading the recorded denials and the permission mode —
  is added and tested, but no such driver exists in the runner, so nothing calls it yet (#309).
- `harness worktree remove` finishes the cleanup after a squash merge. The quality gate has to run
  before a push and writes `__pycache__`, which used to leave the worktree unremovable and reported
  as dirty by `harness worktree audit`; removal no longer counts the regenerable caches it knows
  (`__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `node_modules`, `.astro`, plus a
  top-level directory named with `--also-clear NAME`) as work, git deletes them with the checkout,
  and audit reports a checkout holding only those as clean. Modified,
  untracked and other ignored entries still refuse, naming the first few. With `--merged` the
  local branch is deleted too, but only once `gh` reports a merged pull request whose head commit
  is the branch tip: after a squash the branch's commits never reach the default branch, so
  ancestry cannot answer and `git branch -d` refuses work that did land. A missing or failing
  `gh`, no merged pull request from this repository, a tip the merged head does not match, or the
  default branch refuses with the reason and deletes nothing. `/land` now hands both steps to one command.

- The documented de-duplication query runs as written. Every exported record now carries
  `harness.exported_at`, the export time as a fixed-width RFC 3339 UTC string, and the example in
  `docs/telemetry.md` orders on it instead of `ObservedTimestamp` — a column the OpenTelemetry
  ClickHouse exporter's `otel_logs` table does not have, since the observed time is dropped on
  ingest and `Timestamp` is the row's own end time, identical across replays. Attributes land in
  that table as a `Map(String, String)`, so the stamp is fixed width for lexical order to equal
  time order, and the example casts `harness.usd` with `toFloat64OrNull` before summing it. A
  test checks the example names no column outside the real schema.

- Each stance reaches a backend once, as `harness.<dimension>`. The exported body no longer
  carries the `stances` map, which a backend that parses a JSON body flattened into a second
  dotted copy of every stance beside the attributes; every other field still travels in the body.

- A client launched under a substituted `HOME` no longer raises the macOS "A keychain cannot be
  found" dialog. The acceptance runner already gave its disposable homes a keychain, but two other
  launches did not: every role worker runs its client in a private home that had none, and
  `harness doctor` ran `claude doctor` in whatever `HOME` it was given, including a throwaway one
  an agent built to test a config. A role worker's home now carries its own throwaway keychain, and
  a worker whose keychain cannot be created fails instead of launching; `harness doctor` skips the
  client's doctor, and says so, when `HOME` has no default keychain. `harness keychain <home>` is the
  same guard for a home you build by hand. Other hosts are unchanged.

- The `gatherer` role no longer declares web tools its only execution path cannot give it. The
  role listed `WebFetch` and `WebSearch`, the spawn guard refuses a native `gatherer` in favour of
  `harness role run gatherer`, and that isolated worker is launched with `Read`, `Grep` and `Glob`
  under a read-only sandbox with hosted search disabled — so a web dimension of `/research` had
  nowhere to run. The confinement stays: a worker that can both read a workspace and fetch can
  carry what it read back out, and a fetched page is untrusted input inside a confined process.
  Instead the declaration now matches the launch, the role says it is offline and that online
  evidence arrives as files granted with `--read-dir`, the refusal that points at `harness role
  run` adds where a web dimension goes instead, and `/research` routes by where the evidence
  lives — files and repositories to the isolated worker, the live web to an in-session band
  worker. A test asserts the command line a `gatherer` worker is actually launched with.

- `transcript-hygiene/brief-without-cap` is now `transcript-hygiene/model-wrote-no-cap`, because
  that is what it always measured. A transcript records an `Agent` call as the model wrote it,
  and a `PreToolUse` hook's `updatedInput` is written to a separate `attachment` line the scan
  never reads — so `brief-guard` capping a brief could not move the number, and the rate was
  unchanged before, during and after the hook shipped. The detector's behaviour is unchanged and
  the rename makes `promote?` on it mean something: the orchestrator writes no bounds and the hook
  is carrying the rule. `rule-detectors.RENAMED` names the successor and `usage --rules` folds it
  as it reads — by rule, by repo and by stance — so a row written under the old id reports under
  the new one, with no rewrite of the ledger file and no split in the series.

- A Codex subagent thread is recorded as a `kind: "subagent"` row joined to the thread that
  spawned it, with its depth, nickname, model, effort and tool-call count, instead of as a
  session of its own. On the machine this was measured on, 307 of 438 rollouts were subagent
  threads and every one of them was a session row. A thread that inherited its parent's history
  writes the parent's `session_meta` further down its own file; only the first one is read now,
  which is what 36 of those 307 turned on. `harness usage --rescan` migrates the misclassified
  rows, deleting the stale keys and copying the ledger to `usage.jsonl.bak` first.

- The rescan reads `~/.codex/archived_sessions/` as well as `~/.codex/sessions/`. Codex moves a
  rollout there unchanged, and 96 of the 131 top-level rollouts on that machine lived only in the
  archive, so most Codex sessions never reached the ledger at all. Codex capture is rescan-driven:
  whether the runtime's `SessionEnd` payload names the rollout file is not established, so the
  hook now accepts `rollout_path` and `session_path` beside `transcript_path` and `docs/usage.md`
  says the rescan is the path known to work.

- A Codex session whose snapshot carries `total_tokens` alone — 85 of 107 top-level Codex Desktop
  rollouts — is recorded as `partial` with a `total` and unknown typed fields, rather than summed
  as a session that spent nothing.

- `harness usage` sums Codex subagent rows and still skips Claude Code ones: a Codex thread's
  total counts that thread alone. Four of the 21 measurable parent threads report fewer tokens
  than their own children sum to, which a total including them could not do. `--by model` also
  reads the single `model` a subagent or worker row names instead of grouping it as unknown.

## [0.11.1] — 2026-09-21

### Added

- A `stable` branch that always points at the latest release. The release workflow fast-forwards
  it to the tag's commit after publishing, `scripts/advance_stable.py --check` verifies it, and the
  branch never moves backward. `main` stays the trunk.

### Changed

- The `builder` role's report closes two gaps a downstream soak found. A hand-edited fixture,
  golden file or pinned value must now name the generator or the command that produced it —
  "hand-typed, copied from run X" answers it, silence does not — and where a generator exists the
  builder regenerates instead of hand-editing. The gate's result is read from the test command's
  own exit status, captured with `PIPESTATUS`, `pipestatus` or no pipe, rather than from whatever
  `tail` returned. The fixed report gains one item for the edited fixtures and what produced them.
- Qualify the Claude Code and Codex CLIs on macOS and Linux for this source with version-pinned
  native evidence across all eleven acceptance cases, and record the limitations those runs
  established in the compatibility catalog.

### Fixed

- The Review Card's diagram is a plain-text drawing in a `text` fence. The `plan-authoring` skill,
  its template and example, and the `planner` role defaulted to a mermaid `flowchart`, which the
  plan-mode pane and the chat sidebar show as raw source — so the card's one diagram was unreadable
  where the card is reviewed. New or changed nodes carry a `*`; mermaid stays for the addendum and
  for docs read on GitHub.
- The `delegation: off` stance said a hook asks before any spawn, where the lifecycle denies the
  spawn outright and never reaches that hook. The stance now says a spawn under it is denied and
  that changing the selected stance is the way to delegate, and it no longer names a hook — the
  name it used, `tier-spawns`, was not the file doing the refusing either.
- The spawn guard no longer refuses a constrained role only by the name a spawn chose. Refusing a
  native `reviewer` spawn moved the work rather than stopping it: the client re-issued the same
  brief as an unnamed subagent and it ran unconfined. A refusal is now remembered for the session,
  and a later spawn that names no constrained role but carries the same brief — normalised, or a
  near-identical rewording — is refused with the same `harness role run` instruction and told that
  dropping the role name changed nothing. Independently, a brief whose own first line reads
  `harness-role: <role>` may only run as that role's isolated worker, whatever `subagent_type` the
  spawn names or omits. The BMad review layers now carry that line. Session state that cannot be
  read or written leaves the guard exactly as it was, and `delegation: off` is untouched.

## [0.11.0] — 2026-09-21

### Added

- Add the `designer` role: one pass of visual design work toward a locked target, validated and
  captured, never self-scored. It declares the `frontier` class, which is the only way a spawn
  reaches the strongest model now that the hook refuses it by request. The design loop hands it
  the build and fix steps; `design-judge` still scores from a fresh context.
- A usage feed tells the orchestrator what it is spending while the session runs: a turn line on
  `UserPromptSubmit`, a line for each subagent as it returns, a line at the next prompt for every
  background spawn that finished meanwhile, and a note when more agents are running than the
  variant's `max_parallel`. A subagent's figure is summed from its own transcript, because a tool
  response reports only that agent's last response. The behaviour is `turn_feed`, `nudge_at` and
  `max_parallel` in the active `cost` variant; `off` injects nothing and writes nothing. Per-session
  state is an append-only journal plus a `flock`-guarded reader file, because these hooks run
  concurrently and nothing slow runs under that lock; a figure that could not be summed inside
  the hook's budget is reported as `(partial)` or `spend unknown`, never as zero. Stale files are
  swept after a fortnight and `harness uninstall` removes them.
  Codex raises none of the three events and declares the feed uncovered.
- `harness tiers check` compares the Codex class table with the model catalog Codex fetches from
  its provider, offline, and fails on a mapped model that is gone, superseded or ranked out of
  order. A missing catalog reports *unverified*, not a pass.
- `tiers.<runtime>.<class>` in the configuration remaps a capability class for every role that
  names it, without a harness release.
- The usage log records one row per subagent and one per `harness role run` worker beside the
  session row, each naming its `kind`, agent type, model, effort, token counts, tool calls and
  spawn depth. Rows are upserted by `(session_id, runtime, kind, agent_id)` and hold counts
  only: no prompt text and no command text.
- Each `cost` variant carries a JSON sidecar beside its `.md` holding its switches and its
  model class, effort and soft budgets per role and per band. A variant resolves over its
  `extends` chain, a variant with no sidecar resolves to `balanced`'s, and an unknown key is a
  warning rather than an error so a later release cannot break a variant you wrote.
- `posture: fixed` in a role's frontmatter, set on `reviewer`, `spec-reviewer`, `design-judge`
  and `log-compressor`: a cost variant may budget the role but never change its class or effort.
- `harness stances --json` carries the resolved cost table — switches, rows with base and scaled
  budgets, default band, the `extends` chain with each sidecar's path, and warnings. Lint
  validates shipped sidecars against the schema and against their own prose.
- Three band worker roles, `worker-a`, `worker-b` and `worker-c`, carrying the A/B/C bands'
  class and effort into a native spawn. Their descriptions hold the band rule, so an
  orchestrator chooses a band by spawning one of them by name. They name no tool list, so a
  rerouted spawn keeps every tool it had as `general-purpose`, MCP tools included; an adapter
  role entry may now carry `disallowed_tools` instead, which is how they give back the one
  tool a role with `delegation: none` must not hold.
- `harness usage --by role` reports, per agent type, the number of runs and the p50, p75 and p90
  of output tokens and of tool calls over the window — the distribution a per-role budget has to
  be set against. A run whose runtime reported no counts is named, never averaged in as a zero.
- Every brief states the spend the cost variant expects of it: the row's output tokens and tool
  calls in one sentence, soft — finish if close, otherwise return what you have — because a
  subagent cannot see the variant that priced it. A spawn that named a role is priced by that
  role and one that named none by the band worker it is about to be routed to, computed by the
  same function that routes it — and only on a runtime that reroutes, so a spawn Codex will run
  as written is priced by its role or by nothing. A brief that already prices itself, an
  unbudgeted role and a table that will not build are all left exactly as before.

### Changed

- Claude Code's native agent definitions follow the resolved cost variant. A role the selected
  posture does not move keeps its symlink to the committed projection, so a default install is
  exactly what earlier releases wrote; a role it does move is rendered and written as a managed
  file, which is how a variant's class and effort finally reach a native agent. The class its row
  names resolves through the adapter's `tiers` table. Precedence is the role's own tier and the
  adapter's effort, then the variant's row, then `role_bindings.<runtime>.<role>`, which still
  wins; a `posture: fixed` role takes neither cell. Effort and model are therefore sync-scoped: a
  session `HARNESS_STANCE_COST` does not move them until the next sync. Roles move between link
  and file in both directions as the posture changes, and a definition you edited or a link you
  redirected is preserved and reported, never replaced. `sync --dry-run` names each role whose
  rendering has moved, with its class, model and effort.
- Stances resolve in one place for the dispatcher and every policy hook alike: built-in defaults,
  the user configuration, the file `HARNESS_PROJECT_CONFIG` names, then `HARNESS_STANCE_*`. The
  hooks therefore honour `HARNESS_HOME` and a project configuration, which they ignored before,
  so a disposable home or a per-repository selection now reaches the spawn, brief, grading and
  usage hooks rather than only the CLI; both are environment variables the user sets, at the
  same trust level as the `HARNESS_STANCE_*` the hooks already honoured. The grading hook is
  the exception that fails closed: a stance it cannot resolve is graded under the strictest
  variant, named as unresolved in the prompt.
- A spawn that names no agent definition, or names `general-purpose`, is rewritten to the cost
  variant's default band worker and runs on that band's class — the only way the posture's
  effort reaches it, because the `Agent` tool has no effort input. A model the caller named is
  kept, a request for the top class is refused and the band's class applies in its place, and a
  variant with no `default_band`, an unreadable table, a machine whose worker definitions are not
  installed and a session whose agent registry predates them all leave the spawn exactly as the
  previous release did. A repository that ships its own `.claude/agents/worker-<band>.md` is never
  routed to, because a project definition outranks the user's. The cost table is read only for a
  spawn that named nothing, so naming a role costs nothing.
- Subagent usage rows carry `requested_type` and set `rerouted` when the type the parent
  recorded differs from the one the subagent ran as, joined on the tool use id. The reroute is
  measured from the transcript rather than reported by the hook that made it.
- The spawn hook reads its model ladder from the adapter's `bindings.json` `tiers` table instead
  of a list written in the hook; a table it cannot read leaves the spawn as written and says so.
- The spawn hook says so when the session's model is not on its ladder, instead of leaving the
  subagent on the session model without a word.
- Shared roles name a provider-neutral capability class (`tier:` — `frontier`, `strong`, `standard`,
  `light`) and each adapter's `bindings.json` maps classes to native models in a `tiers` table.
  `reviewer` and `planner` run on `strong`, `spec-reviewer` on `standard` and `design-judge` on
  `frontier` instead of inheriting the session model, so their cost no longer follows whatever
  the session happens to run. An unmapped class resolves upward or inherits, never downward.
- Codex roles gain model tiering: its table maps the four classes to `gpt-6-astra`, `gpt-5.6-sol`,
  `gpt-5.6-terra` and `gpt-5.6-luna`. Codex roles previously inherited the session model.
- The spawn hook tiers a planning-framework repository like any other, and refuses the top class
  by request: an unnamed spawn asking for it runs on the band it is routed to, or one class below
  the session where nothing routes it, and a named agent falls back to its definition. The
  `session-model` stance is unchanged and remains the opt-out.
- `harness role run`, the constrained-role refusal message and the BMad override templates no
  longer tell the caller to pass the parent session's model; they name it only where the adapter
  maps none. Role effort above `high` is rejected.
- Native qualification now requires an eleventh case, `cost-posture`, so a client cannot be
  qualified without the cost posture layer having run natively: the roles a variant moves and only
  those, an unnamed spawn routed to the default band worker at its row's model and effort, the
  budget sentence in its brief, the feed and `harness usage` rows against that budget, a session
  that predates the workers left alone, and the priced-nothing variant doing none of it. Evidence
  is scoped to the harness version it records, so 0.9.0 and 0.10.0 records stay valid history.
- Qualify the Claude Code and Codex CLIs on macOS and Linux for this source with version-pinned
  native evidence across all eleven acceptance cases, and record the limitations those runs
  established in the compatibility catalog.

### Fixed

- Nearly every spawn raised a permission-hook notice about a rewrite that is the ordinary case:
  the budget sentence `brief-guard` appends now carries no notice at all, and the line naming the
  band an unnamed spawn is routed to is said once a session. The return-bound notice, the refusal
  of the strongest class by request and the repository-supplied-worker refusal are unchanged,
  because each reports something the caller asked for being changed or refused.
- An unnamed spawn was rerouted to a band worker whenever the definition existed on disk, which
  failed every such spawn in a session that was already running when `harness sync` installed the
  workers: the tool loads its agent registry once, at process start, and rejected the type. The
  SessionStart policy now records what each session's registry held, and a reroute requires the
  worker to be in that record; without one the spawn keeps the previous one-rung behaviour and the
  session is told once to start a new one. Only a session's own start may widen that record: a
  resume narrows it to what is still on disk and creates none, and any failure to answer the
  question at all leaves the spawn unrouted rather than raising into a refusal. Records are
  private to their owner, refreshed while a session is in use, swept after a fortnight, and
  removed by `harness uninstall`.
- A session whose transcript carried both a subagent's sidechain lines and that subagent's own
  file counted every delegated token twice. The session's totals are now taken over one map of
  message ids that both reads fill, so a message recorded in two places is one message. Agents
  nested under `subagents/workflows/wf_<id>/`, which the Workflow tool writes and a flat walk
  missed entirely, are counted too and name their workflow.
- Output tokens were undercounted, by a factor of several on a long response. The log took each
  message id's usage from the first transcript record carrying it, and the early records of one
  streamed response carry a partial `output_tokens` — 7,126 against the response's real 40,868
  on a measured subagent transcript. Each message id now counts at the largest figure it ever
  reported, so a reordered or truncated tail cannot lower it either. `harness usage --rescan`
  corrects the recorded history.
- Every session total was short by whatever its delegation cost. A subagent's tokens live in its
  own transcript, which the log never read, so a session that fanned out reported only the
  orchestrator's own spend. Session totals now include their subagents'; `harness usage --rescan`
  backfills the history, and the token groupings sum session rows alone so nothing is counted
  twice.
- A managed link that reaches its file through an alias of the checkout, such as `claude/stances`
  for `primitives/stances`, is no longer reported as redirected. `harness uninstall` and the
  retirement of a removed link treated the same link as the user's and left it behind; they now
  remove it. A link pointed at a different file is still reported and still preserved.
- A named agent asked onto the top class now gets the model its definition names, or the class
  below when there is none to read. The hook used to remove the request, and the lifecycle
  coordinator only carries rewrites, so the request reached the spawn unchanged.
- The lifecycle coordinator relays a hook's notice on Claude Code instead of dropping it, so a
  tiered spawn and a session model the ladder does not know are both reported.
- A role worker whose runner died now reports as `orphaned` instead of `running` forever. The
  status record kept nothing that could tell a live run from an abandoned one, so a killed session
  left `status: running` with no result and no error, and `harness role status` could not separate
  it from work in flight. A run now records the pid supervising it and that process's start time,
  and status reports a worker whose process is gone with no result written as the terminal
  `orphaned`, writing that state back into `status.json` alone. The start time guards a recycled
  pid; a record from a release that stored no pid, or a platform that will not report a start
  time, still reads as `running`.
- `harness uninstall` now removes the empty directories the sync created for its own files —
  `~/.claude/rules/harness-stances` and each `~/.agents/skills/harness-*` — instead of leaving
  them behind. A directory that still holds anything is kept untouched.
- A stale `harness task save --revision` prints one line on stderr naming the remedy and exits 1,
  where it raised an uncaught `ValueError` and printed a traceback carrying the checkout path.
  The guard itself is unchanged: a save against a revision that is no longer current is refused.
- `harness doctor` reports a client that is `not on PATH` rather than `not installed`, and says so
  explicitly when Codex credentials are present with no `codex` the shell can reach.
- A permitted Codex tool call no longer reports `hook: PreToolUse Failed`. The PreToolUse envelope
  carried `permissionDecision: "allow"` on every non-gated call; a client that lists `allow` as
  unsupported discards the whole hook output, so every allowed call showed a failure and a real one
  was indistinguishable. Codex now hears nothing where its own default already allows, and `allow`
  is sent only with an `updatedInput` rewrite, which that runtime applies under no other decision.
  Denials, the ask-to-deny narrowing and Claude Code's envelope are unchanged.
- An isolated role worker now follows the selected cost variant. `harness role run` bound a role
  from its `tier:` alone, so under `frugal` a `gatherer` worker ran on the role's own class while
  the same sync in the same home rendered that role one class lower — and the constrained roles
  are denied as native spawns, so neither the posture nor the soft budget ever reached the roles
  that carry measured budgets. A worker now resolves its row through the same function and the
  same precedence the sync path renders a definition with — role defaults, the variant's row
  (class only under a tiered `delegation`, never for a `posture: fixed` role), `role_bindings`,
  then `--model` — on both runtimes and through the whole stance ladder, so a session-scoped
  `HARNESS_STANCE_COST` reaches it. Its brief ends with the same `Expected spend` sentence a
  native brief gets, from one function shared with the brief guard, unless the row prices nothing
  or the brief already states a budget; `status.json` records the variant, the resolved class,
  where model and effort each came from, and the figures appended. A variant with no row for the
  role, or a table that will not build, leaves the worker exactly as it was.

- The `auto` permission posture now gives Codex the automatic approval review it promises. Sync
  wrote `approval_reviewer`, and Codex names the field `approvals_reviewer`: codex-cli
  0.154.0-alpha.6.2, 0.155.0-alpha.9, 0.155.1 and 0.156.0-alpha.9 all reject the old spelling
  under `--strict-config` and drop it in silence otherwise, so the posture resolved in the client
  as review by the user with no warning. Sync now asks the installed client which name it accepts
  — from its own emitted protocol schema, or a `--strict-config` probe in a throwaway
  configuration home, neither of which starts a model turn — writes that one, and takes the stale
  spelling back out. Both spellings are harness-owned, so a key the harness wrote is removed or
  restored on re-sync and uninstall while a key of the same name that you set yourself is left
  alone. With no client installed, the name the newest supported version accepts is written; a
  client that accepts neither gets no reviewer key, a sync notice and a `harness doctor` finding.

- The usage feed reports a finished subagent's actual spend instead of `spend unknown`. A
  `SubagentStop` summed the agent's transcript the instant it fired, and at that instant the
  transcript can hold only the `user` and `attachment` records the parent wrote into it — so the
  stop was journalled with null totals and the reporter printed them, while replaying the same
  payload a moment later yielded 297. A stop that carries no figure, or one read out of a
  response still being written, is now summed again on the line that names it: before the lock,
  with the bounded settle wait, inside one wall-clock budget shared by every agent that event
  reports. `spend unknown` now means a transcript that is not there; a transcript that is there
  and holds no response yet says `spend not yet recorded`, and the figure it gains later raises
  the session totals without the agent being named a second time.
- The usage feed's line for a synchronous subagent return no longer stops short of that agent's
  last response. Claude Code writes one API response as several records, and the return could
  fire between a partial streaming count and the record that ends the response — 143 output
  tokens reported live for an agent a later scan put at 278. The return now waits a bounded
  moment (at most a second, over the transcript's tail) for the response to end, says `(so far)`
  when it never does, and raises the session totals from the settled figure the journal brings
  afterwards without naming the agent a second time.
- A usage row names a subagent's model one way. A routed spawn's row carried the alias the spawn
  hook asked for and a directly spawned agent's the full id its transcript records, so one model
  appeared under two names. A subagent row now records what its own transcript reports — the most
  frequent model across its assistant records — and falls back to the requested alias only when
  it recorded none; `harness usage --rescan` normalises rows already on file. Worker rows still
  record what the worker reported, which is the only thing that knows.
- The native acceptance runner no longer raises a macOS keychain dialog on every client turn.
  macOS resolves the default keychain under `HOME`, a disposable home had none, and a client that
  stores an item then prompts "A keychain cannot be found" — once per launch across a whole
  matrix, with a destructive **Reset To Defaults** button. Each disposable home now carries its
  own throwaway keychain at the default path, so the store succeeds silently and never touches
  the operator's login keychain; a home whose keychain cannot be created reports the case
  `unverified` instead of launching a client. Other hosts are unchanged. The test suite raised
  the same dialog twice a run: two reviewer-key tests called `doctor` in a temporary home without
  hiding the installed client, so the real `claude doctor` ran there. They now hide it, and a
  tripwire test fails if a doctor call in a temporary home ever launches it again (#282).

### Migration

- A `role_bindings` override of `model` still wins over the class, so existing overrides keep
  working. A fork that added a role gives it a `tier:` line.
- A Codex install on a provider without these model ids sets `model` to `inherit` for each role
  under `role_bindings.codex`, which restores the previous behavior.
- Re-run `harness bmad apply <framework-root>` to pick up the revised templates.

## [0.10.0] — 2026-09-19

### Added

- Add the shared architecture-viewer profile, lifecycle and external process adapter. The preview
  works with a separately installed protocol 1 viewer and does not bundle or publish that viewer.
- Add bidirectional BMad-to-GitHub issue traceability, deterministic mapping audits and safe
  fallbacks for repositories that cannot project every native issue type or hierarchy.
- Add a versioned compatibility and migration contract, lifecycle acceptance runner and immutable
  release-source pinning.

### Changed

- Qualify the Claude Code and Codex CLIs on macOS and Linux with version-pinned native evidence.
  Keep the VS Code surfaces and Codex Desktop as unqualified previews; keep Cursor and Grok planned.
- Preserve released qualification evidence until runtime source changes, then fail the release
  check rather than silently changing a published support claim.

## [0.9.0] — 2026-09-19

### Provider-agnostic harness

- Lead with your working style, extensible custom primitives and switchable personal stances.
- Keep one shared authority for rules, stances, skills, roles, workflows and presentation;
  project it through Claude Code and Codex adapters.
- Add safe native configuration ownership, structural TOML updates, recovery journals, custom
  homes, drift diagnostics and conflict-preserving uninstall.
- Compose lifecycle policies, strengthen gate invalidation, and normalize usage observations
  while preserving unknown metrics and detector failures.
- Add custom stance authoring, semantic BMad roles and versioned bidirectional task handoffs.
- Add a native compatibility catalog and release gate. Claude Code and Codex are qualified on the
  required CLI, VS Code and desktop surfaces; Cursor and Grok, hosted agents, native memory merging
  and the UML viewer are deferred.
- Coordinate reference-site and personal-site positioning around the same user-aligned primitive
  model and immutable release identity.

### Changed

- Require a dedicated delivery issue for every PR, with a CI ownership check rejecting missing,
  multiple, foreign and reused closing issues. Document replacement PRs and the cross-PR race limit.

- User-authored drafts now defer to an untracked personal voice profile before applying the
  selected reply-layout stance, and the harness documents where that profile belongs. Accidental
  typos are explicitly excluded from imitation.

## [0.8.0] — 2026-09-17

### Added

- `docs/getting-started.md`: zero to a first useful session for someone who has not used a coding
  agent before. What the harness is and is not, the prerequisites as a table with a way to check
  each, install, `init`, a first session with three things to actually type, what changed about the
  answers, the five commands with which of them need a code project, what a session costs, and the
  three commands that diagnose a broken install. The README links it above the install block and
  from the docs list; `SUPPORT.md` now opens with it and says plainly that everything else there
  needs a GitHub account and is public. (#82)

- A **Before you start** block on the README's first screen: a Claude account on a plan that
  includes Claude Code — stated, rather than discovered after `install` has already run — the
  supported platforms, `git` and Python 3.9, and which of the rest are optional. (#82)

- A **What a session costs** section in `docs/preferences.md`, naming the rate-limit window, the
  commands that fan out, and the `cost` stance as the dial. Nothing previously said that a
  `/research` run costs several times a plain turn. (#82)

- `identity.expertise`, `expert` or `beginner`, selecting one paragraph of the personal file. The
  line telling the agent to communicate at expert level and skip fundamentals was hardcoded in
  `CLAUDE.personal.template.md` and reached every user, including one who had never written code —
  instructing the agent to withhold exactly the explanation they needed. `expert` is the default,
  so a config predating the field resolves to the behaviour it had. (#83)

- Stance presets, asked by `init`: `software` is the shipped defaults, `general` turns off the
  commit, test, licensing and build-vs-buy ceremony and lightens plans, for work that is not
  shipping software. Escaping the professional-SDLC defaults previously meant discovering five
  separate opt-outs. A preset only supplies the defaults for the questions that follow, so every
  stance is still asked. `delegation`, `autonomy` and `cost` are untouched by either: how work is
  spread, how far it runs unattended and what it costs are the same questions whatever the work
  is. (#83)

- A `voice` stance dimension, closing the last always-loaded rule that was a pure preference (#68).
  `scannable` defers to the output style as before and is the default, so nothing changes for an
  existing install. `answer-card` is for reading on a phone: the answer in the first line, then why,
  the catch, and the alternatives, about 150 words, no tables, with the reasoning left in the file
  it links rather than re-argued in the message. `off` imposes no shape at all. The two `voice/`
  detectors are gated on the dimension, so a voice nobody selected is not measured as a violation.

### Changed

- The three rules written entirely about code work say so in their headings — `verification`,
  `secrets` and `conciseness` — and one line of the always-loaded preamble states that a rule
  about repositories, tests or pull requests does not apply elsewhere. Rules link as a directory
  rather than per file, so they cannot be deselected; the fix is for them to read as inapplicable
  instead of as instructions about work the reader is not doing. Length-neutral apart from that
  one line. (#83)

- `voice-and-format.md` drops from thirteen lines to six, keeping only what no variant changes:
  a subagent inherits no voice, so its brief has to carry the output shape itself. Always-loaded
  context moves 193 to 195 of the 196-line budget.

- A `decisions/no-alternatives` detector, and `decisions-and-plans` leaves `OPT_OUT`. The rule
  asks for "the alternatives with their honest case", and nothing measured whether a decision
  block carried one: the opt-out reasoned from the Review Card and the chooser, and left the
  clause that does the work unobserved. The detector fires on a final message whose batched
  `Decisions` block or recommendation line names no other course, reading the markers out of the
  raw text so an alternative named inside a quote still counts. A recommendation in running prose is not a
  decision block and does not fire. (#78)

- `harness init`: a first-run wizard that writes `config.json` by asking for identity one field
  at a time and offering each stance's variants with the default in brackets, so configuring the
  harness no longer means hand-editing JSON. It detects the timezone from `/etc/localtime` and the
  GitHub handle from `gh` when it is logged in, refuses to clobber an existing config without
  `--force`, and names `config set` when there is no terminal to ask in. (#81)

- `harness config set KEY VALUE`, which validates before it writes: an unknown stance variant,
  stance, identity field, permission posture or top-level key is refused with the options named,
  rather than being written and failing at the next sync. (#81)

- `sync` and `doctor` report identity fields still carrying the example file's value. `load_config`
  backfills from `config.example.json` and `render_personal` writes the result into always-loaded
  context, so an unedited config had the agent address you as the placeholder name with nothing on
  screen to say so. Reported, never fatal: a dry-run sync against the example config still
  succeeds. (#81)

### Fixed

- `install` and `sync` refuse to run on Windows and name WSL2, rather than half-working: the
  harness links into `~/.claude` with symlinks and every hook is a POSIX command. Nothing in the
  README or the docs had ever said which platforms are supported. `_run` also treats an absolute
  path that does not exist as a missing tool, so `/bin/bash` being absent reports rather than
  raises. (#82)

- `doctor` now reports whether each registered hook can actually run, instead of printing an
  executable bit that never mattered. It resolves the interpreter and the script path of every
  hook command in the live settings and names what is missing. Claude Code treats a hook that
  fails to start as non-blocking, so a machine without `python3` on PATH, or an install that was
  never synced, turned all eleven hooks into silent no-ops — the command grader that asks before
  something irreversible and the stop gate that runs the repository's checks among them. Both
  guards disappeared with nothing on screen to say so. (#85)

- The two hook messages a user actually sees are written for a reader now. The grade-bash denial
  said "No prompt exists in this mode" and told them to re-run with a marker; it now says the
  command was refused because nothing can prompt, and what to say before running it again. Every
  grade carries its meaning in words — "this cannot be undone" — alongside the label. The stop
  gate says where the failing command came from, and the untrusted-folder notice names the command
  that fixes it. (#85)

- The four commands that assume a git repository now check for one before they start, and name a
  fallback instead of stopping dead. `/build` says up front that it needs a repository, a remote
  and `gh`, offers to make the change in place when there is no repository, and stops at the local
  commit when there is no remote — rather than failing at `gh pr create` with the work already
  done. `/review` says there is no diff to review outside a repository, before it spawns either
  pass, and offers named files or a pasted patch. `/plan` and `/handoff` write beside the work in
  the current directory when there is no repository root, and `/plan` now says outright that it
  needs neither a repository nor code. (#84)

- `bin/harness install` no longer ends in a traceback on a machine that lacks `gh` or `npm`.
  `subprocess.run` raises `FileNotFoundError` when argv[0] does not exist and `check=False`
  suppresses only a non-zero exit, so the unguarded `gh auth status` at the end of every install
  and the `npm install -g @openai/codex` step both crashed rather than reported — reachable with
  `--no-brew` on macOS and on every Linux run. Every external call now goes through one helper
  that resolves the executable first, names it when it is missing, and carries on. The lookup also
  searches the keg-only `node@22` bin directory, which Homebrew does not link into its prefix, so
  `npm` is found after a plain `brew install` on a machine with no other node. (#80)

## [0.7.0] — 2026-09-17

### Added

- A `code-quality-instruments` skill: branch coverage over line coverage, mutation score as the
  only instrument here that measures assertions rather than execution, complexity joined to
  coverage to rank the risky functions, and duplication as a refactor signal that is never a gate.
  Carries per-language instruments for Python, TypeScript, Rust and Go, and the operating rules
  that keep them usable: mutate the diff rather than the tree, run one instrument at a time, bound
  the workers. The `testing: required` variant gains a one-line pointer, which is the whole
  always-loaded cost. Adapted from `unclebob/swarm-forge`, whose engineering article pins real
  instruments per language where our stance only asked that tests exist. (#73)

- An eleventh hook, `brief-guard`: PreToolUse on `Agent`, it appends a 400-word return bound to
  a subagent brief that states none, rather than asking the orchestrator to write one.
  `transcript-hygiene/brief-without-cap` fired 536 times across 30 percent of sessions, so the
  prose was not working. What counts as a bound and which agents are exempt are imported from
  `rule-detectors.py` rather than copied, and a test asserts the appended text satisfies the
  detector, since a bound the detector cannot see would never move the number. Adapted from
  `unclebob/swarm-forge`, whose handoff helper fills the commit SHA so the agent never types
  one. No-op under `delegation: off`, where `tier-agent-spawns` already gates the spawn. (#72)

- A `commit-msg` hook in `templates/repo/hooks/`, installed per repository, refusing a subject
  that is not a Conventional Commit. It reads the `commits` stance and does nothing under `off`
  or `as-you-go`; under `conventional-attributed` it also warns on a missing `Co-Authored-By:`
  trailer, which it cannot add because the model name is session state a git hook cannot see.
  Adapted from `unclebob/swarm-forge`, which appends its byline the same way. A git hook was the
  right surface because it sees the final message however it was written, where the
  `commits/non-conventional` detector parses only `-m` and undercounts. (#71)

## [0.6.1] — 2026-09-17

### Fixed

- The instruction to gather with subagents unasked no longer loads under every stance. It sat in
  `claude/CLAUDE.md` and `claude/rules/delegation.md`, both always-loaded, and contradicted the
  `delegation: off` variant outright, so the selection did not decide the behaviour it named. It
  now lives in the `tiered` and `session-model` variants that mean it, and a regression test
  asserts that no always-loaded file carries one. Always-loaded context drops from 195 to 192
  lines. (#67)

### Changed

- The README, `docs/how-it-works.md` and `docs/preferences.md` say which layer is switchable and
  which is the floor, name the test a stance has to pass, and list the rules that do not pass it
  yet instead of leaving them implicit. (#67, #68)

## [0.6.0] — 2026-09-17

### Added

- A rule-detector registry (`claude/hooks/rule-detectors.py`): fourteen deterministic
  detectors over a session transcript, one or more per always-loaded rule, with an explicit
  opt-out list for the three rules nothing in a transcript can decide. `harness lint` now fails
  on a rule with neither, and reads its secret patterns from the same module. (#58)
- A tenth hook, `grade-bash`: every Bash command is graded 0–3 on the read-only grammar's
  decomposition (read-only, local, remote-mutating, irreversible) and the autonomy stance sets
  the gate: `execute` on grade 3, `confirm-writes` on 2 and up, `ask` on 1 and up. Prompting
  modes get `ask` with a one-line reason; `auto` and `bypassPermissions`, where a hook's `ask`
  is ignored, get `deny` with the same reason and a chat-confirmed re-run prefixed
  `HARNESS_CONFIRMED=1`. (#60)
- The session-end worker runs the detector registry and records `rules`, `counts` and `stances`
  per session; `harness usage --rules [--by rule|repo|stance]` reports hits, sessions and share per
  detector, marks `promote?` above 30 percent of at least 20 sessions and `unobserved` at zero over
  at least 20, and `--rescan` backfills from existing transcripts. (#59)

### Changed

- The README leads with the positioning line; the docs explain command grades, the ask-versus-deny
  split per permission mode with the hooks-reference quotes, and rule telemetry as the signal for
  pruning the always-loaded rules. (#61)

## [0.5.1] — 2026-09-16

### Changed

- Provenance credits a year of coding agents, most of it in Cursor and the last two months in
  Claude Code, rather than a year in `~/.claude`.
- The README and the comparison no longer claim the read-only hook is what stops plan mode
  prompting: Claude Code's own classifier does that by default in auto mode. The hook's value
  is deterministic, no-round-trip approval that also covers Manual mode and API, Bedrock and
  Vertex sessions.

## [0.5.0] — 2026-09-16

### Added

- A `tier-agent-spawns` hook (`PreToolUse` on `Agent`) applies the `delegation` stance to every
  subagent spawn that names no agent definition and no model, which is what a planning
  framework's or a plugin's "launch a subagent" produces: one tier below the session under
  `tiered`, untouched under `session-model`, a prompt under `off`. Frontmatter and explicit
  model choices are left alone. Inside a repository that carries a framework runtime
  (`_bmad/scripts/` or `_bmad/core/`), a bare spawn keeps the session model: the framework's
  lenses are judgment work its overrides cannot rename, and its own rule is same capability.
- `templates/bmad/custom/` carries override files in BMad's own format for `bmad-build`,
  `bmad-build-auto` and `bmad-code-review` that run their review layers as the `reviewer` and
  `spec-reviewer` agents and the implementation handoff on the builder's tier. `harness bmad
  apply` installs them into a repository's `_bmad/custom/`, skipping a template whose keys or
  layer ids the installed skill no longer declares, and `harness bmad check` reports that drift.
  The `harness-session` hook runs `apply` for the repository a session starts in and says so
  once when it wrote, kept or skipped a file.
- `docs/bmad.md` records how the two pieces keep the delegation stance in charge of a
  framework's spawns, and why the implementation handoff is not routed to `builder`.

## [0.4.1] — 2026-09-16

### Security

- The `readonly-bash` hook approved any command placed after a `#` comment and a newline: the
  lines were joined with `;` before tokenizing, so shlex's comment handling swallowed the rest
  and only the benign prefix was judged. Each line now loses its own comment first and a `#`
  inside a word stays part of the word, as in bash. Found by an independent review of 0.4.0.

### Fixed

- A bare `date MMDDhhmm` operand, which sets the system clock, falls through to the prompt.
- `harness uninstall` removes the PATH line it added to `~/.zprofile` and the ignore block it
  added to `~/.config/git/ignore`, leaving every other line in place.

### Changed

- CI runs `harness sync --dry-run` against the example config, as CONTRIBUTING said it did.
- The README points at `--help` for the full command surface and names `config get`;
  `docs/preferences.md` documents the `vscode.manage` and `codex.manage` keys.

## [0.4.0] — 2026-09-16

### Added

- `harness trust <path>` records a repository root whose `## Gate` block the stop gate may
  run, and `--remove` forgets it; the list lives in `~/.config/agent-harness/trusted.txt`.

### Security

- The `stop-gate` hook runs a repository's `## Gate` block only in a folder whose trust dialog
  has been accepted in Claude Code, or whose root is listed by the new `harness trust <path>`
  command, so a freshly cloned repository can no longer run commands on the first Stop. Until
  then it skips with a note on stderr.
- The `session` hook frames the handoff file it injects at session start as repository
  content on both sides, to be treated as data rather than instruction, the way the
  `neutralize` hook frames tool output.

### Fixed

- The `readonly-bash` hook approved several commands that write or execute: a second command
  after a newline, `awk` scripts calling `system()` or redirecting output, `env` with a program
  argument, `fd -x`, `rg --pre`, `sed -n` scripts using `w` or `e`, `sort -o`, `tree -o`,
  `yq -i`, `git grep --open-files-in-pager`, a `PATH=` or `GIT_*=` prefix, any binary run by
  absolute path with a read-only name, and the `>|`, `&>>`, `>&` and `<>` redirections. Each now
  falls through to the permission prompt. `tests/test_allow_readonly_bash.py` pins the corpus.
- The settings template no longer carries the allow rules that granted the same primitives
  without the hook: `Bash(awk *)`, `Bash(sort *)`, `Bash(sed -n *)`, `Bash(fd *)`, `Bash(rg *)`,
  `Bash(tree *)`, `Bash(file *)`, `Bash(date *)` and the leading-wildcard `Bash(* --version)`.
  The hook approves the safe invocations of every one of them.

### Changed

- `harness sync` removes an allow rule that an earlier template added and the current one has
  dropped, while still keeping rules the user added themselves.

## [0.3.0] — 2026-09-16

### Added

- A `plan-webfetch` PreToolUse hook that approves `WebFetch` while in plan mode, for
  `http`/`https` URLs only, so gathering context for a plan no longer prompts for every
  documentation URL. Every other permission mode is unchanged, and the `neutralize` hook still
  scans the fetched text (#37).

### Changed

- The `readonly-bash` hook now decomposes compound commands — `;`/`&&`/pipelines,
  `for`/`while`/`until`/`if` blocks, subshell `( )` and group `{ }`, and command substitutions
  `$(...)`, backticks and `<(...)` — and approves the whole only when every command inside is
  read-only, so plan mode stops prompting for read-only loops and substitutions. A write
  anywhere still falls through, and a reserved word used as an argument, such as `grep -q done`,
  is treated as data rather than syntax (#37).

## [0.2.0] — 2026-09-16

### Added

- `permissions.deny` rules in the settings template for credential files and generated
  directories, so the file tools and the Bash commands that read files are both covered.
- Three subagent definitions — `gatherer`, `reviewer` and `log-compressor` — carrying their
  model, effort level and tool list, so the delegation tiers hold without a retyped brief.
- A `sandbox` skill: container or built-in sandbox posture for an unattended loop.
- A `filter-output` PreToolUse hook that pipes a test, build, lint or type-check run through a
  line filter, keeping failures, summaries and the tail while preserving the exit status.
- A `cost` stance with `frugal`, `balanced` and `max` variants, and a `cache-hygiene` rule.
- A `neutralize` PostToolUse hook that flags instruction-shaped text in `Bash`, `WebFetch` and
  `Read` output, advisory only, never blocking or rewriting a result.
- A `stop-gate` Stop hook that runs the fenced `## Gate` block of a repository's `AGENTS.md`
  and refuses to end the turn while it is red, bounded by a block count and a time budget.
- Four slash commands — `/research`, `/plan`, `/build` and `/review` — each composing skills
  the harness already ships.
- A `usage-log` SessionEnd hook and `harness usage`, reporting per-session tokens and cache hit
  rate from a local file; see `docs/usage.md`.
- A `/handoff` command that writes `.claude/progress.md` and promotes durable learnings into a
  dated file under `docs/solutions/`, and a SessionStart hook that reads that progress file and
  the last five commits back as context. The progress file is added to the global git ignore.
- A `builder` agent carrying the standing implementation brief — a worktree of its own, tests
  with every change, the repository's gate, one local Conventional Commit and no push — so
  `/build` spawns it and verifies the gate itself instead of retyping the steps.
- A `spec-reviewer` agent that reports scope deviations only, and a two-stage `/review` that runs
  it before the quality `reviewer`, each in a context that has not seen the other's findings.
- A `planner` agent carrying the Review Card contract, so `/plan` can hand the file-writing to a
  fresh context and keep its own for the review conversation.
- A `design-judge` agent carrying the design loop's scored critique and its hard gates, so the
  independent judge is a fixed definition the skill names rather than a rubric pasted each round.

### Fixed

- The agent sync tests restore the environment they change, so a later test in the same run is
  no longer affected by them.

### Changed

- Always-loaded context (`claude/CLAUDE.md`, every rule, and the longest variant of each stance) is
  capped at 200 lines and `harness lint` fails with a per-group breakdown when it is exceeded. The
  rules keep their operative lines and point at the skill holding the reasoning; the rationale,
  examples and evidence moved verbatim into `delegation-tiering`, `plan-authoring`,
  `harness-authoring`, the new `transcript-hygiene` and `api-verification` skills,
  `docs/how-it-works.md` and `docs/preferences.md`. 583 lines before, 185 after.

## [0.1.1] — 2026-09-16

The repository was re-created with a fresh history for this release. The 0.1.0 tag and its
history are gone: the lint in that release embedded a denylist of the maintainer's own
identifiers, which is a disclosure of the very values it existed to catch.

### Changed

- The lint carries no list of real values. It matches personal-data shapes (12-digit account
  ids, email addresses, home-directory paths, cloud ARNs, hosted-zone ids, identity-provider
  tenants, private IPs) and secret patterns everywhere in the tree with no file exempt, derives
  the maintainer's name from `LICENSE` and `CODEOWNERS`, and reads personal terms from the
  untracked `~/.config/agent-harness/lint-terms.txt` (see `lint-terms.example.txt`).
- `harness lint --staged` and a `.githooks/pre-commit` hook, installed by `harness sync`, lint
  every commit in the checkout before it is made.
- `permissions: bypass` is refused unless `permissions_bypass_acknowledged` is `true` in the
  config file, and is documented as unsuitable for any machine that touches regulated data.
- Test fixtures assemble identifier-shaped strings at run time, so the tests are linted like
  everything else; a regression test asserts no file in the tree carries an identifier shape.

## [0.1.0] — 2026-09-16 (withdrawn)

### Added

- Nine core rules, seven stances with twenty variants, ten skills, three hooks and the
  Scannable output style, extracted from a working harness and rewritten in second person.
- `bin/harness` with `install`, `sync`, `diff`, `doctor`, `uninstall`, `lint`, `workspace
  create` and `config get`; standard library only.
- Symlink-based live sync into `~/.claude`, ownership-scoped settings merge, identity rendered
  from `~/.config/agent-harness/config.json`, per-session `HARNESS_*` overrides.
- VS Code owned settings and extension lists; generated Codex `AGENTS.md`; repo starter
  templates.
- Community files, issue and PR templates, CI with lint and tests, Dependabot for actions.

[Unreleased]: https://github.com/JakeSelby/agent-harness/compare/v0.8.0...HEAD
[0.8.0]: https://github.com/JakeSelby/agent-harness/releases/tag/v0.8.0
[0.7.0]: https://github.com/JakeSelby/agent-harness/releases/tag/v0.7.0
[0.6.1]: https://github.com/JakeSelby/agent-harness/releases/tag/v0.6.1
[0.6.0]: https://github.com/JakeSelby/agent-harness/releases/tag/v0.6.0
[0.5.1]: https://github.com/JakeSelby/agent-harness/releases/tag/v0.5.1
[0.5.0]: https://github.com/JakeSelby/agent-harness/releases/tag/v0.5.0
[0.4.1]: https://github.com/JakeSelby/agent-harness/releases/tag/v0.4.1
[0.4.0]: https://github.com/JakeSelby/agent-harness/releases/tag/v0.4.0
[0.3.0]: https://github.com/JakeSelby/agent-harness/releases/tag/v0.3.0
[0.2.0]: https://github.com/JakeSelby/agent-harness/releases/tag/v0.2.0
[0.1.1]: https://github.com/JakeSelby/agent-harness/releases/tag/v0.1.1
