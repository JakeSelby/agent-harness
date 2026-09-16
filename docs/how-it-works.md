# How it works

The harness is a set of files Claude Code already knows how to read, arranged so that the
generic parts live in one git checkout and the personal parts live outside it.

## The layers, in load order

```
~/.claude/CLAUDE.md ─────────────▶ claude/CLAUDE.md          global instructions, delegation, the cap
   └─ @~/.claude/CLAUDE.personal.md                           rendered from config; yours, untracked
~/.claude/rules/harness/ ────────▶ claude/rules/*.md         core rules, every session
~/.claude/rules/harness-stances/ ▶ claude/stances/<p>/<v>.md one chosen variant per preference
~/.claude/rules/*.md                                          your own personal rules, untouched
~/.claude/skills/<name>/ ────────▶ claude/skills/<name>/     procedures, loaded on invocation
~/.claude/agents/<name>.md ──────▶ claude/agents/*.md        subagent definitions, spawned by name
~/.claude/hooks/harness/ ────────▶ claude/hooks/*.py         run at lifecycle points, no judgment involved
~/.claude/output-styles/scannable.md ▶ claude/output-styles/ the shape of every reply
~/.claude/settings.json  ◀ merge ─ claude/settings.template.json  only the keys OWNERSHIP.json names
```

Arrows are symlinks, created by `harness sync`. The one file that is merged rather than linked
is `settings.json`, because Claude Code writes to it too.

## Why each layer exists

- **Rules** are for behaviour you want on every turn: how to read files without flooding the
  transcript, how to present a decision, what counts as verified. Each costs context on every
  turn, so there are nine and they are short.
- **Stances** are rules a reasonable person might hold the other way. Instead of arguing in
  the file, the harness ships variants and you pick one in config. Licensing, commit style,
  testing philosophy, autonomy level, plan ceremony, delegation tiers, build-versus-buy.
- **Skills** are procedures. They cost one line of description until invoked, so they can be
  long: how to write a plan someone can review in one screen, how to run a design loop with an
  independent judge, how to contribute to someone else's repo.
- **Agents** are subagent definitions the harness ships so the delegation tiers are enforced by
  frontmatter instead of by a brief someone retypes: `gatherer` for read-only gathering,
  `reviewer` for fresh-context adversarial review, `log-compressor` for reducing a test or build
  log to its failures. Each carries its model, its effort level and its tool list, and the tool
  list is what makes a read-only agent read-only. Frontmatter `model` beats the
  `CLAUDE_CODE_SUBAGENT_MODEL` environment variable, and a project overrides any of them by
  placing a same-named file in its own `.claude/agents/`.
- **Hooks** are the things that must happen regardless of what the model decides: a validator
  that checks every plan file against the card contract, a classifier that lets read-only shell
  commands through in plan mode, a session-start check for drift and env overrides, and a
  scanner that flags instruction-shaped text in `Bash`, `WebFetch` and `Read` output.

  The scanner is advisory: on a match it appends one line naming the tool and the patterns it
  matched — control tags, "ignore previous instructions", directives addressed to the agent,
  attribution instructions, environment-update mimicry, and edits to settings or permissions —
  and it never blocks a call or rewrites a result. Claude Code already wraps subagent returns in
  a notice of that shape, but the wrapper is built into the tool rather than supplied by a hook,
  so this one mirrors its wording for the tool results that arrive unwrapped. A commit trailer on
  its own does not trip it: `Co-Authored-By` counts only within three lines of wording that tells
  the reader to use it.
- **The output style** is the shape of every reply: verdict first, registers separated, action
  items in one place.
- **Settings** are the tool configuration that makes the above work: hook registrations, a
  read-only allowlist so plan mode does not prompt, the output style selection.

## Filtering verbose output

