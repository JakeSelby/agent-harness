# `concise` voice variant with reply shapes chosen by purpose

> **Verdict.** Adds a `concise` voice with six reply shapes picked by purpose and seven rules every reply
> keeps, all in plain prose. Selecting it sets Claude Code's built-in `Concise` style, sends the same
> stance to Codex, and removes the competing reply templates from always-loaded text.
> **Effort** ~2 days · **Risk** medium, the always-loaded set is at 199 of 200 lines · **Blast radius** reply shape under every voice, and uncapped subagent briefs

## At a glance

- **Outcome** — `voice: concise` can be selected, and replies take the shape their purpose calls for on both Claude Code and Codex.
- **Approach** — a built-in style map beside the file registry in `bin/harness`, one new stance file, the competing template lines rewritten, and two gated detectors.
- **Touches** — this repository only, about 40 files: harness, voice files, three rules, two hooks, two workflows, two skills, notices, listings, tests.
- **New deps** — None. Wording is adapted from openai/codex (Apache-2.0), openai/openai-cookbook (MIT) and garrytan/gstack (MIT).
- **Not in scope** — changing the default voice, Codex `model_verbosity`, the other rules' plain-language rewrite, the Scannable style fix, humanizer.
- **Exit test** — `harness lint` is clean, `unittest discover -s tests` passes, and a sync shows `Concise` plus the stance in Codex `AGENTS.md`.
- **Open question** — how to fit about 24 more always-loaded lines under a 200-line cap (decision 2).

## System design

```text
config: voice = concise ──▶ harness sync
harness sync ─┬─▶ *built-in style map ── "Concise" ──▶ Claude settings.json
              ├─▶ *voice/concise.md ──▶ Claude Code stance rules
              │                      └─ same text ──▶ Codex AGENTS.md
              └─▶ *rules, workflows, skills: reply templates removed
*brief-guard ── brief + return shape ──▶ subagent
each final reply ── scaffold labels, heading first ──▶ *rule-detectors
```

`*` marks a new or changed node. The Codex side needs no code change, because `render_codex_agents` already emits the selected stance.

## Steps

