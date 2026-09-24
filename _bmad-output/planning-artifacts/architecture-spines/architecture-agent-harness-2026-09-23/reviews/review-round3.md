# Round 3 review: ARCHITECTURE-SPINE.md (agent-harness, 2026-09-24)

Reviewed on the `docs/783-roadmap-corpus` branch, after the update for #783 added AD-22 and AD-23, amended
AD-12 and re-dated AD-16. `SPINE` is
`_bmad-output/planning-artifacts/architecture-spines/architecture-agent-harness-2026-09-23/ARCHITECTURE-SPINE.md`.
Line numbers refer to the spine as reviewed, before the fixes.

**Verdict:** fail. The AD-16 re-date and its capability-map rows were consistent. AD-23 did not say how
observation stays out of model context, and its test could not be checked. AD-22 left resolution
unassigned, and neither decision defined its fingerprint or labels well enough to prevent divergence.

**Counts:** 11 findings: 2 high, 5 medium, 4 low. All 11 fixed in the same pull request.

## 1. Findings and resolutions

**S1**
- **Severity:** high
- **Location:** SPINE AD-23, the Rule (SPINE:432-433).
- **Defect:** Observation runs in the bare arm, but the rule does not say how. The one dispatcher mixes
  logging with output that reaches the model: `neutralize-tool-output` on every tool result,
  `harness-session` at session start and `stop-gate` at stop (`lib/harness_core/lifecycle.py:547-573`).
- **Resolution:** Fixed. Observation runs through an observation-only hook path that appends to the ledger,
  prints nothing, adds no context and returns no decision. Only that path is installed in the bare arm, and
  context-emitting handlers are enforcement or advisory modules that observation never rides on.

**S2**
- **Severity:** high
- **Location:** SPINE AD-23 (SPINE:433).
- **Defect:** The "identical model context" test named no comparison point, and it covered only the bare
  arm while the title claimed every arm.
- **Resolution:** Fixed. The test compares the first model request (system prompt, tool schemas and first
  user message), byte-identical after normalising timestamps and session ids, per arm: bare and each
  harness profile under test. The title now says "any arm's model context".

**S3**
- **Severity:** medium
- **Location:** SPINE AD-22 (SPINE:423).
- **Defect:** A fingerprint built only from the switched-on set lets two different profiles share a
  fingerprint.
- **Resolution:** Fixed. The fingerprint is a digest of the resolved selection: each switched-on module
  with its version or content digest, the stance variants, the configuration values that reach the model
  or the hooks, and the harness version.

**S4**
- **Severity:** medium
- **Location:** SPINE AD-22 (SPINE:413, 417-418).
- **Defect:** Nothing checks that two modules cannot take one slot, and the v0.14.0 tag also covered the
  scorecard and the slot model.
