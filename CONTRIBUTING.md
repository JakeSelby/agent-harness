# Contributing

Ideas are as welcome as patches. If a rule, stance or skill here made your agent better or
worse, say so. If you have a fix, send it. This page tells you where things go and how the
review works.

## Two ways to contribute without code

- **An idea** — open an [Idea issue](../../issues/new?template=02-idea.yml) or start a
  [Discussion](../../discussions). Say what you wanted the agent to do, what it did instead,
  and what you tried.
- **A proposed rule, stance or skill** — open a
  [Rule or skill issue](../../issues/new?template=03-rule-or-skill.yml) with the text you have
  in mind and which rung of the ladder below it lands on.

Anything bigger than a typo fix is better discussed first. A PR that arrives after a short
thread almost always merges faster than one that arrives cold.

## The fork → branch → pull request flow

1. Fork and clone:
   ```sh
   gh repo fork JakeSelby/agent-harness --clone --remote
   cd agent-harness
   git remote -v        # origin = your fork, upstream = JakeSelby/agent-harness
   ```
2. Keep `main` on your fork current with upstream, and branch from it:
   ```sh
   git fetch upstream && git checkout main && git rebase upstream/main
   git checkout -b <short-topic>
   ```
3. Make the change. Run the checks (next section).
4. Commit with a [Conventional Commit](https://www.conventionalcommits.org/) message:
   `docs(rules): fold the 403 line into working-style`, `feat(cli): add workspace create`,
   `fix(hook): treat dangling && as unparseable`.
5. Push to your fork and open the PR against `main`:
   ```sh
   git push -u origin <short-topic>
   gh pr create --repo JakeSelby/agent-harness --base main --fill
   ```
6. CI runs the lint and the tests. Fix anything red; the merge button stays disabled until the
   checks pass. Squash merge is the only merge method, and the PR title becomes the commit
   message, so make the title a good Conventional Commit line.

If you use the harness yourself, the `harness-authoring` skill runs steps 2 to 5 for you from
inside a Claude Code session.

## Checks to run before opening a PR

```sh
bin/harness lint                       # no personal strings, no secret patterns
python3 -m unittest discover tests     # merge, link, config and lint logic
bin/harness sync --dry-run             # for content changes: the stance and link plan still resolves
```

CI runs exactly these, and `harness sync` installs `.githooks/pre-commit` in the checkout so
every commit is linted before it exists. The lint is strict on purpose and carries **no list of
real values**: it matches shapes (12-digit account ids, email addresses, home-directory paths,
cloud ARNs, hosted-zone ids, identity-provider tenants, private IPs, secret patterns), derives
the maintainer's name from `LICENSE` and `CODEOWNERS` and forbids it inside installed content,
and reads your own terms (employer, town, hostnames) from the untracked file
`~/.config/agent-harness/lint-terms.txt` (see `lint-terms.example.txt`). A denylist of real
values would itself be a disclosure the moment it was committed; that is exactly what happened
in the first release, and why the design is this way.

## What goes where

Every instruction has one right home. First match wins:

1. **Must run at a lifecycle point regardless of the model's judgment** → a hook under
   `claude/hooks/` plus its entry in `claude/settings.template.json`.
2. **Tool or editor configuration, not behaviour** → an owned key in
   `claude/settings.template.json` or `vscode/settings.owned.json`, listed in
   `claude/OWNERSHIP.json`.
3. **True of one person, one machine, or one project** → not this repository. It belongs in
   that person's `~/.claude/` or that repo's `AGENTS.md`.
4. **A preference a reasonable engineer might hold the other way** → a variant under
   `claude/stances/<pref>/`, plus a line in `docs/preferences.md`. Licensing, commit style,
   testing philosophy and autonomy level are stances.
5. **A procedure with steps, or something only needed on a trigger** → a skill under
   `claude/skills/<name>/SKILL.md` with a description that says when to use it.
6. **Short, generic, wanted on every turn** → `claude/rules/<topic>.md`. Rules cost every user
   context on every turn, so the bar is high; the usual outcome is one sentence folded into an
   existing rule.

## What will not be merged

- Anything personal or project-specific, however good. Put it in your own `~/.claude/`.
- Copyleft, share-alike or unlicensed material, including vendored text and code snippets whose
  origin you cannot name. See `THIRD_PARTY_NOTICES.md` for how the one derived item is recorded.
- Credentials of any kind. The lint and GitHub push protection both block them, and a PR that
  trips either is closed.
- A rule that restates something already in the repo. Grep first.
- A change to `bin/harness` or a hook without a test.

## Review

One maintainer reviews every PR, usually within a week. Expect questions about which rung the
change lands on and whether it is generic. Small, single-concern PRs go fastest. The maintainer
may push small edits to your branch before merging; you will see them in the PR.

## Licensing of contributions

By opening a pull request you agree that your contribution is licensed under the MIT licence
of this repository, with no additional terms, and you confirm you have the right to contribute
it. GitHub's Terms of Service already say the same for any repository with a licence notice
("inbound = outbound", [section D.6](https://docs.github.com/en/site-policy/github-terms/github-terms-of-service#6-contributions-under-repository-license)):
"Whenever you add Content to a repository containing notice of a license, you license that
Content under the same terms, and you agree that you have the right to license that Content
under those terms." No CLA, no sign-off line.
