---
title: 'technical research: runtime platform limits and native release qualification'
type: 'technical'
topic: 'runtime platform limits and native release qualification'
decision: 'Which Claude Code and Codex capabilities the harness architecture may rely on, which it must work around, and what a release has to prove natively before it ships.'
source: 'process: in-repo docs and compatibility catalog at commit 3020251; GitHub issues and PRs of JakeSelby/agent-harness; maintainer notes (unpublished), 2026-09-21, release-process cost analysis; 7 fetches of official Claude Code and Codex documentation (imports/SOURCES.md)'
status: complete
preset: 'standard'
validation: 'normal'
issue: 617
claims_verified: 6
claims_unverified: 7
claims_disputed: 2
claims_overturned: 0
created: '2026-09-23'
updated: '2026-09-23'
---

# technical research: runtime platform limits and native release qualification

**Decision this research serves:** which Claude Code and Codex capabilities the harness architecture
may rely on, which it must work around, and what a release has to prove natively before it ships.

## Executive summary

**Verdict:** build enforcement on Claude Code `PreToolUse` deny and rewrite, isolated CLI workers
and the local ledger. Treat Codex as an advisory surface whose event set must be probed for each
client version. Make a release requirement of at least one natively qualified target, now that
every required case is scripted.

What drives it:

1. **Hooks gate inputs; they do not own outputs or context.** Claude Code hooks cannot replace a
   built-in tool's result and cannot trigger compaction [30]. Codex hooks cannot `ask`, need
   per-definition trust and miss hosted tools [31][4]. A plugin cannot carry hooks without firing
   them twice [29].
2. **Confinement has three holes the architecture must name.** Codex read confinement is
   advisory [7]. The Workflow tool's `agent()` spawns bypass the whole `Agent` hook chain [11].
   The spawn guard misses a paraphrased brief [13].
3. **Qualification is now automatable but unproven.** 0.12.0 shipped with no qualified target:
   one of eleven cases was automated, and a partial record cannot qualify a client [15][1]. All
   required cases are now scripted, but no Codex round has been driven through the runner, and
   the claim that a release costs one round has not been measured [16][3].

**Biggest caveat:** the Codex event surface is disputed. The catalog says Codex raises no
`UserPromptSubmit`, `SubagentStart` or `SubagentStop` [13], and current Codex documentation lists
all three [31]. The harness evidence is on Codex 0.154–0.155 and the latest release is 0.156.1
[35]. Until a native probe settles it, design Codex features as version-gated.

## 1. Hook and event surface per runtime

- Claude Code can replace a `PostToolUse` result only for MCP tools, through
  `updatedMCPToolOutput`. Built-in tools such as Bash and Read do not support output
  modification [30].
- No Claude Code hook can trigger or request compaction; `PreCompact` and `PostCompact` are
  display-only [30].
- Claude Code settings, policy and plugin hooks run inside subagents, and their tool events carry
  `agent_id` and `agent_type` [30].
- Codex cannot pause on `ask`: the value is parsed, unsupported, and marks the hook run failed
  [31]. The harness therefore denies with a reason where Claude would ask [4].
- Codex documents `deny`, and `allow` with `updatedInput` as a rewrite [31]. This disputes #310's
  statement that the Codex client rejects `allow` [22], and the catalog records that Codex output
  filter rewrites are never applied [13].
- Codex `PreToolUse` covers Bash, `apply_patch`, MCP and local function tools, not hosted tools
  such as WebSearch [31]. This matches the harness's statement that hosted search is not
  universally intercepted [4].
- Codex runs a non-managed hook only after the user trusts that exact definition [31]. Hook
  registration is therefore not activation [4].
- **`UserPromptSubmit` on Codex is disputed.** The catalog limitation says Codex raises none of
  `UserPromptSubmit`, `SubagentStart` or `SubagentStop`, so the usage feed is Claude-only [13].
  The current Codex hooks page lists all three [31]. The 0.156.x changelog records no hook change
  [35], so when these events arrived is unknown.

## 2. Cost and telemetry exposure

