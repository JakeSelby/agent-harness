# Runtime controls

One shared policy engine (`lib/harness_core/lifecycle.py`) consumes normalized events. Native
adapters register one coordinator per lifecycle event and translate decisions. A deny wins over
an allow or rewrite; independent rewrites compose. Codex cannot pause with Claude's hook `ask`
decision, so a request requiring confirmation is denied with its reason. Output filtering never
grants an otherwise unapproved shell command merely to rewrite it.

Hook registration is not activation. Codex requires native trust for the current hooks content;
accept it in the client. `harness trust` separately authorizes running a repository's gate and
does not manufacture native hook trust. Native permission restrictions always take precedence.
Hosted search and continuation through an already running shell are not universally intercepted.
Hooks assist workflow policy; they are not a substitute for the runtime sandbox.

The stop gate hashes HEAD, staged and unstaged binary differences, untracked file contents,
repository identity, and gate definition. Commands share a shell so `cd` and `export` persist.
A gate that changes the tree, times out, or exhausts its retry budget is unverified, never green.
Unexpected gate errors block. State writes are atomic.

Constrained roles use [isolated CLI workers](role-workers.md), with shared role/stance resolution
and fixed native tool controls. The harness validates and publishes planner content to a new
approved artifact path. Direct native role defaults are not confinement: Codex can reapply parent
permission overrides. Active lifecycle hooks route constrained role launches to the worker
command. Native qualification is still required; do not treat a projection or unit test as certification.

Native agent definitions are resolved at sync from the cost variant in force. A role the selected
posture does not move stays a symlink to the committed projection, exactly as before; a role it
moves is rendered into the Claude home, so the class and effort it runs with are written into the
file on disk rather than decided per session. A
session-scoped `HARNESS_STANCE_COST`, like any `HARNESS_STANCE_*`, stays in that session and does
not move them until the next `harness sync`; an isolated [role worker](role-workers.md) resolves
its class, effort and soft budget per run, from the same table and the same precedence, so it
follows that session selection and a constrained role cannot run one way as a worker and another
as a definition. A `role_bindings.<runtime>.<role>` entry still wins over the variant's row.
Routing of spawns that name no agent definition turns itself off in a workspace that ships its own
`.claude/agents/worker-*.md`, since a project definition outranks the user's and routing to it
would put that repository's instructions on every unnamed spawn; the spawn runs as written and the
hook says so.
Before downgrading to a release that only links these definitions, either select `balanced` with
no role bindings and sync once, which restores the links, or run `harness uninstall`. Syncing a
home back with the older release is not enough on its own: role files the older release does not
ship stay in `~/.claude/agents` and `~/.codex/agents`, and its `harness diff` reports no drift,
because code that never knew those roles cannot miss them. `harness uninstall` before the
downgrade is the remedy; it removes what the newer release wrote.

Routing is session-scoped for the same reason that effort is sync-scoped: what a native agent is
comes from files read at a moment, not from a live lookup. Claude Code loads its agent registry
when the session process starts and never reloads it, so session start records which definitions
that registry held, and an unnamed spawn is routed only to a worker named in its own session's
record. A `startup` writes the record, a `resume` may only narrow an existing one, and `clear` and
`compact` leave it alone. A session with no record keeps the previous behaviour and is told once
to start a new one, so start a new session after a sync that installs or changes the band workers.
Any failure to answer the routing question leaves the spawn unrouted and silent, never refused.

Usage records identify the runtime and available runtime version. Codex cumulative token snapshots
are counted once; missing measurements remain null and reports label partial totals. Detector
failures are reported separately and excluded from clean-session denominators. Lock contention
refuses an overwrite; detached worker failures go to `usage.errors.jsonl` beside the usage ledger.
Transcript adapters cannot observe nested tool calls absent from the transcript and do not prove
that a stance caused a behavior.

