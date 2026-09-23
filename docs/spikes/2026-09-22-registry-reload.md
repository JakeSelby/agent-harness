# Spike: can a running session learn that it can resolve the band workers?

> **Result: keep the conservative gate, and refresh it from a signal that exists.** Claude Code
> reloads its agent registry mid-session in an interactive session and never in a headless one,
> and it records both cases in the transcript as an `agent_listing_delta` attachment. That record
> is a per-session, positive statement of what this session can resolve now, so the spawn hook can
> lift its gate without guessing which kind of session it is in.

## Question

A spawn hook reroutes an unnamed subagent to a band worker only when the session's own start-time
record names that worker, because a `subagent_type` the running session cannot resolve fails the
spawn outright. Is there a signal a hook can read that says a session which started before
`harness sync` installed the workers can now resolve them — or does none exist, leaving the gate
permanent?

## Machine

Apple M5 Pro, 24 GiB, macOS 26.5 (Darwin 25.5.0). Claude Code 2.1.278 for the headless probes;
the client self-updated to 2.1.280 during the interactive ones. Codex CLI 0.155.0-alpha.9.2 was
not exercised, for the reason under "Not run". Eight sessions, about $4 of usage.

## Experiment

Each probe started a session, created an agent definition **after** it was running, waited, and
asked the session to spawn that type. The definition's body returned a token that appeared nowhere
in the prompt, so a reply proves a subagent ran rather than the main model paraphrasing a file.

| Probe | Session | Where the definition was created | Result |
| --- | --- | --- | --- |
| A | `claude -p` | project `.claude/agents/`, directory created in the same turn | `Agent type … not found` |
| B | `claude -p` | project `.claude/agents/`, directory existed at start, 15 s wait | `Agent type … not found` |
| D | `claude -p --input-format stream-json`, two turns in one process | project `.claude/agents/`, created in turn 1, spawned in turn 2 | `Agent type … not found` |
| E/F | interactive (pty-driven) | project `.claude/agents/`, directory existed at start, 30 s wait | spawned, token returned |
| G | interactive | `~/.claude/agents/`, added as a **symlink**, which is the shape `harness sync` writes | spawned, token returned |
| I/J | interactive | `~/.claude/agents/`, plain file | spawned, token returned |

Probes H and I also installed a `SessionStart` and a `FileChanged` hook through `--settings`, to
see what a hook is told.

## Measured

- **The registry does reload, but only in an interactive session.** Every headless probe failed
  with the same error, which enumerates the registry as loaded at process start. Probe A's failure
  is the documented exception: the watcher covers only `agents` directories that existed when the
  session started.
- **The transcript says so.** Every session writes an `attachment` record of type
  `agent_listing_delta` with `isInitial: true` and an `addedTypes` list holding the registry at
  start. The interactive probe wrote a **second** record — `isInitial: false`,
  `addedTypes: ["probe-iota"]`, `removedTypes: []` — after the definition appeared, attached to the
  user turn before the assistant's `Agent` call. No headless session wrote a second record. The
  signal and the capability line up exactly, so a reader needs no interactive-versus-headless
  guess.
- **`FileChanged` fires in both kinds of session.** A `SessionStart` hook returning `watchPaths`
  for a worker path, plus a `FileChanged` hook, was delivered `{"event": "add", "file_path": …}` in
  the headless probe as well as the interactive one. It reports that a file appeared, not that a
  registry reloaded, so it is not safe on its own: acting on it in a headless session would turn a
  spawn that works into one that fails.
- **`SessionStart` carries `model` interactively and omits it headlessly** in these runs. The hooks
  reference says the field is not always included, so it is a correlation, not a gate.
- **The vendor documentation agrees with the interactive measurements** and states the three cases
  that still need a restart: an `agents` directory created after the session started, a directory
  added with `--add-dir`, and a session started with `--disable-slash-commands`. It does not
  mention headless sessions; the measurement above is the evidence for those.

## Verdict — keep, with a refresh, which landed with this record

The conservative gate stays as the floor, and the session record gained a second source in the
same change: `posture.transcript_agents` reads the `agent_listing_delta` attachments in the
session's own transcript, over a bounded tail, and `routable()` in the spawn hook routes to a
worker the record predates when a later delta names it. Only records with `isInitial` false
count, and `addedTypes` and `removedTypes` are applied in the order they were written. Run against
the transcripts these probes left behind, the reader answers `["probe-iota"]` for the interactive
session that reloaded and `None` for the headless one that could not.

The invariant holds: the set is the runtime's own statement about itself, so it can only name a
type the session has loaded. A session that never reloads produces only the initial record, which
is what the start-time record already holds. A delta that lands mid-turn is not attached until the
next user turn, so routing resumes one turn later than it could — conservative in the safe
direction.

## What the code does with it, and what it still does not

- An absent transcript, an unreadable tail and a listing that has fallen out of the tail all read
  as unknown, which routes nothing: the session record decides those, exactly as before.
- The "start a new session to route unnamed spawns" notice is still what a session that has not
  reloaded hears.
- The pricing hook asks the same function with the same transcript, so a spawn is never priced by
  one band and routed to another.
- Nothing is built on `FileChanged` or on `SessionStart`'s `model` field; both were measured and
  both are weaker than the delta.
- Left open: the delta is attached at the next user turn, so a session that reloads mid-turn
  resumes routing one turn later than it could. Conservative in the safe direction, and no code
  can shorten it.

## Not run

- **Codex.** The gate exists only in the Claude Code hooks, and Codex has no spawn hook that could
  consume a reload signal; its role projections are files under the client's own `agents`
  directory. Whether that client rereads them mid-session is a question for the run that gives
  Codex an equivalent gate.
- **An edited definition**, as opposed to an added one. The gate is about types a session cannot
  resolve at all, so a changed body was out of scope.
