---
description: Implement an approved plan or issue in its own worktree, run the gate, open the pull request.
argument-hint: <plan path or issue number>
---

# Build

What to build: $ARGUMENTS

1. **Invoke the `worktree-per-agent` skill and create the worktree** off the default branch
   before you change a single file. Never implement in the shared checkout.
2. **Read the whole plan or issue first**, then the code it touches. Execute the approved steps
   without re-asking at each one; stop and surface only a step that has become unsafe, one that
   was never in the plan, or a blast radius that has grown.
3. **Implement it with tests**, per the selected testing stance. Read a neighbouring test
   before writing a new one and follow the repo's own placement convention.
4. **Run the repo's gate** — the exact commands its `AGENTS.md` names, or what CI runs when it
   names none — in the worktree you are about to push. Fix what is red, including pre-existing
   failures in files you touched. Run the formatter before the gate, not after.
5. **Commit** with a Conventional Commit title and a body saying what changed and why, keeping
   whatever attribution trailer your tool supplies.
6. **Push the branch and open the pull request** with `gh pr create`, based on the default
   branch. Never push to the default branch directly.

Report the pull request URL, the last few lines of the gate output, and anything still open: a
decision you took on the user's behalf, a step you could not finish, a test you had to skip.
