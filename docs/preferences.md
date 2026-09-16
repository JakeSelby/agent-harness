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

Env overrides win over the file: `HARNESS_STANCE_LICENSING=open-source`,
`HARNESS_STANCE_COMMITS=off`. At sync time the env value is what gets linked. At session start
the `harness-session.py` hook compares the environment with the synced config and injects one
line of context for any difference, so `HARNESS_STANCE_TESTING=off claude` works for one
session without a re-sync.

The `plan-ceremony` stance also decides whether the plan-card validator hook is registered.

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

## Proposing a new stance or variant

A stance is right when a competent engineer could reasonably want the opposite. Add the
variants under `claude/stances/<name>/`, add the name to `STANCE_NAMES` in `bin/harness`, add
the default to `config.example.json`, add a row here, and add a line to the CHANGELOG.
