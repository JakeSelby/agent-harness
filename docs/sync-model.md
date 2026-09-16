# Sync model

`harness sync` is idempotent and records everything it does in
`~/.local/state/agent-harness/manifest.json`. It never replaces a file it did not create.

## Links

| Live path | Target | Kind |
| --- | --- | --- |
| `~/.claude/CLAUDE.md` | `claude/CLAUDE.md` | file link |
| `~/.claude/rules/harness` | `claude/rules/` | directory link; rules are discovered recursively, so a new rule file is live at once |
| `~/.claude/rules/harness-stances/<pref>.md` | `claude/stances/<pref>/<variant>.md` | one file link per stance; re-pointed when config changes |
| `~/.claude/skills/<name>` | `claude/skills/<name>/` | one directory link per skill; a new skill needs a sync |
| `~/.claude/hooks/harness` | `claude/hooks/` | directory link |
| `~/.claude/output-styles/scannable.md` | `claude/output-styles/scannable.md` | file link |

Personal files (`~/.claude/rules/*.md`, `~/.claude/skills/<yours>/`) are siblings of the links
and are never touched.

## When a path is already taken

- A symlink to the expected target: fine, recorded.
- A symlink elsewhere, or a real file or directory: reported, not replaced. Run
  `harness sync --adopt` to move it to `~/.local/state/agent-harness/pre-harness/` (recorded in
  the manifest, restored by `harness uninstall`).
- A plain file with the same name as a rule or hook the harness now supplies (for example a
  hand-copied `~/.claude/rules/delegation.md`): it would load twice, so `--adopt` moves it
  aside too.

## Settings merge

`claude/settings.template.json` is merged into `~/.claude/settings.json`:

- Keys in `OWNERSHIP.json → claude.owned_keys` are set to the template's values.
- `permissions.allow` is a set union: template rules are added, your rules stay.
- Hook entries are recognised by the `# harness:<id>` marker in their command (and, once, by
  the script basename for hand-installed copies), replaced in place, and dropped when the stance
  that owns them is not selected.
- `permissions.defaultMode` is written only when the `permissions` knob in config is not
  `inherit`.
- Everything else, including `model`, `theme` and unknown keys, is left exactly as found.

The write is read-modify-write to a temp file with an atomic replace, a `.bak` copy, and an
abort if the file's mtime moved while the merge ran. The applied projection is saved to
`~/.local/state/agent-harness/applied.json` so `harness diff` can tell a live-side change from a
pending template change.

## Other surfaces

- **VS Code** — `vscode/settings.owned.json` is merged the same way into the user settings
  file, with the posture keys added when the knob is set. A settings file with comments is left
  alone with a warning.
- **Codex** — `~/.codex/AGENTS.md` is generated: the global instructions, every rule, every
  chosen stance, then the contents of `~/.codex/AGENTS.personal.md`. A hand-written file is
  never overwritten; `--adopt-codex` moves it to `AGENTS.personal.md` once. Owned keys in
  `~/.codex/config.toml` are added or updated in place.
- **Global git ignore** — `.claude/plans/` and `.design-loop/` are appended when missing.
- **PATH** — on macOS with zsh, `~/.local/bin` is added to `.zprofile` if nothing mentions it,
  because the Claude Code native launcher lives there.
- **Pre-commit hook** — `git config core.hooksPath .githooks` is set on the harness checkout,
  so every commit there runs `bin/harness lint --staged` first.

## Cowork and other symlink-skipping hosts

Desktop Cowork sessions skip a symlinked user `CLAUDE.md` and symlinked rule files. A copy
mode (`harness sync --copy`) is the planned answer; until then those sessions see no harness.
