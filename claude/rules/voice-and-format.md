# Voice and output format

The **Scannable** output style at `~/.claude/output-styles/scannable.md` governs the main
conversation. It does not reach subagents, which run their own system prompt. Close that gap
two ways.

**Relaying a subagent's report.** Never paste an agent's prose through, verbatim or lightly
edited — synthesize it into your own answer under the Scannable contract: verdict first, action
items under their own heading, paragraphs capped at three sentences, status stated with the
literal words *Fixed / Partially fixed / Not fixed / Unverified*. A finding that does not change
what the user does is cut, not reformatted. See `transcript-hygiene.md`.

**Spawning a subagent whose output the user reads directly.** Put the shape in the prompt:
"Report back as: one-line verdict, then **What changed** / **What you need to do** / **Still
open** / **Verification**. No process narration." Subagents inherit no format; the shape must
be in the brief.

**Plan files and other markdown deliverables** follow the same rules — verdict-first sections,
bolded lead-ins, file paths as workspace-relative markdown links rather than backticks. Anything
the user reads in order to approve work — plan, proposal, design doc, handoff, research summary —
opens with the Review Card from the `plan-authoring` skill when the `plan-ceremony` stance is
`review-card`, with the detail below the rule, and is handed over in that skill's chat-message
shape.

**Editors do not always repaint a markdown preview when a file is rewritten out of band.** When
iterating on something the user is previewing, tell them to close the preview tab, or write the
next version under a new filename.

## Posts published in the user's name

When drafting comments, tickets or review replies that go out under the user's name, keep them
to **about three sentences**. No deferential sign-off flourishes: no "your call", no "let me
know". The reasoning lives in linked docs and tickets, not inline in the comment; link out for
depth. Longer structure is fine for ticket bodies with scope sketches; comments stay terse.

Terse is not unformatted. Once a comment carries three or more parallel items — decisions,
findings — break them into bold-led bullets with blank lines between. Structure is not licence
to bloat: link the artifact instead of inlining its reasoning.
