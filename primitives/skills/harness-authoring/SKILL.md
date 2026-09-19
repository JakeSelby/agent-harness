---
name: harness-authoring
description: Decide where an instruction belongs and write it there. Use when asked to add, change or remove a rule, skill, instruction, hook, setting or CLAUDE.md line, when asked to "remember" something that should persist beyond this session, or when a correction should apply to future sessions. Routes the change into the agent-harness checkout, a personal file, a repo's own instructions, or auto memory, and runs the sync and lint.
---

# Harness authoring

Every instruction has exactly one right home. This skill finds it, writes there, and keeps the
harness checkout as the source of truth for everything generic.

## Find the checkout and the caller

```bash
python3 - <<'EOF'
import json, pathlib
m = json.load(open(pathlib.Path.home() / ".local/state/agent-harness/manifest.json"))
print(m["repo"])
EOF
git -C "$(…)" remote -v
```

If the manifest is missing, locate or install the harness before editing managed content.
Do not create a second authority in a runtime configuration directory. If `origin` is `<owner>/agent-harness` and you are that owner, you are the
**maintainer**. If `origin` is a fork and `upstream` is the harness, you are a **fork user**.

## The ladder — first match wins

1. **Must run at a lifecycle point regardless of the model's judgment** (a check before every
   commit, a validator after every write) → a hook under `claude/hooks/` plus its entry in
   `claude/settings.template.json`, with a `# harness:<id>` marker in the command.
2. **Changes tool or editor configuration, not behaviour** → an owned key in
   `claude/settings.template.json` or `vscode/settings.owned.json`, and the matching entry in
   `claude/OWNERSHIP.json`.
3. **True of this user only, a secret, or about one project** → never the harness repo. A
   fact about the user goes in `~/.claude/CLAUDE.personal.md` below the marker, or a plain
   file in `~/.primitives/rules/`. A fact about one repo goes in that repo's `AGENTS.md`.
4. **A reasonable user would hold the opposite preference** → a stance variant under
   `primitives/stances/<pref>/<variant>.md`, and a line in `config.example.json` and
   `docs/preferences.md`. Never a core rule.
5. **A procedure with steps, longer than 40 lines, or only needed on a trigger** → a skill
   under `primitives/skills/<name>/SKILL.md`, with a description that says when to use it.
6. **Applies only to some kinds of file** → a rule with `paths:` frontmatter, in the repo it
   applies to.
7. **Short, global, wanted on every turn** → `primitives/rules/<topic>.md`. Check every existing
   rule first; the usual outcome is one sentence folded into an existing file, not a new one.
8. **Otherwise it is a memory, not an instruction** → auto memory for the current project.

A "remember this" request runs the same ladder from the top. A fact about one project or one
machine is auto memory for that project, never the harness. A correction to how the agent
should behave anywhere is a rule or a stance, and you say so before writing it. A fact about
the user is a personal file, outside the repo.

## Tests to apply before writing

- **Rule or skill?** Rules load every session and cost context on every turn for every user.
  Skills load on invocation. When a rule starts growing steps, it wanted to be a skill.
- **Core or stance?** If you can imagine a competent engineer choosing the opposite, it is a
  stance. Licensing, commit style, testing philosophy and autonomy level are stances; "verify
  before you claim it works" is not.
- **Does it duplicate a global rule?** Grep `primitives/rules/` and `primitives/stances/` for the
  topic. Do not restate a policy that lives in a global rule inside a project rule; link it.
- **Is it generic?** No names, no paths under a home directory, no employer, no project. The
  lint will reject it anyway; write it in second person from the start.

## Write, sync, lint, commit

1. Edit under the checkout. Nothing harness-owned is edited under `~/.claude/` directly: those
   paths are symlinks, so the edit would land in the checkout anyway, but going through the
   repo keeps the commit and the lint in the loop.
2. Run `bin/harness generate` for native views and `bin/harness generate --check` to verify them.
   See `docs/primitive-authoring.md` for custom dimensions and native bindings.
   `bin/harness sync` — a new rule file is already live; a new skill, stance or hook needs the
   link or the settings entry.
3. `bin/harness lint` — fails on personal strings and secret patterns.
4. Commit with a Conventional Commit. Then, by who you are:
   - **Maintainer:** every change goes on a branch in a worktree and opens a PR; the `main`
     ruleset requires green checks and a squash merge. Code changes (`bin/harness`, hooks,
     tests) carry a test; content changes are gated by the lint and review.
   - **Fork user:** commit to your fork's `main`, which is your live harness. If the change is
     worth sharing, `git fetch upstream && git rebase upstream/main`, push a branch to the fork,
     and `gh pr create --repo <owner>/agent-harness`.
5. Record in one line where the item went and why, so the placement is auditable.

## Writing rule and comment text: the conciseness examples

`conciseness.md` was cut to its operative lines when the always-loaded context was capped. Its
worked examples live here.

**Explain a decision once.** Pick the single most natural home for a design rationale — usually
the module or class docstring where the thing is defined, or the user-facing doc page for
anything a user needs. Every other file that touches the concept gets a short pointer back, not
a restatement.

```python
# Bad — restates the full rationale in a consuming file
# We chunk at 999 rather than the documented 10,000 limit because early testing
# suggested the endpoint became unreliable above 1,000 records, and because ...

# Good — one line, points at the canonical explanation
# Chunked per `batch_size`; see the class docstring for the API's limits.
```

If a second doc explains the same concept as a first, it links to it.

**Don't narrate what the code already says.** Comments explain a non-obvious *why*. If a comment
would be an accurate one-line summary of the next line of code, delete it.

**Docstrings follow the house pattern.** Match the surrounding style exactly. Read a neighbouring
function before writing a new one. Do not add docstrings purely to satisfy a linter that isn't
running; add them where a user of the public API needs them.

**No private-context references in shipped code.** Code, tests, and docs must stand on their own
to a stranger. No references to planning docs, other repos, internal ticket numbers, or
evaluation notes. Public issue and PR numbers are fine and useful — they are resolvable by any
reader.

**PR descriptions.** Lead with what and why in a few bullets, plus a link to the issue. Fill in
the template's sections and delete none, but keep each short. A long PR description with heavy
heading and bold formatting is harder to review, not more informative. Long explanatory content
belongs in the issue or in `docs/`, referenced from the PR body.

## The always-loaded cap

`claude/CLAUDE.md`, every file in `primitives/rules/`, and the longest variant of every stance
dimension are loaded on every turn of every session. `harness lint` fails when their combined
line count exceeds `ALWAYS_LOADED_CAP` in `bin/harness`. A rule that needs more room than the
cap allows is telling you it wanted to be a skill: keep the operative line resident, move the
rationale, examples and evidence into the skill the rule points at, and leave a one-line pointer
behind. The stance count uses the *longest* variant per dimension, so no configuration a user
can select is ever over the cap.
