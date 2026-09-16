# Commits stance: commit as you go

For repos without a review gate — planning repos, knowledge bases, personal dotfiles — do not
let work pile up uncommitted at the end of a task.

- **Commit incrementally** as logical units finish: a finished document, a completed findings
  file, a new set of drafts are each their own commit. Not once at the end of a long session,
  and not line by line.
- **Push after committing** so the work is durable and visible, not sitting in a local tree.
- **Conventional Commits** still apply: `type(scope): summary`.
- **Hold off** on secrets or anything credential-adjacent, on exploratory content the user has
  called throwaway, and mid-edit of a single file within one turn.
- **Application repos with a review gate are different.** There, branch, open a PR, and let the
  gate do its job. This stance is for repos where stale local-only state is pure cost.
