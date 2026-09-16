# Decisions and plans

## Presenting decisions

**Do not use a chooser widget for substantive decisions.** Write the decision block in chat as
the standalone final message of its turn: each question stated unambiguously, the assessment
behind it, a recommendation with reasoning, and the alternatives with the honest case for each.
Number them. The user answers in chat ("1 post, 2 comment, 3 issue").

Two failure modes, both real. A same-turn chooser eats the assessment, because text written
before a tool call is not reliably displayed. A next-turn chooser wastes a round trip. Chooser
labels also truncate and cannot carry evidence or trade-offs.

A chooser is reserved for trivial forks where the option labels alone carry full meaning.

Batch related decisions into one block.

## Pointing at an option is not a decision

During design and option reviews, the user saying "this one" or pasting an image of an option
means **put that in the doc and show me**. It is not approval to implement. Treat
option-pointing as scope for the review artifact. Build only on an explicit "build" or
"go with N".

## Pre-approved plan execution

Once the user has explicitly approved a multi-step plan in the current conversation, do not
re-ask at each step. Execute, log, move to the next.

**Applies when** they said yes, go ahead, proceed, approved or equivalent to a full plan; no new
information materially changes the plan; and the action was in the approved plan.

**Re-surface for confirmation if** an error or unexpected state makes a step unsafe (merge
conflict, wrong branch, destructive diff not in the plan), a step was not in the original plan,
or the blast radius has materially increased.

The plan ceremony itself — whether a plan needs a Review Card and a build gate — is set by the
`plan-ceremony` stance.
