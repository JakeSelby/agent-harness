---
name: plan-authoring
description: Write or revise a plan file, proposal, design doc or handoff that the user reviews before approving work. Carries the Review Card contract — the one-screen summary, the system diagram, the numbered steps, the decision block — and the addendum rules for everything below it. Use before writing anything into .agent-harness/plans/, and for any markdown deliverable whose job is to get a go/no-go.
---

The trigger lives in the `plan-ceremony` stance. This is the contract.

## Why this exists

A plan has two audiences and they are not the same reader.

- **The reviewer reviews the approach.** System design, steps, and the decisions that are
  theirs — in one screen, before they read anything else.
- **The implementing agent executes it.** Paths, sequencing, edge cases, evidence.

One document written for both produces the 884-line file the reviewer gets lost in. So a plan
is one file with a hard seam: a **Review Card** above the first `---`, an **Addendum** below it.

**Failure test:** if the reviewer has to scroll to learn what is being built, the plan has
failed, however good the work behind it is.

## The Review Card

Everything above the first `---`. **Target 50 source lines, hard cap 70**, diagram included.
The one thing allowed to push past 70 is a full `## Decisions for the reviewer` block — three
lines each, five maximum. Never cut a real decision to hit a budget.

Not an introduction to the plan — the whole plan at review altitude.

These sections, this order. Do not rename them, do not add to them, do not fold one into another.

1. **`# <title>`** — 1 line. What gets built, as a noun phrase. Not a sentence.
2. **Verdict blockquote** — at most 4 lines. Two sentences, what this builds and the mechanism,
   then one metadata line: Effort · Risk · Blast radius.
3. **`## At a glance`** — 7 bullets. Outcome · Approach · Touches · New deps · Not in scope ·
   Exit test · the one open question.
4. **`## System design`** — at most 15 lines. One diagram, no prose above it, one caption below.
5. **`## Steps`** — at most 8. Numbered, two lines each: what and where, then the exit test.
6. **`## Decisions for the reviewer`** — at most 5. Question, recommendation with its reason,
   alternative. One line each.
7. **`## Risks`** — at most 3 bullets. One line each: the trigger, and what we do when it fires.

`TEMPLATE.md` in this directory is the skeleton. `EXAMPLE.md` is a real long plan reduced to
its card.

## A plan contains no markdown tables. Anywhere.

Not in the card, not in the addendum. A markdown table renders as a bordered grid whose first
column is pinned narrow, so at reading width every cell longer than a clause wraps into a tall,
ragged block. That is the density a plan exists to avoid, and it is no better below the rule
than above it.

- **`## At a glance`** — seven `- **Label** — value` bullets.
- **`## Steps`** — a numbered list, two lines per step.
- **Any pairing or mapping** — one bullet per row, with the paired terms bolded together:
  `- **old/path.ts → new/path.ts** — what changes.`
- **Anything with a "why" column** — fold the why into the sentence. A three-column table is
  almost always a list of bullets with an em dash in it.
- **Not bare bold-label lines**, in any of these: many markdown previews collapse consecutive
  soft-wrapped lines into one paragraph. The list marker is what guarantees the break.

The validator hook rejects any line starting with `|` in a plan file.

## There is no Context section in the card

The most common defect: every plan opens with `## Context` and three paragraphs of background.
Background is addendum material. The verdict's two sentences carry the why — and if they
cannot, the plan is not yet understood well enough to write.

## Never in the card, always in the addendum

- Working rules, governance constraints, the agent's own operating instructions
- Evidence tables, verification logs, what was checked and what could not be
- ID ledgers, allocation tables, file inventories, touch matrices
- Per-agent or per-handoff narratives
- Gate registers beyond the one gate that actually blocks
- Alternatives beyond the single line each already in Decisions
- Any restatement of the request

## The diagram

The card is reviewed in a plan-mode pane and a chat sidebar, and both show a mermaid fence as
raw source. The card's diagram is therefore plain text, which renders everywhere.

- **A box-and-arrow drawing in a `text` fence** — `├─▶`, `└─▶`, `──▶`, a dotted `┄┄▶` for a
  weak or polled link. Cap 12 nodes. If it needs more, the diagram is at the wrong altitude —
  draw the subsystem being changed, not the whole world.
