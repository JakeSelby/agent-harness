---
description: Answer a research question with parallel read-only gatherers and one synthesized digest.
argument-hint: <question>
---

# Research

Read `harness stances --json` for research depth and budgets. With delegation off, work inline.
Quick-check answers the narrow question; source-led corroborates decisive claims; exhaustive covers
relevant perspectives until the bounded budget is exhausted, then reports gaps.

The question: $ARGUMENTS

Load the `transcript-hygiene` and `api-verification` skills in full before you spawn anything.
They carry the return caps and the shared search budget this command depends on.

1. **Split the question into at most three independent dimensions.** Independent means one
   gatherer's answer never changes another's brief. Fewer is better. If the question is one
   dependent chain, answer it inline and spawn nothing.
2. **Spawn one `gatherer` subagent per dimension, in parallel, in a single message.** Every
   brief names the exact question for that dimension, the files or sources to start from, a
   resolved gather_words return cap, the rule that detail goes to a scratchpad file while only the verdict
   and the decision-changing findings come back, that dimension's share of the session search
   budget, and what the gatherer must not decide.
3. **Synthesize in your own words.** Never paste, quote or lightly edit a report. A finding
   that does not change the answer does not appear at all. Where two gatherers disagree,
   adjudicate it yourself and say which source won and why.
4. **Verify anything load-bearing** before you rely on it: prove a filter bites, spot-check one
   returned record, count swallowed errors separately from empty results.

Report the verdict first, then the findings that matter, then **Still open**. End with the
scratchpad file paths the gatherers wrote, one per line, so the detail is one read away.
