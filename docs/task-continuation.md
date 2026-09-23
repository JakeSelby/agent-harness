# Continue a task in either runtime

Shared task continuation is a harness capability and names no planning framework; the
[BMad integration](bmad.md) is one of the things it carries work for.

The shared human-readable snapshot is `.agent-harness/progress.md`; session start reads the old
`.claude/progress.md` only when the shared file is absent. Plans live in `.agent-harness/plans/`.
Native transcripts and memory stay in their own runtime stores.

For a structured handoff, prepare a JSON file:

```json
{
  "objective": "Complete the selected change",
  "next_steps": ["Inspect the current diff", "Run the repository gate"],
  "decisions": ["Keep the public API stable"],
  "artifacts": ["docs/design.md"],
  "framework_root": "/path/to/shared-checkout",
  "baseline": "the-reviewed-base-commit"
}
```

```sh
harness task show
harness task save --input task-input.json --runtime claude-code --revision 0
# In Codex, from the same worktree:
harness task show
harness task save --input task-input.json --runtime codex --revision 1
```

The revision rejects concurrent stale writers. Repository identity and a content fingerprint
prevent a changed tree from inheriting a verification claim. Shared plans and progress count as
inputs even when ignored by Git; only task bookkeeping is excluded. Reported verification is retained
as unverified evidence; the receiving session runs the gate itself. Next steps are data, never
executed by the loader, and approvals never transfer. Storage rejects symlinks. Keep personal
handoff data out of commits with a project ignore entry when needed.
