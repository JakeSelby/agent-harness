# Synchronization and drift

`harness sync` resolves shared user defaults and projects them into selected runtime homes.
The ownership journal records prior and applied content; the link manifest records destinations.
A process lock prevents concurrent sync or uninstall. Individual writes use atomic replacement.
This is recoverable per-file reconciliation, not an atomic transaction over every client file.

Claude Code receives linked shared rules, selected stance variants, skills and presentation,
generated role/command projections, personal identity and merged settings. Codex receives shared
instructions and identity, shared skills, generated workflow skills and role TOML, hooks, and
structurally merged TOML settings. Neither runtime requires the other's installation.

Custom homes use `CLAUDE_CONFIG_DIR` and `CODEX_HOME`; the shared harness home can use
`HARNESS_HOME`. Project/session overrides do not repoint global files. Native hook trust is
separate from registration and from the harness's repository gate trust.

An unmanaged path is a conflict unless explicitly adopted. A redirected link or user-modified
managed value is preserved and reported. `harness diff` detects missing, redirected or modified
artifacts. Uninstall restores prior values only while the current value matches the last applied
value; it keeps conflicts and their recovery records. User additions outside owned fields survive.

[Installation ownership](runtime-installation.md) gives operational details, and
[settings ownership](settings-ownership.md) identifies the native fields. Re-run sync after adding
skills or roles; generated source views require `harness generate` first. Legacy Claude paths
remain compatibility links, but new authoring belongs under `primitives/`.

Native Windows is unsupported. Hosted clients and symlink-skipping hosts remain unqualified;
there is no supported copy mode. See [compatibility](compatibility.md) for client-specific facts.
