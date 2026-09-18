# Cache hygiene

- **Nothing that rebuilds the cached prefix mid-task:** no model, effort or fast-mode switch, no
  tool-set or MCP change, no `/compact`. Editing files, CLAUDE.md or permission mode keeps it.
- **A new session starts cold**, worktrees included: batch small tasks; `/clear`, not `/compact`.
