---
description: Implement an approved plan or issue in its own worktree, run the gate, open the pull request.
argument-hint: <plan path or issue number>
---

# Build

What to build: {{arguments}}

**Check first, before spawning anything.** This command needs a git repository, a remote you can
push to, and `gh` logged in. No repository: say so and offer to make the change in place, with
tests, and no worktree or pull request. A repository but no remote or no `gh`: run steps 1 to 4,
stop at the local commit, and report the branch as ready to push.

1. **Work from the plan path or the issue number you were given**, and say which in your first
   message. Never search for a plan: `/plan` renames the approved file and hands over its path,
   and a plan found by date is as likely to be last week's. With neither a path nor an issue,
   ask for one. Give the builder the absolute plan path and tell it to copy the file into its
   worktree and commit it — a worktree carries no untracked file, and the plan belongs in the PR.
2. **Spawn the `builder` agent** with the plan or issue text, the repository path, the base
   branch, and the attribution trailer your tool supplies. Its definition already carries the
   standing brief — a worktree off the base branch per `worktree-per-agent`, the repository's own
   instructions read first, tests with every change, the repository's gate, one local Conventional
   Commit — so retype none of it. Give it the scope instead: the files it may touch and the ones
   it must leave alone.
3. **Run the gate yourself** in the worktree it names, with the repository's own commands. Never
   take an agent's word for a verifier; you read the exit status, not its account of the run. Red
   means you fix it or hand the finding back, never that you push anyway.
4. **Check the commit** before it leaves the machine: a Conventional Commit title, a body ending
   in `Closes #N` and the attribution trailer, and nothing in the diff that fails to trace to the
   issue.
5. **Push the branch and open the pull request** with `gh pr create`, based on the default
   branch, never pushing to that branch directly. Body: a few bullets on what and why, `Closes
   #N`, and the generated-with line your tool supplies.
6. **Answer the review bot**, where the repository runs one: a `.coderabbit.yaml`, a
   `greptile.json`, or a bot that reviewed earlier pull requests. Wait up to ten minutes for its
   first review of this pull request, and say so if none arrives. Then take each unresolved bot
   thread as a finding: fix it in the worktree, rerun the gate and push, or reply with the reason it
   does not apply. Then resolve the thread (GraphQL `reviewThreads`, then `resolveReviewThread`).
   Two rounds at most; report whatever remains. A human's thread is never yours to resolve.

Report the pull request URL, the tail of your own gate run, the bot threads answered and any
still open, and anything else still open: a decision taken on the user's behalf, a step left
unfinished, a test that had to be skipped.
