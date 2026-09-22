# Roadmap intake: learnings from an enterprise agent-platform review

Assessed 2026-09-22 against `main` at `d884cff`. Every claim below was checked at that commit
before an opinion was formed; file and line references are to that tree. The source review is
scrubbed and stays scrubbed: nothing here names it, and every number is this repository's own.

## Verdict

Of ten inbound items, four apply and earn a roadmap slot (B5, B4, B2, B3), three are cheap
documentation or test lines rather than mechanisms (B1, B10, B7), one is mostly done already
(B1), and two do not apply (B8, and B6 as a mechanism). B9 applies but is ranked lower than the
prompt proposes, because a replay tier does not produce the number the benchmark exists to
publish. Nothing here invalidates the 0.12 ship premise; the one item that comes close (B3,
family price inheritance) is a documented, deliberate behaviour with a stated caveat, so it is
the first cost story after 0.12 rather than a blocker inside it.

## Part A: stale claims at `main`

| # | Claim | Found | Action |
| --- | --- | --- | --- |
| 1 | "Nineteen detectors" | 17: 6 generic from the vendored wheel plus 11 repo-specific (`claude/hooks/rule-detectors.py:390-405`). `README.md:38`, `product.json:9,34`. No test or landing-copy check asserts the count. | Fix both files; add a test that derives the number from the registry and compares it with `product.json`, so the copy cannot drift again. |
| 2 | Zero line headroom | True: 196 of 200 lines, `LINE_BUDGET = LINE_CAP - 4` (`tests/context_budget.py:28-33`); the token cap (3,696 of 4,202) has room. | Decide, not drift: the gap has done its job once (the diff that spent it said so). Set `LINE_BUDGET = LINE_CAP` and keep the line cap as the secondary guard `docs/how-it-works.md` already calls it; the binding cap is tokens. |
| 3 | "ships zero constraints" | False: `primitives/constraints.json` holds 4 stance constraints. `docs/field-scan.md:157-159`. | Reword. |
| 4 | "no labelled corpus" | False as written, true operationally: the wheel ships `validity.py` and `corpus/`, and nothing in this repository's CI or tests runs it. `docs/field-scan.md:147`, `docs/caught-in-the-act.md:79`. | Reword with the residue stated: 6 of 17 detectors scored, 11 repo-specific ones unscored, floor not wired into CI here. The wiring is a story (below). |
| 5 | "cites no source" | False: `bin/harness:161-169` cites the memory docs and #430. `docs/field-scan.md:162`. | Reword. |
| 6 | `EXPECTED_MODULES = 18` | Stale against HEAD (19) and correct at the pinned `parent_sha`. `benchmarks/oracles/hook_ids.py:6`. | Comment that it is pinned to the task's sha, and derive it from the glob at that sha in the fixture check rather than by hand. |
| 7 | `issue-map.json` stale date | True: `generated_at` 2026-09-19, items to #507. | Regenerate in the same PR as the reservations. |
| 8 | Two always-loaded numbers | Different scopes: `benchmarks/static.json` (21 files, includes the output style and listings) vs `harness lint` (CLAUDE.md, rules, longest stance variant). | Name the scope in both places. |
| 9 | Docs site serves `stable` | Premise false in this repository: no site workflow exists; `stable` is the install branch. The site is a separate repository. | Not in this PR; check the site repository's source ref separately. |

## Part B: the inbound learnings

### Applies, roadmap

