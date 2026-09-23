---
title: 'technical research: the optional decision layer (jev provider and decision-provider contract)'
type: 'technical'
topic: 'the optional decision layer: the jev decision provider and the decision-provider contract'
decision: 'How far the optional decision layer may go (shadow, advise, act), what evidence gates each stage, and which ecosystem constraints bind it'
source: 'Process mode over in-repo docs at commit 3020251, GitHub issues and PRs of JakeSelby/agent-harness, vendor documentation and terms, one third-party integration, and maintainer notes (unpublished), 2026-09-21'
status: complete
preset: 'process'
validation: 'normal'
created: '2026-09-23'
updated: '2026-09-23'
claims_verified: 23
claims_unverified: 8
claims_disputed: 0
claims_overturned: 0
issue: 617
---

# Technical research: the optional decision layer

**Decision this research serves:** how far the optional decision layer may go (shadow, advise, act), what evidence gates each stage, and which ecosystem constraints bind it.

## Executive summary

**Verdict.** The layer may go as far as `act`, and only as far as tightening an `allow` into an `ask`. Deny and widening stay permanent non-goals. Today it has reached none of the stages in practice. No hook consults a provider yet, and no live request has ever been made [1][15]. So `shadow` is the next reachable stage, and each point's `advise` gate is its own written criterion on held-out decision-log rows [3][5].

What drives the answer:

1. **The evidence chain has not started.** The contract, the modes, the kill switch, the outbound allowlist, the packs, the evaluation runner and the ledger rows are all merged [14][15][16][17][18]. But command grading still answers the permission question on its own [1]. The label-yield spike found far fewer labelled decisions than the bar required, so hand-labelled seed fixtures became the long pole [3]. The first consumer also needs the completion claim, and that field is off by default [2][19].
2. **Tighten-only matches fail-open, and it grants no authority.** The provider can only withdraw an allow into a prompt. It never widens and never denies, and every failure returns the deterministic answer [1][15]. The public integration closest to this design blocks fail-closed and optimises fail-open [25]. A deny mode would therefore force a fail-closed path and break the layer's fail-open invariant.
3. **Vendor terms bind the design.** Aliases move on release, and no deprecation policy is stated [21]. The customer agreement bars using output to train an imitating model [24]. Zero data retention is offered to enterprise customers only, and no retention window is stated [23].

**Biggest caveat.** The re-scoped release plan publishes per-point numbers from the harness's own logs [8]. The epic's acceptance asks for per-point agreement, calibration, cost and latency [3]. For the `jev` provider, those figures measure a third-party model's accuracy and performance, and this project may not publish that.

## 1. The contract

- `decide(action, counterparty, context)` returns `allow`, `ask` or `deny` with a level of 1 to 3. `record` and `learn` complete the surface. `none` is the default, and `local` reads `.agent-harness/governance.json`. Neither provider reaches the network [1][14].
- `jev` carries `local` underneath it. It may turn an `allow` into an `ask`, and it never widens a decision or produces a `deny`. No key, a timeout, an exhausted budget, a malformed response or an exception all fail open to the deterministic decision [1][15].
- The service has no abstention outcome, so a `choice` question without an explicit `unknown` option is refused before sending [15]. The vendor's own guidance is to add an `other` or none option [22].
- Every mode (`off`, `shadow`, `advise`, `act`) is set per decision point and defaults to `off`. A point name the harness does not know reads `off` [1][16].
- A sentinel file disables every call while it exists. It is read per decision, with no restart [1][16].
- Outbound data is an allowlist, empty by default, over `command` and `summary` only. Secret-shaped values are dropped whole [1][16].
- Answers are not deterministic across identical requests. The harness promises only that the same request hashes the same [1][15].

## 2. The staged path, and whether tightening is authorization

