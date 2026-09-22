# Installing shared primitives into agent runtimes

Select targets independently in your user configuration:

```json
{"claude": {"manage": false}, "codex": {"manage": true}, "vscode": {"manage": false}}
```

`bin/harness config set claude.manage false` makes the same change. A Codex-only sync creates
its configuration home even on a fresh machine; it does not require a Claude installation.
`CLAUDE_CONFIG_DIR` and `CODEX_HOME` select nondefault runtime homes. `HARNESS_HOME` isolates
the harness's own configuration and state for fixtures. It is not a native runtime setting.

Codex receives shared instructions and identity, the skill catalog under `~/.agents/skills`,
seven generated role configurations, and five `harness-*` workflow skills. Source generation
and installation do not establish native hook activation, role confinement, or client support.
Runtime qualification is reported separately.

The permission choices express intent through different native controls. Codex `manual` uses
`on-request`, `read-only`, and the user reviewer. `auto` uses `on-request`, `workspace-write`,
and automatic approval review. `bypass` uses `never` with full access and requires the existing
explicit acknowledgement. `inherit` preserves native choices. Codex renamed the reviewer field to
`approvals_reviewer`, and a client drops a spelling it does not know without a word, so sync asks
the installed client which name it accepts — from its own protocol schema, or `--strict-config`,
neither of which starts a model turn — writes that one, and removes the other. A client that
accepts neither gets no reviewer key, a sync notice and a `harness doctor` finding. Native
requirements and live
permission overrides can restrict or supersede defaults; these mappings are not an assertion
that Claude and Codex permission modes are equivalent.

Configuration changes own fields, not whole files. A protected ownership ledger records prior
and last-applied values before replacement. TOML editing preserves unrelated tables/comments;
TOMLKit is bundled unmodified with its MIT notice, so no global Python package install is
required. JSON-with-comments editor files are left unchanged with an explicit diagnostic.

`harness diff` detects modified generated content and owned settings. Uninstall restores prior
values only when they still match the harness's last write; intervening user changes remain
with a conflict report and recoverable ownership state. It never deletes a redirected link.
Concurrent sync/uninstall operations refuse a second writer. Interrupted generated/config
writes retain an intent record that the next sync can reconcile.

Unmanaged instructions and skills require explicit adoption. Adopted Codex instruction text
is included in subsequent projections and restored on uninstall. Existing user-owned files,
MCP/plugin settings, selected model and credentials are not replaced by a default config.

`sync` installs user defaults only. Project and session stance overrides are resolved by the
lifecycle adapter in that invocation; they never repoint global links used by another session.
`HARNESS_PERMISSIONS` is not a way to grant native permissions to a running client. Set a durable
posture through user configuration and sync, or use that client's own permission controls.
Custom Claude configuration homes receive an instruction file importing their own personal file.

Link and adoption intent is journaled before filesystem changes, so an interrupted sync retains
its recovery path. Malformed native JSON/TOML is rejected during preflight. Uninstall preserves
redirected links and occupied restoration destinations, returning a conflict status and retaining
the recovery manifest. It does not overwrite even a dangling user symlink to restore a backup.

## Install from the plugin marketplace

Claude Code can load the projected primitives without a checkout. In a session:

```
/plugin marketplace add JakeSelby/agent-harness
/plugin install agent-harness@agent-harness
```

`.claude-plugin/marketplace.json` lists one plugin whose source is the repository root, so the
install reads `.claude-plugin/plugin.json` and nothing is duplicated between the two manifests.
That manifest carries the skills, the eleven subagent roles, the slash commands and the output
style. Claude Code namespaces them: a plugin skill is `/agent-harness:<name>`.

A marketplace install is a strict subset of `bin/harness install`. It does not give you:

- the ownership journal, `harness diff`, or a restoring `harness uninstall`;
- stance selection — no rules, no `CLAUDE.md` projection, no personal file;
- the Codex projection under `~/.agents/skills` and `~/.codex`;
- hooks, so command grading, the stop gate and the usage feed are all off.

The marketplace path is its own client surface in
[the compatibility catalog](compatibility.md) and is **unqualified**: no native evidence has been
recorded for it. `harness doctor` reports which of the two paths is active.
