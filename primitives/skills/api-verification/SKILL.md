---
name: api-verification
description: Prove a search, filter or API answer is real before you rely on it, and budget web search across a fan-out. Use when querying an unfamiliar API, when a filter returns suspiciously clean results, when a per-item error might have been swallowed, and when briefing research agents.
---

# Research and API verification

The operative lines live in the resident rule `primitives/rules/research-and-verification.md`. This
skill carries the reasoning, the arithmetic behind the search budget, and what to do after a
fan-out.

Read the research stance and `harness stances --json` operational budgets before allocating
searches. Provider limits are separate hard ceilings; budget exhaustion leaves explicit gaps.

## Search budget

**Web search is capped per session and shared by every subagent in that session.** Allocate the resolved `search_calls` budget across the whole session before delegating;
also respect the provider's actual limits.

Keep the fan-out within `fan_out` and assign each gatherer a share of the search budget. For bigger runs, stagger
waves across separate sessions, or brief agents to lean on fetching known primary sources.

After a fan-out, check each subagent's search count and re-run starved, discovery-heavy
dimensions in a fresh session. Fetch-only agents are fine for licence pages and official docs,
thin for "what shipped recently" questions.

## Prove an API answer is real

- **Unknown query parameters are silently ignored by most APIs.** Prove a filter bites by
  sending a value that can never match and confirming the result is empty.
- **Spot-check one returned record** against the field you filtered on before trusting the set.
- **A swallowed per-item error is unknown, not absent.** Count the failures separately from the
  empties.
- **Re-check the live spec** before assuming a documented workaround is still needed.

## Prefer primary sources

Defer to human-written documentation over agent-generated summaries, and trace every rule you
rely on to a quotable source. When a file's header and its body disagree, neither is ground
truth: find the code or the spec that decides it.
