# Adversarial review: PRD, addendum and brief (agent-harness, 2026-09-23)

Reviewed against the checkout at `5e383ff` (VERSION `0.12.0`, tag `v0.12.0` at `d4cf311`).
Paths are repository-relative. `prd` = `prds/prd-agent-harness-2026-09-23/prd.md`, `add` =
`.../addendum.md`, `brief` = `product-briefs/brief-agent-harness-2026-09-23/brief.md`.

**Verdict:** the rubric fixes held, but the Status lines are systematically wrong against the
`v0.12.0` tag, and at least seven testable consequences contradict the code as it stands.

**Counts:** critical 0 · high 7 · medium 22 · low 20.

Personal, employer, secret and contractual scan: nothing critical. No names, employer, paths,
emails or credentials in the three files. The addendum paraphrases the `jev` vendor's terms
(add:291-293) without quoting or disclosing them, and the PRD commits to keeping that vendor's
figures local (FR-49). No finding.

## High

1. **Status lines say "unreleased (0.13)" for work that shipped in the v0.12.0 tag.**
   - Location: prd:335 FR-3, prd:354 FR-13, prd:385 FR-14, prd:446 FR-17, prd:455 FR-18, prd:512
     FR-19, prd:531 FR-21, prd:608 FR-26, prd:741 FR-38, prd:873 FR-47, prd:984 FR-52 (per-case
     progress); §9.2 v0.13.0 list (prd:1346-1352); add:45-52.
   - Defect: `git tag --contains` puts each of these in `v0.12.0`. They are #472 (per-capability
     matrix), #478 (import), #473 (four constraints; `git show v0.12.0:primitives/constraints.json`
     already has 4), #479 (installer), #475 (plugin), #488 (vendored engine), #492 (runtime list),
     #474 (token cap), #486 (contract with `none`/`local`), #467 (field scan), and #339 (per-case
     progress, CHANGELOG.md:685-691 under 0.12.0). FR-19's detector-or-reason lint is older still:
     `check_detectors` arrived in #62 (`d4703d8`, first tag v0.6.0; bin/harness:2132-2153).
   - Root cause: the 0.12.0 changelog and `compatibility/migration.json` never list #465-#494,
     so the PRD followed the changelog instead of the tag. Fix the Status lines to say
     "implemented (0.12, not in the 0.12.0 notes)" and file a changelog amendment.
2. **FR-52 and the §9.1 note describe #336 as open and unmilestoned. It is closed.**
   - Location: prd:985 ("automates 1 of 11 cases (#336, unscheduled)"), prd:1340-1341 ("#336 has
     no milestone yet").
   - Defect: #336 is CLOSED on milestone v0.13.0, and every required case now has a driver.
   - Evidence: `gh issue view 336`; CHANGELOG.md:70; commit `74ae3a0` ("automate all eleven cases").
3. **FR-67 says the harness reads declarative detectors. `harness usage --rules` never loads them.**
   - Location: prd:546-547.
   - Evidence: the harness registry is `Registry(_REGISTRY)` only (policy/hooks/rule-detectors.py:422-428).
     `rule_ids` reads `DETECTORS` alone (bin/harness:3742-3751). Nothing in `bin/harness` or the
     rule pack calls ruleprobe's `load_bundle` or reads `.ruleprobe/detectors.yaml` (wheel
     `ruleprobe/rules.py:257`). The brief's line "Declarative detectors let a developer measure their
     own rules" (brief:56) holds only for standalone `ruleprobe`.
4. **FR-20 and FR-13 promise an unmeasured-rules listing that `harness usage --rules` does not produce.**
   - Location: prd:526 ("Rules with no detector are reported as unmeasured, with their reasons"),
     prd:359 (imported rules reported as unmeasured), prd:548.
   - Defect: the report iterates detector ids, not rules. It prints no rule without a detector,
     no `OPT_OUT` reason and no share measured.
   - Evidence: bin/harness:3754-3790. Rule-level `measured/dark/unmeasured` exists only in
     ruleprobe, and only with `--rules <dir>` (wheel `ruleprobe/rules.py:1-15`).
5. **FR-35 says grade 3 is denied under every autonomy variant. It is asked in prompting modes, and a marker passes it.**
   - Location: prd:709-710.
   - Evidence: `grade-bash` emits `ask` unless the permission mode is `auto` or `bypassPermissions`
     (policy/hooks/grade-bash.py:55, 921-935). A leading `HARNESS_CONFIRMED=1` passes any grade
     silently (grade-bash.py:31-34, 914-916).