- **Resolution:** Fixed. Two switched-on modules claiming one slot is a resolution error unless one cedes
  it. The tag is split: fields and checks v0.14.0 (#554), scorecard v0.15.0, slots and adapters v0.16.0.

**S5**
- **Severity:** medium
- **Location:** SPINE AD-22 (SPINE:419-423).
- **Defect:** Manifest parsing and dependency resolution had no owner and no home, which risks a second
  resolver and a conflict switching off a core hook.
- **Resolution:** Fixed. Manifests live with each primitive in the catalog (AD-1), and `posture.py` (AD-2,
  AD-6) parses them and resolves dependencies and conflicts. A conflict never switches off a fixed
  invariant without AD-2's acknowledgement.

**S6**
- **Severity:** medium
- **Location:** SPINE AD-23 (SPINE:434).
- **Defect:** "Every ledger row" clashed with AD-11's additive schema. Decision-log rows cannot carry token
  counts, and per-module token attribution is an unlabelled estimate.
- **Resolution:** Fixed. Every new ledger row carries the fingerprint, additive under AD-11, and older rows
  read as unattributed. Usage rows carry token attribution under AD-12's soft-estimate label. Decision-log
  rows carry hook-decision attribution only.

**S7**
- **Severity:** medium
- **Location:** SPINE AD-12 (SPINE:288) and the status-words convention (SPINE:445).
- **Defect:** Nothing defined soft against measured, and the labels overlapped FR-11's availability words.
- **Resolution:** Fixed. AD-12 defines measured, soft estimate and unmeasured, and states that they are
  orthogonal to FR-11's known, partial, unavailable and failed. The status-words convention lists both.

**S8**
- **Severity:** low
- **Location:** SPINE AD-23 heading (SPINE:425).
- **Defect:** The tag named no issue, though #482 exists.
- **Resolution:** Fixed. The tag reads `[PLANNED: v0.14.0, #482]`.

**S9**
- **Severity:** low
- **Location:** SPINE Capability → Architecture Map (SPINE:520).
- **Defect:** The measured-rules row lacked AD-22, which binds FR-19.
- **Resolution:** Fixed. The row lists AD-13 and AD-22.

**S10**
- **Severity:** low
- **Location:** SPINE AD-12 (SPINE:287).
- **Defect:** "Manifest" meant both the ablation manifest and the module manifest.
- **Resolution:** Fixed. AD-12 names the ablation manifest and distinguishes it from AD-22's module
  manifest.

**S11**
- **Severity:** low
- **Location:** the spine `.memlog.md`, the entries for this update.
- **Defect:** The log omitted the AD-12 Binds and Prevents edits, and recorded the review gate as skipped.
- **Resolution:** Fixed. The memlog records the AD-12 edits, this round and its fixes. The gate ran as this
  review.

## 2. Checked and consistent

- AD-16's re-date to the backlog matches the roadmap's placement of #542 and #543.
- The capability-map rows for selection, ledgers and benchmarks cite AD-22 and AD-23.
- The spine linter reports no findings before or after the fixes.

## 3. Second pass

**Verdict:** fail, 7 findings (2 high, 5 medium). S1 and S5 were still partly open.

**P1**
- **Severity:** high
- **Location:** SPINE AD-22 (SPINE:431).
- **Defect:** The rule let AD-2's acknowledgement switch off a fixed invariant; AD-2 allows that only for a
  core hook. Kept S5 open.
- **Resolution:** Fixed. A conflict never switches off a fixed invariant, and switches off a core hook only
  with AD-2's acknowledgement.

**P2**
- **Severity:** high
- **Location:** SPINE AD-23 and the conventions (SPINE:448-450, 466, 473).
- **Defect:** The observation path had no registration, and the dispatcher fails closed, so an observation
  error would change the bare arm. Kept S1 open.
- **Resolution:** Fixed. Observation has its own registered entry point beside `hook.py`, outside the
  dispatcher. It fails open and silent: exit 0, no output, errors to a local log only. The Hook ids
  convention allows the second entry point, and the Failure posture table gains an observation row.

**P3**
- **Severity:** medium
- **Location:** SPINE AD-23 (SPINE:453-455).
- **Defect:** The test compared only the first model request, missing later events.
- **Resolution:** Fixed. A scripted session against a recorded model drives every installed hook event, and
  every model request is compared, per arm.

**P4**
- **Severity:** medium
- **Location:** SPINE AD-22 (SPINE:429).
- **Defect:** Hook manifests had no home.
- **Resolution:** Fixed. Each manifest sits beside its module's source: primitives in the catalog, hooks in
  `policy/hooks/`. The one resolver reads both.

**P5**
- **Severity:** medium
- **Location:** SPINE AD-12 (SPINE:290-293).
- **Defect:** Direct counts and figures from pre-fingerprint rows fit no label.
- **Resolution:** Fixed. Measured covers direct row counts and run estimates, each naming its fingerprint;
  an estimate also carries n and an interval. Unattributed qualifies figures from rows with no fingerprint,
  which support only whole-profile statements.

**P6**
- **Severity:** medium
- **Location:** SPINE AD-23 against AD-12 (SPINE:441, 458-459, 274).
- **Defect:** v0.14.0 would ship a label defined only in v0.15.0.
- **Resolution:** Fixed. The labels are tagged v0.14.0 with attribution; the soft-estimate report and series
  stay v0.15.0.

**P7**
- **Severity:** medium
- **Location:** the spine `.memlog.md` (line 50).
- **Defect:** The log claimed all 11 findings fixed.
- **Resolution:** Fixed. A correction entry records S1 and S5 as partly fixed, followed by this pass and one
  change line per fix.