- **Epic plan.** The stages run `off` → `shadow` → `advise` → `act`. In 0.13.0, `act` may only tighten. The epic adds three more limits: the provider never relaxes a deny, never sees a grade-2-or-higher command, and never overrides a named role's bindings [3]. The grade-2 exclusion is not stated in the runtime-controls doc, so it rests on the epic alone (unverified).
- **Shadow entry.** Classify last in the hook chain. The provider runs beside a deterministic check, never between the check and its consumer. The epic sets p95 under 1 s over 200 live decisions, with a 2 s timeout [4][1].
- **Advise gate for stop-claim verification.** The held-out rows must show discrimination well above wording alone and no more than two false blocks per 100 stops. Even then `stop-gate` still decides [5].
- **Points held in shadow.** Skill shortlists rank rather than threshold, and are labelled by the skill actually invoked [6]. Band recommendation has a weak label and no promotion criterion yet [7]. Brief-quality and return-compliance checks wait for labelled rows [9][10].
- **Is tightening authorization? No.** A tightened call reaches the user as an `ask`. The user's answer is the authorization, and the provider's judgment is "not verification or permission" [4][5]. What tightening costs is interruptions. Sampled allows exist so that false alarms can be measured [12]. *Inference:* an approval of a provider-caused `ask` would log as `ran`, the same as an approval of a deterministic ask. Unless the cause is recorded, the label set mixes the two.

## 3. Evidence gathered so far

