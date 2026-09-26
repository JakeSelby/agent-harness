# Synchronization and drift

`citizen sync` resolves shared user defaults and projects them into selected runtime homes.
The ownership journal records prior and applied content; the link manifest records destinations.
A process lock prevents concurrent sync or uninstall. Individual writes use atomic replacement.
This is recoverable per-file reconciliation, not an atomic transaction over every client file.

Claude Code receives linked shared rules, selected stance variants, skills and presentation,
generated role/command projections, personal identity and merged settings. Codex receives shared
instructions and identity, shared skills, generated workflow skills and role TOML, hooks, and
structurally merged TOML settings. Neither runtime requires the other's installation.

Sync honours the switch kinds of [the selection document](preferences.md#the-selection-document).
A rule, skill, workflow or role the user's layers switch `off` is absent from both runtimes: no
rule link and no section in the Codex `AGENTS.md`, no skill link in either skills home, no command
and no generated Codex skill, no agent definition in either home, and the spawn hook never routes
to an `off` band worker. A projection an earlier sync made is retired on the next one, and `harness
diff` reports a switch changed since the last sync. The repository's rules are linked one file at
a time into the real directory `~/.claude/rules/harness/`; the single directory link releases
before 0.14.0 made there is migrated on the next sync, with its prior and applied states journaled
in the link manifest, and uninstall removes the directory once its links are gone. `harness
selection` reports the always-loaded line count of the selection in force; the lint cap still
counts the worst case over every selection.

Every root in `primitive_roots` is projected too, after this repository's own and in
configuration order, with names sorted inside each root. A root's rules are linked into
`~/.claude/rules/harness-roots/<root>/` and rendered into the Codex `AGENTS.md` behind a comment
naming the root they came from; its skills are linked beside the repository's in both runtimes.
The name-collision check runs across the repository and every root before anything is written,
so no root can shadow another silently. The link manifest records the root each link came from,
which is what lets `citizen diff` name the root to fix and `citizen uninstall` take back exactly
what it adopted; a rule a root stops carrying has its link retired on the next sync. A root the
configuration names but the disk does not carry is one warning and a skip, not a failed sync.

Custom homes use `CLAUDE_CONFIG_DIR` and `CODEX_HOME`; the shared harness home can use
`HARNESS_HOME`. Native hook trust is separate from registration and from the harness's repository
gate trust.

## Project and session stance selections

Sync projects only your user-level selection, so the linked stance text is the one your last sync
resolved. A project selection (`HARNESS_PROJECT_CONFIG`) or a session one (`HARNESS_STANCE_*`,
`HARNESS_SESSION_CONFIG`, `HARNESS_MODE`) never repoints those global links. Instead, the
session-start hook resolves the full ladder with `citizen stances --json` and, for each dimension
whose variant differs from the one the sync manifest records, adds that variant's text to the
session's context as an "Effective session stance" line that replaces the linked variant for that
session. Hooks read the same resolution at run time, so the prose you follow and the switches the
hooks act on agree.
`citizen diff` compares the links against your user-level selection, so a project or session
selection is not drift; it says so when one is set.

The injection costs context only when a selection differs; a session with no selection, or one
that matches the synced variants, pays nothing. What it injects is re-read on every turn, like the
always-loaded layer, so it shares that layer's budget: the token cap `citizen lint` enforces, less
what the sync already made always-loaded (the instructions, the rules it linked and the linked
stance variants). Each differing dimension is always named. Its text is included in dimension order
while it fits what is left; a variant that does not fit is named with the path of its file and an
instruction to read and follow it, so a long custom variant degrades to a pointer rather than
overrunning the budget. The `custom-stance` qualification case observes both a project and a
session selection natively.

An unmanaged path is a conflict unless explicitly adopted. A redirected link or user-modified
managed value is preserved and reported. `citizen diff` detects missing, redirected or modified
artifacts. Uninstall restores prior values only while the current value matches the last applied
value; it keeps conflicts and their recovery records. User additions outside owned fields survive.

[Installation ownership](runtime-installation.md) gives operational details, and
[settings ownership](settings-ownership.md) identifies the native fields. Re-run sync after adding
skills or roles; generated source views require `citizen generate` first. Legacy Claude paths
remain compatibility links, but new authoring belongs under `primitives/`.

Native Windows is unsupported. Hosted clients and symlink-skipping hosts remain unqualified;
there is no supported copy mode. See [compatibility](compatibility.md) for client-specific facts.
