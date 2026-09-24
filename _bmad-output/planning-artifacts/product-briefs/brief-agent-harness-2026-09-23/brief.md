---
title: Agent Harness product brief
status: final
created: 2026-09-23
updated: 2026-09-24
supersedes: ../brief-agent-harness-2026-09-19/brief.md
sources:
  - ../../source-ledger.md
  - ../../prds/prd-agent-harness-2026-09-23/prd.md
  - ../../research/
---

# Product Brief: Agent Harness

## Executive summary

Agent Harness is a user-owned layer over the coding agents a developer already runs, today Claude Code and
Codex. A developer states their working style once, as rules, skills, roles, workflows and switchable
stances. The harness then:
- projects that style into each runtime's native configuration;
- enforces it with hooks wherever a check is cheap and deterministic;
- measures whether each rule actually fires.

Its front door is a question no other tool in the field answers: which of your agent rules actually fire?
Every rule in the harness's catalog names a detector over the agent's own transcripts, or says why none
can decide it. Lint refuses a rule that does neither. `harness usage --rules` then reports hit rates by
repository, and by the preference variant that was selected. The same measurement engine ships on its own, as `ruleprobe`, so
anyone can point it at their transcripts before adopting anything else.

Now is the time for it:
- Developers switch between coding agents weekly.
- Always-loaded instructions grow unmeasured, and the standing prefix is the single largest cost on short
  tasks.
- The field is full of configuration compilers and skill packs, and all of them are open-loop.

The harness closes the measurement half of the loop today. Proposing stance changes from that evidence is
the next half.

## The problem

- **Instructions are written, never checked.** A developer's `CLAUDE.md` grows to hundreds of lines, and
  nobody knows which lines change behaviour. The dead ones cost tokens on every call.
- **Every runtime wants its own copy.** Instructions, skills, hooks, roles and settings are all
  runtime-specific. Moving between agents means re-authoring. Copying files does not carry hooks,
  permissions or lifecycle events, so the two copies drift apart.
- **Cost controls are either caps or guesses.** A developer can cap spend and cripple long tasks, or guess
  which subagents need which model. Budgets, routing and a live view of spend are missing, and so is any
  honest comparison against running the agent bare.
- **Configuration tools make people nervous.** A tool that rewrites your agent settings has to prove it
  will not destroy hand edits, and that it can be removed cleanly.

## The solution

- **Measured rules.**
  - A detector per rule, a lint gate, and hit rates by repository and variant.
  - Declarative detectors let a developer measure their own rules with `ruleprobe`, without writing code.
    Loading them in `harness usage --rules` is planned.
  - Seventeen detectors ship today, and a labelled corpus scores them in CI.
- **One authority, native adapters.**
  - One provider-neutral catalog, projected into Claude Code and Codex.
  - Each adapter states how its runtime carries each capability: as an instruction only, or backed by a
    hook.
- **Stances and, soon, a full selection model.**
  - Nine switchable stance dimensions today, such as autonomy, delegation, cost and voice.
  - Planned for 0.14: every rule, hook, skill, workflow and role switchable, with named modes. A
    methodology skill library can then layer on top, with the harness ceding process and keeping
    enforcement.
- **Cost posture without caps.**
  - Capability classes instead of model names, and right-sized band workers for unnamed spawns.
  - A soft budget in every brief, and a live usage feed.
  - A local usage ledger that prices spend as list-price equivalents, with no remote service required.
- **Guardrails where determinism is cheap.**
  - Shell commands graded from read-only to irreversible.
  - A stop gate that will not end a turn on a red build.
  - Tool output treated as data.
  - Isolated role workers for constrained work.
- **Ownership you can undo.** Every sync is previewed, recorded field by field, and reversible.

## What makes this different

- **Measured rules.** The only project we know of that binds a detector to each rule file, fails lint on
  an unmeasured rule, and reports per-rule hit rates by repository and preference variant. The field scan
  is dated 2026-09-21 and will be re-checked by 2026-12-01.
  - It complements observability platforms rather than competing with them: the ledger exports over OTLP
    and adds the one signal those platforms cannot see, whether the rules fired.
  - The nearest neighbour reads transcripts for cost leaks, which is the inverse direction.
- **Honest claims by construction.**
  - The cost benchmark compares against a bare runtime, with a publish bar fixed in advance.
  - The one clean result so far, 1.052 times bare on a four-task set, failed that bar. It is published as a failure, and no
    saving is claimed.
  - The instrument has already caught two of the harness's own features doing nothing. That write-up is
    public.
- **Switching per enforcement unit.** Bundling settings into modes is common in the field. Switching each
  rule, hook and role individually, across two runtimes, is not.

## Who this serves

- **Primary:** developers who already customise Claude Code, Codex or both, and who move between them.
  They run several sessions at once, and they will read a dry run before letting a tool manage their
  configuration.
- **Secondary:** anyone curious whether their instructions work. `ruleprobe` needs no adoption.
- **Also:** maintainers of agent frameworks and skill libraries. The harness governs them through
  declared integrations rather than bespoke code.
- **Contributors:** from 0.14, the design of every work item lives in its story file beside the code, not
  in a private conversation.

## Success criteria

