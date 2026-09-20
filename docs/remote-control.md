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
