# gh issue create applies relations after the issue exists

- 2026-09-24: `gh issue create --parent`, `--blocked-by` and `--type` create the issue first and apply
  those afterwards; when that second step fails, gh exits non-zero and prints no URL, so a caller that
  retries files a duplicate (gh v2.101.0, `pkg/cmd/issue/create/create.go:482-495`). Create with
  content only, keep the URL it prints, then run `gh issue edit <n> --parent <p> --add-blocked-by <b>`.
- 2026-09-24, checked on a private sandbox with gh 2.101.0: applying a relation that already exists fails,
  `--add-blocked-by` with "Target issue has already been taken (addBlockedBy)" and `--parent` with "Issue
  may not contain duplicate sub-issues (addSubIssue)", so read `gh issue view <n> --json parent,blockedBy`
  first and add only what is missing. A milestone title that already exists returns 422 `already_exists`
  rather than a second milestone. `gh label create <name> --force` without `--color` recolours an existing
  label and keeps its description.
- 2026-09-24, an eval of BMad's ticketing preview publishing through this command with the relation step
  failing once: a larger model found the orphan by title and kept one issue per ticket in 6 of 6 trials,
  while a smaller one retried the create and filed a ticket four times in 2 of 3. An instruction that
  leaves recovery to the agent's care fails with the less careful agent; put the order in the instruction.
