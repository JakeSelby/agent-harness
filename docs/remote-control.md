# Remote Control servers

This page describes a Claude Code adapter feature for macOS. Codex has no equivalent.

Claude Code's `/remote-control` shares one running session with the mobile app and
claude.ai/code. Starting a *new* session from the phone needs `claude remote-control` running as
a server in the folder, and one server serves one folder. `harness remote-control` keeps one
server per configured folder alive under launchd, so the folders are reachable after a reboot
with no terminal open.

Serve each workspace root from its own entry. A host runs with its folder as the working
directory, so every session it starts loads that folder's `CLAUDE.md`, skills and hooks; one host
for a parent directory of several repositories loads none of theirs.

## Configure

Add the folders to the user configuration, then install:

```json
"remote_control": {
  "folders": [
    "~/repos/project-one",
    {"path": "~/repos/notes", "spawn": "same-dir", "env": {"EXAMPLE_FLAG": "1"}}
  ],
  "spawn": "worktree",
  "permission_mode": "default",
  "keep_awake": false
}
```

```sh
harness remote-control install [--dry-run]   # one launchd agent per folder; drops agents for removed folders
harness remote-control status                # launchd state and log path per folder
harness remote-control uninstall             # unload and remove every agent
```

- **`folders`** entries are a path, or an object with a `path` and optionally its own `spawn`,
  which overrides the block's, and `env`, string names to string values added to that host's
  launchd environment. The launchd label is derived from the path alone, so switching an entry
  between the two forms keeps its agent.
- **`spawn`** is passed to `--spawn`. `worktree` gives each phone-started session its own git
  worktree, so two sessions never share a checkout; `same-dir` and `session` are Claude Code's
  other modes. A folder that is not a git repository needs `same-dir`.
- **`permission_mode`** is passed to `--permission-mode` and applies to every session the server
  starts. The server is reachable from any device signed in to your account, so choose it as
  you would for an unattended session.
- **`keep_awake`** wraps the server in `caffeinate -is`. That holds idle sleep, and system sleep
  on AC power. Nothing keeps a laptop awake with the lid closed.

Re-run `install` after changing the block. An agent whose definition is unchanged is left
running, because reloading it would cut off the sessions its server is carrying.

The host runs without `--no-create-session-in-dir`. Claude Code 2.1.280 reads the folder's
bridge pointer, and so reuses the environment on a relaunch, only while `createSessionInDir` is
on; with the flag, every restart registered a new environment. The cost is the one session each
host pre-creates in its folder, which is reused across restarts while the pointer is fresh.

A host that reused an environment at start keeps its sessions and its environment when it is
stopped with `SIGTERM`. One that did not — the first host after an upgrade, or after a pointer
expired — archives every session and deregisters its environment on `SIGTERM`. So a changed
agent whose host is running is *adopted* rather than replaced: `install` reads the environment
from the host's log, writes the folder's pointer for it with no pid, sends `SIGKILL` to the
`claude` process, which skips the shutdown path, and then reloads the agent, whose new host
reuses the environment. `--dry-run` names the environment it would adopt.

Restart a host only with `harness remote-control install`, never `launchctl kickstart -k`: that
sends `SIGTERM`, and a host that did not reuse its environment archives its sessions on it.

## Keeping sessions across a restart: `heal`

A server that loses the network for ten minutes gives up, archives every session it was
carrying and deregisters its environment; launchd then starts it again as a *new* environment
that adopts nothing, and the chats open on your phone are gone. Claude Code can re-adopt the old
environment — it asks the server to reuse the id in the folder's
`~/.claude/projects/<slug>/bridge-pointer.json` — but only while that file is younger than its
four-hour TTL and names a pid that is no longer running, and a server that started without a
pointer never writes one. `harness remote-control heal` closes that gap: once a minute it reads
each running agent's live environment id from its log and rewrites the folder's pointer with it,
so a relaunch asks for the environment the sessions are actually on. `--dry-run` reports without
writing, `--once` is the single pass the `com.agent-harness.remote-control-heal` agent runs, and
`--preserve-worktrees` WIP-commits any dirty `bridge-cse_*` worktree first, so nothing unpushed
can be deleted by a cleanup. Actions are appended to
`~/.local/state/agent-harness/remote-control/heal.log`, and `status` reports the last one.
Heal does not rescue an environment the give-up path already deregistered: reuse is refused once
the environment is gone, and so is the bridge reconnect endpoint.

## Stopping a host before it gives up

