# What is supported

The architecture is model-provider agnostic: your rules, skills, roles, workflows and personal
stances have one source. That does not mean every runtime implements every capability.
`compatibility/catalog.json` is the versioned authority; `harness compatibility --json` emits it.
A separate [compatibility and release policy](compatibility-policy.md) defines the stable v1
interfaces, preview boundary, versioning, deprecation and migration rules.
A **qualified** entry requires native evidence for its exact runtime, client and platform.
**Unqualified** means no complete passing evidence, **planned** means no current integration,
and **unsupported** means a combination explicitly outside the integration contract.

Claude Code and Codex are this release's integration targets. The v0.11.1 stable support floor
qualifies their CLIs on macOS and Linux. The Claude Code and Codex VS Code surfaces and Codex Desktop on macOS remain
unqualified previews. Do not read successful source generation or deterministic tests as native
client qualification.

<!-- harness:compatibility:start -->
**Qualified:** `claude-code-cli-macos`, `claude-code-cli-linux`, `codex-cli-macos`, `codex-cli-linux`.

**Unqualified:** `claude-code-vscode-macos`, `codex-vscode-macos`, `codex-desktop-macos`.

**Planned:** `cursor`, `grok`.
<!-- harness:compatibility:end -->

Hosted agents and native memory merging remain deferred. The [architecture-viewer binding](viewer-integrations.md)
is a preview for separately installed custom adapters. A local protocol 1 candidate passed
process-level harness acceptance; no viewer is bundled, and native viewer interaction and
distribution/license clearance remain unverified. Native Windows is unsupported; WSL2 has not
been qualified.

A model provider supplies the model. An agent runtime orchestrates its tools and context.
A client surface is the CLI, editor integration or desktop app exposing that runtime.
Cursor belongs in the runtime/client integration catalog, with model providers described
separately: selecting the same underlying provider does not prove equivalent Cursor behavior.

## Qualification procedure

Start with an isolated test user/configuration home and a disposable repository. Record exact
runtime and client versions, operating system, source commit, date, configuration, commands,
and observed results. Never commit credentials, full private transcripts or personal settings.
For every target listed in the catalog, verify every `required_cases` entry natively:

1. Install, restart, and inspect effective instructions, discovered skills and registered roles.
2. Switch a representative communication and delegation stance; observe both instruction text
   and agent/tool behavior. Repeat with a custom dimension, project override and invalid choice.
3. Exercise manual, auto and acknowledged bypass postures against native restrictions.
4. Check hook trust, composition, denials and multi-file patches; attempt writes from read-only
   roles and outside the planner artifact scope. Configuration defaults are insufficient proof.
5. Change staged and untracked files after a green gate; check reruns and unverified failures.
6. Run a BMad workflow from its shared framework checkout against an assigned worktree.
7. Continue the same task Claude→Codex and Codex→Claude, including changed-tree and stale-writer
   cases; establish permissions anew. Verify migration, drift and uninstall preserve user data.
8. Select a non-default cost variant and sync; confirm that only the roles it changes are
   rewritten and that every other role keeps its link. In a session started after that sync,
   spawn a subagent that names no role, and confirm from the subagent's own transcript that it
   ran as the variant's default band worker at that row's model and effort, that its brief ends
   with the budget sentence, that the usage feed reported its spend against that budget, and that
   `harness usage --rescan --by role` records the routed row. Confirm that a session already
   running before the workers were installed is not rerouted and that its spawn still succeeds.
   Then select a variant with the feed off, no default band and no budgets, and confirm that none
   of this occurs. On a runtime that does not route native spawns, verify the posture through an
   isolated role worker's model and effort and the budget sentence in a named role's brief, and
   record the feed as not applicable with that reason.

Store a redacted JSON evidence artifact with `kind: native`, `client`, `harness_version`,
`source_commit`, `runtime_version`, `client_version`, `platform`, `observations`, and a `cases`
object whose values are `passed`, `failed`, or
`unverified`. Add its path and SHA256 to the client entry. Evidence cannot be reused for another
client or harness version. Its full source commit must be an ancestor of the release with no
subsequent runtime-source changes; changed adapters or primitives invalidate the evidence. Set exact runtime/client versions before changing status to qualified.
Each linked record must match the catalog's exact runtime version, client version and platform.
Linked failed or unverified results block qualification even if another record passes the same
case. When a rerun supersedes a record, remove the old reference from the active claim while
preserving the historical evidence file. Unknown cases and result values are rejected.
The CLI verifies these records and `harness compatibility --release-check` fails until all
required clients are qualified. A reviewer must assess the observations; a JSON label alone is
not empirical evidence.

A released catalog pins the exact source commit its evidence qualifies. Later development does
not rewrite or invalidate that historical release record, but any change under the runtime-source
paths makes `harness compatibility --release-check` fail until the new source has its own candidate
catalog and native evidence.

[Runtime controls](runtime-controls.md) records current enforcement gaps. Adapter coverage in
`harness stances --json` distinguishes instruction policy, hooks and settings, including custom
stances which are advisory by default. No preference overrides a native restriction.
