---
description: Turn a topic or issue into a plan the reviewer approves in the native plan pane.
argument-hint: <topic or issue number>
---

# Plan

What to plan: {{arguments}}

1. **Invoke the `plan-authoring` skill and read it in full.** Never write the card from memory
   of its contract; a hook validates the file you write.
2. **Ask before entering plan mode**, in one line naming the topic — entering it is the user's
   call. A runtime with no plan mode takes step 6 instead.
3. **Gather inside plan mode.** Read the issue if you were given a number, read the code the
   plan will touch, and delegate the wide reads; long-form research goes to the scratchpad,
   never beside the plan file, which is the only file plan mode lets you write. `harness role
   run planner` writes an artifact, so run it before you enter, with the active runtime,
   explicit session model, brief file and `--artifact <new-plan.md>`. Ask the user only for
   what you cannot find yourself, and batch every question into one message.
4. **Write the Review Card into the plan file plan mode designated.** The runtime names that
   file and you cannot rename it here; `/build` gives it a topic name once writes are allowed.
   The card is the file's first screen and everything else lives below it, under `# Addendum`.
5. **Post the review message in the skill's shape, then call `ExitPlanMode`.** Leave off its
   closing build line: the native approval is the gate, so never ask for a typed reply as well.
6. **No plan mode:** write the plan under `.agent-harness/plans/` — at the repository root, or
   the current directory when there is no repository — named for the topic, open it for the
   reviewer with an absolute path, and end at the skill's build line.

This command needs no repository and no code; a plan for anything at all lands the same way.
Implement nothing. Create no branch and no worktree; that happens at build, not before. If the
user comes back with changes, revise the plan file, refresh its **Changed this round** line, say
in chat only what changed, and call `ExitPlanMode` again. When they approve, `/build` takes over.