A cap on a multi-item read is a budget: ask the source for newest-first where it can be asked,
check the order that actually arrives, refuse the page when it is not descending, and record at
the declaration which end is dropped — when several sources compete for one budget, drop the
least authoritative first. The Remote Control sessions page (`remote_control.fetch_sessions`) and
the usage feed's `OPEN_TAIL` both keep the newest, because a correction that arrives last is the
one a trimmed history must not lose. The sessions endpoint takes no sort parameter and is ordered
by `last_event_at`, so that read asserts the order rather than requesting it, and a refusal is
reported as not checked, never as nothing found. A count over a page that carries a cursor names
the page it counted rather than the account.

## Decision providers

`lib/harness_core/decision.py` holds one transport-agnostic contract for the question "may this
action proceed, and how": `decide(action, counterparty, context)` returns a `Decision` carrying an
outcome of `allow`, `ask` or `deny`, an autonomy level of 1 to 3, the provider name, a reason, and
an `injected_cognition` block of rule matches and optional agent and user messages;
`record(action_outcome)` notes how an action turned out; `learn(approval_stream)` takes past
approvals and may be a no-op. The shape deliberately mirrors the `decide`/`record`/`learn` surface
of an external control plane, so a hosted provider can be added later without a second contract.
An action names a class — `coding.shell_exec`, `coding.git_commit`, `coding.git_push`,
`coding.deploy`, `coding.file_write` — and the command grade where one is known. A counterparty is
the `repo:<name>/<branch>` slug the usage ledger already derives.

Two providers ship. `none` is the default: every action is allowed at level 3 with the reason
`governance: none`. `local` reads `.agent-harness/governance.json` in the repository
(`defaults`, `pairs`, `caps`) and resolves a level in that order — an explicit counterparty pair,
then the action class default, then the level the autonomy stance implies (`execute` 3,
`confirm-writes` 2, `ask` 1, and 1 when nothing resolves). A cap is a ceiling the resolved level
never exceeds; `coding.deploy` carries a built-in cap of 2 that a policy file may lower and may not
raise. Level 3 allows every grade, level 2 asks at grade 2 and up, level 1 asks at grade 1 and up,
and an unknown grade is judged as 1. A policy file that cannot be honoured as written is an error
naming the file, never a silent "no policy". Both providers write to the existing
`decisions.jsonl` ledger and neither reaches the network.

A third provider, `jev`, lives in `lib/harness_core/decisions/jev.py` and answers over the
network. It asks a validated question pack — a `choice` judgment and a `score` severity — about
the action class, the counterparty, the command grade and at most a command string and a summary,
and it carries the deterministic `local` provider underneath. The service has no abstention
outcome, so every `choice` question must offer an explicit `unknown` option and a pack without one
is refused before anything is sent; `unknown` and an answer below the confidence threshold both
mean "use the deterministic answer". A judgment may turn an `allow` into an `ask` and may never
widen a decision or produce a `deny`. Every other outcome fails open to the deterministic
decision: no key, a timeout, an exhausted budget, a malformed response, an unexpected exception.
Each call writes one `event` row carrying the status, the requested and returned model ids, the
pack and request hashes, the usage and the latency, and never the state; `harness decide`
suppresses that row, because a reporting command changes nothing. The endpoint must be `https`
and the opener can reach no other scheme, since a bearer key goes with every request, and a
request is charged to its budget as it is sent rather than when it succeeds, so a failing
endpoint cannot be retried without limit. The token ceilings, the endpoint, the response shape
and the status mapping come from the vendor's documentation and have not been checked against
the live service from this repository. Answers are not
deterministic across identical requests, so nothing promises a repeated request answers the same
way — only that the same request hashes the same. Credentials come from `TYPESAFE_API_KEY` or
`JEV_API_KEY` in the environment; no key file is ever read. The client is not live unless it is
constructed with `live=True`, so selecting this provider today calls nothing: the opt-in
configuration, the per-decision-point modes and the sentinel that disables every call are #137.

`governance.provider` selects one; the default is `none`. `harness decide --action <class>
[--grade N] [--counterparty <slug>] [--json]` prints the decision for the current repository.
Nothing consults a provider yet: command grading still answers the permission question on its own,
and binding the two is separate work.

Session start checks a declared integration's configuration without installing it. Installation
remains explicit. See [task continuation](task-continuation.md), the [BMad integration](bmad.md),
[installation ownership](runtime-installation.md),
and the compatibility catalog for qualification evidence.
