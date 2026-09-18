---
description: Turn a topic or issue into a reviewable plan file and stop at the build gate.
argument-hint: <topic or issue number>
---

# Plan

What to plan: $ARGUMENTS

Honor the selected `plan-ceremony` and `decision-interface` throughout. Under `light`, write a
short plan with decisions and exit criteria; the Review Card layout below applies only to
`review-card`. Existing explicit approval remains valid; do not ask again for approved work.

1. **Invoke the `plan-authoring` skill and read it in full.** Never write the card from memory
   of its contract; a hook validates the file you write.
2. **Gather what the plan needs before you write it.** Read the issue if you were given a
   number, read the code the plan will touch, and delegate wide reads only when the selected delegation stance permits it. Ask the user only
   for what you cannot find yourself, and batch every question into one message.
3. **Write the plan under `.agent-harness/plans/`** — at the repository root, or in the current
   directory when there is no repository — named for the topic. The Review Card is the
   file's first screen and everything else lives below it, under `# Addendum`. Use `harness role run planner` with the active runtime,
   explicit session model, brief file and `--artifact <new-plan.md>` when delegation is useful;
   otherwise write it yourself; you post the message and end at the
   build gate either way.
4. **Post the chat message in the skill's shape** — the verdict, the at-a-glance bullets, the
   numbered decisions verbatim, a workspace-relative link to the plan file, and nothing else.
   The diagram and the numbered steps stay in the file.
5. **End the turn at the build gate.** Close with the skill's build line and stop.

This command needs no repository and no code; a plan for anything at all lands the same way.
Implement nothing. Create no branch and no worktree; that happens at build, not before. If the
user comes back with changes, revise the file, refresh its **Changed this round** line, and say
in chat only what changed. When they approve, `/build` takes it from there.