- **The ranking was reversed.** The original plan led with skill selection and response style, and deferred completion checking [3][8]. The 2026-09-21 re-scope made the narrow stop-claim check the first consumer and cut skill selection to shadow only [5][6]. Five prose-quality checks were closed because they had no consumer and no label [11]. Broad whole-task completion inference is still excluded [5].
- **Label supply is the binding constraint.** Only `grade-bash` ask/deny and `stop-gate` carry outcomes. `ran` is not proof that the prompt was unnecessary, and `not_run` conflates a refusal, an interrupt and a crash. The other three points are not labelled yet [2][13]. The label-yield spike came in below the bar [3] (single source; the spike issue was outside this run's sources).
- **What each stage needs, and what exists:**
  - `shadow`: a hook binding, which does not exist yet [1]. The row shape does exist, and it carries the deterministic outcome and the one `act` would have reached [1][18].
  - `advise`: a fitted, held-out threshold. A point with no dev labels reports as unfitted, and there is no global default [1][17].
  - `act`: a false-alarm measurement against sampled allows. Those sample distinct commands rather than invocations, so their rates cannot be scaled [2][20].
- **Unverified plumbing.** No live request has been made. The endpoint, limits and status mapping come from vendor documentation only [1][15][17]. No model price is in the price table [2][18].

## 4. Ecosystem constraints

- **Moving model.** Aliases move when a release ships, and the vendor says to pin a version ID once thresholds are tuned. No deprecation policy is stated, and rate limits can change without notice [21].
- **Data.** The vendor does not train on customer requests. Zero data retention is enterprise-only, and no retention window is stated [21][23]. The agreement lets the vendor delete customer data at will [24].
- **Use restriction.** MCA §2.3(b) bars using output to distil a model, to train a model that imitates the service, or to build a competing product [24].
- **Client floor.** The vendor SDK needs Python 3.10 and five packages, against this repository's 3.9 floor. The client is therefore stdlib-only [15].
- **Integration patterns.**
  - The one framework integration is still an open pull request. Its tool gate fails closed and its router fails open. It sends user messages and tool metadata, never tool output or assistant prose [25].
  - An open issue on that integration shows a gate reviewing a call that an inner middleware later replaced [26]. The harness's classify-last rule answers that failure [4].
  - Community Claude Code gates reportedly fail open to the normal permission prompt [27] (unverified). The vendor publishes no first-party hook or permission classifier [28] (unverified).

## Cross-dimension insights

- **Fail-open works because of tighten-only.** The provider is never the only blocker. Adding `deny` would make it one, and the ecosystem's own rule for blockers is fail-closed [25]. The two invariants therefore stand or fall together.
- **Promotion evidence cannot be published.** The evidence that gates `advise` and `act` is an accuracy measurement of a third-party model, so it has to stay a private artifact. Whether even a public "met or missed" line counts as a performance result is an open question.
- **Thresholds expire.** A threshold is tied to its pack version [1], and the vendor's model moves under an alias with no deprecation notice [21]. A fitted threshold lasts only as long as the pinned model behind it.

## Contrary evidence

The red-team pass did not run (`validation: normal`, `red_team` off).

## Recommendations

1. **Tighten-only, permanently** → *PRD non-goals; spine invariant.* `act` may only turn `allow` into `ask`. Deny, widening and semantic auto-authorization are non-goals, and tightening is not authorization. Confidence: high [1][15][25].
2. **Stage gates per point** → *PRD decision-layer requirements.* A point may enter `shadow` only when it is bound last in the chain, meets its latency bar, and one live request has been verified. It may reach `advise` only on its written held-out criterion, with a threshold that is not unfitted. It may reach `act` only when its false-alarm rate against sampled allows is also measured. A point with no criterion stays in `shadow`. Confidence: medium, because the per-point criteria each rest on a single source [3][4][5][7][17].
3. **Key thresholds to the pinned model and the pack version** → *spine invariant.* A returned model id that differs from the pinned one voids the fitted threshold, and the point falls back to deterministic. Confidence: medium; this is an inference from the vendor docs and the pack design [1][18][21].
4. **No distillation** → *PRD non-goal.* `learn()` stays a no-op for `jev`. Any local model trains on the harness's own labels, never on provider output. Confidence: high [24].
5. **Keep jev accuracy figures private** → *PRD requirement; amends #147 and the #135 acceptance.* Eval reports and per-point agreement, calibration and latency for `jev` stay unpublished. Public notes carry harness-owned figures only. Confidence: high on the conflict [3][8]; the exact publishable boundary is open.
6. **Fund the labels first** → *PRD requirement.* Hand-labelled fixtures are the critical path. The completion claim must be on before stop-claim verification can gather inputs. The cause of an `ask` must be recorded on its row. Confidence: medium [2][3][19].
7. **Egress stays minimal** → *spine invariant.* The two-field allowlist stays empty by default. Per-point field documentation cites the vendor's terms as they stand. Confidence: high [16][23][24].

## Open questions

1. Is the grade-2-or-higher exclusion enforced in code? It is stated only in the epic. To settle it, read the provider or the grading hook.
2. What is each point's current labelled count? Answer: `harness usage --by decision` on the owner's machine.
3. Does the live API match the documented shape? This needs one opt-in request with the owner's key [15].
4. Is the `stop-gate` label mapping (`failed` as confirm) right? The runner flags it for owner review [17].
5. Should decision-log rows carry the action class and the grade? Today the runner derives them [17].
6. Does a public "met or missed criterion" line count as a performance result under the publication bar?
7. What promotion criterion does the ask-band gate carry? That issue was outside this run's sources.

## Source appendix

| n | Claim or finding it supports | Publisher | Pub date | Accessed | Confidence |
| --- | --- | --- | --- | --- | --- |
| 1 | Contract, modes, allowlist, eval method; no hook consults a provider | [agent-harness, docs/runtime-controls.md at 3020251](https://github.com/JakeSelby/agent-harness/blob/main/docs/runtime-controls.md) | 2026-09-23 | 2026-09-23 | high |
| 2 | Decision log, label definitions, sampled allows, completion claim, no price | [agent-harness, docs/usage.md at 3020251](https://github.com/JakeSelby/agent-harness/blob/main/docs/usage.md) | 2026-09-23 | 2026-09-23 | high |
| 3 | Epic re-scope, stages, act limits, label-yield outcome, acceptance | [agent-harness issue #135](https://github.com/JakeSelby/agent-harness/issues/135) | 2026-09-21 | 2026-09-23 | medium |
| 4 | Shadow binding: classify last, beside not between, latency bar | [agent-harness issue #140](https://github.com/JakeSelby/agent-harness/issues/140) | 2026-09-21 | 2026-09-23 | medium |
| 5 | Stop-claim advise criterion; stop-gate still decides | [agent-harness issue #141](https://github.com/JakeSelby/agent-harness/issues/141) | 2026-09-21 | 2026-09-23 | medium |
| 6 | Skill shortlists shadow-only, rank not threshold | [agent-harness issue #143](https://github.com/JakeSelby/agent-harness/issues/143) | 2026-09-21 | 2026-09-23 | medium |
| 7 | Band recommendation shadow-only, no criterion | [agent-harness issue #145](https://github.com/JakeSelby/agent-harness/issues/145) | 2026-09-21 | 2026-09-23 | medium |
| 8 | Release plan: harness numbers in notes; original bars restricted results | [agent-harness issue #147](https://github.com/JakeSelby/agent-harness/issues/147) | 2026-09-21 | 2026-09-23 | high |
| 9 | Brief-quality check shadow until labelled | [agent-harness issue #156](https://github.com/JakeSelby/agent-harness/issues/156) | 2026-09-21 | 2026-09-23 | medium |
| 10 | Return-compliance check shadow until labelled | [agent-harness issue #157](https://github.com/JakeSelby/agent-harness/issues/157) | 2026-09-21 | 2026-09-23 | medium |
| 11 | Five checks closed: no consumer, no label (#158 to #162) | [agent-harness issue #158](https://github.com/JakeSelby/agent-harness/issues/158) | 2026-09-21 | 2026-09-23 | high |
| 12 | Decision log as the layer's benchmark | [agent-harness issue #370](https://github.com/JakeSelby/agent-harness/issues/370) | 2026-09-21 | 2026-09-23 | high |
| 13 | Decision log shipped; ask/deny only; ran and not_run | [agent-harness PR #385](https://github.com/JakeSelby/agent-harness/pull/385) | 2026-09-21 | 2026-09-23 | high |
| 14 | Contract with none and local; not consulted | [agent-harness PR #486](https://github.com/JakeSelby/agent-harness/pull/486) | 2026-09-22 | 2026-09-23 | high |
| 15 | Jev provider: tighten-only, fail-open, stdlib, no live request | [agent-harness PR #575](https://github.com/JakeSelby/agent-harness/pull/575) | 2026-09-23 | 2026-09-23 | high |
| 16 | Modes, kill switch, allowlist | [agent-harness PR #592](https://github.com/JakeSelby/agent-harness/pull/592) | 2026-09-23 | 2026-09-23 | high |
| 17 | Packs, eval runner, unfitted points, open label mapping | [agent-harness PR #596](https://github.com/JakeSelby/agent-harness/pull/596) | 2026-09-23 | 2026-09-23 | high |
| 18 | Ledger rows, pinned and returned model, no price | [agent-harness PR #597](https://github.com/JakeSelby/agent-harness/pull/597) | 2026-09-23 | 2026-09-23 | high |
| 19 | Completion claim off by default | [agent-harness PR #574](https://github.com/JakeSelby/agent-harness/pull/574) | 2026-09-23 | 2026-09-23 | high |
| 20 | Sampled allows as false-alarm negatives | [agent-harness PR #593](https://github.com/JakeSelby/agent-harness/pull/593) | 2026-09-23 | 2026-09-23 | high |
| 21 | Aliases move, pin, no deprecation policy, rate limits, no training | [TypeSafe, models](https://docs.typesafe.ai/models.md) | 2026-09-23 | 2026-09-23 | high |
| 22 | No abstention; add an other or none option | [TypeSafe, Choice](https://docs.typesafe.ai/primitives/choice.md) | 2026-09-23 | 2026-09-23 | high |
| 23 | ZDR enterprise-only; no retention window | [TypeSafe, legal](https://docs.typesafe.ai/legal.md) | 2026-09-23 | 2026-09-23 | high |
| 24 | MCA 2.3(b) distillation bar; 10.3 deletion at will | [TypeSafe, Master Customer Agreement](https://typesafe.ai/legal/mca) | 2026-09-23 | 2026-09-23 | high |
| 25 | Framework integration: gate fail-closed, router fail-open, bounded input | [LangChain PR #40556](https://github.com/langchain-ai/langchain/pull/40556) | 2026-09-21 | 2026-09-23 | high |
| 26 | Gate reviews a call that inner middleware replaces | [LangChain issue #40694](https://github.com/langchain-ai/langchain/issues/40694) | 2026-09-21 | 2026-09-23 | high |
| 27 | Community Claude Code gates fail open | maintainer notes (unpublished), 2026-09-21, decision-model ecosystem survey | 2026-09-21 | 2026-09-23 | low |
| 28 | No first-party hook or permission classifier from the vendor | maintainer notes (unpublished), 2026-09-21, decision-model vendor primary sources | 2026-09-21 | 2026-09-23 | low |

## Staleness map

Computed with `recon_kit.py staleness`. Windows: harness-state 1 month, versions 1 month, ecosystem 6 months, patterns 24 months.

- 2026-10-21: promotion criteria per point (#141, #143, #145); label yield below the bar.
- 2026-10-23: no hook consults a provider; no live request; vendor aliases and deprecation; rate limits; no abstention.
- 2027-03-21: framework integration status; community gates fail open.
- 2027-03-23: vendor data terms; MCA §2.3(b).
- 2028-09-21: classify the request actually executed.

Earliest re-check: **2026-10-21**. The harness-state claims will change first, when a hook binds a provider.
