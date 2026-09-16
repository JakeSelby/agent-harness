# Voice and output format

- **The Scannable style** (`~/.claude/output-styles/scannable.md`) governs the main conversation and
  does not reach subagents. Rewrite anything relayed under its contract: verdict first, action items
  under one heading, paragraphs capped at three sentences, status in the literal words *Fixed /
  Partially fixed / Not fixed / Unverified*.
- **Put the output shape in every subagent brief**, since subagents inherit none: "one-line verdict,
  then **What changed** / **What you need to do** / **Still open** / **Verification**."
- **Markdown deliverables follow the same rules** — verdict-first sections, bolded lead-ins,
  workspace-relative links, the Review Card when the `plan-ceremony` stance asks, and a warning to
  close any preview before you rewrite the file behind it.
- **Posts in the user's name run about three sentences**, no sign-off flourishes, reasoning linked
  not inlined; three or more parallel items become bold-led bullets. See `plan-authoring`.