**B5, a tier-0 rung.** The band ladder's floor is `light` (`delegation-tiering/SKILL.md` "The
bands"); the sidecar schema allows `strong | standard | light` on a row (`policy/hooks/posture.py:396`);
no role is "no model". Yet the repository already runs one tier-0 classifier in production:
`grade-bash` is a deterministic grader with a tested sub-0.2 s bound, and `worker-a` is described
as classification and extraction work. A `class: none` row makes the pattern nameable: the resolver
treats it as no spawn, the caller decides deterministically, and `check_cost_sidecars` validates it
like any other class. Composes with `extends` and with 0.14's adaptive cost posture, which needs a
rung below `light` to tighten into. **Slot: 0.14 (#523).**

**B4, cache instrumentation.** The headline "prompt caching beats both" (`SKILL.md:35`) rests on
list-price arithmetic (`SKILL.md:222-238`), not on a measurement; `usage --by prefix` measures a
write-over-read-plus-write miss ratio and a day-slice step, and `docs/benchmarks.md` carries a
cache-normalised cost, but the replay has no cache axis and no TTL decision is recorded anywhere.
The transferable part is the method: a default flip is recorded as "off for cost, not for
brokenness" only after the competing explanation is refuted. Two stories: promote prefix stability
to a replay axis (arms differ by cache state, not only by environment), and record the TTL position
as *measured elsewhere, disputed, reproduce before believing* in `cache-hygiene.md`'s skill. The
harness does not set the TTL; Claude Code does, so the pre-warming finding is out of reach here and
is recorded as such. **Slot: 0.14, beside #431 (#524).**

**B2, the inflation factor.** Dedup is real and unbounded in `usage-log.py:186`; the raw sum is
discarded, `cmd_usage` and the OTLP export read only the deduplicated row, and `docs/usage.md:60`
says per-line counting inflates without saying by how much. A `raw_vs_deduped` ratio per row is a
one-hook change plus a column and an attribute. Also found: id-less assistant records are keyed per
line and never deduplicated (`usage-log.py:673`), which is a small correctness story of its own.
**Slot: 0.13, small (#518, #519).**

**B3, pricing traps.** One applies and is self-admitted: an unlisted variant inherits its family's
rate (`policy/prices.json:27-29`), which under-bills a premium variant by a multiple. This is the
one place the repository presents an unknown as a known figure. Change: an unlisted variant is
**unpriced** (`None`, footer, never zero), matching `pricing.py:16`. Cache fields are read per
runtime and tested (`test_usage_prices.py:362-386`); Codex reads a `cache_write_input_tokens` it never
writes, which `NO_CACHE_WRITES` documents. No corrected-cost column exists; keep it that way, and
say so where the ledger is declared the record (`docs/telemetry.md:8-10`, which already names the
30-day backend TTL). **Slot: 0.13, first cost story after 0.12 (#517).** Not a 0.12 blocker: the behaviour is
documented, the caveat is stated, and no shipped price row exercises it today.

### Applies, one line each

**B1, is the restriction real?** Enforced, not advisory, on Claude Code: `lifecycle.py:430` invokes
`tier-agent-spawns`, which rewrites an explicit top-tier `model:` on an Agent call to one rung
below unless a role declares it, and `tests/test_tier_agent_spawns.py` asserts it. Two honest
gaps: the session's own `--model` is deliberately never touched (`docs/settings-ownership.md:38`),
and Codex has no spawn hook. `docs/compatibility.md` has a capability matrix but no
enforced-versus-advisory column. Action: one row per runtime saying which. **Slot: 0.13 docs (#520).**

**B10, single-coordinator dispatch.** Confirmed: `lifecycle.py:484-488` registers exactly one hook
entry per event; `main()` is fail-closed; `OffTheHotPath` (`tests/test_cost_sidecars.py:462`) keeps
the cost table off the hot path. `docs/how-it-works.md:57` describes it obliquely; no per-event
overhead figure exists anywhere. Actions: a paragraph in `how-it-works.md`, a measured per-event
dispatch figure in `benchmarks/static.json`, and a finding: `claude/settings.template.json` still
lists twelve-plus per-hook entries that `runtime_template()` replaces, dead weight worth deleting.
**Slot: 0.13 docs (#521); the figure rides #524.**

**B7, ordering under a cap.** Two caps exist: `usage-feed.py:81 OPEN_TAIL` keeps the newest 64
(correct), and `remote_control.py:370` fetches 50 sessions in server order with no order asserted.
Action: request newest-first explicitly and assert it in the test. **Slot: 0.13 (#526).**

### Does not apply

**B8, deterministic failures.** There is no retry of a role run anywhere; hooks are one-attempt and
never block (`telemetry.py:31`, `brief-guard.py:62`); the only "retries" are accounting
(`UNSUMMED_TRIES`). Record the decision instead: if a retry is ever added, auth denials escalate on
first occurrence and throttles keep their full budget. No item.

**B6, hard schemas.** `spec-reviewer` and `design-judge` are `posture: fixed` with prose caps of
300 words and no mechanical bound. But neither native runtime offers a per-subagent
`max_output_tokens` or a response schema on the Agent tool, so a hard bound is unenforceable here;
what remains is a fenced reply template, which `design-judge` already carries. No mechanism; a doc
line under budgets stating why the bound stays soft on fixed roles too.

### Applies, ranked lower than proposed

**B9, record/replay.** True: `scripts/cost_bench.py` calls the real CLI, keys nothing by request
hash, and #369 is open with no result committed. But a replay tier does not yield the saving
figure; both arms would score stale responses, and the benchmark's purpose is the live number. What
it would buy is regression coverage of the runner and fixtures, which `verify_tasks` already gives
without a model. The blocker on #369 is attention and spend on a release candidate, which the
0.13 plan already schedules. **Slot: 0.15 (#525), after #369 has one published row**, as a fail-loud
fixture cache for the runner's own tests.

## Ranking

1. **B3** unlisted-variant pricing to unpriced. Smallest change, the only wrong-direction number.
2. **B5** tier-0 class. The most interesting mechanism; it names something already true.
3. **B4** cache axis and the recorded TTL position. Turns the strongest claim into a measured one.
4. **B2** inflation factor. Cheap diagnostic; folds into the same usage work.
5. **B10 / B1 / B7** one-line honesty surfaces.
6. **B9** after #369.

The prompt's top three were B5, B9, B4. B9 drops because it cannot produce the published figure;
B3 rises because it is the one item where a reader is told a number that is known to be low.

## Not doing, with reasons

- **No enforcement layer, no spend cap.** B6 stays a template, B5 is a class, neither denies.
- **No pre-warming or TTL change.** The harness does not own the TTL; the finding is disputed at
  its source and is recorded as such, not adopted.
- **No corrected-cost column.** Fix the source or mark the row unpriced.
- **No retry machinery** just to classify its failures.
- **No docs-site change in this repository**; the site is elsewhere.
- **No re-run of the live replay from this intake**; #369 owns it.
- **Nothing into 0.12.**

## Filed 2026-09-22, one per mechanism

- story: #517 unlisted model variants are unpriced rather than inheriting the family rate (B3), v0.13.0
- story: #523 `class: none` tier-0 row in the cost sidecar schema and resolver (B5), v0.14.0
- story: #524 cache axis in the live replay, dispatch overhead figure, recorded cache-TTL position (B4, B10), v0.14.0
- story: #518 `raw_vs_deduped` inflation ratio in `usage-log`, `harness usage` and the OTLP attribute (B2), v0.13.0
- bug #519: id-less assistant records are never deduplicated (B2 finding), v0.13.0
- chore: #520 enforced-versus-advisory column per runtime in `docs/compatibility.md` (B1), v0.13.0
- chore: #521 dispatch model paragraph; delete the dead hook entries in `settings.template.json` (B10), v0.13.0
- chore: #522 wire `ruleprobe corpus --floor 0.9` into this repository's CI and score the 11 repo-specific detectors (A4 residue), v0.13.0
- chore: #516 Part A copy fixes and the detector-count test, one PR (A1 to A8), v0.13.0
