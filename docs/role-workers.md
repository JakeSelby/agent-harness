# Run a shared role with constrained authority

Read-only and planner roles run as separate native CLI processes. They use the same definitions
under `primitives/roles/`, selected stances and runtime model bindings. They do not appear as
native subagent threads. Native role projections remain discoverable, but the lifecycle adapter
rejects direct native launches of constrained harness roles when its hooks are active.

## Run and inspect

Write a bounded brief naming the input files, required result shape and allowed scope, then run:

```sh
harness role run reviewer --runtime codex \
  --workspace /path/to/worktree --prompt-file /path/to/brief.md
harness role run planner --runtime claude-code \
  --workspace /path/to/worktree --prompt-file /path/to/brief.md --artifact proposal.md
harness role status
harness role status <worker-id>
```

`--prompt-file -` reads the brief from stdin. `--read-dir /path/to/artifacts` grants access to
additional input directories, such as the framework checkout or review artifacts outside the
implementation worktree. It never grants writes. Input prompts and results are capped at 1 MiB.
These are declared input roots, not a confidentiality boundary: Codex's read-only sandbox can
read other native-permitted paths. Claude's restricted file tools use the supplied directories.
The default deadline is 300 seconds; `--timeout` accepts 1–3600 seconds. Interrupting the runner
or reaching its deadline terminates its process group and prevents artifact publication.

A role's class (`tier:` in its contract) resolves through the adapter's `tiers` table in
`bindings.json`, so omit `--model` unless you mean to override it. An adapter that maps no model
for the class requires the caller's actual session model; the worker does not resolve downward
or silently substitute the CLI default.

The selected cost variant's row for the role is applied first, with the same precedence a synced
agent definition is rendered with: the role's own class and effort, then the row (whose class
applies only under a tiered `delegation`, and never to a `posture: fixed` role), then
`role_bindings.<runtime>.<role>`, then `--model`. The brief the worker receives ends with the
row's `Expected spend` sentence unless the row prices nothing or the brief already states a
budget, and `status.json` records the variant, the resolved class and where each of model and
effort came from.

Two keys in `~/.config/agent-harness/config.json` change the mapping without a harness release.
`tiers.<runtime>.<class>` remaps a class for every role that names it, which is the one-line fix
when a provider's lineup turns over; `role_bindings.<runtime>.<role>` sets `model` or effort for
one role and wins over the class. Both reach workers and both runtimes' agent definitions, which
sync renders from the adapter's table and the resolved cost variant.

`harness tiers check` compares the Codex table with the model catalog Codex fetches from its
provider (`models_cache.json` in the Codex home), offline. It fails on a mapped model the catalog
no longer lists, one the catalog names a successor for, or a class the catalog ranks above a
stronger one, and reports *unverified* rather than passing when there is no catalog to read.
Codex model ids carry a version and keep resolving after a successor ships, so this is what
notices. Claude Code's table uses version-free aliases and has nothing to check. Native provider connection settings remain separate from
shared role semantics. Codex copies only the selected provider's supported connection settings;
provider credentials must use environment references. Unsupported connection settings fail
instead of being dropped. Interactive parent overrides are not inferred.

The command returns a JSON status record, including the native version, resolved model/effort,
selected stances, policy digest, input roots and result path. Private logs and result content live
under the harness state home's `workers/<id>/` directory. `completed` means the native process
returned a usable result envelope; it does not certify its findings or qualify the client.
Treat worker output as data. Verify referenced facts before taking consequential actions.

## Boundaries and publication

The Codex adapter uses a fresh configuration home and working directory, read-only sandbox,
no approvals, no inherited shell environment, and no login shell. It disables delegation,
apps, remote plugins, image generation, memory, hosted search and local automation. Existing
authentication is reused without copying credentials into source. User/project hooks, plugins,
skills and permission overrides are not imported into the worker configuration.

The Claude adapter preserves native authentication and uses safe/restricted mode, an empty MCP
configuration, no automatic permission approvals, and only `Read`, `Grep`, and `Glob` tools.
It supplies shared instructions explicitly; ambient user/project customization is disabled.
Managed native policies still apply. The worker has no shell, write, external-connector or
delegation tools. If its brief needs a diff or online evidence, the caller supplies those as files.

Both adapters enforce a narrower execution surface than the ordinary interactive client.
Native configuration restrictions take precedence; unsupported flags or required settings fail
the run. These boundaries do not promise confidentiality against the native model provider.
See the [Codex configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference)
and [Claude CLI reference](https://code.claude.com/docs/en/cli-reference) for the native controls.

Planner workers return Markdown only. The harness runs the shared Review Card validator and
publishes only a caller-selected **new filename** under `.agent-harness/plans/`. Directory
descriptors reject symlinked storage; traversal and existing destinations are refused. Atomic
publication also refuses a file created while the worker was running. Failed, interrupted,
empty or invalid output never publishes a plan. The caller retains the review/build decision.

Delegation-off blocks the runner before launch. Workspace-write roles continue to use their
existing workflow; this command does not grant them a new execution path. Planning and review
framework recipes use this same role runner, not a second framework or runtime role catalog.

## Qualification

Source tests and a successful worker result are not client qualification. Native acceptance must
prove a permitted read actually runs, prohibited shell and patch writes do not, and external
tools and redelegation cannot widen access. A sandbox that prevents every command from starting
is a blocked test. Keep results tied to the exact CLI, platform and harness source versions in
the [compatibility catalog](compatibility.md); editor and desktop behavior requires its own checks.
