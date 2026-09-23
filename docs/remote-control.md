# Remote Control servers

This page describes a Claude Code adapter feature for macOS. Codex has no equivalent.

Claude Code's `/remote-control` shares one running session with the mobile app and
claude.ai/code. Starting a *new* session from the phone needs `claude remote-control` running as
a server in the folder, and one server serves one folder. `harness remote-control` keeps one
server per configured folder alive under launchd, so the folders are reachable after a reboot
with no terminal open.

## Configure

Add the folders to the user configuration, then install:

```json
"remote_control": {
  "folders": ["~/repos/project-one", "~/repos/project-two"],
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

- **`spawn`** is passed to `--spawn`. `worktree` gives each phone-started session its own git
  worktree, so two sessions never share a checkout; `same-dir` and `session` are Claude Code's
  other modes.
- **`permission_mode`** is passed to `--permission-mode` and applies to every session the server
  starts. The server is reachable from any device signed in to your account, so choose it as
  you would for an unattended session.
- **`keep_awake`** wraps the server in `caffeinate -is`. That holds idle sleep, and system sleep
  on AC power. Nothing keeps a laptop awake with the lid closed.

Re-run `install` after changing the block. An agent whose definition is unchanged is left
running, because reloading it would cut off the sessions its server is carrying.

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

## Sessions that were lost anyway: `status`

`harness remote-control status` asks the account which sessions are still `active` with a
`disconnected` bridge on an environment this Mac registered, and prints the reattach command for
each. It does not run them. A `claude remote-control --session-id <id>` host registers the lost
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
