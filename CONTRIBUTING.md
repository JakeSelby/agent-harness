# Contributing

Contribute to one shared primitive authority under `primitives/`. Personal stances are extensible
policy switches; runtime differences belong in adapters, never duplicate stance or skill catalogs.
[The authoring contract](docs/primitive-authoring.md), [compatibility catalog](docs/compatibility.md)
and [compatibility policy](docs/compatibility-policy.md) define extension, qualification and the
stable public contract. Regenerate projections after changing shared roles or workflows.

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

Every change, including documentation, needs a dedicated delivery issue before implementation.
Each PR closes exactly one issue in this repository with `Closes #N`; each delivery issue belongs
to one PR. Split work requiring multiple PRs into child issues. Contextual issue references are
welcome, but do not use closing keywords for them. A replacement PR may reuse the issue only
after the previous PR closes without merging.

The required `issue-ownership` check validates GitHub's closing links and rejects issues already
claimed by an open or merged PR. It runs on PR creation, body edits, reopening and new commits.
Re-run it immediately before merging if another PR's links have changed: GitHub does not provide
an atomic uniqueness constraint across PRs, and another PR changing cannot invalidate an old check.

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
inside your selected agent runtime.

## Checks to run before opening a PR

```sh
bin/harness lint                       # no personal strings, no secret patterns
python3 -m unittest discover tests     # merge, link, config and lint logic
bin/harness sync --dry-run             # for content changes: the stance and link plan still resolves
```

CI runs exactly these (the sync dry run against the example config), and `harness sync`
installs `.githooks/pre-commit` in the checkout so
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
   `policy/hooks/` plus its lifecycle-adapter mapping and tests.
2. **Tool or editor configuration, not behaviour** → an owned key in
   `claude/settings.template.json` or `vscode/settings.owned.json`, listed in
   `claude/OWNERSHIP.json`.
3. **True of one person, one machine, or one project** → not this repository. It belongs in
   that person's harness configuration or that repo's `AGENTS.md`.
4. **A preference a reasonable engineer might hold the other way** → a variant under
   `primitives/stances/<pref>/`, plus a line in `docs/preferences.md`. Licensing, commit style,
   testing philosophy and autonomy level are stances.
5. **A procedure with steps, or something only needed on a trigger** → a skill under
   `primitives/skills/<name>/SKILL.md` with a description that says when to use it.
6. **Short, generic, wanted on every turn** → `primitives/rules/<topic>.md`. Rules cost every user
   context on every turn, so the bar is high; the usual outcome is one sentence folded into an
   existing rule. `CLAUDE.md` plus every rule plus the longest variant of each stance is capped at
   225 lines and `bin/harness lint` enforces it, so a rule carries its operative lines and points
   at the skill holding the reasoning.

## What will not be merged

- Anything personal or project-specific, however good. Put it in your own harness configuration or custom primitive root.
- Copyleft, share-alike or unlicensed material, including vendored text and code snippets whose
  origin you cannot name. See `THIRD_PARTY_NOTICES.md` for how the one derived item is recorded.
- Credentials of any kind. The lint and GitHub push protection both block them, and a PR that
  trips either is closed.
- A rule that restates something already in the repo. Grep first.
- A change to `bin/harness` or a hook without a test.

## Landing a pull request (maintainers)

`main` takes pull requests through a merge queue and requires linear history, so a landing
follows one shape. Each line here cost a broken landing before it was written down.

- A merge enqueues. `gh pr merge --squash` still works: it adds the pull request to the queue,
  whose own merge method (squash) decides how it lands. The queue builds a temporary
  `gh-readonly-queue/main/pr-<n>-<sha>` branch holding `main` plus every entry ahead of it, runs
  the required checks there, and merges once they are green. The queue
  replaces the up-to-date requirement, so there is no need to merge `origin/main` into a branch
  just to land it. When a branch does need `main` (a conflict), use
  `git merge --no-edit origin/main`, never a rebase or a force-push.
- A queue failure removes the pull request from the queue; the entries behind it are rebuilt
  without it and carry on. `gh pr view <n>` shows it no longer queued, the pull request's timeline
  says it was removed from the merge queue, and the failing run is listed by
  `gh run list --event merge_group`, on a branch named for the pull request. Fix it on the
  branch and merge again. A check that never reports on the queue branch stalls the queue until
  its timeout, which is why every pull request workflow also runs on `merge_group`.
- After 0.13.0, every change under `bin/`, `lib/`, `adapters/`, `primitives/`, `policy/`, `docs/`
  or `scripts/` carries a changelog fragment,
  `changelog.d/<issue-or-pr>.<added|changed|removed|fixed>.md`, instead of an edit to
  `CHANGELOG.md`, so two branches never conflict over one section; see
  [`changelog.d/README.md`](changelog.d/README.md). `bin/harness lint` fails a branch without one.
- Run the gate and read its exit code directly. `python3 -m unittest discover -s tests | tail -1`
  hides a red suite behind `tail`'s exit code; redirect to a log and test for `^OK`.
- `gh pr checks <n> --watch` returns at once when no check has registered yet, and a merge right
  after is refused. Wait until `gh pr checks <n>` lists every required check, then watch, then
  `gh pr merge --squash` to enqueue. Never `--admin`.
- `scripts/bmad_issue_sync.py new` files the issue and then races the list endpoint. When it prints
  "not reserved", wait a few seconds and run `reserve --issue N --kind K --parent P`. Two worktrees
  reserving at once can take the same ID; keep `main`'s entry and re-reserve the other issue.
- The personal-data lint reads a scoped npm spec with a pinned version (at-sign, scope, slash,
  name, at-sign, version) as an email address, and flags third-party contact addresses quoted from
  READMEs. Write "version 1.2.3 of the npm package" instead, and scrub imports before staging.
- Never bypass the pre-commit hook, not even for a first attempt you intend to redo; a commit that
  skipped the lint is still a commit.

## Review

One maintainer reviews every PR, usually within a week. Expect questions about which rung the
change lands on and whether it is generic. Small, single-concern PRs go fastest. The maintainer
may push small edits to your branch before merging; you will see them in the PR.

CodeRabbit also reviews every PR into `main`, forks included, once when it opens, or when a draft is
marked ready. Treat its comments as you would a reviewer's: push a fix, or reply with why one
doesn't apply, then resolve the thread, because `main` won't merge while a review thread is open.
Comment `@coderabbitai review` for another pass after you push. Its comments are advice, and where
you disagree with it, the maintainer decides.

## Licensing of contributions

By opening a pull request you agree that your contribution is licensed under the MIT licence
of this repository, with no additional terms, and you confirm you have the right to contribute
it. GitHub's Terms of Service already say the same for any repository with a licence notice
("inbound = outbound", [section D.6](https://docs.github.com/en/site-policy/github-terms/github-terms-of-service#6-contributions-under-repository-license)):
"Whenever you add Content to a repository containing notice of a license, you license that
Content under the same terms, and you agree that you have the right to license that Content
under those terms." No CLA, no sign-off line.

Shared roles and workflows are authored in `primitives/`, with native bindings in `adapters/`.
Run `bin/harness generate` after changing them; see [primitive authoring](docs/primitive-authoring.md).