- Keep every line under 80 columns; a wrapped line breaks the drawing.
- Label edges with what moves, not with verbs: `api ── encrypted episode ──▶ web`.
- Mark the delta so the reader sees what is new: prefix each new or changed node with `*`, and
  name the marker in the caption.
- **Mermaid belongs below the `---`,** and in docs that are read on GitHub — a
  `sequenceDiagram` when ordering across processes is the actual subject. Never on the card.
- Mandatory when the change crosses more than one component. Omit only for single-file edits.

## Steps

A numbered list — these are genuinely ordered — with two lines per step:

```markdown
3. **[Bake the shadow map](#step-3--bake-the-shadow-map)** — `tools/bake/shadow.py`, new file.
   *Exit:* `terrain_map_8192` writes in under 3 minutes and both shaders sample it once.
```

- **Line one** is what happens and where, with the title linked to its addendum anchor when it
  has detail. **Line two** is the exit test, always led by `*Exit:*`.
- **Every step carries a real exit test** — a command, a render, a passing assertion.
  "Implemented" is not an exit test.
- Execution order, and step 1 is the cheapest thing that could invalidate the rest.
- Past eight steps, group under `### Phase` headings, at most three.
- A plan names the skills it will run and the order they run in.

## Spikes inside a plan

When a step is an experiment rather than a build, write it as a spike: the question it
answers, the cheapest experiment that answers it, the exit criterion as a number, and the
machine the budget was measured on. Read the exit criterion against measured numbers, never
against impressions.

## Decisions for the reviewer

Numbered, answerable in chat by number ("1 A, 2 your rec"). Three lines each:

> **3. Borders from geometry ribbons, or from the attribute texture?**
> *Recommend* ribbons — the real boundary lines already exist and stay crisp at every zoom.
> *Alternative* the gradient technique, which we need anyway for runtime cell changes.

With nothing to decide, write **None — approve to proceed**. Never invent decisions to fill the
section, and never leave a real one buried in the addendum.

## Revisions

When the plan changes after feedback, one blockquote line directly under the verdict:

> **Changed this round.** Dropped the CDLOD spike · Gate 2 now blocks publication · +1 day.

Three items maximum, one line. Delete the previous round's version — the card shows the latest
delta only. Full revision history lives in the addendum.

## The addendum

Below the first `---`, under `# Addendum`. No budget. Everything the implementing agent needs
and the reviewer does not.

- One `## Step N — <title>` heading per step with detail, so card rows can anchor to it.
- Nothing above the rule is repeated below it. If the addendum restates the approach, cut it.
- Written for an agent with no context: exact paths, exact commands, expected output.

## The chat message

The plan ships as two artifacts. The file is the document; the chat message is what the
reviewer replies to. Three shapes, and nothing improvised.

**First post, when the plan is ready.** In this order, nothing else:

1. **Verdict line** — one or two sentences, the same ones from the card.
2. **`## At a glance`** — the seven bullets, verbatim. This is the "is this even the right
   scope" check, and it saves opening a plan that was going to be redirected anyway.
3. **`## Decisions`** — the numbered blocks, verbatim. The reviewer answers by number in chat,
   so they must be readable where they type.
4. **A workspace-relative markdown link** to the plan file, with a note on how to preview it.
5. **The closing line**, only where there is no plan mode, exactly: *Reply **build** to
   proceed, or keep refining.* Under plan mode the message ends at the link.

Deliberately excluded: the diagram (the file holds it), the steps, the
risks, the addendum. Those are what the file is for. Do not summarize them either.

**Under plan mode the file is already the review surface.** Plan mode designates the plan file
and names it itself — a slug of your opening words plus two random words, fixed before any
content exists — so you neither choose the name nor rename it while planning. Write the card
there, post the message, and call `ExitPlanMode`: the native approval is the gate, and asking
for a typed *build* on top of it is a second gate nothing downstream can read. Once it is
approved, rename the file to a topic slug — never over a name already taken; take `-2` and say
so — and hand `/build` that path rather than leaving it to be searched for.

**Without plan mode, put the file on screen before you post the message.** A link in chat is a
path, not a rendering: in some clients it is clickable, in others it is dead text, and a plan
written straight to disk never reaches a native plan view, because nothing registered it as one.
The reviewer is then asked to approve a document they cannot see. So if the runtime can open a
file beside the conversation, open the plan there first, and pass an **absolute** path unless you
have confirmed that relative ones resolve; a rejected path is the common failure and it is
silent. If the runtime cannot, say in the message how to open the file. The same applies on every
revision round, since the reviewer is reading a changed file, not the one they opened before.

