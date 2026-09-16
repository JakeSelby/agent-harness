# Transcript hygiene

- **Read narrowly.** Never `cat` a whole file, or chain `cat`s, to answer a narrow question — reach
  for `head`, `grep -n`, or a `sed` range. Filter every `find` and `ls`; 100+ lines needs a reason.
- **Cap the return:** gathering 400 words, research digest 600, adversarial review findings only.
- **Detail goes to a file, not into the return** — the long version to the scratchpad; the verdict,
  the decision-changing findings and the path come back. A word cap is not a budget to spend.
- **Synthesize, never relay.** Never paste a subagent's report, echo the brief you sent, or narrate
  that agents have returned. Start with the verdict; thinking summaries stay.
- **The tool `description` is the action log:** one clear action in plain words, no flags or paths.
- **Quote verbatim only when the exact text *is* the finding** — an error, a licence clause, a
  failing assertion. Quote the line, not the report. Examples: the same-named skill.
