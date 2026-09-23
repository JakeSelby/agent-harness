---
title: 'competitive research: configurability and selection models across agent-configuration projects'
type: 'competitive'
topic: 'configurability and selection models across agent-configuration projects'
decision: 'How should the harness selection model and modes work relative to how comparable projects expose configuration (epic #552), and what is genuinely differentiated?'
source: 'process'
status: complete
preset: 'standard'
validation: 'normal'
claims_verified: 10
claims_unverified: 6
sources: 30
created: '2026-09-23'
updated: '2026-09-23'
---

# competitive research: configurability and selection models across agent-configuration projects

**Decision this research serves:** how the harness's selection model and modes should work
compared with how comparable projects expose configuration (epic #552: every rule, hook, skill,
workflow and role switchable; modes as bundles; a superpowers mode), and what is genuinely
differentiated.

## Executive summary

**What to do.** Build the #552 selection model as planned, with two changes and one addition.

- **Change one: modes must actually take effect.** `harness init` writes all nine stance keys
  into the user config [1], and #557 puts a mode below the user's explicit keys [11]. Together
  they mean `mode: superpowers` changes no stance for anyone who ran `init`. Codex puts its named
  profiles above the base user config [29]. Either `init` stops writing keys that equal the
  defaults, or a mode sits above the user's base config.
- **Change two: say "no user present" in the selection itself.** Every plan-ceremony variant
  waits for a go-ahead [30], and `delegated` waits for the host's approval step [12]. Headless
  arms get that fact only as a sentence in the task prompt [13].
- **The addition: measure selections, not just stances.** `harness usage --rules` groups hits
  by stance variant and nothing else [1]. Grouping by mode and by switch is what makes the new
  switches measurable.

**Findings behind that answer.**

1. **Nobody else switches individual enforcement units.** Claude Code turns plugins on and off
   whole [25]. Codex has no per-skill or per-hook flag [29]. rulesync selects by target and
   feature [26][27]. The three projects with behavioural preferences ship one to three enums
   each [16].
2. **Modes as bundles are not new.** Codex ships named profiles natively [29], and
   planning-with-files, gsd-core and the harness's own `init` presets already bundle settings
   [1][16].
3. **Measured rules remain the one novel capability, and they got stronger.** A labelled corpus
   now scores all seventeen detectors in CI [5]. What limits it is scope: it measures only the
   harness's own rules [4][18].

