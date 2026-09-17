# Settings ownership

`claude/OWNERSHIP.json` is the contract for what `harness sync` may write. Read it before
changing the template.

## Claude Code (`~/.claude/settings.json`)

- **Owned keys**: `outputStyle`, `plansDirectory`, `useAutoModeDuringPlan`,
  `showThinkingSummaries`. Set to the template's values on every sync.
- **Posture key**: `permissions.defaultMode`, written only when config `permissions` is not
  `inherit` (`bypass` → `bypassPermissions`, `auto` → `auto`, `manual` → `default`).
- **Allow rules**: the template's list is merged as a set into `permissions.allow`. The list is
  what lets plan mode run read-only commands without prompting: reads anywhere under home,
  read-only shell tools the built-in set misses, read forms of `gh`, `npm`, `cargo`, `uv`,
  `WebSearch`, and documentation and registry domains for `WebFetch`. Rules you added yourself
  are kept. A rule that an earlier template carried and the current one has dropped is removed
  at the next sync, so a rule withdrawn here does not outlive it in your settings. Tools whose
  read-only form depends on their flags (`sort`, `sed`, `awk`, `fd`, `rg`, `tree`) are not in
  the list; the `readonly-bash` hook approves their safe invocations and lets `sort -o`,
  `sed w`, `fd -x` and the like fall through to the prompt.
- **Hooks**: nine entries carrying `# harness:<id>` markers — `readonly-bash`,
  `filter-output`, `plan-webfetch` and `tier-spawns` (PreToolUse), `plan-card` (PostToolUse, only under the
  `review-card` plan ceremony), `neutralize` (PostToolUse), `session` (SessionStart),
  `stop-gate` (Stop), `usage-log` (SessionEnd). `claude/OWNERSHIP.json` lists them under
  `hook_ids`; that list is the one to read, and this page follows it.
- **Never touched**: `model`, `theme`, `viewMode`, `effortLevel`, `alwaysThinkingEnabled`,
  `skipDangerousModePermissionPrompt`, `env`, `permissions.deny`, `permissions.ask`, and any
  key not named here.

## VS Code (user `settings.json`)

- **Owned**: `claudeCode.focusView`, `claudeCode.preferredLocation`, `claudeCode.hideOnboarding`.
- **Posture**: `claudeCode.initialPermissionMode`, `claudeCode.allowDangerouslySkipPermissions`.
- Everything else, including editor, terminal and theme settings, is left alone.

## Codex (`~/.codex/config.toml`)

- **Owned**: `project_doc_fallback_filenames = ["CLAUDE.md"]`.
- **Posture**: `approval_policy` and `sandbox_mode`.
- **Generated**: `~/.codex/AGENTS.md`, recognised by its first-line banner.
- Model, reasoning effort, notify hooks, MCP servers, plugins and per-project trust are never
  touched.

## Adding an owned key

Add it to the template, to `OWNERSHIP.json`, to this page, and to a test in
`tests/test_harness.py` that shows a user's value for a non-owned key survives the merge.
