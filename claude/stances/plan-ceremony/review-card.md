# Plan ceremony stance: Review Card and build gate

Plan mode should feel like a design review: the approach in chat, a link to the plan file, an
explicit build gate, then autonomous implementation.

1. **Before writing or revising a plan file, invoke the `plan-authoring` skill.** The plan file
   is the real deliverable, and it is a *review* document before it is an execution document.
   **Non-negotiable even if the skill is skipped:** the file opens with a **Review Card** —
   title, two-sentence verdict, at-a-glance bullets, one diagram, numbered steps with exit
   tests, numbered decisions, risks — capped at 70 lines, carrying **no `## Context` section**.
   Everything else lives below a `---` under `# Addendum`. Length below the card is free.
   Length above it is the defect. A hook validates the card on every write.
2. **When the plan is ready, do not exit plan mode yet.** Post the review message in chat first;
   its three shapes are in the skill. **Non-negotiable:** verdict, the at-a-glance bullets, the
   numbered decisions verbatim, a workspace-relative link, and nothing else. The diagram and
   the steps stay in the file. End the turn with: *Reply **build** to proceed, or keep refining.*
3. **Iterate in plan mode** until the user replies "build" or an equivalent explicit go-ahead.
   When the plan changes, update the file, refresh the **Changed this round** line in the card,
   and say in chat only what changed.
4. **On "build": exit plan mode.** The approval dialog is the build button. After approval,
   implement the whole plan without pausing for per-step confirmation.

Skip this ceremony only if the user explicitly asks for a quick plan or says to just exit plan
mode.
