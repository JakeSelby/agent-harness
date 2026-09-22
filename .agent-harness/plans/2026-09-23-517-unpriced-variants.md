# Unlisted model variants unpriced, not inherited

> `price_key` becomes an exact lookup, after `normalise_model` learns to
> strip a release suffix — a date stamp, `-v1:0`, `@date`. An id the price
> table does not list resolves to `None`, never to its family's rate.
> Effort half a day · Risk low · Blast radius `policy/` only.

## At a glance

- **Outcome** — an unlisted variant is unpriced, not billed at a sibling rate.
- **Approach** — strip the release suffix, then match table keys exactly.
- **Touches** — `pricing.py`, `prices.json`, `docs/usage.md`, the price tests.
- **New deps** — none; stdlib `re`, already imported by `pricing.py`.
- **Not in scope** — a corrected-cost column, price research, ledger rewrite.
- **Exit test** — 3443 real ledger rows price to the same cent afterwards.
- **Open question** — decision 1: exact match, or a declared `prefix` flag.

## System design

```text
ledger id ──▶ *normalise_model ──▶ *price_key
                                      │    │
        usd ◀── rate ◀── in table ────┘    │
        unpriced footer ◀── None ◀─────────┘
```
`*` marks what changes; an unpriced row also drops `harness.usd` in OTLP.

## Steps

1. **Extend `normalise_model`** — `pricing.py:77-93`, strip a release suffix.
   *Exit:* `normalise_model("claude-opus-5-20260401") == "claude-opus-5"`.
2. **Make `price_key` a lookup** — `pricing.py:111-120`, drop the prefix scan.
   *Exit:* `price_for(T, "gpt-5.5-pro")` is `None`; `"gpt-5.5"` still 5.0.
3. **Replay the ledger before and after** — throwaway script, not committed.
   *Exit:* 0 of 3443 rows change `(usd, as_of)`; unpriced count and total equal.
4. **Rewrite `_limitations`** — `prices.json:25-33`, inheritance clause out.
   *Exit:* `grep -c inherits policy/prices.json` returns 0.
5. **Rewrite the resolution bullet** — `docs/usage.md:412-418`.
   *Exit:* `grep -c "longest prefix" docs/usage.md` returns 0.
6. **Add and adjust tests** — `tests/test_usage_prices.py`, five cases below.
   *Exit:* `bin/harness lint` and `python3 -m unittest discover -s tests` green.

## Decisions for the reviewer

**1. Exact match after normalisation, or a `prefix` flag per entry?**
*Recommend* exact — a release suffix is a spelling, and `normalise_model`
already owns spellings; a flag re-opens the hole on every entry that sets it.
*Alternative* the flag, which is what #517's acceptance literally names.

**2. What may follow a listed id and still be the same model?**
*Recommend* a release suffix only: `-20260401`, `-2026-04-01`, `@20260401`,
`-v1:0`. Anything else, including a trailing word, is a different model.
*Alternative* allow a trailing word too — which is the `-pro` case we close.

**3. Does the strip live in `normalise_model`, or in a `price_key` helper?**
*Recommend* `normalise_model` — one notion of "same model" for pricing and
for the parent/subagent join, verified to change no ledger row.
*Alternative* a private helper: smaller radius, two notions to keep aligned.

## Risks

- **An id shape we did not anticipate** falls outside the grammar and goes
  unpriced — the safe direction, but watch the footer count after release.
- **A same-price snapshot with a word suffix** (`gpt-5.6-terra-high`) needs
  listing before it prices; one table entry or a `config.json` override.
- **`normalise_model` also feeds `row_model`'s parent/child join**, so more
  ids now compare equal; re-run the step 3 replay immediately before merge.

---

# Addendum

Facts below were re-verified at `main` `d4cf311` (0.12.0), not the `d884cff`
named in the brief; line numbers are from that checkout.

## Step 1 — Extend `normalise_model`

`pricing.py:77-93` lower-cases, drops a `[...]` suffix, takes the last `/`
segment, then peels alphabetic `<vendor>.` prefixes. Its docstring ends "the
remainder is matched by prefix, so a dated id still reaches its family"
(`pricing.py:83-84`) — that sentence is the behaviour being removed and has
to be rewritten in the same commit.

