# Comparing harnesses

If you run a different set of rules and skills, these are the properties worth comparing.
Each is observable in a transcript, not a matter of taste.

- **Transcript cost per task.** How many lines the user has to scroll past to find the answer:
  raw tool output, relayed subagent reports, narration between tool calls. This harness caps
  subagent returns at 400 words, forbids reprinting them, and makes the tool-call description
  the log line.
- **Where the verdict sits.** First line, or after the process story. The output style here
  bans process openers and puts action items in one labelled section.
- **What a plan looks like before approval.** One screen with the decisions numbered, or a
  long document. The plan-authoring skill and its validator hook enforce a 70-line card.
- **Delegation posture.** Whether gathering work is delegated by default, what tier it runs
  on, and whether the return is bounded in the brief. Also whether anything found in a
  subagent's summary can be executed directly (here: never).
- **Permission posture in plan mode.** Whether exploring a codebase prompts on every read-only
  command. The read-only hook and allowlist here make plan mode prompt-free for exploration.
- **How preferences are handled.** Baked into the rules, or separable. Stances make the
  preference layer explicit and swappable, and keep a fork mergeable.
- **How the harness updates itself.** Whether "add a rule" lands in a repo with a lint and a
  commit, or in a home directory nobody reviews.
- **What is enforced versus advised.** Hooks enforce; rules advise. Count each.

Send a comparison, or a counter-example, as an Idea issue. The point of publishing the harness
is to find out which of these hold up outside one person's workflow.
