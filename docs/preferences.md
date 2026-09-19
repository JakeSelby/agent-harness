# Preferences

Two kinds of preference exist, and they are configured differently because Claude Code reads
rule text literally: there is no variable substitution inside a rule or CLAUDE.md.

## Identity

The `identity` block of `~/.config/agent-harness/config.json` (`name`, `pronouns`, `role`,
`github`, `timezone`) is rendered into `~/.claude/CLAUDE.personal.md` on every sync. Anything
you write below the `<!-- harness:personal-below -->` marker in that file survives a re-render;
that is also where a personal writing-voice profile belongs.
Tracked rules never carry a name; they are written in second person.

Env overrides: `HARNESS_IDENTITY_NAME`, `HARNESS_IDENTITY_PRONOUNS`, and so on.

`expertise` is `expert` (the default, and what every config that predates the field resolves to)
or `beginner`. It selects one paragraph of the personal file: `expert` skips fundamentals,
`beginner` says what each step and command does, defines terms on first use, and assumes no prior
knowledge of programming, version control or the command line. It is the only identity field that
changes behaviour rather than describing you.

`harness init` writes the whole file by asking, and `harness config set identity.name "…"`
changes one field. Neither needs an editor. Until `name`, `role` and `github` differ from the
example file, `sync` and `doctor` both say so: what they hold is what the agent believes about
you, so a config left unedited has it addressing you by the placeholder. `pronouns` and
`timezone` are never reported, because `they/them` and `UTC` are answers someone might mean.

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
| `voice` | `scannable`, `answer-card`, `off` | `scannable` |

`harness config set stances.testing off` checks the variant exists before writing, and names
the options when it does not.

### Presets

The defaults above are a professional software workflow, and escaping it meant finding five
separate opt-outs. `harness init` asks what the work is and uses a preset as the defaults for the
questions that follow; every stance is still asked, so a preset is a starting point, not a lock.

| Preset | Changes from the defaults |
| --- | --- |
| `software` | nothing; the table above |
| `general` | `licensing: off`, `build-vs-buy: off`, `commits: off`, `testing: off`, `plan-ceremony: light` |

`general` is for work that is not shipping software — writing, research, organising files, a
personal script. It leaves `delegation`, `autonomy` and `cost` alone, because how work is spread,
how far it runs unattended and what it costs are the same questions whatever the work is.

The topic rules are not switchable and do not have presets; a rule about repositories, tests or
pull requests simply does not apply when the task is not code work, and the always-loaded preamble
says so.

Env overrides win over the file: `HARNESS_STANCE_LICENSING=open-source`,
`HARNESS_STANCE_COMMITS=off`. At sync time the env value is what gets linked. At session start
the `harness-session.py` hook compares the environment with the synced config and injects one
line of context for any difference, so `HARNESS_STANCE_TESTING=off claude` works for one
session without a re-sync.

The `plan-ceremony` stance also decides whether the plan-card validator hook is registered.

## What a session costs

Every turn spends tokens against your plan's limit, and the ones that fan work out to several
subagents spend several times as much: `/research` and `/build` are the expensive commands, and a
wide review is the expensive habit.

The `cost` stance is the dial. `frugal` keeps fan-out narrow and effort low, `balanced` is the
default, `max` spends freely on hard problems. It sets how much; the `delegation` stance sets what
gets delegated and to which model tier. `HARNESS_STANCE_COST=frugal claude` applies it to one
session.

`harness usage` summarises what sessions have actually spent, from a local file with no network
call — see [usage.md](usage.md).

## Other surfaces

`"vscode": { "manage": true }` and `"codex": { "manage": true }` in the config file let sync
write the owned VS Code keys and the Codex `AGENTS.md` and config keys. Set either to `false`
to leave that surface alone; Claude Code is always managed.

## Permission posture

`permissions` in config is `inherit` (default: the harness never touches permission mode),
`bypass`, `auto` or `manual`. When set, one knob drives `permissions.defaultMode` in Claude
Code, `claudeCode.initialPermissionMode` and `claudeCode.allowDangerouslySkipPermissions` in
VS Code, and `approval_policy` plus `sandbox_mode` in Codex. Session environment values do not grant native permissions or mutate global configuration.

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
for yourself unless the user asks. The `grade-bash` hook enforces the stance: it grades every
shell command 0–3 and gates at grade 3 under `execute`, 2 and up under `confirm-writes`, 1 and up
under `ask`; [how-it-works.md](how-it-works.md#command-grades) explains the grades and the modes.

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

**Voice.** `voice` governs how a reply is laid out, and nothing about what the work is. `scannable`
defers to the Scannable output style: verdict first, registers separated, at most one table.
`answer-card` is for reading on a phone — the answer in the first line, then why, the catch, and the
alternatives, about 150 words, no tables, with the reasoning left in the file it links rather than
re-argued in the message. It wins over the output style where the two differ. `off` imposes no shape
at all. A personal voice profile is different: it tells the agent how to draft in the user's name
and stays in the untracked personal file. The rule keeps only what no variant changes: a subagent
inherits no voice, so its brief has to carry the output shape itself.

**Delegation.** The evidence for the tier bands, the cost-per-solved-task numbers and the
boundaries where they stop holding are in the `delegation-tiering` skill, not here. The
`tier-agent-spawns` hook enforces the chosen variant on spawns that name no agent definition:
one tier down under `tiered` (the session model inside a framework repo), untouched under
`session-model`, a prompt under `off`.

## Proposing a new stance or variant

A stance is right when a competent engineer could reasonably want the opposite. Add the
variants under `claude/stances/<name>/`, add the name to `STANCE_NAMES` in `bin/harness`, add
the default to `config.example.json`, add a row here, and add a line to the CHANGELOG.

## What is deliberately not a stance

The always-loaded rules in `claude/rules/` do not switch. A rule has to hold whichever way every
stance is thrown, which is what lets the harness install for someone whose preferences nobody
knows. Apply the same test in reverse before adding one: if a competent engineer could reasonably
want the opposite, it belongs in `claude/stances/`, not `claude/rules/`.

Two rules do not pass that test yet, tracked rather than hidden. `voice-and-format.md` hard-wires
the Scannable output style (#68), and `conciseness.md` is comment and doc style. `cache-hygiene.md`
is cost-dimension content the `cost` stance already points at.

## Extend your choices

Stances are custom harness primitives, not native provider features. Add dimensions, variants and
constraints through [the authoring contract](primitive-authoring.md). Inspect effective selections
and adapter coverage with `harness stances --json`; native restrictions remain authoritative.
