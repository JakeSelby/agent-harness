---
description: Merge an approved pull request, clean up its worktree and branch, then check whether a release is due.
argument-hint: <pull request number or URL> [worktree name]
---

# Land

What to land: {{arguments}}

**Check first, before changing anything.** This command needs a git repository, a remote, and `gh`
logged in. Resolve the pull request, the branch behind it, and the worktree that produced it; when
any of the three is missing, say which and stop. Merging is approval-gated — get an explicit
go-ahead before the merge — and this command never tags and never deploys.

1. **Verify the head that will merge.** Every required check green on the current head, not on an
   earlier push; where the repository runs an issue-ownership or closing-link check, confirm that
   it passed on that same head. A pending, failing or stale check stops the workflow, named.
2. **Merge it** with `gh pr merge --squash --delete-branch`, into the default branch.
3. **Fast-forward the shared checkout** on its default branch with `git pull --ff-only`. Anything
   other than a fast-forward means the branch diverged: stop and report it, never merge locally.
4. **Remove the worktree** with `harness worktree remove <name>`. Never force a removal. A dirty
   worktree stops the workflow with the reason and the path, so the work can be read first.
5. **Delete the local branch** with `git branch -d <branch>`, which refuses an unmerged branch —
   that refusal is the check, and it stops the workflow. Never `git branch -D`, and keep it out of
   compound commands: the shell-grading hook denies a whole compound command when any one segment
   is irreversible, so a chain containing it runs none of its steps.
6. **Audit** with `harness worktree audit`, and report every stale or dirty checkout it names
   along with what each still holds. Leave them in place; removing them is the user's call.
7. **Check the release rule.** Read the repository's own agent instructions for when a release is
   due. Either state "no release due" with the reason those instructions give, or post a release
   card — the version, what landed since the last one, the surfaces the instructions require —
   and wait for approval. Approval belongs to the release, not to this command.

Report the merge commit, what was removed, what the audit still shows, and the release decision
with the line in the repository's instructions it came from.
