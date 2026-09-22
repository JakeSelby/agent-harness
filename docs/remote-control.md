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

## What it will not do

- **Accept workspace trust for you.** The server refuses a folder whose trust dialog was never
  accepted, and launchd would restart that refusal forever, so `install` skips the folder and
  says so. Run `claude` in the folder once, accept the dialog, and re-run `install`.
  `harness trust` is a different gate: it lets the stop-gate hook run a repository's gate.
- **Take over a folder already served from a terminal.** Claude Code allows one server per
  folder per device. Stop the terminal server; the agent retries every minute.
- **Sign in.** The server uses the claude.ai login of the account that ran `install`. An API key
  or a cloud-provider credential does not support Remote Control.

Each agent logs to `~/.local/state/agent-harness/remote-control/`. Read the log first when
`status` shows an agent that is loaded but not reachable from the phone.