The `filter-output` hook rewrites a Bash command that runs tests, a build, a lint or a
type-check — `pytest`, `cargo test`, `npm test`, `go test` and their neighbours — so the run
pipes through `claude/hooks/filter-lines.py`, which keeps failures, tracebacks, summary lines
and the last twenty lines and drops the rest; `set -o pipefail` keeps the real exit status. The
rewrite is skipped when the command already pipes to `head`, `tail`, `grep`, `less` or `wc`,
redirects to a file, or passes `--watch`, so piping to `tail -50` yourself is how you see a run
whole — there is no environment switch to turn the filter off. Both scripts live in
`claude/hooks/`, which is linked as a directory, so the hook resolves the filter beside itself
at run time. The hook emits `updatedInput` and no permission decision: the hooks documentation
does not say how two `PreToolUse` hooks on `Bash` combine their output, so this one leaves the
read-only classifier's decision alone.

## What the harness deliberately does not contain

- Anything about one person. Identity is rendered into `~/.claude/CLAUDE.personal.md` from
  config; personal rules sit beside the harness links as plain files.
- Anything about one project. That belongs in the project's `AGENTS.md`; `templates/repo/`
  shows the shape. Its `settings.json` keeps the files an agent must never read out of reach with
  `Read` deny rules, because Claude Code has no ignore file and a deny rule is the mechanism.
- Credentials, MCP server configurations, or anything else that carries a token.
- A planning framework. The harness works with or without one; `docs/bmad.md` records how one
  is kept out of the way.

## The dogfood loop

Because the live paths are symlinks, editing a rule in the checkout changes the next session
with no step. `harness diff` reports the other direction: a setting changed through the tool's
own UI shows as "live-only" so it can be brought back into the repo. The `harness-authoring`
skill routes every "add a rule" request through the checkout, the lint, and a commit, so the
repo never falls behind the live harness.

## The always-loaded cap

`CLAUDE.md`, the nine rules and the selected stances are re-read on every turn of every session,
so their combined size is a standing tax on every task the agent does. `harness lint` enforces a
cap of 200 lines on that set, counting the *longest* variant of each stance dimension so no
configuration a user can select is ever over it. The rules therefore carry operative lines only —
the instruction, stated once, in second person — and each ends with a pointer to the skill or doc
that holds its reasoning, its examples and its evidence. That is progressive disclosure: a skill
costs one line of description until something invokes it, so the detail is available when it is
needed and absent when it is not. When a rule grows past its share of the cap, it is telling you
it wanted to be a skill.

## Rationale relocated from the rules

The sentences below explain rules that now state only the instruction.

- **Never open a PR on unverified work**, because a PR that fails lint burns a reviewer's
  attention on nothing. Record the expected clean-tree output in the repo's agent instructions the
  first time you run the gates: the exact "all checks passed" line, the test count, the known
  benign warning. Then any deviation is yours, and you can tell a pre-existing failure from one
  you caused. Test auth anonymously, with redirects not followed: a test that follows redirects to
  a login page and asserts 200 proves nothing.
- **Reasoned pushback on review comments** means assessing legitimacy against the actual codebase
  first — actionable, already-resolved, banter, or informational — and, when the analysis disagrees
  with a reviewer (especially one phrased as suspicion rather than directive), drafting a reasoned
  rebuttal rather than complying blanket.
- **Provisioning commands are gated, and that gate is not yours to lift.** When a permission
  classifier refuses a deploy or apply command, build and validate everything, run the read-only
  plan or diff, and hand the user the exact commands. Run a wrapper only when the user has named it
  themselves.
- **Escalate sparingly in autonomous loops.** Review rounds are capped at two to three per story;
  the cap is a cap, not a target.
- **"Should work" is not a status**, and when an error is reported you read the actual error and
  the logs before the source — never theorize from the code alone.
- **A secret in a committed file does not become unleaked when you delete it**; history keeps it,
  which is why the credential must be rotated before anything else happens. Agent rule directories
  are the case that rule exists for: they feel private and are not. Read credentials from the
  environment instead:

  ```bash
  # Correct
  curl -H "Authorization: token $SERVICE_TOKEN" ...

  # Wrong — never do this
  curl -H "Authorization: token abc123def456" ...
  ```

  Cloud CLIs resolve credentials from a profile or a secret store; use `--profile` or an
  environment variable, never a pasted key.