1. **[Delivery issue and story file](#step-1--delivery-issue-and-story-file)** — `scripts/bmad_issue_sync.py new`, story kind, milestone `v0.14.0`.
   *Exit:* `_bmad-output/issue-map.json` maps the issue, and the story file exists.
2. **[Write the stance and measure the budget](#step-2--write-the-stance-and-measure-the-budget)** — `primitives/stances/voice/concise.md`, then lint.
   *Exit:* the `context:` line from `python3 bin/harness lint` is recorded in the story file, and decision 2's answer covers the overage.
3. **[Wire the variant to the Concise style](#step-3--wire-the-variant-to-the-concise-style)** — `bin/harness`, `claude/OWNERSHIP.json`, two test files.
   *Exit:* `python3 -m unittest tests.test_voice_output_style tests.test_voice_stance` passes.
4. **[Remove the competing templates](#step-4--remove-the-competing-templates)** — three rules, `brief-guard.py`, `/research`, `/build`, two skills.
   *Exit:* `grep -rn "What changed" primitives/rules primitives/workflows policy/hooks` prints nothing, and the brief tests pass.
5. **[Rewrite answer-card and scannable in plain prose](#step-5--rewrite-answer-card-and-scannable-in-plain-prose)** — both stances and the Scannable text.
   *Exit:* `grep -n "arrow list" primitives/presentation/scannable.md` prints nothing, and the voice and detector tests pass.
6. **[Two concise-gated detectors](#step-6--two-concise-gated-detectors)** — `policy/hooks/rule-detectors.py`, its tests and the labelled corpus.
   *Exit:* `python3 -m unittest tests.test_rule_detectors` and `python3 scripts/detector_corpus.py --floor 0.9` pass.
7. **[Attribution and listings](#step-7--attribution-and-listings)** — notices, `third-party.json`, `product.json`, README, docs, `changelog.d`.
   *Exit:* `python3 bin/harness lint` and `python3 scripts/cost_bench.py static --check` pass.
8. **[Gates, sync check and follow-ups](#step-8--gates-sync-check-and-follow-ups)** — every CI command, a throwaway-home sync, three follow-up issues.
   *Exit:* `python3 -m unittest discover -s tests` passes, and the sync shows `outputStyle` `Concise` and the stance in Codex `AGENTS.md`.

## Decisions for the reviewer

> **1. Should new installs keep `scannable` as the default voice?**
> *Recommend* yes, for this change. `docs/compatibility-policy.md` treats a changed default's effective behaviour as a breaking change unless it is opt-in, so measure `concise` first and revisit.
> *Alternative* make `concise` the default now. Every new install gets the shapes from day one, but under that policy it is a major-version change.

> **2. How is the stance paid for in always-loaded text?**
> *Recommend* raise the 200-line cap to 225. If step 2 finds the token cap exceeded too, raise it by the stance's measured size and cite this issue. The stance has to reach every reply, and a skill cannot do that.
> *Alternative* keep both caps. Cut the stance to 12 lines with no examples, and fold `cache-hygiene.md` into the `cost` stance, since `docs/preferences.md` already calls that rule misplaced.

> **3. Should the Scannable coding-instructions fix land before this change?**
> *Recommend* yes, as its own bug pull request. `scannable` is the shipped default, so default installs run without Claude Code's coding instructions today, and step 5 edits the same style.
> *Alternative* file it now and land it after. The two reviews stay independent, but the defect stays live longer and this branch needs a rebase.

> **4. Which briefs should `brief-guard` give the return shape?**
> *Recommend* only briefs with no return bound, which is the hook's existing path. Its parity with the cap detector stays exact, and the rule still asks the orchestrator to write a shape.
> *Alternative* every brief without a shape sentence. Capped briefs get the shape too, but most spawns change and the hook needs a second pattern to recognise a shape.

> **5. Where does the notice for the adapted wording live?**
> *Recommend* in `THIRD_PARTY_NOTICES.md` and `third-party.json`, naming the stance file and what changed. Any line inside the stance is paid for on every turn.
> *Alternative* also add a one-line comment at the stance's foot. That is the most literal reading of Apache-2.0's modified-file notice, and it costs one always-loaded line.

## Risks

- **Concise is missing from the pinned Linux client (2.1.278), or ignored in bridge and Agent SDK sessions.** The stance still carries the shapes. State the client floor in the changelog and in `docs/compatibility.md`.
- **Ungated corpus scoring pushes `voice/scaffold-leak` under the 0.9 floor.** Label the scaffold rows already in both corpora as positives rather than narrowing the pattern.
- **A rewrite drops "no tables" or "at most one table", which native acceptance reads from the stance.** Keep both phrases, and pin them in `tests/test_voice_stance.py`.

---

# Addendum

Everything below is for the implementing agent. Paths are relative to the repository root.

## Step 1 — Delivery issue and story file

- Work in a managed worktree (`harness worktree create`), never in a sibling checkout.
- File the issue:
  `python3 scripts/bmad_issue_sync.py new --title "feat(voice): concise voice with reply shapes chosen by purpose" --kind story --body-file <body.md> --milestone v0.14.0`.
  - The body links this plan, lists the steps, and names no person.
  - The milestone is `v0.14.0` because adding a primitive with an unchanged default is a minor release under `docs/compatibility-policy.md:37-38`.
  - If the milestone does not exist yet, create it (`AGENTS.md:66-67`).
- Per `docs/bmad-governance.md:33-37`, `new` reserves the BMad ID in the same step. The brief also asked for `reserve --issue N`, but run `python3 scripts/bmad_issue_sync.py reserve --issue N --kind story` only if `_bmad-output/issue-map.json` does not map N afterwards.
- The story file at `_bmad-output/implementation-artifacts/<BMad ID>.md` needs the sections `bmad_issue_sync.py:44` expects for a story: Story, Acceptance criteria, Design, Tasks, Dev notes. The acceptance criteria are the card's exit tests.
- If decision 3 is answered "first", file the Scannable bug now (text in step 8) and land it before step 5.

## Step 2 — Write the stance and measure the budget

- **Baseline, counted by line count during planning:**
  - `claude/CLAUDE.md`: 10 lines.
  - `claude/rules/`: 112 lines across 10 files.
  - The longest variant of each of the 9 stance dimensions: 77 lines, with `voice/answer-card.md` counted at 9.
  - Total: 199 lines against `ALWAYS_LOADED_CAP = 200` (`bin/harness:180`).
  - The token cap is `12607 // 3 = 4202` (`bin/harness:173-174`), pinned by `tests/test_harness.py:420-424`. The current token total was not measured during planning.
- Write `primitives/stances/voice/concise.md` from the draft below. It is 33 lines, so it replaces a 9-line longest variant and adds about 24 lines and roughly 600 tokens (at four characters a token).
- The rewrites in step 4 replace lines one for one, so they free almost nothing. Expect about 223 lines before decision 2 is applied.
- Run `python3 bin/harness lint` and copy its `context:` line into the story file's Dev notes. Stop if decision 2 is unanswered and lint is over either cap.
- Style probe: run `claude --version`. With `"outputStyle": "Concise"` set in a throwaway home's settings, confirm that `/output-style` lists `Concise` in that client. Record the version in Dev notes.
  - The style was verified present in 2.1.280.
  - The Linux qualification round recorded 2.1.278 (`docs/compatibility.md:199-200`).

## Step 3 — Wire the variant to the Concise style

- **`bin/harness`**
  - Beside `harness_output_styles()` (line 439), add `BUILTIN_OUTPUT_STYLES = {"concise": "Concise"}`, with a one-line comment saying it selects Claude Code's own style by name and copies no text.
  - Change `voice_output_style` (line 461) to return the file-backed style first, then the built-in one.
  - Keep built-ins out of `harness_output_styles()` itself. `strip_claude_settings` removes every name that function returns when the journal is unrecorded (line 553), and a user's own `Concise` must survive an uninstall that predates the journal.
  - Update the docstring at lines 440-446, which calls the file directory "the whole registry".
- **Codex:** no code change. `render_codex_agents` already writes the selected stance body (lines 1024-1025), and the presentation append stays tied to `scannable` (lines 1026-1028).
- **`claude/OWNERSHIP.json`** `output_style` and **`docs/settings-ownership.md:11-17`:** a variant mapped to a Claude Code built-in style (today only `concise`) installs that style by name. Journal ownership is unchanged.
- **`tests/test_voice_output_style.py`**
  - `EXPECTED` gains `"concise": "Concise"`.
  - `test_the_style_name_is_read_from_the_style_file` checks only file-backed styles.
  - `RuntimeAgreementTests` has a false premise under `concise`: Claude installs a style, but Codex gets no presentation file. Restate it as "Codex appends the Scannable presentation exactly when the variant is `scannable`", and add a test that the Codex text under `concise` contains the stance body.
  - Add preservation tests: a user's own `Concise` survives a sync at `off`, and survives `strip_claude_settings(live, TEMPLATE, harness.UNRECORDED)`.
- **`tests/test_voice_stance.py`**
  - Four variants.
  - `LONGEST_VARIANT` set to the final line count of `concise.md`.
  - Assert shape phrases on whitespace-normalised text: "no tables" in answer-card and concise, "at most one table" in scannable, "Concise wins" in concise.
- **`tests/test_native_acceptance_stance_switch.py:74`:** the fake sync maps only `scannable`. Add `concise` → `Concise` so the fixture matches a real sync.

## Step 4 — Remove the competing templates

- **`primitives/rules/voice-and-format.md`:** replace lines 3-4 with the draft below. `tests/test_voice_stance.py:93-98` needs 6 lines or fewer, the phrase "subagent brief", and no "Scannable".
- **`policy/hooks/brief-guard.py:49-50`** `BOUND` becomes:
  `"\n\nReturn at most 400 words: the result in your first sentence, then only the findings that change a decision, in plain sentences or short bullets with no section labels. Write anything longer to a file and return its path, not its contents."`
  Keep the "Return at most 400 words" prefix so `WORD_CAP_RE` still matches. Mirror the change in `tests/test_brief_budget.py:34`, and run `tests.test_brief_guard` for the parity assertion.
- **`primitives/rules/transcript-hygiene.md:8-9`:** "Start with the verdict; thinking summaries stay." becomes "Shape the reply by the `voice` stance; thinking summaries stay."
- **`primitives/skills/transcript-hygiene/SKILL.md:44`:** "Start with the verdict; the reader does not need the machinery." becomes "Shape the reply by the `voice` stance; the reader does not need the machinery."
- **`primitives/rules/decisions-and-plans.md:3-6`:** replace with the draft below, still 4 lines.
- **`primitives/workflows/research.md:33-36`**, aligned to the Brief shape:
  "Report as a brief: two or three sentences of bottom line, then three to five findings with the numbers behind them and what they mean for the reader. Link the rest: end with the scratchpad file paths the band workers wrote and the worker ids `harness role status` will show, one per line. An isolated `gatherer` writes nothing itself: save its returned detail to a scratchpad file yourself before you synthesize."
- **`primitives/workflows/build.md:36-37`**, aligned to the Report shape:
  "Report the outcome in one sentence with the pull request URL, then at most five bullets on what the reader must know: a decision taken on their behalf, a step left unfinished, a test that had to be skipped. Give the gate result in one line, and its failing output in full if it failed."
- **Generated copies:** run `python3 bin/harness generate` and commit the regenerated `claude/commands/research.md` and `build.md`. Never edit those two files by hand.
- **`primitives/skills/plan-authoring/SKILL.md`, "Rationale relocated from the resident rules":**
  - Under `### Voice and output format`, put a marked replacement note first, then the current rationale (drafts below).
  - Keep the plan-files, editor-repaint and posts-in-your-name paragraphs. In the plan-files paragraph, change "verdict-first sections, bolded lead-ins" to "the selected voice".
  - Under `### Presenting decisions`, add a dated amendment line rather than rewriting the paragraph.
  - Paraphrase Anthropic's point about prompt formatting and link the docs page. Do not quote it: outside-library review rates Anthropic docs as inspiration only for verbatim text.

## Step 5 — Rewrite answer-card and scannable in plain prose

- Rewrite `primitives/stances/voice/answer-card.md` and `primitives/stances/voice/scannable.md` from the drafts below. The contracts do not change.
- Rewrite `primitives/presentation/scannable.md` (served as `claude/output-styles/scannable.md`) as prose with fewer bold labels, and delete "A causal chain is an arrow list" from rule 3 (line 25). Keep all of the following:
  - the `name: Scannable` frontmatter, which `harness_output_styles` reads;
  - every `BANNED_OPENERS` entry and `BANNED_CLOSER` (`tests/test_rule_detectors.py:375-379`);
  - the phrase "at most one table".
- Do not add `keep-coding-instructions` here. That is the separate bug (decision 3).
- `scripts/native_acceptance.py:1110-1126` looks for "no tables" or "at most one table" in the resolved voice text. Both phrases must survive.

## Step 6 — Two concise-gated detectors

- **Gate:** `_VOICE_CONCISE = ("voice", ("concise",))` next to `_VOICE_ON` (`rule-detectors.py:385`). Both detectors use rule `voice-and-format` and event `assistant-final`, and report hits with `hit(event, tool_use_id=False)`, like `second_table`.
- **`voice/scaffold-leak`**
  - One hit per final message.
  - Scan the lines of `_unmarked(text)` that sit outside fences (`_fenced_lines` shows the fence rule).
  - A label is a line that, after an optional list marker, heading marks and bold or italic, starts with one of: What changed, What you need to know, What you need to do, Still open, Verification, Why, Catch or The catch, Alternatives. It must be followed by a colon, a closing emphasis, or the end of the line.
  - Also flag Fixed, Partially fixed, Not fixed or Unverified when used as a label, meaning bold-wrapped or line-leading with a colon.
  - Backticked or quoted mentions do not count.
- **`voice/heading-first`:** one hit when the first non-blank line of the final text matches `^\s{0,3}#{1,6}\s`.
- **`tests/test_rule_detectors.py`**
  - Add a hitting case and a clean case per id to `CASES`.
  - Set the corpus `STANCES` (line 23) to `voice: concise`, which turns every voice detector on.
  - Add `StanceTests` asserting that both new detectors stay silent under `scannable`, `answer-card` and `off`.
- **Corpus:** add sessions in `tests/fixtures/detector-corpus/build_sessions.py` with `fire`/`near` labels in `labels.yaml`, following `voice-openers.jsonl` (line 150). `scripts/detector_corpus.py` scores without gates (lines 38-45), so existing rows that contain the scaffold must be labelled as positives for `voice/scaffold-leak`.
- **Published detector counts:** seventeen becomes nineteen in `product.json:177`, `README.md:80`, `docs/field-scan.md:166` and `docs/caught-in-the-act.md:79`. Also update `tests/test_doc_figures_derive_from_code.py:91` (11 becomes 13) and `scripts/detector_corpus.py:5` ("eleven" becomes "thirteen").
- **`docs/usage.md:775-776`:** add a row for each new detector id with its one-line meaning.

## Step 7 — Attribution and listings

- Run the `licensing-review` skill for the three sources. Pin each to the upstream commit read at build time, and check whether `openai/codex` has a `NOTICE` file at that commit. If it does, its content goes into `THIRD_PARTY_NOTICES` (Apache-2.0 §4(d)).
- **`THIRD_PARTY_NOTICES.md`:** add a section in the design-loop style (draft below).
- **`THIRD_PARTY_NOTICES`:** add the MIT notices for openai/openai-cookbook and garrytan/gstack with their copyright lines, and the Apache-2.0 text for openai/codex.
- **`third-party.json`:** append one component per source with these fields:
  - `name`, `version` (the commit SHA), `source`;
  - `artifact_url` (the raw file at that SHA) and `sha256` of that file;
  - `license`, `rightsholder`, `modifications`;
  - `runtime_dependencies: []`, `notice: "THIRD_PARTY_NOTICES"`, `file: "primitives/stances/voice/concise.md"`.

  Append without reordering, because `tests/test_reconciliation.py:220-223` reads `components[0]`.
- Do not create an `ATTRIBUTION.md` under `primitives/stances/voice/`. Every `.md` file there becomes a selectable variant (`VariantsTests`, `VoiceStanceTests`).
- **Listings:**
  - `product.json:130` and `README.md:63`: "Choose concise, answer-card or scannable. Same content, shaped for how you read." The two lines must match.
  - `README.md:125`: add `concise` to the reply-shape row.
  - `docs/preferences.md:52`: add `concise` to the `voice` row. Keep the default `scannable`.
  - `docs/preferences.md:256-266`: add one sentence on `concise` (six shapes, selects the built-in Concise style on Claude Code, the stance text alone on Codex), and correct "the only variant that carries presentation material" to cover the built-in style.
  - `docs/preferences.md:296-297`: `voice-and-format.md` no longer hard-wires the Scannable template, so update that sentence.
- **`changelog.d/<N>.added.md`:** "Added a `concise` voice variant. It picks each reply's shape by what the reply is for — a one-line done message, a short answer, a report, a decision, a brief or a deep dive — and holds every reply to seven rules. On Claude Code it also selects the built-in Concise output style, available from Claude Code <verified version>; Codex receives the same stance text through AGENTS.md. The default voice is unchanged. The What-changed reply template no longer appears in the always-loaded rules, and two new detectors count template labels and heading-first replies under this voice."
- **Budget:** apply decision 2 in `bin/harness:173-180`, and in `docs/how-it-works.md:119` if the token cap moves. Keep the `#430` and docs citation that `tests/test_harness.py:427-431` requires. If `cost_bench.py static --check` reports growth above 5%, add a `benchmarks/allow.json` entry with `harness_version`, `est_tokens` and a reason (`docs/benchmarks.md:30`). Do not run `static --write` mid-cycle; that happens at release.

## Step 8 — Gates, sync check and follow-ups

- **Gates:** run the commands `.github/workflows/ci.yml` runs, in this order:
  - `python3 bin/harness lint`
  - `python3 scripts/smoke_tier.py --skip credentials`
  - `python3 scripts/detector_corpus.py --floor 0.9`
  - `python3 -m unittest discover -s tests -v`
  - `python3 scripts/cost_bench.py static --check`
  - `python3 scripts/bmad_issue_sync.py audit`
  - a `bin/harness sync --dry-run` against `config.example.json` in a throwaway `HOME`.
- **Concise sync check:**
  ```sh
  export HOME="$(mktemp -d)"
  mkdir -p "$HOME/.config/agent-harness"
  printf '{"stances":{"voice":"concise"}}' > "$HOME/.config/agent-harness/config.json"
  python3 bin/harness sync --dry-run
  ```
  Look for `outputStyle` `Concise` in the output. Whether the dry run prints the settings value and the `AGENTS.md` body was not verified during planning. If it prints neither, run the same commands without `--dry-run` (the home is disposable), then `grep outputStyle "$HOME/.claude/settings.json"` and `grep -c "Voice: concise" "$HOME/.codex/AGENTS.md"`.
- **Follow-up issues:** file with `bmad_issue_sync.py new`; build none of them here.
  - **Story:** "Rewrite the always-loaded rules in plain language". Fewer bold labels, and positive examples over bans. It is expected to give back always-loaded lines.
  - **Bug:** "Scannable output style drops Claude Code's coding instructions". `claude/output-styles/scannable.md` lacks `keep-coding-instructions: true`, and `scannable` is the default voice. Skip this one if step 1 already filed it.
  - **Spike:** "Licence review of the humanizer skill for drafts". The repository is MIT, but its pattern list derives from a CC BY-SA page, and whether copied text carries share-alike terms is unresolved.
- Open the pull request with `Closes #N` and the generated-with line.

## After merge, outside the repository

- The reviewer switches their own configuration to `concise` (`bin/harness config set stances.voice concise`), runs `bin/harness sync`, and starts a new session.
- The reviewer schedules a weekly re-run of their private reply-history index and compares shape mix and reply length against its baseline. Decision 1 waits on that measure. The index and its outputs stay out of this repository.

## Draft: the concise stance

```markdown
# Voice: concise

Write each reply for a reader who will act on it, and let the shape of the answer match the shape
of the problem: pick the shape by what the reply is for, and keep it as short as that shape
allows. On Claude Code the built-in Concise output style is active too; where the two differ,
Concise wins.

A done message is one line, with the link or identifier the reader needs. An answer puts the
answer in its first sentence and ends within three, with a caveat only if it changes what the
reader would do. A report gives the outcome in one sentence, then at most five bullets that
change what the reader does next; the detail stays in the pull request or a file, and if the
explanation outgrows the change, cut the explanation. A decision opens with the question and your
recommendation, then numbered options, one line each with its honest case, so the reader can
answer by number. A brief, for research, review or status, gives two or three sentences of
bottom line, three to five findings with their numbers, and what they mean for the reader, then
links the rest. Go deep only when the reader asks for depth or is deciding a design, and then
lead with a summary and use headers that state conclusions. A draft in the user's name is the
draft, then at most two lines of notes, under any personal voice profile.

Whatever the shape, the first sentence is the result, the answer, or your question, and anything
the reader must do or decide is in the first two lines. Use plain words: no coined terms,
internal IDs or file paths unless the reader will act on them, and give an issue number its
title. Add structure only when it is real: bullets for parallel items, headers only in a long
answer, no tables unless asked, and never an empty section. Skip the ritual: no status labels
unless you are reporting a fix, no recap, no narration of your steps, and no caveat or
alternatives unless there is one. After the answer, post nothing that does not change it; a
background task finishing is not news. Errors, failing output, security warnings and
confirmations of destructive actions keep their full detail.

A done message: "Merged #214, Fix the login redirect loop." A report that leads with the point:
"auth.ts:47 returns undefined when the session cookie expires, so users see a white screen. The
fix is a null check and a redirect to /login." Not: "I've identified a potential issue in the
authentication flow that may cause problems under certain conditions."
```

Where each borrowed piece comes from:

- "let the shape of the answer match the shape of the problem" is from the Codex CLI prompt (Apache-2.0).
- The tiered limits (one line, up to three sentences, at most five bullets) adapt the cookbook's `output_verbosity_spec` (MIT).
- "If the explanation outgrows the change, cut the explanation" and the good/bad example pair are adapted from gstack's voice directive (MIT).

If decision 2 goes to the alternative, drop the last paragraph and merge the shapes into one 5-line paragraph.

## Drafts: the edited rules, voices and notices

`primitives/rules/voice-and-format.md`:

```markdown
# Voice and output format

- **Every subagent brief carries its output shape**, since a subagent inherits no voice; the
  `brief-guard` hook appends one to a brief that states no return bound.
- **Deliverables and posts in the user's name honor any personal voice profile first**, then use the
  `voice` stance for layout; never imitate incidental typos. See `plan-authoring`.
```

`primitives/rules/decisions-and-plans.md`, first bullet:

```markdown
- **No chooser widget for substantive decisions.** Flag the ask in the reply's first two lines; the
  numbered decision block may still close the message: each question stated unambiguously, the
  assessment, a recommendation with reasoning, the alternatives with their honest case. Batch
  them; choosers suit trivial forks whose labels carry full meaning.
```

`primitives/stances/voice/answer-card.md`:

```markdown
# Voice: answer card

Treat each reply as a decision, not a summary; where this and the output style differ, this wins.
When a file, plan or artifact holds the reasoning, link it once and do not argue it again.

Put the answer in the first line. Then say why, then the catch, then the alternatives with their
honest case, then what you need from the reader. Keep it to about 150 words and use no tables,
since they wrap unreadably on a narrow screen. Report status in the literal words Fixed, Partially
fixed, Not fixed or Unverified.
```

`primitives/stances/voice/scannable.md`:

```markdown
# Voice: scannable

The Scannable output style governs the main conversation; its text is in
`primitives/presentation/scannable.md`, and it does not reach subagents. When you relay what a
subagent found, rewrite it to that contract: the verdict first, action items under one heading,
paragraphs of at most three sentences, at most one table, and status in the literal words Fixed,
Partially fixed, Not fixed or Unverified.
```

`plan-authoring` SKILL.md, the opening of `### Voice and output format`:

```markdown
*Replaced on <merge date> by #N.* The paragraphs that stood here described the Scannable style's
What changed template and status words as the contract for relays and subagent briefs. The
`voice` stance now owns reply shape and the `brief-guard` hook appends the subagent return shape;
the earlier text is in this file's git history.

The selected `voice` variant governs the main conversation. On Claude Code, `concise` and
`scannable` also set an output style, which reaches only the main conversation and its forks;
other subagents run their own system prompt and inherit no voice. So a relayed report is
rewritten in the selected voice's shape, a finding that does not change what the reader does is
cut, and every subagent brief carries its return shape.

The voice files are written in plain prose with few bold labels because a prompt's formatting
tends to carry into the reply; see Anthropic's prompting guidance on controlling response format
(<link>).
```

The amendment line under `### Presenting decisions`:

```markdown
*Amended on <merge date> by #N:* the block may still close the message, but the reply's first two
lines say that a decision is waiting.
```

`THIRD_PARTY_NOTICES.md` section:

```markdown
## concise voice stance — adapted wording (Apache-2.0, MIT)

`primitives/stances/voice/concise.md` adapts short passages from three sources: from
[openai/codex](https://github.com/openai/codex) (Apache-2.0, commit <sha>), the Codex CLI
prompt's "let the shape of the answer match the shape of the problem"; from
[openai/openai-cookbook](https://github.com/openai/openai-cookbook) (MIT, commit <sha>), the tiered
length limits of `output_verbosity_spec` in the GPT-5.1 and GPT-5.2 prompting guides; and from
[garrytan/gstack](https://github.com/garrytan/gstack) (MIT, commit <sha>), the bounded closer and a
good/bad example pair from its voice directive. Modifications: reworded, shortened and merged into
six reply shapes and seven rules. Upstream licence texts are in `THIRD_PARTY_NOTICES`. Claude
Code's built-in Concise style is selected by name; none of its text is included.
```

## Evidence and verification

- **Line budget:** counted per file during planning. `claude/CLAUDE.md` has 10 lines, the rules 112, and the longest stance variants 77, for 199 in total. The token total was not measured.
- **Style registry:** it is file-driven (`bin/harness:439-464`), so a built-in style needs its own map. The unrecorded-journal strip removes every name the registry returns (`bin/harness:553`).
- **Default voice:** it is `scannable` (`config.example.json:19`, `tests/test_voice_stance.py:61-64`). That is why the missing `keep-coding-instructions` affects default installs, not only people who pick Scannable.
- **Detectors:**
  - Gates are declared per detector (`policy/hooks/rule-detectors.py:384-406`).
  - The corpus runs under a fixed `STANCES` (`tests/test_rule_detectors.py:23`) and is scored without gates (`scripts/detector_corpus.py:38-45`).
  - Detector counts are published and tested (`tests/test_doc_figures_derive_from_code.py:77-107`).
- **CI:** the gates are in `.github/workflows/ci.yml:23-70`.
- **Not verified:**
  - what `sync --dry-run` prints for `outputStyle` and `AGENTS.md`;
  - whether Concise exists in 2.1.278;
  - whether `outputStyle` applies in bridge and Agent SDK sessions.

## Deferred, and why

- **`/review` report format** (`primitives/workflows/review.md:28`) **and the design-loop judge's "score and verdict first"** (`references/judge.md:40`) were not in this change's list. They go to the plain-language follow-up.
- **The word caps on subagent returns** in `transcript-hygiene.md` and `brief-guard` stay in words, because the cap detector parses word counts. The no-words budget rule applies to replies, not returns.
- **Codex `model_verbosity`** was ruled out of scope by the reviewer.
- **Changing the default voice** waits on decision 1 and the weekly measure.
