---
title: Agent Harness PRD addendum
created: 2026-09-23
updated: 2026-09-23
companion: prd.md
---

# PRD addendum

This file keeps the depth that `prd.md` does not carry: why each decision went the way it did, the
alternatives that were rejected, and the numbers the requirements rest on. Anything that binds
implementation belongs in `prd.md` or in the architecture spine. This file explains those documents; it
does not add to them.

## 1. How the product got here

The chronology below comes from the changelog, the release tags and the linked PRs.

- **0.1 to 0.8 (2026-09-16 to 09-17): a personal Claude Code harness made public.**
  - Rules, stances, skills, hooks and a standard-library CLI.
  - Then lint, safe sync and uninstall, trusted folders, read-only command handling, usage counting,
    roles, workflows, handoffs, delegation policy, tiered agents, BMad overrides, graded command
    authorization and rule detectors.
  - 0.8 added the interactive initializer, presets and the answer voice.
- **0.9 (2026-09-19): the provider-agnostic rebuild.**
  - The trigger was switching between Claude Code and Codex daily. An assessment found:
    - Codex received five divergent skill copies and none of the agents;
    - a preset stopped Codex from starting;
    - the TOML updater crossed section boundaries;
    - uninstall left Codex permissions changed;
    - "read-only" agents still had shell access.
  - The rebuild made one catalog, one resolved policy and thin adapters. It added reversible ownership,
    task continuation, native evidence and the isolated role workers (PRs #101 to #115).
- **0.10:** the architecture-viewer surface. Qualification narrowed to the four CLI targets; the VS Code
  and Codex desktop clients returned to preview.
- **0.11 and 0.11.1:** cost posture. This was the first release to price and route work by capability
  class, and 0.11.1 is the last release qualified on both CLIs.
- **0.12 (2026-09-22):**
  - usage ledger fixes, pricing, OTLP export and native telemetry
  - the decision log
  - the plan-mode posture
  - the static benchmark tier and the live replay runner

  It shipped with no qualified target, a stated pre-1.0 choice recorded in #533.

  The 0.12.0 tag also carries the adoption work first planned for 0.13, although the 0.12.0 release notes
  omit it:
  - measured rules as the front door (#468);
  - `ruleprobe` carved out as its own MIT package and vendored back (#488);
  - import, the installer and the plugin listing;
  - the field scan;
  - the first four stance constraints;
  - the token cap;
  - the decision-provider contract.
- **Unreleased on `main` since the 0.12.0 tag:**
  - the `jev` provider, stages, packs and eval;
  - the smoke tier, per-runtime evidence invalidation, and drivers for every native case;
  - integration descriptors and framework review confinement;
  - the plan-mode review surface;
  - Remote Control environment reuse;
  - tag replay;
  - the detector corpus in CI;
  - the merge queue.

## 2. Resolved contradictions

Where the design record disagreed with itself, the latest explicit decision wins. Each resolution is
logged in `.memlog.md`.

- **Headline.**
  - "Cheaper, clearer coding agents" was approved, then withdrawn on the same day pending a measured
    number.
  - #468 then repositioned the front door on measured rules: "Find out which of your agent rules actually
    fire."
  - The PRD leads with measured rules. "The layer under your agents' skills" is the direction for the
    selection-model copy (#561). No published copy says "cheaper" until SM-2 passes.
- **Qualification before 1.0.** 0.12.0 shipped with no qualified target on purpose, and FR-12 now says a
  pre-1.0 release may do so only when its compatibility status says so. From 1.0 on, qualification of the
  stable floor is a hard gate. #533 restores the floor in 0.12.1.
- **Ledger retention.** A rolling 14-day local log was proposed. The adopted design keeps the ledger
  unpruned, with an optional `retention_days`, because release comparison needs history and runtime
  transcripts expire after 30 days. Eight weeks of ledger is about 1.5 MB.
- **Nudge thresholds.** The issue said to ship them empty until measured. The 0.13 build shipped starting
  thresholds. The PRD records them as placeholders (§12).
- **Remote Control hosts.** A single hub host was built, then replaced by one host per workspace. A host
  only loads the instructions, skills and hooks of the folder it starts in, and each workspace carries its
  own set.
- **BMad's native run in qualification.** It was a required case until #349 replaced it with a generic
  framework-spawn-routing probe and moved the native run to an optional suite (PR #591).
- **Decision layer and authorization.** The 2026-09-19 epic said "no probabilistic auto-authorization or
  tool blocking". The 2026-09-21 re-scope added an ask-band gate. The two are consistent because `act`
  only turns an allow into an ask, and the user's answer is the authorization. Tightening is not
  authorization.
- **Adoption before 1.0.** The 2026-09-19 decisions put adoption after v1. 0.13 was re-scoped as the
  adoption release. The #212 body still says "post-v1".
- **Milestone names.** On 2026-09-22 the milestones were renumbered: 0.14 is the selection model, 0.15
  closes the loop, and 0.16 is breadth. Earlier documents that say "0.14" for the decision layer mean
  today's 0.15.
- **The cost stop condition.** The approved cost-roadmap revision adopted a stop condition. If the clean
  long-task set shows no harness win, the instrument findings are published as the result, and the saving
  claim is retired. The PRD records this as decided (SM-2).

## 2a. Positioning history

- **The first frame, 2026-09-18 to 09-19: "Your way of working, across AI agents."** The README told the
  story in this order:
  1. The user owns the working style.
  2. Stances make preferences explicit and switchable.
  3. Custom primitives let users extend the harness.
  4. Runtime adapters carry the choices across agents.
  5. The compatibility catalog states what actually works.

  A demo would flip a stance and show both runtimes change.
- **A rejected narrowing.** An audit of "every opinion is a switch" found the claim only partly true, and
  proposed narrowing the pitch to "Strong defaults, explicit trade-offs, and configurable workflow
  preferences." That was withdrawn. The headline was kept, and only the absolute "every opinion" wording
  was narrowed.
- **Vocabulary approved on 2026-09-19:**
  - user-owned agent harness
  - stance-driven agent harness
  - cross-runtime working-style layer
  - portable working preferences

  "Multimodal" and "multi-model" were rejected as the lead. "Model-agnostic" is accurate but crowded. The
  novelty claim was bounded after prior art turned up: composable behavioural traits in one project, and
  custom modes in another.
- **The hero line, 2026-09-21.** "Cheaper, clearer coding agents" was accepted, then withdrawn the same day
  until there is a measured number. The hero sentence stays pinned by a test.
- **The front door, 2026-09-22.** The adversarial field scan found stances demoted: three other projects
  ship switchable behavioural variants, and only three of nine stance axes bind to enforcement. Measured
  rules became the front door (#468).
- **Unadopted line.** The scan also proposed "The harness that tells you when your rules stopped working,
  and tightens itself when they do." It describes the closed loop, and it is not adopted until FR-50
  ships. Even then, proposals need the developer's approval.
- **Name and mark.**
  - The name "Agent Harness" was kept. Renaming would break the scraped topic, the domain, the plugin name
    and live submissions. Collisions are handled with the full repository path, and with a display name that
    carries the maintainer's name where needed.
  - A mark that counted runtimes was rejected, because it would go stale when a third runtime lands. The
    rule became "nothing that counts".
  - Font subsets were not shipped, because their licence terms and provenance could not be cleared.

## 2b. Rejected and closed-unbuilt ideas

- **A prerelease channel for unqualified integrations, beside a stable channel.** Proposed in 0.9. It was
  replaced by a per-release split between qualified and preview targets, recorded in the compatibility
  catalog.
- **Porting SoL-Pi's mechanisms.** The published claim is 45 to 49% fewer tokens on multi-hour runs. An
  independent replication measured −8% on short tasks and −21% on minutes-long ones. On this project's
  own transcripts:
  - action fusion would have touched 1.8% of calls;
  - large results were never re-read;
  - no hook exists for compaction.

  None of the mechanisms was adopted.
- **An output archive with recall.** The spike ran over 30 days of transcripts: 25,663 shell calls and
  1,688 test and build commands. The model had already piped 92% of those commands to `head`, `tail` or
  `grep`. Only 21 were filterable, and filtered runs were not re-run. The plan was closed unbuilt.
- **Harbor as the benchmark runner.** Deferred. The runner is laid out so tasks can port later. Whether
  Harbor can inject user-level configuration is an unrun spike.
- **A narrow publication boundary for planning.** The first BMad commitment proposed keeping story files
  thin to "avoid duplicating stories". The maintainer rejected hiding reasoning in a permissively licensed
  repository. The publication boundary was reversed at the time, but the thin stories stayed until
  2026-09-23.
- **Model-traversed graph orchestration as a default.** Rejected. The field's documentation and two
  controlled studies favour flow held in code, and the delegation rules exist to take topology away from
  the model. A workflow-script arm stays a measured experiment (#545).

## 3. Rationale and rejected alternatives by feature

### Shared primitives and projection (FR-1, FR-3, FR-10, FR-13)
- **Chosen:** one catalog and thin adapters. "Different native representations are acceptable;
  duplicated authoritative behaviour is not."
- **Rejected:** Codex-specific primitives added beside the Claude ones. The stance primitive is the
  harness's own invention and maps to no runtime primitive, so every primitive must be runtime-neutral.
- **Terminology:** model provider, agent runtime and client surface are tracked separately. Cursor is a
  runtime, because it owns the loop and tools even when another company serves the model.

### Stances and selection (FR-2, FR-14 to FR-16)
- **The test for a stance:** could a competent developer reasonably prefer the opposite? If not, it is an
  invariant, not a stance.
- **A switch is complete only when the selected behaviour survives every layer:** rule text, skills,
  commands, settings, hooks and detectors. #117 made one effective policy the first blocking task after an
  audit reproduced three switches being ignored by a hook, the output style and telemetry.
- **Two kinds of stance.** Prose stances change instruction text. Enforced stances also change hooks or
  rendered files:
  - on Claude Code: autonomy, delegation, cost and plan-ceremony;
  - on Codex: three, because Codex records `cost` as instruction-only.

  A prose stance cannot become enforced without code.
- **The selection model, planned for 0.14.**
  - Every rule, hook, skill, workflow and role gets an id and a switch, in one document.
  - Modes are bundles resolved below the developer's explicit keys.
- **Finding from the configurability research:** because `harness init` writes all nine stance keys, a
  mode placed below user keys would change nothing for anyone who ran `init`. FR-16 therefore requires
  that a mode takes effect after a default `init`, and #557 picks the mechanism.
- **Rejected:** thirty onboarding questions. Presets and modes carry coherent combinations instead.

### Ownership lifecycle (FR-4, FR-5, FR-17, FR-18)
- **Field-level ownership:** sync owns individual fields, never whole files. Each Claude Code `env`
  variable is owned on its own.
- **`stable` as a non-default branch.** Making `stable` the default branch was rejected, because closing
  links only form for PRs that target the default branch and the rulesets target it.
- **The plugin as a sampler.** A plugin's settings cannot select an output style, and plugin hooks merge
  with user hooks, so both would fire. The long-term option is for `harness sync` to generate the plugin
  manifest and omit its own hook block when the plugin is enabled.

### Measured rules (FR-19 to FR-22)
- **Why this leads.** The field scan found switchable behavioural variants in three other projects, so
  stances alone are not distinctive. Measured rules are distinctive: a detector bound to each rule, a lint
  gate that refuses an unmeasured rule, and hit rates by repository and variant.
  - **Burnd** is credited as the nearest neighbour. It reads transcripts for cost leaks, which is the
    inverse direction.
  - **Observability platforms** such as Langfuse, MLflow, Opik and Phoenix are complementary: the ledger
    exports into them and adds rule firing, which they cannot see.
- **Why `ruleprobe` is its own package.** The instrument can reach users who will never adopt anyone's way
  of working. About 55% of the detector code was rule-agnostic and carried over. A `ruleprobe` release
  means a harness version bump, because the harness vendors the wheel.
- **Corpus agreement is not field accuracy.** The labelled corpus shows that the labels agree with the
  detectors. It does not show that the detectors catch every real instance.

### Ledger, pricing and telemetry (FR-11, FR-23 to FR-27)
- **Ledger as the record.** Native telemetry has no replay, and one runtime drops token metrics under its
  default sink. A backend is a replica rebuilt by replay.
  - **Rejected:** the backend as the record, with the ledger pruned.
- **OTLP only.**
  - **Rejected:** a `telemetry-export` slot in the integration contract. It would generalise a
    viewer-shaped contract for an unmet need.
  - **Rejected:** per-vendor plugins, which would put vendor code in a vendor-neutral repository.
- **Settings in a `telemetry` block, not a stance.** Stances steer agent behaviour. An export endpoint is
  an endpoint plus a secret.
- **ClickStack as a recipe, not bundled.**
  - Files-only mode already answers cost.
  - The backend needs a manual first user and an ingestion key.
  - Its all-in-one image includes an SSPL component that the licensing policy excludes.
- **Pricing honesty.**
  - Dollars are list-price equivalents computed from tokens, not an invoice.
  - Unknown models are unpriced, never $0.
  - Exact-match pricing replaced family-rate inheritance after a release suffix mispriced a model variant.
- **Codex realities.**
  - Parent totals exclude children, the opposite of Claude Code, so Codex spend was undercounted until
    #323.
  - Most top-level sessions live under `archived_sessions/`.
  - Desktop sessions often record only totals, which the ledger marks `partial`.

### Cost posture and delegation (FR-28 to FR-34)
- **"Guardrails where determinism is cheap; knowledge everywhere else."**
  - Hooks route spawns and refuse undeclared frontier requests.
  - Budgets, the live feed and the nudge are information.
  - Nothing is denied for cost.
- **Routing moved measurably after cost posture shipped.**
  - Top-effort spawns fell from about half of all spawns to none.
  - The mid-tier model's share of subagent output rose several-fold.
  - The prompt-cache hit rate stayed flat at about 97% throughout, at every fan-out size.
  - Savings and quality were not demonstrable from that data: small samples, no contrast arm, no outcome
    proxy.
- **Delegation has not fired.** There were zero spawns in 19 headless runs, then in 40. A spawn pays its
  whole prefix first, so the break-even is 4.8 to 7.6 absorbed calls. On the three larger benchmark tasks
  (17 to 45 calls) a spawn would have paid. This is recorded as a harness defect (#429), with a
  PostToolUse nudge planned (#513).
- **Checks bind subagents.** A check that binds a session binds its subagents. Each level decides what it
  can, and only the top session asks the user. This came from repeated approval prompts that surfaced
  from inside subagents.

### Guardrails (FR-35 to FR-39)
- **Plan mode.** Plan mode must force a plan, questions and a wait for approval. It must not force
  permission prompts below the selected posture while investigating.
  - **The catch accepted:** grade 1 includes real local writes, so "no changes" is enforced for edit tools
    but only instructed for the shell.
  - Codex rejects `allow`, so the feature is Claude Code only.
- **The context cap.** Always-loaded context has a token cap of 4,202 and a line cap of 200. The token
  cap binds, and the line cap is the secondary guard. Both are close to full: about 3,858 tokens and 199
  lines.
  - A rule whose action a hook can gate is a candidate to defer behind that hook.
  - The deferral spike (#430) measured action-gated rule text at 1,253 tokens, 36% of a 3,524-token layer.
    It has not run.

### Roles, workers and the delivery loop (FR-40 to FR-44)
- **Why constrained roles are isolated processes.**
  - Codex's native subagents inherit the parent's permissions, which would make role limits advisory.
  - Isolation costs native subagent-thread visibility; that trade was accepted on 2026-09-18.
  - **Rejected:** native subagents with advisory limits.
- **Why the gatherer stays offline.** A worker that can both read a workspace and fetch pages could
  exfiltrate what it read. Web questions go to in-session band workers instead.
- **Why confinement moved to a session-level signal.** Prompt-text matching failed natively. Runtimes
  paraphrase briefs, and a marker survived in only 2 of 21 spawns. While a routed review is in flight,
  unnamed spawns carrying review work are refused.

### Framework integrations (FR-45, FR-46)
- **The contract.** A framework emits intents; policy binds at the harness's own hooks. An integration is
  a descriptor with a version pin, spawn recognition, a spawn-to-role mapping and readable input roots.
- **Two tenants from day one.** BMad and the architecture viewer, so the contract cannot quietly become
  shaped around one of them. BMad is a data descriptor today. The viewer is still integration code, and it
  moves to a descriptor with its mailbox adapter.
  - The earlier bespoke `harness bmad check|apply` was replaced, and survives as an alias for one release.
- **The viewer.** Its upstream renderer includes components under licences the permissive-only policy
  excludes, so the viewer is a user-installed external adapter. A mailbox adapter will replace the session
  adapter once the upstream seam lands.

### Decision providers (FR-47 to FR-50)
- **Where a typed judge fits.** Narrow, self-contained judgments with minimal, controlled inputs: stop
  claims against gate evidence, the ask band, shortlist ranking. It does not fit whole-agent completion
  verification, because collecting the evidence is the hard problem.
- **Order.** The narrow stop-claim check comes first. Skill-shortlist ranking stays shadow-only.
  Prose-quality checks with no consumer were closed.
- **Publication boundary.**
  - The provider's customer terms bar publishing benchmarks of its model without permission, and bar
    training an imitating model on its output.
  - Evaluation figures for that provider therefore stay local, and `learn` records nothing for it.
  - Harness-owned figures, such as label yields and decision counts, can be published.
- **Label yield is the long pole.** A spike found about 13 stop labels and 19 ask labels against the 200
  needed, so hand-labelled fixtures (#377) come first.

### Compatibility and release (FR-6, FR-7, FR-12, FR-51 to FR-54)
- **Release cost baseline.** One round of four targets took about 60 minutes wall clock and about 1M
  orchestrator tokens.
  - Codex targets took 49 to 61 minutes, against 20 to 30 for Claude Code, because Codex cases were driven
    by hand.
  - Three of 0.11.0's four rounds produced no new observation.
  - The fixes, all from #340:
    - freeze on a release branch, with no fixes mid-round
    - a model-free smoke tier
    - per-target invalidation
    - scripted cases
- **Freeze records.**
  - A round runs on `release/v<version>`, cut at the commit it qualifies and recorded in
    `compatibility/freeze.json`. `main` keeps merging meanwhile.
  - The evidence commit must stay an ancestor of the qualification source commit, so a squash-merged or
    diverged release branch fails closed instead of publishing an unqualified source.
- **Five release surfaces,** worked in order and each reported, so no surface is inferred from another.

### Cost benchmarks (FR-55 to FR-58)
- **The bare arm must be truly bare.**
  - A signed-in empty configuration directory, because a clean directory is not logged in.
  - A working directory outside the home directory, because the runtime walks parent folders for memory
    files.
  - A scrubbed environment and strict MCP configuration: MCP servers doubled the cost of a trivial run.
- **Ratios, not dollars.** Models change under the same id, so stored absolute baselines mix harness
  changes with model changes. The previous tag and the candidate run on the same day.
- **The contamination.**
  - Every scored set through 2026-09-22 was contaminated by a test-isolation leak (#498). Those sets stay
    in history, labelled as contaminated.
  - The first clean figure was 1.052, which fails the bar. It is a ceiling, because the bare arm was still
    inflated on one task.
- **The first live figures, before the leak was found.**
  - The harness added 12,607 tokens to every call, 22% of the harness arm's spend.
  - With that prefix removed, the ratio would have been 0.913.
  - The prefix's share falls as context grows: 26% at 49k mean context, 5% at 250k. So the harness pays
    off on long, grinding work, not on small tasks.
- **Output and brevity.**
  - Output tokens are about 20% of spend, so a brevity rule is a 2 to 3% lever. Turn count swings cost by
    about 60%.
  - A separate published study found that cutting tool-output tokens by 38.4% raised billed cost by 6.8%,
    because it broke the cached prefix.

### Session operations (FR-8, FR-59 to FR-63)
- **Remote Control root cause.** Hosts were launched with a flag that, in the 2.1.280 client, also
  disabled reading the saved environment pointer. Every restart therefore registered a new environment,
  and every stop archived sessions. The heal loop now keeps hosts on their environments. A session the
  server already archived cannot be restored, because that needs elevated authorization.
- **Coordination.** The literature favours shared state over peer messaging.
  - Pull-request pairs from different agents conflicted 41.7% of the time, against 19.8% for pairs from
    the same agent.
  - Write-time conflict detection beat a worktree baseline.
  - 11 of 12 solver and memory-system pairings failed to beat running with no memory. Directly injected
    experience did help, so what fails is delivery, not history.
  - Hence: path claims, a pull-only archive, and retrieval deferred until it demonstrably pays.

### Public planning (FR-9, FR-64, FR-65)
- **Why the stories were stubs.** On 2026-09-19, every historical issue needed a committed file at an
  immutable path, linked both ways.
  - The tool generated those files from GitHub records, under a rule that the issue owns the scope.
  - No story-writing workflow was available in that session.
  - The later decision to publish reasoning by default changed what was published, but not where the
    content lived.
- **What changed on 2026-09-23.** The story file becomes the design record, and the issue keeps a summary.
  - Rich story shape: story, acceptance criteria, design, tasks, cited dev notes, dev record, review
    findings.
  - Enforcement is a CI depth check on each PR's own story, not a runtime hook, because a hook would be
    brittle.
  - A repository rule routes every operation through its BMad skill.

## 4. Research bindings

- `technical-runtime-platform-limits-and-qualification-2026-09-23`: FR-3, FR-12, FR-32, FR-51 to FR-53,
  NFR-14.
- `technical-cost-context-and-benchmark-measurement-2026-09-23`: FR-34, FR-55 to FR-58, SM-2, SM-3,
  SM-4, NFR-15.
- `technical-decision-layer-evidence-2026-09-23`: FR-47 to FR-50.
- `academic-lit-agent-coordination-and-memory-2026-09-23`: FR-63, non-goals.
- `competitive-configurability-and-selection-models-2026-09-23`: FR-15, FR-16, FR-20.
- `competitive-agent-harness-field-scan-what-the-config-2026-09-21`: §1.1, positioning, SM-C1.
