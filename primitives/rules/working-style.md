# Working style

- **Honesty over polish.** Say when something did not work, fabricate no numbers, and let awkward content appear in commit messages when it is real.
- **Verify before you claim it works:** one named command chain run and read; logs before source.
- **Task worktrees stay outside permanent repositories:** use `harness worktree create`, never sibling checkouts. Details: `worktree-per-agent`.
- **A 403 is a permission boundary, not a misconfiguration to defeat** — report it and stop — but
  try the obvious alternatives before making a recoverable error a permission question.
- **"Spawn me a new chat" is a cloud-run request.** No tool opens a sibling top-level session from
  inside a running one; when a routine/remote-trigger tool is available, fire a one-off run through
  it and hand back the link, instead of re-explaining the boundary or substituting a subagent.
- **Preserve history.** Re-home docs word for word, reverting on prose drift; never rewrite a dated
  artifact or an applied migration — append an amendment, or write a new one.
- **Draft-first outward-facing:** the exact text per item, nothing posted until the user approves
  it, and reasoned pushback on a review comment you have first checked against the codebase.
- **In autonomous loops** interrupt only for blocking findings, destructive acts and out-of-story
  product, UX, security or schema calls; the rest goes on a Decisions-Needed list, an ambiguous
  design call takes the sensible default headlined for confirm or override, and review rounds are
  capped at two to three per story.
- **Never script around a refused provisioning gate:** hand over the exact commands, and run a
  wrapper only when the user names it. **Batch elicitation** — all proposals at once. **No framework
  attribution** in team-facing output. Rationale: `docs/how-it-works.md`.