- Claude Code exports `claude_code.cost.usage` in USD [33]. It resolves OTLP headers at run time
  through `otelHeadersHelper`, which reruns every 29 minutes by default [33][10].
- Codex takes `[otel]` headers only as a literal `map<string,string>` in `config.toml`. It
  documents no environment or command indirection and no resource-attribute key [32]. The harness
  therefore writes no Codex headers or labels, and native Codex export needs an unauthenticated
  endpoint [10].
- Codex's default `metrics_exporter` sink drops token, turn-cost, tool-call and API-call metrics
  client-side, so the harness sets it explicitly. This rests on a source read, not a run [10].
- The harness dollar figure is a list-price API equivalent from `policy/prices.json`, not an
  invoice [10].
- A Claude Code session row includes its subagents. Codex subagent rows and role-worker rows are
  priced alone [10].
- Codex cumulative token snapshots are counted once, and missing measurements stay null [4].
- Claude Code attaches `user.email`, the account ids, `organization.id` and `session.id` by default
  [33]. The harness sets none of the `OTEL_METRICS_INCLUDE_*` switches [10].

## 3. Subagent and worker confinement

- **Isolated worker model.** Read-only and planner roles run as separate native CLI processes.
  They were moved there because parent permissions can override native subagent defaults
  [7][24][4].
  - The Claude worker runs in safe mode, with `Read`, `Grep` and `Glob` only and an empty MCP
    config [7].
  - The Codex worker gets a fresh home and a read-only sandbox, and runs with delegation, hosted
    search and memory disabled [7].
- Read confinement is enforced on Claude Code, where the tools resolve against `--add-dir` roots.
  It is advisory on Codex, whose read-only sandbox can read any path the runtime permits [7].