Add, applied repeatedly until the name stops shrinking:

```python
RELEASE = re.compile(
    r"(?:[-@](?:20\d{6}|20\d{2}-\d{2}-\d{2})"
    r"|-v\d+(?::\d+)?)$")
```

The loop matters: `anthropic.claude-haiku-4-5-20251001-v1:0` needs `-v1:0`
off before the date sits at the end. The date branch is anchored on `20` so
`claude-opus-4-8`, `claude-fable-5-1` and `gpt-5.6-luna` are untouched.

Verified against all four spellings asserted by the existing
`test_a_bedrock_id_and_a_long_context_suffix_reach_the_same_entry`
(`tests/test_usage_prices.py:106-110`), and against
`test_a_dated_id_resolves_to_its_family` and
`test_the_longest_prefix_wins_over_a_shorter_one`. All pass unchanged.

## Step 2 — `price_key` becomes a lookup

```python
def price_key(table, model):
    name = normalise_model(model)
    return name if name in table else ""
```

Signature and contract unchanged: a key, or `""`. `price_for`
(`pricing.py:123-126`) and `row_as_of` (`pricing.py:330`) already handle
`""`, and `bin/harness:3711-3726` does not re-export `price_key`, so no CLI
line changes.

### Design question 2 — every shipped id still prices

All twelve keys in `prices.json:34-101` are already their own normalised
form, so each is an exact hit with no table edit. Verified by running the
proposed normaliser over every key:

- **claude-fable-5-1, claude-fable-5, claude-opus-5** — exact, unchanged.
- **claude-opus-4-8, claude-opus-4-6, claude-sonnet-5** — exact, unchanged.
- **claude-haiku-4-5** — exact; `claude-haiku-4-5-20251001` and
  `anthropic.claude-haiku-4-5-20251001-v1:0` reach it via the release strip.
- **gpt-6-astra, gpt-5.6-sol, gpt-5.6-terra, gpt-5.6-luna, gpt-5.5** — exact;
  the `.` in a `gpt-5.x` id survives because `gpt-5` is not alphabetic and
  the vendor-prefix loop at `pricing.py:88-92` stops there.

`test_every_key_is_already_normalised` (`tests/test_usage_prices.py:81-86`)
is the standing guard for this and passes unchanged.

### Design question 1 alternative — the declared-prefix shape

If decision 1 goes the other way, an entry carries the flag and `price_key`
keeps a prefix scan restricted to flagged keys:

```json
"gpt-5.5": {
  "matches_prefix": true,
  "input": 5.0, "output": 30.0,
  "cache_read": 0.5, "cache_write": 0.0,
  "as_of": "2026-09-21",
  "source": "https://developers.openai.com/..."
}
```

To keep dated ids priced, all twelve entries need the flag — which restores
inheritance everywhere, `gpt-5.5` included. That entry is the issue's own
six-fold example (`prices.json:27-29`), so the flag would re-open the exact
defect it was added to close. Hence the recommendation runs the other way.

## Step 3 — Migration, and how it was checked

**No existing ledger row changes price.** Checked rather than argued: the
shipped module and a patched copy were loaded side by side and
`priced(rows, table)` run over every row of
`~/.local/state/agent-harness/usage.jsonl`.

- **3443 rows read**, 15 distinct ids across `models`, `model`, `by_model`.
- **0 rows** changed `(usd, as_of)`.
- **Unpriced 329 before, 329 after.**
- **Total 26050.116679 USD before and after**, to the full float.

The 15 ids are the seven Claude families, four `gpt` ids, the two aliases
`opus` and `fable` (unpriced before and after), `<synthetic>`, and the dated
and Bedrock Haiku spellings. Nothing in the ledger resolves through a prefix
that is not also an exact key once the release suffix is stripped.

Re-run this replay in the implementing worktree before merge — the ledger
keeps growing, and a newly recorded variant is exactly what would change.

## Design question 3 — what an unlisted variant produces

Take `gpt-5.5-pro`: today priced at `gpt-5.5`'s 5.0/30.0 against a real
30/180, the six-fold case.

