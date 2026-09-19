# What is supported

The architecture is model-provider agnostic: your rules, skills, roles, workflows and personal
stances have one source. That does not mean every runtime implements every capability.
`compatibility/catalog.json` is the versioned authority; `harness compatibility --json` emits it.
A **qualified** entry requires native evidence for its exact runtime, client and platform.
**Unqualified** means no complete passing evidence, **planned** means no current integration,
and **unsupported** means a combination explicitly outside the integration contract.

Claude Code and Codex are this release's integration targets. Qualification is pending for
both macOS CLIs and VS Code integrations, Codex desktop on macOS, and both Linux CLIs. Do not
read successful source generation or deterministic tests as native client qualification.
Cursor and Grok integrations are planned. Hosted agents, native memory merging and the UML
viewer are deferred. Native Windows is unsupported; WSL2 has not been qualified.

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

Store a redacted JSON evidence artifact with `kind: native`, `client`, `harness_version`,
`source_commit`, `observations`, and a `cases` object whose values are `passed`, `failed`, or
`unverified`. Add its path and SHA256 to the client entry. Evidence cannot be reused for another
client or harness version. Set exact runtime/client versions before changing status to qualified.
The CLI verifies these records and `harness compatibility --release-check` fails until all
required clients are qualified. A reviewer must assess the observations; a JSON label alone is
not empirical evidence.

[Runtime controls](runtime-controls.md) records current enforcement gaps. Adapter coverage in
`harness stances --json` distinguishes instruction policy, hooks and settings, including custom
stances which are advisory by default. No preference overrides a native restriction.