The ten-minute give-up is hardcoded in Claude Code and its path is destructive, so the fix is to
never reach it. Each pass reads the host's log for the trailing run of
`Connection error, retrying in 2m (541s elapsed)` lines — the host prints its own error-budget
age, so it is read rather than timed — and at nine minutes sends one `SIGTERM` to the host's
`claude` process, the child when `keep_awake` wraps it in `caffeinate`. launchd's `KeepAlive`
starts it again within the throttle interval, and it registers asking to reuse the environment in
the pointer heal has just refreshed. The stop fires once per host process: the relaunched host has
a new pid and gets its own. A `Detected system sleep (Ns gap), resetting error budget` line, and a
`Reconnected after Ns` line, both end the run, because the host restarts its budget there too.

If the host gave up before the supervisor reached it, its log names the session worktrees the
cleanup deleted. Heal recreates each at its path, attaching the branch when it survived and
branching from the default branch when it did not, so a session picked up by a later lease has its
directory. A worktree the host `kept … · uncommitted changes` is left alone, and every line is
acted on once.

## Reconnecting sessions: `heal`

After its per-folder pass, heal reads the account's sessions once and, for each one still
`active` with a `disconnected` bridge on an environment this Mac holds — any environment a
host's log names, plus the one in each configured folder's pointer — calls
`POST /v1/environments/<env>/bridge/reconnect`, which puts the session back in its environment's
queue for the host to pick up. Each attempt is one `reconnect <session> on <env>: <status>` line
in the heal log, a session is tried at most once every ten minutes, `--dry-run` sends nothing,
and a missing token or a failed call never stops the pass. An archived session is not touched:
unarchiving needs more than the login token, so it stays a manual step.

## Sessions that were lost anyway: `status`

`harness remote-control status` asks the account which sessions are still `active` with a
`disconnected` bridge on an environment this Mac registered, and prints the reattach command for
each, for any session heal could not reconnect. It does not run them. A
`claude remote-control --session-id <id>` host registers the lost
environment a *second* time, as a single-session environment, and the client then routes new chats
to it — recovering five sessions that way leaves five stray environments competing for new work,
and in 2.1.278 each host binds to the session the previous one was asked for rather than its own
`--session-id`. So the recovery stays a deliberate, one-at-a-time act: run the command from an
unused directory, let the session answer, and stop that host.

The read is capped at fifty sessions and the endpoint takes no sort parameter, so the page is
checked on arrival: it must be newest-first by `last_event_at`, the field the server orders by.
A page that is not reads as `not checked (page order unknown)` rather than as an account with
nothing lost, and when the account holds more sessions than one page the count says `in the
newest 50`.

The claude.ai token is read from the login keychain for the duration of the call and is never
printed, logged or written anywhere.

`harness doctor` reports the same ground per configured folder: whether the host process is alive,
which environment it registered, whether the pointer names that environment and that pid, how long
it has been unreachable, and how many of its sessions are disconnected.

## Files an agent sends you

In a Remote Control session, `SendUserFile` uploads nothing. The app keeps the file's path and
asks the session for the file when you open it, and Claude Code serves it only from under the
directory the session started in, which is the session's worktree under `spawn: worktree`, or a
directory added to the session. Most other paths fail in the app with "Couldn't load this file".
Reports, renders and screenshots are routinely written somewhere else: a temp or scratch
directory, a task worktree, or the main checkout seen from a session's worktree.

The `stage-user-files` policy closes that gap in every Remote Control session the harness hooks
run in, whether a host here started it or not. Before `SendUserFile` runs, each file from outside
the session's current working directory is copied to `.agent-harness/outbox/<digest>/<name>`
there, and the call sends the copy instead; a `stage-user-files: copied …` notice says when that
happened. The outbox ignores itself in git, so in a repository a copy never reaches `git status`,
a commit or the lint, and a copy untouched for two weeks is removed the next time a file is
copied. One call copies at most 64 MiB in about four seconds; a file past either limit, or one
that cannot be copied, is sent from where it is, with a notice.

The app still reads the file from the session when you open it, so a file sent from a session
whose worktree has since been removed cannot be opened afterwards.

## What it will not do

- **Accept workspace trust for you.** The server refuses a folder whose trust dialog was never
  accepted, and launchd would restart that refusal forever, so `install` refuses the folder and
  exits non-zero with the fix. Trust is per exact directory: a trusted repository does not trust
  its worktrees, and the failure is a host that exits with
  `Error: Workspace not trusted. Please run \`claude\` in <path> first …` every minute. Run
  `claude` in the folder once and accept the dialog. `harness trust` is a different gate — it
  lets the stop-gate hook run a repository's gate — and `install` names it alongside, because a
  folder served unattended usually wants both.
- **Take over a folder already served from a terminal.** Claude Code allows one server per
  folder per device. Stop the terminal server; the agent retries every minute.
- **Sign in.** The server uses the claude.ai login of the account that ran `install`. An API key
  or a cloud-provider credential does not support Remote Control.

Each agent logs to `~/.local/state/agent-harness/remote-control/`. Read the log first when
`status` shows an agent that is loaded but not reachable from the phone.