- **Row value** — `price_for` returns `None`, `row_cost` returns `None`
  (`pricing.py:271-272`), `priced` yields `(None, "")` (`pricing.py:349`).
  Never `0.0`, which is the discipline stated at `pricing.py:15-16`.
- **`harness usage` footer** — the row joins the count in
  `unpriced: N run(s), unknown model or partial tokens` at
  `bin/harness:4048`, and at `bin/harness:3841` for the role table. The text
  does not change; only N moves.
- **Dollar column** — contributes nothing, as a `partial` row does today.
- **OTLP attribute** — `telemetry.py:351-355` omits both `harness.usd` and
  `harness.price_as_of` when `usd` is `None`. No zero is ever exported.
- **`--json` shape** — there is none to change. `harness usage` has no
  `--json` flag (`bin/harness:4381-4397`); its only machine-readable surface
  is the OTLP export above. Say that in the PR rather than invent one.

## Step 4 — `_limitations`

`prices.json:25-33`. Lines 26-29 carry the clause to delete, `gpt-5.5-pro`
example included. Replacement, same voice, same three beats:

- a model id resolves by exact match after normalisation, which lower-cases,
  drops a cloud vendor prefix, a context-window suffix and a release suffix;
- a variant the file does not name is unpriced, never charged at a sibling's
  rate — an understated figure is worse than an absent one;
- to price one, add an entry here or override it under `prices` in
  `config.json`, which merges field by field (`pricing.py:56-74`).

Keep the long-context paragraph at `prices.json:30-32`; it is still true.

## Step 5 — `docs/usage.md`

Rewrite the **Ids resolve by longest prefix** bullet at `docs/usage.md:412-418`,
heading included. Its closing sentence — "The cost of prefix matching is that
an unlisted variant of a listed family inherits the family's rate even when it
is priced differently" — is the claim that inverts.

The **Unpriced is not free** bullet at `docs/usage.md:444-448` already states
the discipline and gains one clause: an unlisted variant of a listed family
now joins the alias case (`opus`, `fable`) it already names.

## Step 6 — Tests

All in `tests/test_usage_prices.py`, against the invented `TABLE` at lines
37-45 unless a case says otherwise.

1. **An unlisted premium variant is unpriced** —
   `price_for(TABLE, "test-model-pro")` is `None`.
2. **A declared entry still prices through a release suffix** — extend
   `test_a_bedrock_id_and_a_long_context_suffix_reach_the_same_entry` with
   `test-model@20260921` and `test-model-2026-09-21`.
3. **An exact id beats a shorter sibling** — rename
   `test_the_longest_prefix_wins_over_a_shorter_one` (line 103) to say what
   it now proves: `test-model-mini-20260921` reaches `test-model-mini`.
4. **The footer counts the unpriced row** — drive `cmd_usage` through the
   `loud()` helper (lines 56-64) with one `gpt-5.5-pro` row and assert
   `unpriced: 1 run(s)` in the captured output.
5. **Regression for the six-fold case** — against the shipped table,
   `price_for(load_prices({}), "gpt-5.5-pro")` is `None`, named for #517, so
   a future prefix rule cannot quietly restore 5.0 where the provider
   charges 30.0.

Gate, from `CLAUDE.md:21-26`:

```sh
python3 bin/harness lint
python3 -m unittest discover -s tests
```

## Design question 7 — landing copy

`AGENTS.md:64-70`: the `landing-copy` check fails a pull request that
changes `policy/` without touching `product.json`, unless the body carries a
`Landing copy:` line. This corrects a figure the report already prints and
adds no capability, so no `product.json` edit. Exact line for the PR body:

```text
Landing copy: none — this corrects a rate the report
already printed and adds no capability; product.json
says what the harness does, not which prices it knows.
```

## Changelog and release slot

One `### Fixed` entry under Unreleased, naming the behaviour change, so a
reader tracking a month-on-month figure knows why a row went blank. Slotted
to v0.13.0 by the intake
(`roadmap-intake-enterprise-review-2026-09-22.md:141`), which also records it
as explicitly not a 0.12 blocker — "the behaviour is documented, the caveat
is stated, and no shipped price row exercises it today" (line 70).
