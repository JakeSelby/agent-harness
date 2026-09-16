---
description: Review the branch's diff with a fresh-context reviewer and report findings only.
argument-hint: [base ref, default main]
---

# Review

Base ref: $ARGUMENTS — when that is empty, use `main`.

1. **Establish the diff.** Run `git diff --stat <base>...HEAD` and `git diff <base>...HEAD`. If
   the base does not resolve, say so and stop rather than review against the wrong tree.
2. **Spawn the `reviewer` subagent on that diff**, in a context that has not seen the work being
   reviewed. Brief it for findings only: no restatement of what it read, no summary of the
   change, no praise. Each finding carries a severity, a `file:line`, what is wrong and why it
   matters. Tell it to treat a missing test or an untested error path as a finding.
3. **Relay nothing verbatim.** Check each finding against the code yourself before it reaches
   the user and drop the ones that do not hold. Where you disagree with the reviewer, say so
   with your reasoning rather than passing the finding through.
4. **Report the surviving findings ranked by severity**, each one bold-led bullet carrying its
   `file:line`. State the verdict first. If nothing survives, say that in a single line.

Make no edits. This command reads, it does not fix. Hand the findings over and let the user
decide which ones to act on — `/build` is where changes happen.
