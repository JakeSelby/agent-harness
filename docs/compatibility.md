# What is supported

The architecture is model-provider agnostic: your rules, skills, roles, workflows and personal
stances have one source. That does not mean every runtime implements every capability.
`compatibility/catalog.json` is the versioned authority; `harness compatibility --json` emits it.
A separate [compatibility and release policy](compatibility-policy.md) defines the stable v1
interfaces, preview boundary, versioning, deprecation and migration rules.
A **qualified** entry requires native evidence for its exact runtime, client and platform.
**Unqualified** means no complete passing evidence, **planned** means no current integration,
and **unsupported** means a combination explicitly outside the integration contract.

Claude Code and Codex are this release's integration targets. The v0.12.0 release carries no
native qualification: no client has evidence for this source and no client is marked required
for release, a deliberately narrower support contract taken for a pre-1.0 release. The v0.11.1
stable floor remains the last one qualifying those CLIs on macOS and Linux. The Claude Code and Codex VS Code surfaces, Codex Desktop on macOS and the Claude Code
plugin-marketplace install remain unqualified previews. A marketplace install carries the
skills, roles, commands and output style only; the ownership journal, stance selection, the
Codex projection and the hooks come from `bin/harness install`, and
[runtime installation](runtime-installation.md) states the difference. Do not read successful source generation or deterministic tests as native
client qualification.

## What qualified means at each level

Client qualification and capability qualification are separate claims, and this is the default
rule reconciling them; a maintainer decision may replace it, in this section:

> A client is qualified when its required acceptance cases pass natively. A capability is
> qualified for a client only when that client is qualified AND a native acceptance case
> exercising that capability exists and passed; otherwise the capability is `unqualified` and
> inherits nothing from the client. The catalog is the single authority: per-capability state is
> derived from the adapters' capability files at `harness compatibility` time and rendered beside
> the client row, never hand-edited in two places.