**Revision round, after feedback.** Much shorter — the reviewer already knows the plan:

1. **One line naming what changed**, matching the card's **Changed this round** line.
2. **Only the decisions still open**, renumbered from 1.
3. **The link, and the closing line only where there is no plan mode.**

Never re-post At a glance on a revision. If the scope moved enough to need re-reading, say so in
the change line and let the file carry it.

**No decisions outstanding.** Verdict, At a glance, the link, then `ExitPlanMode` — or *Reply
**build** to proceed* where there is no plan mode.
Never invent decisions to fill the block — an empty one is a signal, not a gap.

**Why the message is short.** The hook validates files, not messages. Nothing enforces this
shape, so it has to stay small enough to hold in working memory.

## Delegating

Use `harness role run planner` with `--runtime`, the explicit session `--model`, `--workspace`,
a `--prompt-file` brief and `--artifact <new-plan.md>`. The isolated worker receives the shared
role and resolved stances, and returns plan content; the harness validates and publishes it.
Read the artifact and post the review message yourself. Existing plans are not overwritten.
Run the worker before entering plan mode: it writes an artifact, and plan mode permits no write
but the designated plan file — so inside it, copy the worker's card across rather than delegating.
See `docs/role-workers.md` for input directories, status and native qualification limits.

## Self-check before handing it over

Run it, do not eyeball it:

```bash
awk '/^---$/{exit} {n++} END{print n" card lines"}' <plan file>
```

- [ ] Card ≤ 70 lines, or ≤ 85 with a full decision block
- [ ] No `## Context` above the rule
- [ ] First screen answers: what is being built, how, what it touches, what I must decide
- [ ] No paragraph above the rule runs past three sentences
- [ ] Every step has a real exit test
- [ ] Decisions numbered and answerable by number
- [ ] Nothing above the rule repeated below it

## Rationale relocated from the resident rules

`voice-and-format.md` and `decisions-and-plans.md` were cut to their operative lines when the
always-loaded context was capped. These are the paragraphs they used to carry, word for word.

### Voice and output format

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

**Posts published in the user's name.** When drafting comments, tickets or review replies that
go out under the user's name, keep them to **about three sentences**. No deferential sign-off
flourishes: no "your call", no "let me know". The reasoning lives in linked docs and tickets,
not inline in the comment; link out for depth. Longer structure is fine for ticket bodies with
scope sketches; comments stay terse.

Terse is not unformatted. Once a comment carries three or more parallel items — decisions,
findings — break them into bold-led bullets with blank lines between. Structure is not licence
to bloat: link the artifact instead of inlining its reasoning.

### Presenting decisions

**Do not use a chooser widget for substantive decisions.** Write the decision block in chat as
the standalone final message of its turn: each question stated unambiguously, the assessment
behind it, a recommendation with reasoning, and the alternatives with the honest case for each.
Number them. The user answers in chat ("1 post, 2 comment, 3 issue").

Two failure modes, both real. A same-turn chooser eats the assessment, because text written
before a tool call is not reliably displayed. A next-turn chooser wastes a round trip. Chooser
labels also truncate and cannot carry evidence or trade-offs.

A chooser is reserved for trivial forks where the option labels alone carry full meaning.

Batch related decisions into one block.

### Pointing at an option is not a decision

During design and option reviews, the user saying "this one" or pasting an image of an option
means **put that in the doc and show me**. It is not approval to implement. Treat
option-pointing as scope for the review artifact. Build only on an explicit "build" or
"go with N".

### Pre-approved plan execution

Once the user has explicitly approved a multi-step plan in the current conversation, do not
re-ask at each step. Execute, log, move to the next.

**Applies when** they said yes, go ahead, proceed, approved or equivalent to a full plan; no new
information materially changes the plan; and the action was in the approved plan.

**Re-surface for confirmation if** an error or unexpected state makes a step unsafe (merge
conflict, wrong branch, destructive diff not in the plan), a step was not in the original plan,
or the blast radius has materially increased.

The plan ceremony itself — whether a plan needs a Review Card and a build gate — is set by the
`plan-ceremony` stance. Its `review-card` variant carries the four numbered steps; its `light`
variant asks only for a short chat message and an explicit go-ahead.
