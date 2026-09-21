---
description: Close a finished session: sweep for unfinished work, land and hand off, file the follow-ups, tell the sessions that depend on this one, then archive.
argument-hint: [what is finishing, and "archive" if it should archive without asking again]
---

# Close out

What is finishing: {{arguments}}

**Sweep before you change anything.** A close-out that opens with a merge has already skipped the
question it exists to ask. Outside a repository steps 2 and 3 do not apply; say so.

1. **Name what is still open.** Uncommitted and untracked files in every checkout this session
   touched, `harness worktree audit`, the pull requests this session opened and the state of their
   checks, background work still running, and the decisions you parked for the user. Report that
   list first; an empty sweep is a result, so say it and move on.
2. **Land what is ready** with the `land` workflow, never by inlining its steps: the merge proof
   and its refusals are the point of it. Anything not green, not approved, or not yours to merge
   stays open and goes in the report.
3. **Hand off** with the `handoff` workflow, and only when work in this repository continues past
   this session. A finished piece of work needs no progress file.
4. **Batch the follow-ups.** One line each, title and why, for what this session found and did not
   do. File them as issues on an explicit go-ahead, never before, and never quietly fix one here
   instead of filing it.
5. **Tell the sessions that depend on this one**, where the client can list and message them: a
   branch one was waiting on, a file one holds open, a conclusion that reverses its premise.
   Sharing a group or a repository is not a dependency; where the client cannot, use the handoff.
6. **Archive, or stop.** Archive when the invocation already asked for it, and otherwise end on
   the checklist and wait. Never clear or compact first: archiving ends the session, so both only
   burn the context you still need. Clearing belongs to carrying on in the same session, which is
   the opposite of this workflow.

Log the close-out before the archive call, which ends the turn, and report what landed, what you
filed, whom you told, and what you are leaving open.