An adapter names the cases that exercise a capability with an optional `acceptance_cases` list on
a stance entry or on `role_execution` in `adapters/<runtime>/capabilities.json`; every name in it
must be one of the catalog's `required_cases`. Listing cases under a capability that is not
`qualified`, or claiming `qualified` without them, is a contradiction between the two files:
`harness compatibility --release-check` blocks the release and the test suite fails. Today no
adapter names a case and no client is qualified, so every cell below reads `unqualified`, which is
what the table says. `harness compatibility --json` emits both levels,
each client row carrying its derived `capabilities`. The capability-by-client layout follows the
generated matrix in [wshobson/agents' `docs/harnesses.md`](https://github.com/wshobson/agents/blob/main/docs/harnesses.md).

The table's last row answers a different question: not whether a capability carries native
evidence, but whether the `delegation` stance's model-tier ceiling binds on that surface.
`tier_restriction` in `adapters/<runtime>/capabilities.json` declares it per runtime, with a
`without_hooks` entry for a client that installs no hooks — `"installs_hooks": false` on a catalog
client, which today is the plugin-marketplace install. The Claude Code CLI and VS Code surfaces
read `enforced`, because `claude/hooks/tier-agent-spawns.py` rewrites an `Agent` call that asks for
the strongest class by `model:` down to the class below unless the role it names declares that
class itself. Every Codex surface reads `advisory`: the coordinator does run there, and a Codex
`Agent` call still passes the role, marker, evasion and brief checks, but the tier rewrite is
behind a `runtime == "claude-code"` gate in `lib/harness_core/lifecycle.py`, so the ceiling
reaches Codex as projected prose alone. The marketplace install reads `advisory` for the plainer
reason that it installs no hooks at all.

<!-- harness:compatibility:start -->
**Unqualified:** `claude-code-cli-macos`, `claude-code-vscode-macos`, `claude-code-cli-linux`, `claude-code-plugin-marketplace`, `codex-cli-macos`, `codex-vscode-macos`, `codex-desktop-macos`, `codex-cli-linux`.

**Planned:** `cursor`, `grok`.

A client's status is not a capability's status. Each cell is derived from that runtime's `adapters/<runtime>/capabilities.json` at generation time:

| Capability | `claude-code-cli-macos` | `claude-code-vscode-macos` | `claude-code-cli-linux` | `claude-code-plugin-marketplace` | `codex-cli-macos` | `codex-vscode-macos` | `codex-desktop-macos` | `codex-cli-linux` |
|---|---|---|---|---|---|---|---|---|
| `autonomy` | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified |
| `build-vs-buy` | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified |
| `commits` | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified |
| `cost` | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified |
| `delegation` | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified |
| `licensing` | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified |
| `plan-ceremony` | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified |
| `role_execution` | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified |
| `testing` | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified |
| `voice` | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified |
| tier restriction | enforced | enforced | enforced | advisory | advisory | advisory | advisory | advisory |

The last row is not a qualification state. It says whether the delegation stance's model-tier ceiling is **enforced** (a hook rewrites or refuses the spawn), **advisory** (prompt text only) or **none**, carried advisory by `primitives/skills/delegation-tiering/SKILL.md`, `primitives/stances/delegation/tiered.md`; enforced by `claude/hooks/tier-agent-spawns.py`. `enforced` is narrower than it sounds. It never reaches the session's own model: the `model` settings key is one this harness never writes (`docs/settings-ownership.md`). Within a session it rewrites a spawn only while the selected `delegation` variant is `tiered` — `off` stops the spawn instead, and any other variant leaves it alone — and only while the adapter's class table maps at least two models, since one class is no ladder to move a spawn down. Under every other condition the ceiling is prose, exactly as `advisory` is everywhere.
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

The [qualification runbook](qualification-runbook.md) covers the mechanics of a run: the
acceptance runner's invocation, its disposable homes and the credentials it passes through.
Start with an isolated test user/configuration home and a disposable repository. Record exact
runtime and client versions, operating system, source commit, date, configuration, commands,
and observed results. Never commit credentials, full private transcripts or personal settings.
On macOS, run `harness keychain <home>` on any home you build by hand before a client is launched
under it; a home without a default keychain raises a system dialog, and a home whose keychain
cannot be created does not launch a client. Never repoint your own default keychain or search list.
For every target listed in the catalog, verify every `required_cases` entry natively:

1. Install, restart, and inspect effective instructions, discovered skills and registered roles.
2. Switch a representative communication and delegation stance; observe both instruction text
   and agent/tool behavior. Repeat with a custom dimension, project override and invalid choice.
3. Exercise manual, auto and acknowledged bypass postures against native restrictions.
4. Check hook trust, composition, denials and multi-file patches; attempt writes from read-only
   roles and outside the planner artifact scope. Configuration defaults are insufficient proof.
5. Change staged and untracked files after a green gate; check reruns and unverified failures.
6. Drive the spawn hook in a disposable home against a fixture recipe built from a descriptor
   in `policy/integrations/`: confirm a brief carrying a constrained role's work is denied with
   the isolated-worker instruction whether it is spawned unnamed, under a generic subagent type
   or under a band worker's name; that the refusal names that descriptor's input roots as the
   read roots the worker is limited to; that the recipe's unnamed spawn routes to the cost
   variant's default band worker at that row's class and effort with the budget sentence in its
   brief; and that a null variant rewrites nothing. No third-party framework's own workflow is
   run in a qualification round; that is the optional suite in [BMad](bmad.md).
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
9. Run a review layer of a framework named by a descriptor in `policy/integrations/` as a native
   subagent that names no role, with the brief reworded as the client writes it, and confirm the
   spawn is refused and the refusal names the framework, the layer and `harness role run <role>`.
   Confirm the same layer run the routed way writes isolated worker state and returns findings,
   and that a session with no worker state written is a failed case rather than a passed review.
   Then the false positive: spawn ordinary work whose brief mentions review, a diff or findings
   in passing, and one that edits the framework's own input roots, and confirm both run.

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
The runner appends each finished case to a durable log as the case completes, so a killed round
costs the case it was running rather than the round; rebuild the surviving cases into a record
with `--from-progress`, and link that partial record as the partial record it is.
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
