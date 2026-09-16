---
name: plan-authoring
description: Write or revise a plan file, proposal, design doc or handoff that the user reviews before approving work. Carries the Review Card contract — the one-screen summary, the system diagram, the numbered steps, the decision block — and the addendum rules for everything below it. Use before writing anything into .claude/plans/, and for any markdown deliverable whose job is to get a go/no-go.
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

Mermaid renders in most editor previews, on GitHub, and in artifacts. Use it.

- **Default `flowchart LR`** for components and data flow. Cap 12 nodes. If it needs more, the
  diagram is at the wrong altitude — draw the subsystem being changed, not the whole world.
- **`sequenceDiagram`** only when ordering across processes is the actual subject.
- **ASCII in a fenced block** when the shape is a straight pipeline. It always renders.
- Label edges with what moves, not with verbs: `api -->|encrypted episode| web`.
- Mark the delta so the reader sees what is new:
  `classDef new stroke-width:3px,stroke-dasharray:0` then `class bake,shadow new`.
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

With nothing to decide, write **None — reply `build`**. Never invent decisions to fill the
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
5. **The closing line**, exactly: *Reply **build** to proceed, or keep refining.*

Deliberately excluded: the diagram (mermaid rarely renders in a chat sidebar), the steps, the
risks, the addendum. Those are what the file is for. Do not summarize them either.

**Revision round, after feedback.** Much shorter — the reviewer already knows the plan:

1. **One line naming what changed**, matching the card's **Changed this round** line.
2. **Only the decisions still open**, renumbered from 1.
3. **The link and the closing line.**

Never re-post At a glance on a revision. If the scope moved enough to need re-reading, say so in
the change line and let the file carry it.

**No decisions outstanding.** Verdict, At a glance, the link, and *Reply **build** to proceed.*
Never invent decisions to fill the block — an empty one is a signal, not a gap.

**Why the message is short.** The hook validates files, not messages. Nothing enforces this
shape, so it has to stay small enough to hold in working memory.

## Delegating

A subagent writing a plan never loads the user's rules. Paste the `TEMPLATE.md` card skeleton
into its prompt along with the line cap and the no-Context rule — or reformat its output
yourself before the reviewer sees it.

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
