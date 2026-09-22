# Roadmap arc from 0.13

**Date:** 2026-09-21 · **Status:** proposed · **Scope:** the three releases after the 0.13 adoption release, and the honest ceiling for each

This is direction, not commitment. Each milestone below opens when the previous one empties, per
[releasing.md](../../docs/releasing.md). Claims about other projects are as read on 2026-09-21 and are
re-verified in the field scan before any of them becomes public copy.

## The sentence

Every project in this category is open-loop: write an instruction, hope. The nearest thing to a
sensor elsewhere is Burnd, which reads the same transcripts for cost leaks and proposes a CLAUDE.md
line per leak — credit where due, and the inverse direction of this one. agent-harness has the
sensor bound to the rules themselves (a detector per rule file, lint-enforced) and the actuator
(hooks and stances). What it does not yet have is the controller that connects them.

Three honest gaps in the sensor, found by checking the claim rather than asserting it: detector
validity is unmeasured (no labelled corpus, so a hit rate may be measuring the detector), the
per-variant figures are observational rather than a replayed A/B, and rules that opt out of a
detector are dark. The first two are 0.13 and #431 work; the third is what 0.14's judgment checks
are for.

> The harness that tells you when your rules stopped working, and tightens itself when they do.

Two receipts that the sensor already works, both in this repository's own backlog: #429 (a shipped
stance measured as never firing) and #324 (a shipped hook measured as not moving its own metric).

## 0.14 — close the loop

Where the sentence becomes true. Epic #135 is retitled to say what it is for.

- **Detector generation from rule prose.** The 0.13 instrument ships declarative detectors; 0.14
  proposes one from the text of a rule that has none, so the lint gate stops being a wall for a
  first-time author.
- **Stance drift.** "You declared `autonomy: execute`; 40% of your grade-3 commands were denied;
  your effective autonomy is `confirm-writes`." Declared versus measured, not declared versus
  self-reported.
- **Adaptive cost posture.** The usage ledger already knows the break-even; the posture tightens
  when a session crosses it and says so.
- **Governance as a stance dimension.** `governance: {none, local, external}`, default `none`. A
  `local` variant resolves autonomy per action class and repository from a file; an external
  variant resolves it from a control plane. The public repository stays independent of any one.

*Exit for the milestone:* a stance switch is checked, not assumed — `harness usage --rules` groups
hits by the variant that was selected, and at least one variant is demoted or promoted from that
evidence rather than by hand.

## 0.15 — credibility breadth

Only after the loop closes does breadth become honest. Six runtimes at equal depth — Cursor,
Gemini CLI, OpenCode, Copilot CLI alongside Claude Code and Codex — each with the same ownership
journal, the same policy coordinator, the same detectors. Not fifty-two; nobody chooses a harness
for its long tail, and every one added shallow costs the depth claim.

- **Floor semantics for stances**, borrowed with credit from planning-with-files: a root selection is
  a floor a project or session can only tighten. The current precedence is override.
- **Real `constraints.json` content.** The conflict engine ships empty today; the first constraints
  are the ones the repository already violates.
- **"Across AI agents"** returns to the headline here, and not before.

## 1.0 — the empty slot

Nothing in the field is multi-user. Shared stance floors with personal overrides; rule firing
aggregated across a team's sessions; the usage ledger exported over OTLP into the observability
platform a team already runs, adding the one thing that platform cannot see — whether the rules
fired. This is also where a product would live. Recorded as the ceiling-raiser; not a commitment.

## The honest ceiling

The best-engineered tool in this category has roughly 1,500 stars after fifteen months. The
projects above ten thousand are content packs with an author's audience, or one idea you can say in
a sentence. Engineering depth alone does not get there; this repository has more of it than
anything in the category and fourteen stars.

The standalone instrument can reach thousands: zero-install, vendor-neutral, unbundled from anyone's
opinions, answering a question the whole field is guessing at. The harness itself reaches low
hundreds on packaging parity and depends on the instrument, the sentence, and the 0.14 evidence to
go further. What is not on the path: more operating systems, the fifty-second runtime, or another
capability nobody can say in a sentence.

## What would make this wrong

- The 0.13 instrument fails its sixty-second test — a stranger runs it and learns nothing about
  their own rules. Then 0.14's generation becomes 0.13's problem, and the arc compresses.
- A comparable project ships measured rules first. The field moves in weeks; the field scan is
  dated for exactly this reason.
- Closing the loop turns out not to convert. Measuring configuration has not sold (ctxlint, ninety
  rules, nine stars). The bet is that measuring behaviour is different. It is a bet.