- **Offline gatherer as a boundary.** No isolated worker reaches the network, so a dimension that
  needs the live web goes to an in-session band worker, under session permissions and the search
  budget [7].
  - macOS Codex probes denied network and writes [24].
  - Under Codex `auto`, a worker launched from a sandboxed turn stalls until its deadline (#293)
    [13].
- The spawn guards are best effort. They refuse a constrained role's brief that is re-issued
  verbatim, a near copy of it, or a brief with a `harness-role:` marker [7]. A rewritten brief, or
  a framework no descriptor covers, still runs unconfined, and one confined Linux run took five
  attempts [13].
- **Workflow-tool routing gap.** On Claude Code 2.1.280, a Workflow script's `agent()` calls
  produce no `Agent` tool call [11][27]:
  - no hook matches `Workflow`;
  - `agentType: 'reviewer'` ran the read-only role in session, unconfined;
  - the script sets `model` and `effort` directly;
  - fan-out is one level deep.
- The ledger still records workflow agents, but with an empty `tool_use_id`, so all 1,657
  historical workflow rows read as unrerouted spawns [11]. Guarding the launch (#576) and
  separating workflow spend (#577) are both open [25][26].
- Whether `PreToolUse` fires on a workflow agent's own Bash was not measured [11].

## 4. Session continuity and Remote Control

- Claude Code reloads its agent registry mid-session only in interactive sessions; eight probes
  showed headless sessions never reload [12].
  - The runtime's `agent_listing_delta` transcript record is the only safe signal. `FileChanged`
    fires in both session kinds [12].
  - Routing now resumes from that delta and routes one turn late after a mid-turn reload [28].
  - Codex has no spawn hook, so this was not tested there [12].
- Cross-runtime continuation uses a revisioned shared task record. Verification carries across
  only as unverified evidence, the receiving session reruns the gate, and approvals never
  transfer [9].
- Remote Control hosting is Claude Code on macOS only; Codex has no equivalent [6].
  - A server gives up after roughly 10 minutes offline and exits [34][6], which an observed outage
    confirmed on 2.1.278 [17].
  - Stopped sessions can be brought back for about four hours unless the server started with
    `--no-create-session-in-dir` [34].
  - API keys are unsupported, and workspace trust must be accepted in each exact directory
    [34][6].
- **The harness's supervision rests on internals it read from the client binary**: the
  `bridge-pointer.json` reuse path and the `bridge/reconnect` endpoint [17].
  - Every managed host ran with `--no-create-session-in-dir`, so on 2.1.280 none ever reused its
    environment [19].
  - The fix is an open PR, and 2.1.280 also added two pointer keys [20].
  - The network-cut test needs a human trust dialog and a live session, so it was left to
    qualification [18].
- Disposable homes depend on `CLAUDE_CONFIG_DIR` and `CODEX_HOME` moving the whole native home
  [3]. `CLAUDE_CONFIG_DIR` taking precedence over `HARNESS_HOME` is the correct runtime behaviour;
  the leak it caused was a test-isolation defect [21].

## 5. Plugin channel

- Plugin hooks merge with user and project hooks; they do not replace them [30]. The manifest
  therefore ships no `hooks` key, because a machine running both the plugin and `harness sync`
  would fire every hook twice [29].
- A marketplace install is therefore a strict subset of `harness install`. It has no command
  grading, stop gate, usage feed, stance selection or Codex projection, and it is unqualified [5].
  Its tier restriction is advisory [1].

## 6. Qualification method

- **What a round proves.** A client is qualified when its required cases pass natively [1].
  - A capability is qualified only if a native case exercising it also passed. No adapter names
    one, so every capability is unqualified even on a qualified client [1].
  - A reviewer must assess the observations, and the assessment class is floored at `strong`,
    distinct from the execution class [3].
- **What it costs.** One four-target round took about 60 minutes and about 1M orchestrator tokens,
  plus 0.75M–1.3M client tokens per Codex target [16].
  - Three of 0.11.0's four rounds were rework: about 3 hours and about 3M orchestrator tokens
    [16].
  - Codex targets cost about 2.5× the Claude ones: 49–61 minutes and 224–239 tool calls, against
    20–30 minutes and 86–112 [16][14].
  - Model-free lifecycle acceptance takes about 2 minutes per system [14].
  - Workers ran 0.7×–1.8× their 82K output budget, an estimate [3].
- **How much is automated.** Every required case is now scripted (#336), with per-target scoping,
  a smoke tier and a cheaper execution class landed. The one-round claim still awaits the v0.13.0
  round [16].
  - No Codex round has been driven through the runner. Codex verdicts stay `unverified` until a
    hand qualification agrees and `--home-confirmed` is passed [3].
  - The smoke tier spends no model turn and never counts as qualification [3].
- **Why 0.12.0 shipped with no qualified target.** One of eleven cases was automated, and
  `evidence_errors` rejects a record that does not cover every required case. So one target cost
  roughly what two did, and the release took a narrower contract; no Linux host was available
  either [15].
  - The catalog marks all eight Claude Code and Codex client rows unqualified, with
    `required_for_release: false` [13].
  - The v0.11.1 floor remains the last qualified release [1].
- **How evidence is invalidated.** Per target: the shared runtime source minus other runtimes'
  adapter directories, with `bindings.json`, `capabilities.json` and `worker.py` carved back as
  shared. Only `hook.py` is private [1]. Per-case scoping is not implemented and needs an owner
  decision [1].
  - A record is tied to its exact client version, platform and harness version, and to an ancestor
    commit [1].
  - A released record stays immutable while changed source is blocked [23].
  - A runtime behaviour change is a patch-release reason to narrow a claim [2].
  - The required case set changed after 0.11.1, from 11 cases including `bmad-workflow` to 12, so
    no existing record carries forward [13].

## Cross-dimension insights

- **Codex is advisory everywhere the harness enforces.** The tier restriction is advisory there
  [1], read confinement is advisory [7], `ask` is unavailable [31], and native telemetry cannot
  authenticate [32]. On top of that, the runner has never driven Codex [3]. Any requirement that
  reads "the harness enforces X" is really a Claude Code requirement.
- **Enforcement coverage is a moving target driven by new spawn paths.** The Workflow tool [11], a
  plugin install [5] and headless sessions [12] each opened a path the `Agent`-centred hook chain
  did not see. A qualification case list frozen per release will miss the next one unless a case
  enumerates spawn paths.
- **Two platform features rest on reading undocumented client internals**: the Remote Control
  pointer and reconnect path [17][19], and the Workflow `agent()` signature [11]. The vendor
  changed both within days, from 2.1.278 to 2.1.280 [19][20]. Neither can carry a stability
  promise.

## Recommendations

**Architecture spine: constraints and ADs**

1. **Enforcement constraint:** harness enforcement may rely only on `PreToolUse` deny, a
   `PreToolUse` input rewrite, isolated workers and the local ledger. No AD may depend on:
   - replacing a built-in tool's result;
   - triggering compaction from a hook;
   - Codex `ask` [30][31].
   Confidence: medium (primary vendor docs, single source each).
2. **Per-runtime capability AD:** state every enforced capability per runtime, as the tier
   restriction row already does [1], and probe Codex events for each client version rather than
   hard-coding "Codex lacks `UserPromptSubmit`". That claim is disputed [13][31].
3. **Confinement AD:** constrained roles run only in isolated, offline workers [7]. Every spawn
   path must be enumerated and either guarded or declared unguarded. The Workflow launch guard
   (#576) belongs in the spine as a named gap [11][25]. Confidence: medium, from one experiment.
4. **Plugin channel constraint:** the plugin carries no hooks by construction, so the marketplace
   surface is advisory-only [29][30]. Confidence: high.
5. **Remote Control AD:** isolate everything read from the client binary behind a version-pinned
   adapter with `doctor` checks. Keep it out of the v1 stable surface [17][19][2]. Confidence:
   medium.
6. **Telemetry AD:** the ledger is the record, and native Codex export is unauthenticated-only
   until Codex adds header indirection [10][32]. Confidence: high.

**PRD: release requirements and non-functional requirements**

1. **Release requirement:** a minor release marks at least `claude-code-cli-macos` as required
   for release, now that its cases are scripted [16][3]. Shipping with none, as 0.12.0 did [15],
   should need an explicit waiver published in the catalog. Confidence: medium; the scripted
   round is unmeasured.
2. **Codex requirement:** Codex targets stay non-required until one hand-compared round passes
   `--home-confirmed` [3].
3. **Qualification NFR:** a release costs one round, and the baseline to beat is about 60 minutes
   and about 1M orchestrator tokens [16]. The v0.13.0 round must record its actual figures [16].
   Confidence: medium, from single-publisher measurements.
4. **Evidence NFR:** evidence is invalidated per target, with the assessor class at or above
   `strong` and a reviewer reading every observation [1][3]. Per-case scoping remains an owner
   decision [1].
5. **Capability-scope decision:** before v1, decide whether capability-level qualification is in
   scope. Today no capability can be qualified [1].
6. **Freshness requirement:** a Claude Code or Codex release that changes a relied-on behaviour
   triggers a catalog patch under the policy's external-runtime clause [2]. Platform claims here
   age out within a month.

## Open questions

1. Does Codex 0.156.x raise `UserPromptSubmit`, `SubagentStart` and `SubagentStop`, and does it
   honour a `PreToolUse` `allow` with `updatedInput`? This needs one native probe on the current
   Codex [31][13][22].
2. Does `PreToolUse` fire on a Workflow agent's own Bash? This needs a graded probe, since a
   grade-0 command is not logged [11].
3. Does a scripted round hold a release to one pass, and at what token cost? The v0.13.0 round
   answers it [16].
4. Does the runner's Codex reading agree with a hand qualification? This needs the first Codex
   round [3].
5. Does Codex reread its agent definitions mid-session? This needs a Codex spawn gate first [12].
6. Does the open Remote Control fix survive a real network cut? This needs a trusted folder and a
   live session [18][20].
7. When will a Linux host exist for the Linux targets? This needs provisioning [15].
8. Should capability-level acceptance cases be required before v1? This is an owner decision [1].

## Source appendix

| [n] | claim/finding it supports | publisher | pub date | accessed | confidence |
|---|---|---|---|---|---|
| [1] | qualification levels, per-target invalidation, tier row, 0.12.0 status | [agent-harness docs/compatibility.md](https://github.com/JakeSelby/agent-harness/blob/main/docs/compatibility.md) | 2026-09-23 | 2026-09-23 | high |
| [2] | stable interfaces; external-runtime patch clause | [agent-harness docs/compatibility-policy.md](https://github.com/JakeSelby/agent-harness/blob/main/docs/compatibility-policy.md) | 2026-09-19 | 2026-09-23 | high |
| [3] | runner, class floors, Codex not driven, budget estimate | [agent-harness docs/qualification-runbook.md](https://github.com/JakeSelby/agent-harness/blob/main/docs/qualification-runbook.md) | 2026-09-23 | 2026-09-23 | high |
| [4] | Codex ask, hook trust, hosted search, session-scoped routing | [agent-harness docs/runtime-controls.md](https://github.com/JakeSelby/agent-harness/blob/main/docs/runtime-controls.md) | 2026-09-23 | 2026-09-23 | high |
| [5] | marketplace install subset | [agent-harness docs/runtime-installation.md](https://github.com/JakeSelby/agent-harness/blob/main/docs/runtime-installation.md) | 2026-09-22 | 2026-09-23 | high |
| [6] | Remote Control host behaviour, macOS only | [agent-harness docs/remote-control.md](https://github.com/JakeSelby/agent-harness/blob/main/docs/remote-control.md) | 2026-09-22 | 2026-09-23 | high |
| [7] | isolated workers, offline gatherer, Codex read advisory | [agent-harness docs/role-workers.md](https://github.com/JakeSelby/agent-harness/blob/main/docs/role-workers.md) | 2026-09-23 | 2026-09-23 | high |
| [8] | sandbox is runtime-specific and not owned | [agent-harness docs/sandboxing.md](https://github.com/JakeSelby/agent-harness/blob/main/docs/sandboxing.md) | 2026-09-19 | 2026-09-23 | high |
| [9] | cross-runtime continuation | [agent-harness docs/task-continuation.md](https://github.com/JakeSelby/agent-harness/blob/main/docs/task-continuation.md) | 2026-09-23 | 2026-09-23 | high |
| [10] | native telemetry per runtime, pricing | [agent-harness docs/telemetry.md](https://github.com/JakeSelby/agent-harness/blob/main/docs/telemetry.md) | 2026-09-23 | 2026-09-23 | high |
| [11] | Workflow tool bypass | [agent-harness workflow-tool spike](https://github.com/JakeSelby/agent-harness/blob/main/docs/spikes/2026-09-22-workflow-tool-band-routing-and-ledger.md) | 2026-09-22 | 2026-09-23 | medium |
| [12] | registry reload interactive only | [agent-harness registry-reload spike](https://github.com/JakeSelby/agent-harness/blob/main/docs/spikes/2026-09-22-registry-reload.md) | 2026-09-22 | 2026-09-23 | medium |
| [13] | catalog state, evidence index, limitations | [agent-harness compatibility/catalog.json](https://github.com/JakeSelby/agent-harness/blob/main/compatibility/catalog.json) | 2026-09-23 | 2026-09-23 | high |
| [14] | per-target times, tool calls, lifecycle cost | maintainer notes (unpublished), release-process cost analysis | 2026-09-21 | 2026-09-23 | medium |
| [15] | why 0.12.0 shipped unqualified | [agent-harness #533](https://github.com/JakeSelby/agent-harness/issues/533) | 2026-09-22 | 2026-09-23 | high |
| [16] | round cost, rework, automation landed | [agent-harness #340](https://github.com/JakeSelby/agent-harness/issues/340) | 2026-09-21 | 2026-09-23 | medium |
| [17] | Remote Control outage and binary-read root cause | [agent-harness #483](https://github.com/JakeSelby/agent-harness/issues/483) | 2026-09-22 | 2026-09-23 | high |
| [18] | heal shipped; network-cut test left to qualification | [agent-harness PR #515](https://github.com/JakeSelby/agent-harness/pull/515) | 2026-09-22 | 2026-09-23 | high |
| [19] | no-create-session-in-dir blocks reuse | [agent-harness #603](https://github.com/JakeSelby/agent-harness/issues/603) | 2026-09-23 | 2026-09-23 | high |
| [20] | open reuse fix, new pointer keys | [agent-harness PR #604](https://github.com/JakeSelby/agent-harness/pull/604) | 2026-09-23 | 2026-09-23 | medium |
| [21] | CLAUDE_CONFIG_DIR precedence | [agent-harness #498](https://github.com/JakeSelby/agent-harness/issues/498) | 2026-09-22 | 2026-09-23 | high |
| [22] | Codex rejects allow (disputed) | [agent-harness #310](https://github.com/JakeSelby/agent-harness/issues/310) | 2026-09-21 | 2026-09-23 | low |
| [23] | released evidence immutable | [agent-harness PR #201](https://github.com/JakeSelby/agent-harness/pull/201) | 2026-09-19 | 2026-09-23 | high |
| [24] | why isolated workers; Codex network denied | [agent-harness PR #115](https://github.com/JakeSelby/agent-harness/pull/115) | 2026-09-19 | 2026-09-23 | high |
| [25] | Workflow launch guard open | [agent-harness #576](https://github.com/JakeSelby/agent-harness/issues/576) | 2026-09-23 | 2026-09-23 | high |
| [26] | workflow spend separation open | [agent-harness #577](https://github.com/JakeSelby/agent-harness/issues/577) | 2026-09-23 | 2026-09-23 | high |
| [27] | Workflow spike scope and verdict | [agent-harness PR #578](https://github.com/JakeSelby/agent-harness/pull/578) | 2026-09-23 | 2026-09-23 | high |
| [28] | routing resumes from listing delta | [agent-harness PR #584](https://github.com/JakeSelby/agent-harness/pull/584) | 2026-09-23 | 2026-09-23 | high |
| [29] | plugin ships no hooks: merge double-fires | [agent-harness PR #465](https://github.com/JakeSelby/agent-harness/pull/465) | 2026-09-22 | 2026-09-23 | high |
| [30] | Claude Code hook limits and merge | [Anthropic Claude Code hooks reference](https://code.claude.com/docs/en/hooks) | 2026-09-23 | 2026-09-23 | medium |
| [31] | Codex hook events and decisions | [OpenAI Codex hooks](https://learn.chatgpt.com/docs/hooks) | 2026-09-23 | 2026-09-23 | medium |
| [32] | Codex OTEL headers literal only | [OpenAI Codex config reference](https://learn.chatgpt.com/docs/config-file/config-reference) | 2026-09-23 | 2026-09-23 | high |
| [33] | Claude Code USD metric, headers helper | [Anthropic Claude Code monitoring](https://code.claude.com/docs/en/monitoring-usage) | 2026-09-23 | 2026-09-23 | high |
| [34] | Remote Control give-up, resume window, auth | [Anthropic Claude Code Remote Control](https://code.claude.com/docs/en/remote-control) | 2026-09-23 | 2026-09-23 | high |
| [35] | latest Codex 0.156.1, no hook change listed | [OpenAI Codex changelog](https://learn.chatgpt.com/docs/changelog) | 2026-09-23 | 2026-09-23 | medium |

Source [8] is used only to scope the other claims: the sandbox is the user's to configure, and
the harness writes none of it [8].

## Staleness map

Computed with `recon_kit.py staleness` from the claim ledger. The windows, in months, are
version-compat 1, platform-capability 1, harness-design 3 and cost-measurement 6. Nothing is
stale today.

- **2026-10-21:** the Codex `allow` dispute [22].
- **2026-10-22:** the Workflow bypass [11], registry reload [12] and plugin hook merge [29].
- **2026-10-23:** all other platform-capability and version-compat claims [30][31][4][10][7][34]
  [19][1].
- **2026-12-22 to 2026-12-23:** the harness-design claims [15][16][3][1].
- **2027-03-21:** the qualification cost figures [16].

The earliest re-check is **2026-10-21**. Refresh sooner on any Claude Code or Codex release.
