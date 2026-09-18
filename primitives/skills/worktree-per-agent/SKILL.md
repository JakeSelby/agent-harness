---
name: worktree-per-agent
description: Isolate an agent's work in its own git worktree branched off the default branch, so two agents never land conflicting changes on the shared checkout. Use at the start of any implementation task in a repo where other agents or the user may also be working, and whenever a repo's instructions say "work in a worktree".
---

# One worktree per agent

The shared checkout belongs to the human. An agent that edits it directly races every other
agent and every uncommitted human change. So: branch a worktree off the default branch, work
there, land the result through the repo's normal path, remove the worktree.

## Create

```bash
REPO=$(git rev-parse --show-toplevel)
NAME=<task-slug>
git -C "$REPO" fetch origin
git -C "$REPO" worktree add -b "$NAME" "../$(basename "$REPO")-$NAME" origin/main
cd "../$(basename "$REPO")-$NAME"
```

Sibling directory, named after the repo and the task, branched from the remote default branch
so it starts from what is actually merged. If the repo's instructions name a different base or
location, follow them.

## Work

- Install dependencies in the worktree if the repo needs them per checkout; do not assume the
  shared checkout's `node_modules` or virtualenv is reachable.
- Run the repo's quality gate in the worktree before pushing, per `verification.md`.
- Never `cd` back into the shared checkout to run something "quickly".

## Land

Push the branch and open a PR, or push to `main` if the repo's instructions allow it. Then:

```bash
git -C "$REPO" worktree remove "../$(basename "$REPO")-$NAME"
git -C "$REPO" branch -d "$NAME"      # only after it is merged
```

## Things that bite

- **Tooling that resolves paths against the working directory** (planning frameworks, skill
  projections) will not find its files in a worktree. If a tool halts with a missing-script
  error, that is the guard working; run that tool from the shared checkout only.
- **Shared append-only documents** (a decisions log, a changelog) are not worktree material:
  two agents appending in two worktrees produce a conflict at merge. Append to those on the
  default branch in one place.
- **Generated index files** are rebuilt once at merge, never on both sides.
- **Leftover worktrees** confuse `git status` and history rewrites. `git worktree list` before
  any operation that touches every branch.
