# Research and verification

- **Web search is capped per session — 200 calls on Claude Code — and shared by every subagent.**
  Budget roughly 10 agents at 20 searches, or 6 at 30, and stagger bigger runs across sessions.
  After a fan-out, check each subagent's count and re-run starved dimensions in a fresh session.
- **Prove a filter bites:** send a value that can never match and confirm the result is empty.
- **Spot-check one returned record** against the field you filtered on before trusting the set.
- **A swallowed per-item error is unknown, not absent.** Count failures separately from empties.
- **Re-check the live spec** before assuming a documented workaround is still needed.
- **Prefer primary sources.** Trace every rule you rely on to a quotable source; when a file's
  header and body disagree, find the code or the spec that decides it. See `api-verification`.
