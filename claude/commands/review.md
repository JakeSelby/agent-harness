---
description: Review the diff using the selected depth and independence policy; report verified findings only.
argument-hint: [base ref, default main] [optional spec: issue number, plan path or PR number]
---

# Review

Read $ARGUMENTS as the base ref and spec source; default the base to `main`.

1. Establish the diff before spawning anything, with `git diff --stat <base>...HEAD` and `git diff <base>...HEAD`.
   Stop for an invalid base. Outside a repository, offer to
   review named files or a pasted patch instead. Capture the diff and spec as files for workers.
2. Inspect `harness stances --json`, then `harness policy review --risk <presentation|logic|sensitive>`.
   Use sensitive for authorization, secrets, persistence and migrations. Honor stricter repository review gates.
   Unresolved delegation or family requirements remain unresolved; never silently downgrade them.
3. Scope-and-quality runs `spec-reviewer` first, then `reviewer`, in separate fresh contexts.
   Self-check reviews run inline and are labeled self-review. Independent review runs one quality reviewer.
   Launch constrained roles with `harness role run`, the active runtime, explicit model and supplied diff/spec files.
   If different-family is required, pass explicit author/reviewer models to the inspector with user model_families bindings; launch that reviewer model.
   A successful worker envelope is not evidence that its findings are correct.
4. Verify each finding against source and evidence. Reject unsupported findings and explain material disagreement.
   Findings carry severity, file:line, the defect and its consequence; no restatement of the change or praise.
5. Report **Scope** and **Quality** findings appropriate to the selected depth, plus unperformed checks.
   Follow the selected voice; do not label a self-check independent or an unavailable check passed.

Make no edits. Report findings; implementation requires an authorized build task.
