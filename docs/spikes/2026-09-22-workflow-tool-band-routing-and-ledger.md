# Spike: does the Claude Code Workflow tool bypass band routing, confinement and the ledger?

> **Result: partially bypassed, measured 2026-09-22 on Claude Code 2.1.280.** A workflow script's
> `agent()` calls produce no `Agent` tool call in the session, so `tier-agent-spawns`, `brief-guard`
> and the constrained-role refusal in `lib/harness_core/lifecycle.py` never see them: band routing
> and role confinement are both bypassed, and a script can run a read-only harness role in-session
> by naming it. The usage ledger is not bypassed — `usage-log.py` records every workflow agent —
> but its reroute join is empty for those rows, so compliance cannot be measured from them.

## Question

When a session runs the `Workflow` tool, and the script calls `agent(prompt, {label, phase, schema,
model?})`, do those spawns pass through the harness `PreToolUse` `Agent` chain, and do their returns
land in `~/.local/state/agent-harness/usage.jsonl` as subagent rows attributed to the parent session?

Three sub-questions, from the issue: does `tier-agent-spawns` fire on a script's `agent()` calls; can
a script invoke `harness role run` for a confined role; does `usage-log` attribute a script's agents
to the parent session.

## Machine

Apple M5 Pro, macOS 26.5 (Darwin 25.5.0). Claude Code 2.1.280, harness 0.12.0 installed at user
scope with its hooks live. Four headless `claude -p` runs, $0.90 in total, each under five seconds.

## Experiment

A project workflow at `/tmp/ah013/s540-probe/.claude/workflows/ah-spike-probe.js` with three
`agent()` calls in one phase, run headless from that directory:

```sh
claude -p "/ah-spike-probe" --model sonnet --allowedTools Workflow --output-format json
```

1. `agent('… ALPHA …', { label: 'bare' })` — names nothing, which through the `Agent` tool is what
   `tier-agent-spawns` rewrites to the cost variant's default band worker.
2. `agent('harness-role: reviewer\n… BETA …', { label: 'marker' })` — a brief declaring a constrained
   role, which `marker_role` refuses through the `Agent` tool however it is spawned.
3. `agent('… GAMMA …', { label: 'named', agentType: 'reviewer' })` — names the constrained role
   outright, which `constrained_role` refuses with the `harness role run` instruction.

Three further runs probed the runtime's reach: one agent asked to run `echo`, one asked to run a
destructive `rm -rf` against a scratch directory, and one asked to spawn a nested subagent.

## Measured result

**All three calls ran.** The probe returned `{"bare":"ALPHA","marked":"BETA","named":"GAMMA"}`. The
agent sidecars under `~/.claude/projects/<project>/<session>/subagents/workflows/wf_23583536-65e/`
record what ran:

```json
{"agentType":"workflow-subagent","description":"bare","workflowPhase":"probe","spawnDepth":1}
{"agentType":"workflow-subagent","description":"marker","workflowPhase":"probe","spawnDepth":1}
{"agentType":"reviewer","description":"named","workflowPhase":"probe","spawnDepth":1}
```

**No `Agent` tool call exists for any of them.** The parent transcript for the probe session holds
exactly one `tool_use` block, `Workflow`. `decisions.jsonl` holds zero rows for that session id, so
no hook in the chain ran on the spawns, and none ran on the launch either: the settings template
matches `Bash`, `WebFetch`, `Agent` and `Write|Edit`, and nothing matches `Workflow`.

**The script picks class and effort directly.** The runtime's own signature, read out of the
installed client, is `agent(prompt, opts?: {label?, phase?, schema?, model?, effort?, isolation?,
agentType?})`. `model`, `effort` and `agentType` are what the `delegation` and `cost` stances exist
to decide, and a script sets all three with nothing in the way.

**`agentType` resolves the user's agent definitions.** The third call ran as `reviewer` on that
definition's model rather than the session's `sonnet`, in session, with no isolated worker — the exact spawn `role_deny` refuses through the `Agent` tool.

**The ledger recorded all of it.** `usage-log.py` walks `subagents/` recursively, so the probe
session produced one session row and three subagent rows, each with `workflow: "wf_23583536-65e"`:

| agent_type | model | output | tool_use_id | rerouted | budget_output_tokens |
| --- | --- | --- | --- | --- | --- |
| workflow-subagent | claude-sonnet-5 | 702 | `""` | false | null |
| workflow-subagent | claude-sonnet-5 | 7 | `""` | false | null |
| reviewer | claude-opus-5-5 | 198 | `""` | false | 22000 |

A workflow agent's `.meta.json` carries no `toolUseId` — an in-session subagent's does — so
`mark_reroutes` has nothing to join on and `requested_type` and `rerouted` stay empty for every such
row. Across this machine's history the ledger already holds 1,657 workflow rows, all at
`spawn_depth` 1, all with an empty `tool_use_id`: 1,642 as `workflow-subagent` and 15 as `Explore`
or `Plan`, on models from `claude-sonnet-5` up to `claude-fable-5-1`, the class that
`tier-agent-spawns` refuses by request, at efforts up to `max`.

**A script cannot reach confinement, and does not need to.** The runtime gives the script body no
filesystem or shell access and refuses `import()`, so no script can call `harness role run` itself;
only an agent it spawns could, through `Bash`. It has no reason to: naming the role in `agentType`
gets the role unconfined.

**Fan-out is one level deep.** An agent asked to spawn a nested subagent returned `NO-AGENT-TOOL`;
the built-in `workflow-subagent` definition disallows the `Agent` tool. That matches every historical
row sitting at `spawn_depth` 1, and it means the `Agent` chain has no second chance inside a run.

**Not measured:** whether `PreToolUse` fires on a workflow agent's own `Bash`. The `echo` probe was
graded 0, which the harness does not log, and the `rm -rf` probe was refused by the agent itself
before it reached the tool. The documentation asserts that "the agents' tool calls receive the same
permission checks and sandboxing as any other tool call in the session"; that claim is untested here.

## Verdict

| Sub-question | Answer |
| --- | --- |
| Does `tier-agent-spawns` fire on a script's `agent()` calls? | **No.** Bypassed. |
| Can a script invoke `harness role run` for a confined role? | **No** — and it can run the role unconfined instead. Bypassed. |
| Does `usage-log` attribute a script's agents to the parent session? | **Yes.** Not bypassed. |

Partially bypassed: routing and confinement are out of reach, accounting is intact.

## Follow-ups the code needs

1. **Guard the `Workflow` launch.** The harness cannot rewrite an `agent()` call inside a script, but
   the launch is a tool call it can match. A `PreToolUse` `Workflow` branch should record the launch
   in `decisions.jsonl`, refuse it when the `delegation` stance is `off`, and refuse a script whose
   text names a constrained role in `agentType`, with the same `role_instruction` sentence the
   `Agent` refusal carries; the same read is where an `effort` or `model` a script names could be
   read against the cost variant. The tool input is the script itself, as `script` or `scriptPath`, so the
   check is a read of text the session already has.
2. **Say what a workflow row means.** A workflow row's empty `tool_use_id` makes it look like a spawn
   that was never rerouted, so any compliance figure over the ledger silently counts it as compliant;
   and a row named for a role picks up that role's soft budget although it ran unconfined. `harness
   usage` should separate workflow spend and stop pricing a workflow row against a confined role's
   budget.
