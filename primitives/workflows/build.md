---
description: Implement authorized work within the selected scope, verify it, and prepare the pull request.
argument-hint: <plan path or issue number>
---

# Build

What to build: {{arguments}}

**Check first, before spawning anything.** Read repository instructions, the approved base and `harness stances --json` before work.
No repository: say so and offer to make the change in place, with suitable checks. No remote or authenticated GitHub client:
stop at the local commit and report the remaining publication step.

1. Follow change-scope and testing. With delegation off, work inline. Otherwise use a bounded `builder`
   brief and an isolated implementation worktree per `worktree-per-agent`; constrained reviewers never receive write authority.
   Follow delegation_controls; check declared concurrent writers with `harness policy delegation`.
2. Run the required gate yourself according to verification policy; read command results rather than a worker's account.
   Local-first requires local gates before a PR. CI-authoritative/hybrid may open a draft for remote checks;
   pending, failed and unavailable checks remain unverified. Repository merge gates always apply.
3. Inspect the diff, tests, intended scope, commit convention and applicable attribution before committing.
   Respect repository templates and documentation style. Never bypass pre-commit hooks.
4. Publish only within external-actions authority. Push to the approved branch, not directly to the default
   branch. Link the issue and report tests plus missing evidence. Do not merge without required green checks
   on the exact head and user authorization for that merge.

Report concrete results and the PR or branch, plus unresolved decisions or checks. Do not claim native
qualification from unit tests, generated instructions or a successful worker process.
