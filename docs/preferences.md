# Preferences

Two kinds of preference exist, and they are configured differently because Claude Code reads
rule text literally: there is no variable substitution inside a rule or CLAUDE.md.

## Identity

The `identity` block of `~/.config/agent-harness/config.json` (`name`, `pronouns`, `role`,
`github`, `timezone`) is rendered into `~/.claude/CLAUDE.personal.md` on every sync. Anything
you write below the `<!-- harness:personal-below -->` marker in that file survives a re-render.
Tracked rules never carry a name; they are written in second person.

Env overrides: `HARNESS_IDENTITY_NAME`, `HARNESS_IDENTITY_PRONOUNS`, and so on.

## Stances

Each stance is a directory of variants under `claude/stances/`; config picks one and `sync`
links it into `~/.claude/rules/harness-stances/<stance>.md`. An `off` variant still links a
one-line file so `/context` shows the choice explicitly.

| Stance | Variants | Default |
| --- | --- | --- |
| `licensing` | `permissive-commercial`, `open-source`, `off` | `permissive-commercial` |
| `build-vs-buy` | `capability-ceiling`, `off` | `capability-ceiling` |
| `commits` | `conventional-attributed`, `conventional`, `as-you-go`, `off` | `conventional-attributed` |
| `plan-ceremony` | `review-card`, `light` | `review-card` |
| `delegation` | `tiered`, `session-model`, `off` | `tiered` |
| `testing` | `required`, `pragmatic`, `off` | `required` |
| `autonomy` | `execute`, `confirm-writes`, `ask` | `execute` |
| `cost` | `frugal`, `balanced`, `max` | `balanced` |

Env overrides win over the file: `HARNESS_STANCE_LICENSING=open-source`,
`HARNESS_STANCE_COMMITS=off`. At sync time the env value is what gets linked. At session start
the `harness-session.py` hook compares the environment with the synced config and injects one
line of context for any difference, so `HARNESS_STANCE_TESTING=off claude` works for one
session without a re-sync.

The `plan-ceremony` stance also decides whether the plan-card validator hook is registered.

## Other surfaces

`"vscode": { "manage": true }` and `"codex": { "manage": true }` in the config file let sync
write the owned VS Code keys and the Codex `AGENTS.md` and config keys. Set either to `false`
to leave that surface alone; Claude Code is always managed.

## Permission posture

`permissions` in config is `inherit` (default: the harness never touches permission mode),
`bypass`, `auto` or `manual`. When set, one knob drives `permissions.defaultMode` in Claude
Code, `claudeCode.initialPermissionMode` and `claudeCode.allowDangerouslySkipPermissions` in
VS Code, and `approval_policy` plus `sandbox_mode` in Codex. Env: `HARNESS_PERMISSIONS`.

**`bypass` is refused unless `permissions_bypass_acknowledged` is `true` in the config file**
(the env override cannot grant it). It turns off every permission prompt and puts Codex in
`danger-full-access` with no sandbox. It is a posture for an isolated personal machine. Never
select it on a machine that touches regulated or customer data, and never carry it into an
organisation's fork of this harness: leave `inherit` and let the organisation's managed settings
decide. `auto` is the right choice for a supervised but low-friction setup.

## The reasoning behind each stance

Stance files carry the preference and its operative bullets only, because they count against the
always-loaded cap. The arguments live here.

**Licensing.** `permissive-commercial` exists to catch the case that does not look like a licensing
question, which is why the trigger is "before incorporating or upgrading any third-party material"
rather than "when a licence looks unclear". Preferred software licences: MIT, BSD-2-Clause,
BSD-3-Clause, ISC, Apache-2.0, 0BSD; preferred content licences: CC0-1.0, CC-BY-4.0 — candidates,
not a substitute for checking the exact version and any bundled material. Excluded without
exception: GPL, AGPL, LGPL, MPL, CC BY-SA and ODbL, plus noncommercial, no-derivatives,
editorial-only, research-only, field-of-use, advertising-credit, time-limited, revocable-at-will
and paid proprietary asset licences. Standalone development tools may use copyleft licences where
merely using them imposes no obligation on your output; check bundled runtime components
separately, and never read that exception as permission to incorporate copyleft code or assets.
"Free download", "royalty-free", "source available" and a marketplace tag are not proof: an
uploader's licence claim alone does not establish ownership, and no game rips, unlicensed copies or
material with suspect rights qualify. Under `open-source`, copyleft qualifies when the project's
own licence is compatible and the obligations are recorded in the manifest.

**Testing.** Under `required`, "build feature X" always means build it, make every existing test
pass, and write tests covering every new capability: tests are part of the definition of done, not
a separate step. There is no circumstance where shipping code without tests is acceptable — not for
speed, not for "simple" changes, not for "I'll add them later", because later never comes.
`pragmatic` asks instead that a test buy something, and that the report say plainly which new
behaviour is untested and why.

**Commits.** `type(scope): summary`, with `feat`, `fix`, `docs`, `chore`, `refactor`, `test` and
`ci` as the usual types. The quality gate runs on `HEAD` in the exact checkout you are about to push, because a
gate run somewhere else proves nothing about what lands. Attribution trailers are how a reader
knows an agent wrote the change, which is why `conventional-attributed` keeps them and
`conventional` drops them. `as-you-go` exists for repos where stale local-only state is pure cost —
planning repos, knowledge bases, dotfiles — and explicitly does not apply to application repos with
a review gate.

**Autonomy.** Set defaults by reversibility and blast radius: a deploy is never autonomous, a local
edit always is. The anti-patterns `execute` rules out: ending with "run this in your terminal:" for
setup you can perform, pasting install or start instructions instead of running them, and asking
"say the word and I'll…" for work you can do in the same turn. An autonomy level granted for one
scope does not extend to the next, so never widen your own permissions or record a governance rule
for yourself unless the user asks.

**Plan ceremony.** `review-card` makes plan mode feel like a design review: the approach in chat, a
link to the plan file, an explicit build gate, then autonomous implementation. The card is a review
document before it is an execution document — length below it is free, length above it is the
defect — and a hook validates it on every write. Skip the ceremony only if the user explicitly asks
for a quick plan or says to just exit plan mode. `light` drops the file and the validator but keeps
the explicit go-ahead.

**Build versus buy.** The user has heard the maintenance-burden argument and rejects its premise:
code is cheap now, and an agent-assisted person can maintain custom code fine in three years.
Capability ceilings are the argument class that decides.

**Cost.** `cost` governs how much you spend, never which model: agent definitions carry model ids.
`frugal` runs the session at low effort outside design and adversarial review, keeps subagents to
gatherers with a fan-out of three, never turns on fast mode, and ends a task with `/clear`.
`balanced` is the shipped default — medium effort, fan-out of six, fast mode off unless asked.
`max` spends the model's default effort, fans out as widely as the task needs, and allows fast mode
and compaction. How it meets the tier decision is in the `delegation-tiering` skill.

**Delegation.** The evidence for the tier bands, the cost-per-solved-task numbers and the
boundaries where they stop holding are in the `delegation-tiering` skill, not here.

## Proposing a new stance or variant

A stance is right when a competent engineer could reasonably want the opposite. Add the
variants under `claude/stances/<name>/`, add the name to `STANCE_NAMES` in `bin/harness`, add
the default to `config.example.json`, add a row here, and add a line to the CHANGELOG.
