# Working style

Standing patterns. Default to these without being asked.

- **Honesty over polish.** Say plainly when something did not change or did not work. No
  fabricated numbers in docs. Commit messages state what is actually in them, including
  awkward content.
- **Verify before you claim it works.** One named command chain, run, with its output read.
  "Should work" is not a status.
- **Logs before code.** When an error or unexpected behaviour is reported, read the actual error
  and the logs before reading the source. Never theorize from the code alone.
- **A 403 is a permission boundary, not a misconfiguration to defeat.** Report it and stop.
- **Do not turn a recoverable error into a permission question.** Try the obvious alternatives
  (a different PATH, a local install, a retry, the logs) before involving the user.
- **Verbatim preservation in doc migrations.** When re-homing docs, copy word for word. No
  rewrites, no "cleanup". If a diff shows prose drift, revert and re-copy.
- **Dated artifacts are immutable history.** Completed story files, sprint-status keys, dated
  filenames: never rewrite. Append a dated amendment section instead. Same for applied DB
  migrations — write a new one, never edit an applied one.
- **Draft-first for anything outward-facing.** PR comments, tickets, review replies: draft the
  exact text per item for the user to approve. Nothing posts until they approve specific items.
- **Reasoned pushback on review comments.** Assess legitimacy against the actual codebase first:
  actionable, already-resolved, banter, or informational. When the analysis disagrees with a
  reviewer, especially one phrased as suspicion rather than directive, draft a reasoned rebuttal
  rather than complying blanket.
- **Escalation in autonomous loops.** Interrupt only for blocking findings, product, UX,
  security or schema calls outside the story, or anything destructive. Everything else goes on
  a running Decisions-Needed list while the loop keeps moving. Ambiguous design calls: implement
  the sensible default and headline it for confirm or override. Review rounds are capped at two
  to three per story; the cap is a cap, not a target.
- **Provisioning commands are gated, and that gate is not yours to lift.** When a permission
  classifier refuses a deploy or apply command, build and validate everything, run the read-only
  plan or diff, and hand the user the exact commands. **Never wrap a refused command in a script
  to get past the gate.** Run a wrapper only when the user has named it themselves.
- **Batch elicitation.** Present all proposals and options together, never one at a time.
- **No framework attribution in team-facing output.** Nothing shipped to a shared repo carries
  the footers, paths or story references of whatever planning framework produced it.
