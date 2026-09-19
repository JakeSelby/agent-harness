---
title: 'Migrate GitHub issues to bidirectional BMad traceability'
type: 'feature'
created: '2026-09-19'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: 'd2affb4219838a91435164d0a89c7f6dcd64d1b7'
context:
  - '{project-root}/docs/bmad-governance.md'
  - '{project-root}/docs/bmad.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The repository's GitHub issues have no stable BMad identity or public artifact link, so
planning and delivery cannot be followed in both directions. Historical work must gain traceability
without rewriting its issue record or implying the planning files existed earlier.

**Approach:** Snapshot every repository issue into a typed, hierarchy-independent ID map and
immutable-ID artifact. Add an idempotent standard-library tool that audits, previews and applies only
the Planning block, native type, exact type label and primary parent relationship.

## Boundaries & Constraints

**Always:** GitHub remains authoritative for title, prose, comments, state and acceptance evidence.
Links must resolve on `main` before remote mutation. Closed historical files say `reconstructed`.
New IDs use per-type monotonic counters and are never reused or changed by reparenting.

**Never:** Install Beads, require GitHub Projects, rewrite original issue prose, reopen issues, delete
labels, or treat generated planning metadata as evidence that historical BMad files already existed.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Audit | Committed manifest and artifacts | Zero duplicate, missing, broken-parent or reverse-link findings | Exit nonzero and name every local finding |
| Plan | Live issues differ from manifest projection | JSON lists only the required changes | Report missing issues without mutating |
| Apply | Every artifact exists on `main` | Preserve issue content and idempotently project metadata | Refuse before any mutation when artifacts are missing |
| Reserve | New triaged issue and valid kind | Allocate the next typed ID and authored artifact | Refuse duplicate or missing issues |

</frozen-after-approval>

## Code Map

- `scripts/bmad_issue_sync.py` -- bootstrap, audit, preview, reserve and apply the mapping.
- `_bmad-output/issue-map.json` -- canonical machine-readable IDs, hierarchy and next counters.
- `_bmad-output/implementation-artifacts/AH-*.md` -- public reverse-link artifacts.
- `.github/ISSUE_TEMPLATE/*.yml` -- native intake types and preliminary type labels.
- `tests/test_bmad_issue_sync.py` -- classification, idempotence, audit and allocation regressions.

## Tasks & Acceptance

**Execution:**
- [x] `scripts/bmad_issue_sync.py` -- implement deterministic mapping and guarded GitHub projection.
- [x] `_bmad-output/issue-map.json` and artifacts -- classify every current open and closed issue.
- [x] `.github/ISSUE_TEMPLATE/*.yml` and `docs/bmad.md` -- make the ongoing triage workflow explicit.
- [x] `tests/test_bmad_issue_sync.py` -- cover local invariants and non-destructive body maintenance.

**Acceptance Criteria:**
- Given the current repository issues, when bootstrap and audit run, then all 109 issues have one
  unique typed ID, artifact and consistent parent mapping with zero findings.
- Given an issue body with arbitrary existing prose, when the Planning block is inserted twice, then
  the prose is preserved and exactly one block remains.
- Given artifacts absent from `main`, when apply runs, then it stops before changing GitHub.
- Given a new triaged issue, when reserve runs, then it consumes the next ID without recycling one.

## Implementation Notes

- Added deterministic `bootstrap`, `audit`, `plan`, guarded `apply`, and monotonic `reserve`
  commands using only the Python standard library and the GitHub CLI.
- Classified all 109 issues in the migration snapshot, including 68 primary-parent relationships,
  with one immutable-ID artifact and reverse link per issue.
- Preserved arbitrary issue prose by replacing only the fenced Planning block; remote mutation is
  preflighted against both local artifacts and their availability on `main`.
- Added 15 focused regressions covering classification, provenance, idempotence, audit failures,
  apply preflight, preservation, and ID reservation behavior.

## Spec Change Log

## Review Triage Log