6. **FR-37 says unfiltered output is never lost from the transcript. The filter keeps it out by design.**
   - Location: prd:731-732.
   - Evidence: "only failures, the summary and the tail of a run enter the transcript"
     (policy/hooks/filter-output.py:2-4). No tee or side file exists in filter-output.py or
     filter-lines.py.
7. **FR-29 says `harness tiers check` fails a role that names a model. The command does not look at roles.**
   - Location: prd:643-647.
   - Evidence: `cmd_tiers` checks only the adapters' class-to-model tables against Codex's model
     catalog (bin/harness:4770-4792). `role_binding` explicitly accepts a per-role `model` override
     from `role_bindings` config (lib/harness_core/catalog.py:380-396: "role bindings may change model
     and effort only").

## Medium

8. **FR-25 export is described as duplicate-free and keyed by timestamp.**
   - Location: prd:599-600.
   - Defect: delivery is at-least-once. Readers de-duplicate on `harness.row_key` and keep the
     greatest `harness.exported_at`.
   - Evidence: policy/hooks/telemetry.py:7-9; docs/telemetry.md:153-158, 301-304. The same docs
     need a reader-side dedup query, so FR-25's "no harness-specific adapter" also overstates.
9. **The glossary and §6 misdescribe where the decision log lives and whether it is exported.**
   - Location: prd:264 ("part of the usage ledger"), prd:1268-1269 ("never exported unless the
     developer enables export").
   - Evidence: the hook log is a separate `decisions.jsonl` (policy/hooks/decisions.py:5, 128), and
     it "is no part of `export`" (policy/hooks/telemetry.py:124). The `kind: "decision"` rows in
     `usage.jsonl` are provider calls (lib/harness_core/decisions/ledger.py:7), which is a second
     meaning FR-47 relies on (prd:874).
10. **FR-36 calls its gap unscheduled, and NFR-10 says it is already tested.**
    - Location: prd:715, prd:1233.
    - Evidence: the gap is filed as #611 on milestone v0.12.1 ("interleaved sessions in one
      checkout reset each other's block count"). NFR-10 claims tests prove per-session counters.
      The code keys the count to `session_id` in one per-checkout file (policy/hooks/stop-gate.py:295).
11. **UJ-7's edge case promises "re-runs one target, not four".**
    - Location: prd:208-209.
    - Defect: scoping is per runtime, not per target. Only `hook.py` is private to a runtime, and
      any shared-source change invalidates every target.
    - Evidence: CHANGELOG.md:561-571; docs/releasing.md:118-121.
12. **The addendum says the round runs on `main`. FR-52, UJ-7 and the release doc use a frozen release branch.**
    - Location: add:309-310 vs prd:982, prd:203.
    - Evidence: docs/releasing.md:110-114; compatibility/freeze.json `branch`.
13. **FR-14 says a constraint violation fails `harness stances`. It exits 0.**
    - Location: prd:388-389.
    - Evidence: `cmd_stances` prints the conflict and returns 0 by design (bin/harness:2405-2442).
      Only `sync` refuses.
14. **FR-43 rejects a card "longer than 70 lines, or 85 with a full decision block". The hook has one cap, 85.**
    - Location: prd:798.
    - Evidence: `CARD_CAP = 85` is applied unconditionally (policy/hooks/validate-plan-card.py:13,
      81-86). A 75-line card with no decision block passes. The 12-node and 80-column diagram limit
      (prd:801) is not checked by the hook at all.
15. **FR-6 says doctor reports each item as ok, warn or fail with the next safe command. It prints prose lines.**
    - Location: prd:941.
    - Evidence: a `harness doctor` run prints lines such as `prices: 12 model(s)...` and `drift: 1
      item(s), run harness diff`, with no ok, warn or fail status words (cmd_doctor, bin/harness:1799).
16. **FR-69 lists the keys `config set` accepts too narrowly.**
    - Location: prd:489-490.
    - Evidence: `integrations.*` and `governance.*` are also accepted (bin/harness:2929-2940, 2977).
17. **FR-12 requires a waiver in the compatibility catalog, but the catalog has no waiver field.**
    - Location: prd:956-957.
    - Evidence: no `waiver` key or check in compatibility/catalog.json or
      lib/harness_core/compatibility.py. The only "waiver" in the tree is the changelog fragment
      kind (lib/harness_core/changelog.py:12-14).
18. **FR-54 says published copy has no em dashes and tests check it.**
    - Location: prd:1010.
    - Evidence: README.md:177, 216, 291 and 297 contain em dashes. The only em-dash assertions are
      in tests/test_cost_bench.py:602 and 653, which test benchmark output.
19. **UJ-4 uses a command the CLI cannot express.**
    - Location: prd:179, `harness usage --by role --by day`.
    - Evidence: `--by` is a single-choice argparse option, so the last value wins (`harness usage --help`).
20. **FR-3's per-capability vocabulary does not match the files it names.**
    - Location: prd:333-340; SM-6 at prd:1418.
    - Defect: FR-3 promises enforced, advisory or unsupported per capability. `capabilities.json`
      records stances as `mode: instruction | instruction-and-hook` plus a `qualification` state,
      and only `tier_restriction` uses enforced/advisory.
    - Consequence for SM-6: its "no unknown entries" bar cannot fail, because no field can hold
      `unknown`.
    - Evidence: adapters/codex/capabilities.json; lib/harness_core/compatibility.py:8-9.
21. **SM-2's "Current: 1.052" was measured on a different set from the one its target names.**
    - Location: prd:1391-1395.
    - Evidence: the target is the eight-task release task set, but 1.052 came from a four-task set
      (docs/benchmarks.md:145; benchmarks/tasks.json holds 8).
22. **SM-2's "about 5%" disagrees with the addendum's figures.**
    - Location: prd:1396-1397 vs add:328-331.
    - Evidence: the addendum records the prefix at 22% of harness spend, and at 26% at 49k context.
      5% is the 250k-context figure only.
23. **SM-9 cannot be measured with what the product records.**
    - Location: prd:1431-1434.
    - Defect: nothing records when a first report was run or when a rule was edited, and
      `ruleprobe` records nothing at all. Unlike SM-8 (prd:1429), SM-9 does not say it relies on
      cohort self-report.
24. **NFR-2 cites "the newest Python in the test matrix". CI has no matrix.**
    - Location: prd:1197.
    - Evidence: every job is `ubuntu-latest` with the system `python3`, and "the 3.9 floor is
      proved by running the suite locally" (.github/workflows/ci.yml:17-61, 36).
25. **FR-18's plugin contradicts FR-40 and FR-41 confinement.**
    - Location: prd:452-459 vs prd:764-781.
    - Defect: the plugin installs `gatherer`, `reviewer` and `spec-reviewer` as native agents with no
      hooks, so nothing refuses their native spawn.
    - Evidence: .claude-plugin/plugin.json:12-24. The manifest also pins `"version": "0.11.1"`
      against VERSION 0.12.0.
26. **The brief's universal lint claim is narrower in the PRD.**
    - Location: brief:25-26 ("Every rule names a detector... Lint refuses a rule that does
      neither"); product.json `hero.proof` says the same.
    - Evidence: the lint gate covers the repository's own `claude/rules/*.md` only, not external or
      imported roots (prd:359-360; bin/harness:2138).
27. **The brief states story-file design records in the present tense. The PRD plans them for v0.14.0.**
    - Location: brief:102-103.
    - Evidence: FR-64 is planned (v0.14.0, #620; prd:1160-1162). The addendum says stories stayed
      thin until 2026-09-23 (add:151-153).
28. **Two shipped subcommands have no FR.**
    - Location: §4, against `harness --help`.
    - `harness install` does full machine setup: Homebrew, apps and VS Code extensions
      (bin/harness:2789, 4798-4808). FR-17 covers only the installer script and `stable`.
    - `harness decide` asks the provider about an action class (bin/harness:2445). FR-47 says "no
      hook consults a provider" but never names this CLI surface.
29. **The "does not route models" claim sits badly beside FR-29 and FR-30.**
    - Location: prd:53, and brief:131 ("Out: Model routing or serving").
    - Defect: FR-29 and FR-30 map classes to native models and rewrite spawns onto them. Only §8
      narrows the non-goal to "never selects a provider's endpoint" (prd:1306), so the vision
      sentence and the brief's out-list are contradicted by shipped FRs.

## Low

30. **FR-60 files automatic reconnect under the 0.12 implementation. It shipped after 0.12.**
    - Location: prd:1094-1100.
    - Evidence: in 0.12.0, `status` printed the reattach command and "never runs one"
      (CHANGELOG.md, 0.12.0 #483 entry). `heal` re-queuing via `bridge/reconnect` is unreleased
      (CHANGELOG.md:305-314, #603). The PRD cites PR #604 rather than issue #603.
31. **FR-27 and §6 say rows are capped at 2 KiB. Only the `input` field is.**
    - Location: prd:625, prd:1268.
    - Evidence: `MAX_INPUT` caps `input` only (policy/hooks/decisions.py:18, 51).
32. **FR-27 says one in twenty allows is sampled. Only Bash allows are.**
    - Location: prd:617.
    - Evidence: CHANGELOG.md:217 (#593).
33. **FR-23's fewer-than-30 warning applies to one view only.**
    - Location: prd:582.
    - Evidence: only `--by role` marks `n<30` (bin/harness:4150). `--rules` uses 20 sessions and
      blanks the note instead (bin/harness:3712).
34. **The glossary's stages omit `off`.**
    - Location: prd:283.
    - Evidence: `governance.jev.mode` defaults to `off` (config.example.json:38-40), and #135 lists
      `off → shadow → advise → act`.
35. **The glossary's command grade credits the stance with the ask-or-deny choice.**
    - Location: prd:255-256.
    - Evidence: the stance sets only the threshold. The permission mode picks ask or deny
      (grade-bash.py:22-28, 52-55).
36. **FR-17 says the installer installs and runs a dry-run sync. It installs nothing.**
    - Location: prd:450.
    - Evidence: the script runs `init --yes`, then `harness install --dry-run` (scripts/install.sh:4-5,
      70-81).
37. **The addendum cites an SM that does not exist.**
    - Location: add:370 cites SM-3a, which the PRD no longer has.
38. **The addendum cites a missing memlog.**
    - Location: add:57 says each resolution is logged in `.memlog.md`, but the
      prd-2026-09-23 directory has none (`git ls-files`).
39. **The addendum counts enforced stances two ways.**
    - Location: add:174-175 names four (autonomy, delegation, cost, plan-ceremony); add:119 says
      "three of nine".
    - Evidence: Codex capabilities mark `cost` as `instruction`.
40. **The addendum says the line cap binds. The changelog says tokens bind.**
    - Location: add:257-258.
    - Evidence: "the binding cap is tokens, the line cap is the secondary guard" (CHANGELOG.md:620-621).
41. **The addendum's deferral figures disagree with the spike record.**
    - Location: add:260 says 1,474 tokens and 42%.
    - Evidence: docs/spikes/2026-09-22-deferred-rule-text.md:11-12 says 1,253 tokens and 36% of
      3,524.
42. **Three "implemented" Status lines omit unreleased parts their consequences depend on.**
    - FR-9's worktree-aware `reserve` is #441 (`b94ac78`, after v0.12.0; prd:1158).
    - FR-7's strong-class assessor is #598 (prd:951).
    - FR-23's deduplication ratio is #587 (prd:581).
43. **A shipped hook has no FR.**
    - Evidence: `allow-plan-webfetch` auto-approves WebFetch in plan mode (policy/hooks/allow-plan-webfetch.py:2-6).
      FR-39 covers only Bash grades.
44. **Two repository workflows have no FR.**
    - Evidence: merge-queue CI with changelog fragments (#610, lib/harness_core/changelog.py) and
      the scheduled `bmad-traceability.yml` live audit. Neither is covered by the
      repository-process FRs.
45. **SM-1 cannot be timed, and its first report may not show the share measured.**
    - Location: prd:1384-1389; brief:107-108.
    - Defect: nothing records the one-minute time. ruleprobe states the share of rules measured
      only when `--rules <dir>` is passed, so a first `uvx ruleprobe report` does not.
46. **FR-47 says `learn` records nothing for a third-party provider. It appends a learn-count row.**
    - Location: prd:879.
    - Evidence: `JevProvider.learn` delegates to the local base, which appends a `learn` event row
      (lib/harness_core/decisions/jev.py:738-739; lib/harness_core/decision.py:511-513).
47. **The brief's scope drops a condition the PRD keeps.**
    - Location: brief:123 lists the Codex CLI in the stable contract unconditionally.
    - Evidence: the PRD makes it conditional on #336 and the round agreement (prd:1340-1341).
48. **Landing copy advertises items the PRD does not back.** FR-54 makes product.json the copy source.
    - `on_the_way` advertises "Budget nudges mid-run" (#322), which the spike rejected
      (docs/spikes/README.md:15, "do not build").
    - It also states "Six runtimes at equal depth is the target". Neither item appears in the PRD.
49. **§0 says the PRD covers what shipped from 0.1 to 0.13, but 0.13 is unreleased.**
    - Location: prd:18.
