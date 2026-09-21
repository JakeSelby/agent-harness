# Agent Harness

[![CI](https://github.com/JakeSelby/agent-harness/actions/workflows/ci.yml/badge.svg)](https://github.com/JakeSelby/agent-harness/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![Reference](https://img.shields.io/badge/reference-agent--harness.jakeselby.com-d97706.svg)](https://agent-harness.jakeselby.com)

## Define your working preferences once. Apply them to Claude Code and Codex.

![Terminal output of `bin/harness sync --dry-run` on a fresh home: the resolved personal stances, then every link, rendered file and setting the sync would create for Claude Code and Codex, ending in "sync complete". Nothing is written.](docs/assets/sync-dry-run.svg)

Agent Harness keeps shared instructions, skills, roles, workflows and personal preferences in one
place, then projects them into the native formats each runtime understands. You do not have to
maintain one working agreement for Claude Code and another for Codex.

Agent Harness is not an LLM API gateway, a model provider or a replacement agent runtime. Claude
Code and Codex remain responsible for model access, native permissions and client behavior.

## What it does for you

The same six groups are held as data in [`product.json`](product.json), so this list, the reference
site and the GitHub description cannot drift apart.

### Spend less without capping your agents

A hard cap cuts an agent off after it has already spent the tokens. I'd rather tell it what things
cost and let it pace itself.

- [Cost postures](primitives/stances/cost): Pick frugal, balanced or max, or write your own. One table sets model, effort and a soft budget per role.
- [Model tiering](primitives/stances/delegation): Roles ask for a capability class, not a model name. Gathering files doesn't run on the model that reviews your code.
- [Band workers](claude/agents/worker-a.md): A spawn that names no role gets a right-sized worker instead of your most expensive model.
- [A budget in every brief](claude/hooks/brief-guard.py): Each subagent is told its expected tokens and tool calls. Finish if you're close, otherwise return what you have.
- [Live usage feed](docs/usage.md): The orchestrator sees what each turn and each subagent cost. A decision log on this machine records what a hook decided and what settled it; only harness usage reads it.
- [Lean context](docs/how-it-works.md): Always-loaded instructions are capped at 200 lines, and lint fails the commit past that. Noisy tool output is filtered before it lands in the transcript.

### Answers and plans you can actually read

Most agent output is a wall of text. This puts the verdict first and the ask where you can find it.

- [Voice stances](primitives/stances/voice): Choose answer-card or scannable. Same content, shaped for how you read.
- [Scannable output style](claude/output-styles/scannable.md): Verdict first, action items in one place, and status in plain words: Fixed, Partially fixed, Not fixed, Unverified.
- [Review Card plans](primitives/skills/plan-authoring): Every plan opens with a one-screen card and stops at a build gate until you say build.
- [Bounded subagent returns](primitives/skills/transcript-hygiene): Subagents come back with findings and a word cap, not their whole transcript.
- [Conciseness rules](primitives/rules/conciseness.md): Explain a decision once. Comments say why, not what.

### Your opinions, as switches

Reasonable developers disagree about testing, autonomy and how much to delegate. So none of that is
hardcoded. They're stances, and you flip them.

- [Stance dimensions and variants](primitives/stances): Autonomy, delegation, testing, cost, voice, commits, planning, licensing and build versus buy.
- [User, project, session](docs/preferences.md): Set a default, override it for one repo, override that for one session.
- [Write your own](docs/primitive-authoring.md): A new stance dimension is a folder of Markdown files. No fork needed.
- [See one switch end to end](docs/stance-demo.md): The demo flips delegation and shows what changes in both runtimes.

### Guardrails that leave room for judgment

Hooks handle the few things that should be deterministic. Everything else stays the agent's call.

- [Graded shell commands](claude/hooks/grade-bash.py): Every command is graded from read-only to irreversible, and your autonomy stance decides which grades stop and ask.
- [Autonomy stances](primitives/stances/autonomy): Decide how far an agent goes before it checks in.
- [Stop gate](claude/hooks/stop-gate.py): The turn doesn't end while your repo's own gate is red.
- [Secrets and personal data](primitives/rules/secrets.md): Lint catches tokens, keys and personal strings before they're committed.
- [Untrusted tool output](claude/hooks/neutralize-tool-output.py): Text that comes back from a tool is data, never instructions.
- [Sandboxing](docs/sandboxing.md): Fence the filesystem and network before you leave a loop unattended.

### One way of working, every provider

I started in Cursor, moved to Claude Code, added Codex, and kept rebuilding the same setup. Now it's
defined once and projected into each one.

- [Shared primitives](docs/sync-model.md): Rules, skills, roles and workflows live in one place and sync into each runtime's native settings.
- [Same policy on both](docs/runtime-controls.md): A Claude Code spawn and a Codex spawn resolve to the same delegation policy.
- [Capability classes](docs/role-workers.md): frontier, strong, standard, light. Each adapter maps them to its own models.
- [Honest compatibility](docs/compatibility.md): The catalog says which clients are qualified and where the gaps are.
- [Reversible](docs/settings-ownership.md): Sync has a dry run, diff shows drift, and uninstall restores what it adopted.

### A delivery loop, not just a prompt

Five commands take a piece of work from a question to a reviewed pull request, with fresh eyes at
the review step.

- [The ritual](primitives/workflows): /research, /plan, /build, /review, /handoff.
- [Named roles](claude/agents): Builder, planner, reviewer, gatherer, designer and more, each with its own model class and tool limits.
- [Fresh-context review](claude/agents/reviewer.md): Scope is checked against the ask, then quality, by agents that never saw the code being written.
- [A worktree per agent](primitives/skills/worktree-per-agent): Parallel agents don't step on your checkout or on each other.
- [Testing and commit stances](primitives/stances/testing): Tests required, Conventional Commits, gated pushes. Or switch them.
- [Planning in public](docs/bmad.md): The brief, architecture and stories are in the repo.

### On the way

Planned, not promised.

- **Grok and Cursor adapters:** Grok is next.
- **Fresh-session nudge:** A heads-up when the orchestrator's context has become expensive to keep dragging forward.
- **Budget nudges mid-run:** Today a subagent learns its budget in the brief. Next it hears about it while it works.
- **Jev judgment checks:** Small, bounded checks for the calls a deterministic hook can't make.
- **Architecture viewer, out of preview:** A plan as the front door to a live supervision surface.

## Preferences you can switch

A **stance** is a named choice about how you want an agent to work. Useful defaults ship with the
harness; each choice can be changed independently, and you can add your own dimensions.

| Preference | Choices included today |
| --- | --- |
| Autonomy | `execute`, `confirm-writes`, `ask` |
| Delegation | `tiered`, `session-model`, `off` |
| Testing | `required`, `pragmatic`, `off` |
| Cost posture | `frugal`, `balanced`, `max` |
| Reply shape | `scannable`, `answer-card`, `off` |
| Plan ceremony | `review-card`, `light` |
| Commits | `conventional-attributed`, `conventional`, `as-you-go`, `off` |
| Licensing | `permissive-commercial`, `open-source`, `off` |
| Build versus buy | `capability-ceiling`, `off` |

Some stances are advisory instructions. Others also select implemented hooks or native settings.
`bin/harness stances --json` shows the resolved choice, adapter mode and qualification status for
each one. A stance never overrides a client's native restriction.

**Useful defaults. Preferences you can change. Primitives you can extend.**

## Try it with runtimes you already have

You need `git`, Python 3.9+, and your own account for every runtime you enable. macOS and Linux are
integration targets. Native Windows is unsupported; WSL2 is unqualified. The harness does not
provide model access.

Clone the `stable` branch, explicitly select the runtimes and editor surface you want managed, then
preview every change. `stable` is always the latest release and a `git pull` on it moves you to the
next one; `main`, which this page shows, is the development trunk and can be ahead of any release:

```sh
git clone --branch stable https://github.com/JakeSelby/agent-harness.git ~/repos/agent-harness
cd ~/repos/agent-harness

bin/harness config set claude.manage true
bin/harness config set codex.manage true
bin/harness config set vscode.manage false

bin/harness sync --dry-run
# Review every proposed link, rendered file, setting and conflict.
bin/harness sync
bin/harness doctor
```

Set either runtime to `false` if you do not use it; neither runtime requires the other. Set
`vscode.manage` deliberately too. Configuration is user-level by default—it is not scoped to the
repository you happen to be in. `sync` installs user defaults; project and session overrides stay
with that invocation and are not persisted into global projections.

If the preview reports an existing unmanaged file, stop and read the conflict. The harness does
not recommend `--adopt` by default. After syncing, start a new client session and accept native hook
trust if prompted. [Start with the full guide](docs/getting-started.md).

## Release status

**Release status:** `0.11.1` is the current stable release. Its shared engine, adapters,
configuration and hook decisions are qualified on the four required Claude Code and Codex CLI
targets listed below.

<!-- harness:compatibility:start -->
**Qualified:** `claude-code-cli-macos`, `claude-code-cli-linux`, `codex-cli-macos`, `codex-cli-linux`.

**Unqualified:** `claude-code-vscode-macos`, `codex-vscode-macos`, `codex-desktop-macos`.

**Planned:** `cursor`, `grok`.
<!-- harness:compatibility:end -->

## See one switch reach both adapters

This transcript was captured with Claude and Codex enabled in disposable configuration homes.
Excerpts are shortened; paths and unrelated stances are omitted.

```console
$ bin/harness config set stances.delegation tiered
stances.delegation = "tiered"  (.../.config/agent-harness/config.json)
run `harness sync` to apply it

$ bin/harness stances --json
"delegation": {
  "variant": "tiered",
  "behavior": "# Delegation stance: tiered models\n\n**Gather with subagents ..."
}
"claude-code": { "delegation": { "mode": "instruction-and-hook", "qualification": "unqualified" } }
"codex":       { "delegation": { "mode": "instruction-and-hook", "qualification": "unqualified" } }

$ bin/harness config set stances.delegation off
stances.delegation = "off"  (.../.config/agent-harness/config.json)

$ bin/harness stances --json
"delegation": {
  "variant": "off",
  "behavior": "# Delegation stance: off\n\nDo not spawn subagents unless the user asks ..."
}

$ bin/harness sync --dry-run
stances: ... delegation=off ...
link  .../claude/rules/harness-stances/delegation.md -> .../primitives/stances/delegation/off.md
codex hooks registered; native hook trust must be accepted in the client
```

What changed here:

- **Generated configuration:** both runtime projections receive the resolved `off` policy after
  `sync`; start a new client session to load changed global instructions.
- **Implemented hook decision:** the shared spawn policy asks before any delegation under `off`, so
  only an explicit user request permits the spawn.
- **Native behavior:** qualification varies by client, as reported above. Projection generation and
  unit tests are not proof that a particular client version loaded or followed the policy.

The complete reproducible example is in the [stance demonstration](docs/stance-demo.md).

## Shared authority, native adapters

```mermaid
flowchart LR
  U[Your config and custom primitives] --> P[Shared primitive catalog]
  P --> C[Claude Code adapter]
  P --> X[Codex adapter]
  C --> CP[Generated instructions, settings and hooks]
  X --> XP[Generated instructions, settings and hooks]
  CP -. qualification varies by client .-> CC[Claude Code clients]
  XP -. qualification varies by client .-> XC[Codex clients]
```

`primitives/` is the authoring authority for rules, stances, skills, roles, workflows and
presentation. `policy/` implements shared lifecycle decisions; `adapters/` translates them into
runtime-specific controls. Paths under `claude/` are generated views or compatibility links, not a
second catalog. Run `bin/harness catalog` for source digests and `bin/harness generate --check` for
projection drift.

Custom prose stances are advisory unless you also implement and register corresponding policy.
The shared [architecture-viewer capability](docs/viewer-integrations.md) is a preview that can
invoke a separately installed implementation from either runtime and keep one pinned session
across them. A local protocol 1 candidate passed process-level harness acceptance. The harness
does not bundle a viewer, and native viewer interaction and distribution/license clearance remain
unverified. Hosted agents and native memory merging are also deferred.

## Cost and measurement

The `cost` stance sets a working posture—effort, fan-out and cache habits—not a hard dollar cap.
Model access remains billed by the provider or covered by a subscription, and there is no claimed
savings benchmark. `bin/harness usage` summarizes available local session measurements, labels
partial data and leaves unavailable metrics unknown. It does not send telemetry to a service.
Read [usage and its limits](docs/usage.md).

Each variant also carries a resolved table—a model class, a reasoning effort and a soft budget for
each shared role and for each of the three work bands—which `bin/harness stances --json` prints.
A subagent brief states the budget its row expects; a subagent past it finishes or returns and says
why, and nothing is truncated. A spawn that names no role is routed to the variant's default band
worker, which is the only way a posture's effort reaches a spawn that named nothing. While a
session runs, a usage feed reports the turn's and each subagent's measured spend against those
budgets. All of it is a working posture and local measurement; none of it is a savings claim.

## Full installation and ownership

If you also want the harness to provision missing tools, use the broader installation path:

```sh
bin/harness init
bin/harness install --dry-run
bin/harness install
bin/harness doctor
```

`install` can install applications and packages as well as synchronize configuration. Review
`bin/harness install --help` first; flags can skip Homebrew, apps, VS Code or Codex. Existing
user-owned files, credentials, model choices, MCP servers and plugins are not silently replaced.

The harness tracks fields and files it owns. `uninstall` restores a previous value only when the
current value still matches what the harness last applied; conflicts and redirected links are
preserved and reported rather than overwritten. See [installation ownership](docs/runtime-installation.md)
and the [sync model](docs/sync-model.md).

## Go deeper

- [Compatibility catalog and qualification contract](docs/compatibility.md)
- [How shared primitives and adapters work](docs/how-it-works.md)
- [All preferences and stance rationale](docs/preferences.md)
- [Author a custom stance, skill, role or workflow](docs/primitive-authoring.md)
- [Runtime controls](docs/runtime-controls.md), [sandboxing](docs/sandboxing.md) and
  [workspaces](docs/workspaces.md)
- [BMad integration and bidirectional task continuation](docs/bmad.md)
- [Contributing](CONTRIBUTING.md) and the [public reference](https://agent-harness.jakeselby.com)

Agent Harness uses the open-source [BMad Method](https://github.com/bmad-code-org/BMAD-METHOD)
to structure public product planning, architecture, delivery and release readiness. BMad is a
trademark of BMad Code, LLC; this project is independent and is not endorsed by BMad Code.

## Verify changes

Installed links may point at the checkout, so contribute from a managed worktree. The repository
gate is:

```sh
python3 bin/harness lint
python3 -m unittest discover -s tests
bin/harness generate --check
```

If the idea of user-owned working preferences across agents is useful, try the dry run, open an
issue with the conflict or missing primitive you found, and consider starring the project.