**The biggest caveat.** Whether superpowers stalls when run headless is still open (#553), with
no result yet [7]. Every claim here about superpowers composing with a headless harness is design
evidence, not a measured run.

## 1. What each project lets a user switch, and how finely

**The harness today: stances only.** There are nine stance dimensions with named variants [2].
Rules are projected through one directory link, `~/.claude/rules/harness` → `claude/rules`, so no
single rule can be selected [1]. Skills, workflows, roles and hooks have no switch of their own.
Only three stances reach code: autonomy sets the Bash grade threshold, delegation routes spawns,
and plan-ceremony gates the plan-card validator [3]. The other six are prose. The only bundle is
`init`'s two presets, `software` and `general` [1].

**The harness as #552 plans it: six kinds, each unit switchable, one document.**

- Every rule, hook, skill, workflow and role becomes a unit that is `on` or `off`, default
  `on` [6][8].
- Twelve hook ids become switchable. Four core ids (`grade-bash`, `stop-gate`, `brief-guard`,
  `neutralize-tool-output`) can go off only with an acknowledgement [9].
- Rules move to one link per file [10].

**Comparators.**

- **Claude Code, natively:** a plugin is enabled or disabled whole, through `enabledPlugins`, at
  user, project or local scope. The reference describes no switch for one skill, hook or agent
  inside an enabled plugin [25].
- **Codex:** a config flag can enable or disable no individual skill or hook [29].
- **rulesync:** generation is selected by `--targets` and `--features` [26]. A rule's frontmatter
  carries `targets` ("* = all, or specific tools"), and no per-file disable is documented [27].
  Its preset types model other tools' settings, not preferences of its own [20].
- **planning-with-files, gsd-core, LynxPrompt:** one to three behavioural enums each [16].
- **wshobson/agents:** per-command flags only [20].

**Verdict.** Per-unit switching across six kinds, with enforcement hooks among them, has no
equivalent in the set. There is one structural limit, though. The harness can switch only its own
units. Claude Code's granularity for a third-party library is the whole plugin [25], and
superpowers documents no way to disable one of its skills [23]. So a harness mode can cede ground
to superpowers but cannot trim superpowers itself.

## 2. How defaults, user settings and project settings layer

| Project | Order, lowest to highest | Floor or scope limit |
|---|---|---|
| Harness today | example defaults → user → project (stances only) → `HARNESS_STANCE_*` [1] | Project file refused if it carries any other key [1] |
| Harness per #554/#557 | default → mode → user → project → session [8][11] | Selection may not carry identity, permissions, `manage`, `primitive_roots`, telemetry [8]; core-hook ack [9] |
| Claude Code | user → shared project → project local → command line → managed [24] | Managed wins; list keys such as `permissions.allow` merge across scopes [24] |
| Codex | user base → profile → project → CLI [29] | Profiles may not carry credential, auth or profile-selection keys [29] |
| planning-with-files | root `.mode` is a floor that a slug scope cannot relax [16] | Floor semantics |

**The finding that changes a story.** #557 says "a mode sits below the user's explicit keys, so a
key you typed always wins" [11]. But `init` writes every stance key explicitly, in both its flag
path and its interactive path [1]. For every initialised user, then, the stance half of any mode is
overridden before it applies. `superpowers` would keep `plan-ceremony: review-card` and
`testing: required`. Only the switch kinds would take effect, because `init` writes none of them.
Codex resolves the same tension the other way: the profile overlays the base user file [29].
Confidence is high: both halves are read from code and issue text.

**Where the plan already matches the field.**

- Refusing identity, permissions and credentials inside a selection [8] is the rule Codex applies
  to profiles [29].
- The core-hook acknowledgement [9] is a user-level floor, in the same spirit as Claude Code's
  managed tier [24].

**What the plan does not take.** planning-with-files' floor, where a narrower scope cannot relax
what a wider one committed [16], is still unadopted; `docs/field-scan.md` says it is scheduled [17].
Under #554, a session file or env key can switch a hook off that a project file wanted on [8]. For
a shared repository, that is the case a floor exists for.

## 3. How a skill library composes with a harness underneath, and what headless needs

**Composition is structurally clean at the hook layer.**

- superpowers registers exactly one hook: `SessionStart` on `startup|clear|compact`,
  synchronous [22]. The harness's PreToolUse grading, spawn tiering and Stop gate therefore have
  no competitor at registration.
- superpowers installs only through the plugin system and documents no writes to the files the
  harness owns [19].

**The instruction layer is where they collide.** The collisions, sharpest first [19]:

1. **Autonomy:** superpowers adds two approval gates before any code is written.
2. **Plan ceremony:** it uses a different plan template.
3. **Narration:** it announces every skill it uses.
4. **Testing:** its test-driven development is stricter than the harness's.
5. **Model tiering:** it escalates to a stronger model on its own.
6. **Commits:** it commits per step, with no message format.

The planned superpowers mode cedes 1, 2 and 4 through `delegated` variants and switches [12].
Collision 3 remains, because the narration line lives in an always-on rule [18].

**Precedence favours the harness, by superpowers' own text.** Its bootstrap says: "User
instructions (CLAUDE.md, AGENTS.md, GEMINI.md, etc, direct requests) take precedence over skills"
[23]. The harness projects into exactly those files. That qualifies the 2026-09-22 worry that
superpowers defers to no other framework [19]. It defers to where the harness writes, though not
to the harness by name.

**Workers sit outside the bootstrap.** "If you were dispatched as a subagent to execute a
specific task, ignore this skill" [23]. Harness band workers are dispatched subagents, so its
1-percent rule does not reach them.

**What a headless run needs.**

- **superpowers' side:** its brainstorming gate forbids implementation until a user approves
  [19]. This is unverified this run, and #553 exists to test it [7].
- **The harness's side:** both shipped plan-ceremony variants wait for an explicit go-ahead
  [30], and `delegated` waits for the host's approval step [12]. In a run with no user, the
  harness is therefore a second source of stalls.
- **Current plan:** #559 answers this with a one-sentence no-user preamble in each arm's task
  prompt [13]. That fixes the benchmark and nothing else. A real headless user (CI, a scheduled
  agent) gets no equivalent unless the fact lives in the selection.

## 4. What is genuinely differentiated

**Confirmed: measured rules.**

- Seventeen detectors ship: six generic and eleven repository-specific [4].
- Two rules are opted out, each with a written reason [4].
- Lint fails any rule that has neither a detector nor an opt-out [1].
- `usage --rules` reports hits by rule, by repository and by stance variant [1].
- The field scan's biggest caveat, that there was no labelled corpus, is now retired: #601
  scores all seventeen detectors in CI against a 0.9 floor [5][16].
- The nearest neighbour, Burnd, still measures skill firing without binding a detector to a rule
  file [16].

**Qualified in three ways.**

1. **It measures only the harness's rules.** In the superpowers mode, `decisions-and-plans` and
   `voice-and-format` go off [12]. Those two rules carry three of the eleven repository detectors
   [4], and nothing measures superpowers' own mandates [18].
2. **The measurement is blind to the new selection.** Hits are grouped by stance variant and by
   nothing else [1]. The four-arm set compares cost per passed task per arm, with no per-rule
   view [13]. Grouping by mode and switch is the bounded claim's natural extension: a per-switch
   link needs switches, just as the per-variant link needed variants [16].
3. **The one user question in the field is about superpowers.** It asks how to tell whether
   superpowers is doing anything [16]. A detector pack for a host library's own mandates would
   answer it. No such pack is planned.

**New but modest.** Per-unit switching of enforcement hooks, with a core acknowledgement and
source attribution on every value [8][9], is new in the set. Modes as bundles are not new: Codex
profiles, planning-with-files' `.mode` and gsd-core's profiles already do it [16][29]. gstack's
declared-versus-inferred mismatch check [20] is the closest comparable idea. The harness has the
data for its own version and does not surface it [21].

## Cross-dimension insights

- **Modes are only as good as the layering under them.** The idea of a bundle is commodity (§4).
  What decides whether a mode works is the precedence rule (§2), and there the plan currently
  defeats itself for initialised users.
- **Composition is clean at the hook layer and costly at the measurement layer.** The superpowers
  mode keeps every hook [12] and gives up the rules that carry three of the eleven repository
  detectors [4]. The better the harness fits beside superpowers, the less of the session it
  measures.
- **Headless removes the person who settles collisions.** With a user present, a gate on either
  side is an interruption. Without one, it is a stall, and the harness contributes its own stalls
  [30].

## Contrary evidence

The red-team pass was off for this run, at `normal` validation. The strongest arguments against
the recommendations, taken from the sources:

- **"A key you typed always wins" protects users from surprise.** That matters, and it is the
  reason to prefer fixing `init` over moving modes above user config.
- **A floor adds resolver complexity for a user base the field scan could not show exists.**
  That argues for recording plain override as a stated decision rather than building a floor
  now [16].

## Recommendations

1. **Make modes take effect for initialised users.**
   - Decide one rule. Either (a) `init` writes only keys that differ from the defaults, with a
     one-time migration that drops default-equal keys and journals both states, or (b) a mode
     overlays the user's base config, as Codex profiles do.
   - Either way, `harness selection` names each mode key a user key shadowed.
   - **PRD:** a selection-model requirement with the acceptance "`mode: superpowers` after a
     default `init` changes `plan-ceremony`". Feeds #557 and #558.
   - **UX spec:** mode output lists "applied" and "kept your value" separately.
   - **Confidence:** high [1][11][29].
2. **Carry "no user present" as a selection-level session fact.**
   - `plan-ceremony` and `delegated` resolve it by proceeding. The arms read it instead of relying
     only on a prompt sentence.
   - **PRD:** a headless requirement, with #553's result as its acceptance input.
   - **UX spec:** doctor and session start show "headless" beside the mode.
   - **Confidence:** medium. The harness side is verified [30]; the superpowers side awaits
     #553 [7].
3. **Extend `usage --rules` grouping to mode and to switch state.**
   - **PRD differentiation claim:** "reports per-rule hit rate by repository, by preference
     variant, and by mode".
   - **Brief positioning:** the measured layer under a skill library.
   - **UX spec:** a rule switched on that never fires is shown as a mismatch line. This is the
     gstack pattern applied to real transcripts [20][21].
   - **Confidence:** high on the gap [1], medium on value.
4. **State the ceiling in the brief and the copy.**
   - The harness switches its own units, cedes whole areas to a host library, and cannot trim the
     library itself [23][25].
   - **Brief:** the alternatives section.
   - **PRD:** a non-goal.
   - **Confidence:** medium. It rests on documented absence.
5. **Decide the floor question explicitly.**
   - Either adopt floor semantics for the four core hook ids at project scope, or record plain
     override as intended.
   - **PRD:** the selection-model precedence requirement.
   - **UX spec:** a relaxed floor is refused with the scope that set it.
   - **Confidence:** medium [8][16][17].
6. **Keep the differentiation claim bounded to measurement and per-unit enforcement switching,
   never to "modes".**
   - **Brief:** positioning. Feeds #561 [15].
   - **Confidence:** high for measurement [4][5]; medium for switching, since its comparators
     are single-source [16][25][29].

## Open questions

- **Does headless superpowers stall beside the harness?** Answered by #553 [7].
- **Can a Claude Code permission rule deny a single plugin skill?** The plugins reference does not
  say [25]. One native test would settle whether the harness could trim a host library after all.
- **Does superpowers' bootstrap, re-injected on every `/clear` and compact, displace
  always-loaded rules in practice?** Answered only by the four-arm live set's transcripts [14].
- **Is rulesync's user-level config a runtime layer or only an `init` seed?** The evidence is one
  search snippet [28].

## Source appendix

| # | Supports | Publisher | Pub date | Accessed | Confidence |
|---|---|---|---|---|---|
| [1] | Precedence, project refusal, rules link, presets, `init` writes, `check_detectors`, `rule_report` | [agent-harness `bin/harness`](https://github.com/JakeSelby/agent-harness/blob/3020251/bin/harness) | 2026-09-23 | 2026-09-23 | high |
| [2] | Nine dimensions, ten rules | [agent-harness `primitives/`](https://github.com/JakeSelby/agent-harness/tree/3020251/primitives) | 2026-09-23 | 2026-09-23 | high |
| [3] | Three stances gate code | [agent-harness `lifecycle.py`](https://github.com/JakeSelby/agent-harness/blob/3020251/lib/harness_core/lifecycle.py) | 2026-09-23 | 2026-09-23 | high |
| [4] | Seventeen detectors, two opt-outs | [agent-harness `rule-detectors.py`](https://github.com/JakeSelby/agent-harness/blob/3020251/policy/hooks/rule-detectors.py) | 2026-09-23 | 2026-09-23 | high |
| [5] | Labelled corpus scores all seventeen | [PR #601](https://github.com/JakeSelby/agent-harness/pull/601) | 2026-09-23 | 2026-09-23 | high |
| [6] | Epic outcome | [Issue #552](https://github.com/JakeSelby/agent-harness/issues/552) | 2026-09-22 | 2026-09-23 | high |
| [7] | Headless spike, open | [Issue #553](https://github.com/JakeSelby/agent-harness/issues/553) | 2026-09-22 | 2026-09-23 | high |
| [8] | Selection document, precedence, refused keys | [Issue #554](https://github.com/JakeSelby/agent-harness/issues/554) | 2026-09-22 | 2026-09-23 | high |
| [9] | Hook ids, core acknowledgement | [Issue #555](https://github.com/JakeSelby/agent-harness/issues/555) | 2026-09-22 | 2026-09-23 | high |
| [10] | Per-file rule links | [Issue #556](https://github.com/JakeSelby/agent-harness/issues/556) | 2026-09-22 | 2026-09-23 | high |
| [11] | Mode below user keys | [Issue #557](https://github.com/JakeSelby/agent-harness/issues/557) | 2026-09-22 | 2026-09-23 | high |
| [12] | `delegated` variants, superpowers mode | [Issue #558](https://github.com/JakeSelby/agent-harness/issues/558) | 2026-09-22 | 2026-09-23 | high |
| [13] | Four arms, no-user preamble, cost per task | [Issue #559](https://github.com/JakeSelby/agent-harness/issues/559) | 2026-09-22 | 2026-09-23 | high |
| [14] | Four-arm live set | [Issue #560](https://github.com/JakeSelby/agent-harness/issues/560) | 2026-09-23 | 2026-09-23 | high |
| [15] | Copy direction | [Issue #561](https://github.com/JakeSelby/agent-harness/issues/561) | 2026-09-23 | 2026-09-23 | high |
| [16] | Comparator enums, floor, Burnd, the superpowers user question | [agent-harness field scan research](https://github.com/JakeSelby/agent-harness/blob/3020251/_bmad-output/planning-artifacts/research/competitive-agent-harness-field-scan-what-the-config-2026-09-21/research.md) | 2026-09-21 | 2026-09-23 | medium |
| [17] | Floor scheduled, not adopted | [agent-harness `docs/field-scan.md`](https://github.com/JakeSelby/agent-harness/blob/3020251/docs/field-scan.md) | 2026-09-23 | 2026-09-23 | high |
| [18] | Configurability assessment, complementary split | maintainer notes (unpublished), 2026-09-22, configurability | 2026-09-22 | 2026-09-23 | medium |
| [19] | superpowers collisions, brainstorming gate, install model | maintainer notes (unpublished), 2026-09-22, superpowers evaluation | 2026-09-22 | 2026-09-23 | medium |
| [20] | rulesync presets, wshobson flags, gstack profile | maintainer notes (unpublished), 2026-09-21, competitive position | 2026-09-21 | 2026-09-23 | medium |
| [21] | Mismatch data unsurfaced | maintainer notes (unpublished), 2026-09-21, post-build position | 2026-09-21 | 2026-09-23 | medium |
| [22] | One SessionStart hook | [obra/superpowers `hooks.json`](https://raw.githubusercontent.com/obra/superpowers/main/hooks/hooks.json) | 2026-09-23 | 2026-09-23 | high |
| [23] | 1% rule, subagent exception, user-instruction precedence | [obra/superpowers `using-superpowers`](https://raw.githubusercontent.com/obra/superpowers/main/skills/using-superpowers/SKILL.md) | 2026-09-23 | 2026-09-23 | high |
| [24] | Claude Code precedence, list merge | [Anthropic settings docs](https://code.claude.com/docs/en/settings) | 2026-09-23 | 2026-09-23 | high |
| [25] | Whole-plugin granularity | [Anthropic plugins reference](https://code.claude.com/docs/en/plugins-reference) | 2026-09-23 | 2026-09-23 | medium |
| [26] | `--targets` and `--features` | [rulesync README](https://raw.githubusercontent.com/dyoshikawa/rulesync/main/README.md) | 2026-09-23 | 2026-09-23 | high |
| [27] | Rule frontmatter `targets` | [rulesync file formats](https://rulesync.dyoshikawa.com/reference/file-formats) | 2026-09-23 | 2026-09-23 | medium |
| [28] | Global mode (snippet) | [rulesync global mode](https://rulesync.dyoshikawa.com/guide/global-mode) | 2026-09-23 | 2026-09-23 | low |
| [29] | Codex profiles as a layer | [OpenAI Codex config-advanced](https://learn.chatgpt.com/docs/config-file/config-advanced) | 2026-09-23 | 2026-09-23 | high |
| [30] | Both plan-ceremony variants wait for a go-ahead | [agent-harness plan-ceremony stances](https://github.com/JakeSelby/agent-harness/tree/3020251/primitives/stances/plan-ceremony) | 2026-09-23 | 2026-09-23 | high |

## Staleness map

Computed with `recon_kit.py staleness`, using the pack's windows: capability 3 months, roadmap
6, positioning 6, sentiment 12. No claim is stale today.

- **2026-12-21:** comparator enums and floor (planning-with-files, gsd-core, LynxPrompt) and
  Burnd as nearest neighbour.
- **2026-12-23:**
  - superpowers' hook and precedence text
  - Claude Code plugin granularity and settings precedence
  - Codex profiles
  - rulesync selection
  - the `init` stance writes
  - the detector count and corpus
- **2027-03-22:** the #552 design.
- **2027-09-21:** the superpowers user question.

The earliest re-check is **2026-12-21**. Re-check superpowers and Claude Code sooner if
superpowers ships a release that adds a hook or a skill switch.
