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

Native agent definitions are rendered at sync from the resolved cost variant, so the model class
and effort a role runs with are written into the file on disk rather than decided per session. A
session-scoped `HARNESS_STANCE_COST`, like any `HARNESS_STANCE_*`, stays in that session and does
not move them until the next `harness sync`; role-run workers resolve their class and effort per
run and do follow it. A `role_bindings.<runtime>.<role>` entry still wins over the variant's row.

Usage records identify the runtime and available runtime version. Codex cumulative token snapshots
are counted once; missing measurements remain null and reports label partial totals. Detector
failures are reported separately and excluded from clean-session denominators. Lock contention
refuses an overwrite; detached worker failures go to `usage.errors.jsonl` beside the usage ledger.
Transcript adapters cannot observe nested tool calls absent from the transcript and do not prove
that a stance caused a behavior.

Session start checks BMad configuration without installing it. Installation remains explicit.
See [task continuation and BMad](bmad.md), [installation ownership](runtime-installation.md),
and the compatibility catalog for qualification evidence.