- **A first-time developer learns which of their rules fired within a minute.** The first report says what
  share of their rules is measured.
- **Cohort retention.** Before any launch post: ten installs, five retained users and three actionable
  reports from a direct tester cohort. Attention metrics are not the goal: stars and clone counts are
  explicitly not optimized.
- **A cost claim only when earned.** Harness cost per passed task must be at most 0.85 of bare, on the
  release task set, at adequate power. If long tasks show no win, the instrument findings become the result
  and the saving claim is retired.
- **Lifecycle integrity.** Install, upgrade, sync, rollback and uninstall lose no unrelated file on any
  supported target.
- **Public planning stays current.** Every merged change updates its story file and the part of the corpus
  it touched.

## Scope

- **In, through 1.0.0:**
  - The stable contract covers Claude Code CLI on macOS and Linux. Codex CLI joins it once one scripted
    qualification round agrees with a hand-driven round.
  - Measured rules, the usage ledger, cost posture, guardrails, role workers and the delivery-loop
    workflows.
  - Framework integrations, the decision-provider foundation (shadow first, tighten-only), and the
    selection model.
- **Out:**
  - Stable editor and desktop clients (preview).
  - More runtimes before existing ones reach equal depth.
  - Serving models, choosing providers' endpoints, and hosted services.
  - Spend caps.
    *Amended 2026-09-24:* this stays the default. An opt-in cap module may deny for cost when the user
    switches it on; see the [Vision amendment](#amendment-2026-09-24-a-layered-configurable-measurable-harness).
  - Any provider relaxing a decision.
  - A team surface.

## Vision

The harness becomes the layer that tells a developer when their rules stopped working. It measures every
rule, proposes stance changes from evidence, and leaves the developer in charge of every change. After the
loop closes, breadth follows: more runtimes at equal depth. The ceiling beyond 1.0, which is not a
commitment, is a team surface: shared stance floors, and rule firing aggregated across a team's sessions
and exported into the observability platform the team already runs.

The detailed requirements are in the [PRD](../../prds/prd-agent-harness-2026-09-23/prd.md). The evidence
behind each claim is in the [research](../../research/) artifacts.

### Amendment 2026-09-24: a layered, configurable, measurable harness

Added after the original run; the vision above is unchanged and dated 2026-09-23. The same
amendment is recorded in the [PRD's vision](../../prds/prd-agent-harness-2026-09-23/prd.md#amendment-2026-09-24-a-layered-configurable-measurable-harness).

**What the product is.** It is a lightweight harness you layer alongside whatever agent runtime you use
(Claude Code, Codex and others), however you orchestrate it: native subagents, workflow scripts, or
methodologies such as BMad or Superpowers. It is built from independent layers. Every layer, and every
module within one, can be switched on, off or configured. A user keeps the layers they like and turns ours
off where they already have their own. The harness then cedes that whole area to the other tool rather than
trimming inside it. The north star is running beside a methodology such as Superpowers, with the user
choosing which layer comes from which source.

**The layers.**
- **Observation:** telemetry, meaning ledger, OTel export and transcripts. It must add nothing to the
  model's context.
- **Instruction:** what the model reads. Rules, stances, repository instructions, the session prompt and
  the output style.
- **Capability:** on-demand skills, agent roles and commands.
- **Enforcement:** hooks and guards at tool and turn boundaries.
- **Orchestration:** delegation, choosing a model class and effort for each role inside the host, and
  the context lifecycle (trimming, compaction, clearing, handoff). It never selects a provider endpoint or
  serves a model.
- **Advisory:** recommendations to the human, such as starting a fresh session, clearing context or
  reviewing a plan.
- **Economy** is a concern rather than a layer. Cost posture, budgets and prices run through the
  instruction, enforcement and orchestration layers, and each can be switched on its own. By default
  nothing is denied for cost: budgets inform. A spend cap is an opt-in module that denies only when the
  user switches it on.
- A control plane of profiles, toggles and configuration composes the layers, and an evaluation plane
  measures them.

**Measurable by construction.** Every module declares three things: what it claims to improve, what it
costs to carry, and the instrument that measures it. A module with no instrument is reported as
unmeasured, never as working. Telemetry runs in every arm, including a bare runtime with nothing of ours
loaded, so the harness can measure the baseline it is compared against.

**How it is evaluated.** There are four comparisons, and each runs at the cheapest tier that can answer
it:
1. The whole harness against the bare runtime.
2. One rule, skill or hook in a minimal profile: first alone, then with the economy concern switched on.
   A unit eval never pays for the full context.
3. One of our layers against an external equivalent in the same slot, with everything else held fixed.
4. Permutations of switches within and across layers: screened with fractional factorial designs, then
   tested in combination.

Every comparison is measured on three axes: adherence (did the agent follow it), effectiveness (did the
outcome improve) and efficiency (what it cost). Advisory-layer effects are reported separately, as
estimates that depend on the user following the advice.

**Why.** Agent tooling mostly ships as monoliths that bundle methodology, instructions and enforcement. A
user cannot tell which part helps, or combine the best parts of several. The harness sits beneath them as
a substrate: the control plane, telemetry and evaluation that make any combination configurable and
measurable.
