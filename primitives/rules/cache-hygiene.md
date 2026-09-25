# Cache hygiene

- **Keep the cached prefix stable mid-task:** avoid model, effort, fast-mode, tool-set or MCP
  changes. Native cache behavior differs; do not assume identical invalidation rules.
- **New sessions start cold:** batch small tasks; use the native fresh-session control, not compaction, unless `cost` allows it.