| Finding | Verdict | Route | Evidence |
|---|---|---|---|
| BL-1 stale type labels survive reclassification | medium | patch | `planned_actions` checks only for the desired label and `apply_manifest` unions it, so contradictory owned labels remain. |
| BL-2 artifact metadata audit is incomplete | medium | patch | Audit compares only four frontmatter fields; type, title, lifecycle, provenance, and parent issue can contradict the manifest. |
| BL-3 no live title or lifecycle refresh | low | reject | The map is an explicit migration snapshot and each artifact says GitHub owns delivery state; a live refresh surface is not required by the approved intent and adds nontrivial complexity. |
| BL-4 reserve does not audit first | medium | patch | `reserve` reads `next_ids` directly, so a nonmonotonic counter can be consumed before validation. |
| BL-5 allocated artifact can pre-exist | medium | patch | `write_manifest` preserves an existing target file even when it was not referenced before reservation, allowing unrelated contents to be adopted. |
| BL-6 artifact and manifest writes are not one transaction | low | reject | A filesystem failure can leave a recoverable orphan that the audit identifies, but atomic multi-file rollback adds complexity for an unlikely local failure. |
| BL-7 truncated recursive Git tree is trusted | low | patch | GitHub exposes `truncated`; a direct refusal prevents a false missing-artifact report without adding a new surface. |
| BL-8 remote artifact content is not compared | false | reject | The approved precondition is that links resolve on `main`; local audit validates the committed content, while the remote gate is intentionally an existence check. |
| BL-9 failed reparent can orphan an issue | medium | patch | The current parent is deleted before the desired parent is added, and no recovery restores it if that POST fails. |
| BL-10 malformed or duplicate Planning fences are unsafe | medium | patch | Regex substitution preserves duplicate complete blocks and can consume prose between an unmatched start and a later end. |
| BL-11 global `--repo` is ignored after bootstrap | low | patch | The parser advertises a repository override globally, but every non-bootstrap command intentionally uses the manifest repository. Scoping the option to bootstrap removes the misleading surface. |
| BL-12 malformed manifest keys raise `KeyError` | low | reject | The checked-in manifest is generated and reviewed; exhaustive schema recovery is more complex than warranted for an unlikely manual-corruption path. |
| BL-13 label creation failure escapes the CLI boundary | low | patch | `CalledProcessError` is not among the caught exceptions, so an ordinary `gh label create` failure prints a traceback. |
| BL-14 central mutation-path test gaps | medium | patch | Direct coverage is missing for stale labels, fence repair, remote-tree parsing, reparent recovery, and metadata audit; rejected lifecycle/content claims remain rejected as logged above. |
| EC-1 stale type label edge case | medium | patch | Same verified defect as BL-1: no existing `type::*` labels are removed. |
| EC-2 duplicate traceability blocks | medium | patch | Same verified defect as BL-10: `re.sub` replaces each complete block rather than normalizing to one. |
| EC-3 artifact metadata drift | medium | patch | Same verified defect as BL-2: five manifest-owned fields are not compared. |
| EC-4 sequence 1000 creates an invalid ID | medium | patch | `reserve` formats `1000`, while the audit accepts exactly three digits; reserve must refuse before mutation. |
| EC-5 concurrent reserve can lose an allocation | low | reject | Reservation is a maintainer-local operation and concurrent invocation is unlikely; cross-process locking would add disproportionate complexity. |
| EC-6 stale allocated artifact is adopted | medium | patch | Same verified defect as BL-5: the target path is silently preserved. |
| EC-7 GitHub CLI can hang indefinitely | low | patch | `subprocess.run` has no timeout; a direct timeout bounds every CLI call. |
| EC-8 label creation failure traceback | low | patch | Same verified defect as BL-13: the top-level exception boundary omits subprocess failures. |
| EC-9 failed reparent leaves no parent | medium | patch | Same verified defect as BL-9: removal precedes addition without rollback. |
| VG-1 remote-artifact parser is untested | medium | patch | Pre-verified: every apply test mocks `verify_remote_artifacts`, so its Git tree parsing can regress without a failing test. |
| VG-2 committed corpus is not audited by CI | medium | patch | Pre-verified: CI runs lint and unit tests but never executes the repository audit command. |
| VG-3 stale type labels are not reconciled | medium | patch | Same verified defect as BL-1 and EC-1. |

## Design Notes

The manifest is explicit rather than recomputed during apply so human-reviewed classification and
parentage cannot drift with title edits. The updater uses fenced HTML comments to replace only its own
visible section. Remote application is a separate post-merge operation because pre-merge artifact
links would be broken.

## Verification

**Commands:**
- `python3 scripts/bmad_issue_sync.py audit` -- expected: 109 issues and zero findings.
- `python3 -m unittest tests.test_bmad_issue_sync` -- expected: all traceability regressions pass.
- `python3 bin/harness lint` -- expected: zero findings.
- `python3 -m unittest discover -s tests` -- expected: full suite passes.
- `bin/harness generate --check` -- expected: no projection drift.
