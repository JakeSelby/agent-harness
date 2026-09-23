# Native qualification runbook

How an operator runs `scripts/native_acceptance.py` against a real client. What must be proved,
and what the evidence record must contain, is in [what is supported](compatibility.md); this page
is only the mechanics of a run.

## Before a run

- The checkout must be clean. Native evidence names a source commit, and the runner refuses a
  dirty tree rather than record a commit that does not describe what ran.
- The client must be installed and logged in for the account you intend to qualify, and
  `<client> --version` must report a version the runner can parse.
- Run `python3 scripts/smoke_tier.py` first. It spends no model turn, and the deterministic
  faults it catches — an unreachable credential, a drifted projection, a runner that misreads a
  transcript — are the ones that otherwise surface part-way through a paid round. It is advisory
  and never qualification; see [releasing](releasing.md#freeze-the-qualification-branch).
- Every probe is one short headless turn and costs money. Use the cheapest model the client
  offers; `--model` defaults to it.

## Provisioning the round

A round needs a frozen clone of the commit it qualifies, somewhere to keep each target's record,
and — only if it will run `bmad-workflow` — a BMad framework checkout. Provision all three once,
outside the checkout:

```sh
python3 scripts/qualification_provision.py --out ../round-v<version> --bmad
python3 scripts/qualification_provision.py --out ../round-v<version> --print-env
```

The clone is taken from this repository's own object store and is refused unless the tree is
clean and the clone lands on the commit named. `--bmad` is the only step that reaches the
network, and it runs the pinned installer from [bmad](bmad.md). Without it, `bmad-workflow`
reports itself `unverified` rather than skipping: nothing was read, so nothing is claimed.

## Running

```sh
python3 scripts/native_acceptance.py --client claude-code-cli-macos --dry-plan
python3 scripts/native_acceptance.py --client claude-code-cli-macos --cases cost-posture \
    --model haiku --out ../native-cost-posture.json
python3 scripts/qualification_round.py --round ../round-v<version> --plan
python3 scripts/qualification_round.py --round ../round-v<version> \
    --targets claude-code-cli-macos,codex-cli-macos --model haiku
```

`--dry-plan` launches no client and names, per case, what a run would do. `--keep-home` leaves
each disposable home in place for debugging; without it every home is removed at the end of its
case. Write `--out` outside the checkout: the runner refuses to run against a dirty tree, and an
evidence file is added to the tree deliberately, after review.

`scripts/qualification_round.py` drives a provisioned round: the smoke tier once, then the
runner per target from the frozen clone, one record each. It decides nothing and stops for
nothing — a round collects every target's defects before any of them is fixed, which is the rule
in [releasing](releasing.md#freeze-the-qualification-branch) — and it exits non-zero unless every
case of every target passed.

## Which class executes, and which class reads

A round carries two capability classes per target, not one. The **execution class**, `standard`
by default, is the worker that runs the scripted cases, reads their JSON and writes the findings
file. The **assessment class**, `strong` by default and a floor rather than a preference, is the
reader that assesses the round's observations, which [what is supported](compatibility.md)
requires of a reviewer. Both are written into the evidence record as `tier_routing` and into the
round's `round.json`, so the record says which class produced an observation and which class read
it.

```sh
python3 scripts/qualification_round.py --round ../round-v<version> \
    --execution-class light --execution-class codex-cli-macos=standard
```

A bare class moves every target; `TARGET=CLASS` moves the one it names, so a Codex target can be
executed at a different class from a Claude Code one in the same round. Later arguments win.

The classes are resolved through the target runtime's `adapters/<runtime>/bindings.json`, the
same table `harness tiers` checks; a personal `tiers.<runtime>` override in a user configuration
is not applied, because a round runs from a frozen clone. Two refusals, both before any client is
launched:

- An assessment class weaker than `strong`. A cheaper tier may execute the cases; it does not
  assess them.
- A cheap execution class that resolves to the assessment class's own model — because the
  adapter maps both classes to one identifier, because it spells one model two ways, or because
  it does not map the cheap class at all and an unmapped class resolves upward. The executor
  would then be the only reader of the evidence it produced. The two identifiers are compared
  the way the usage ledger compares them, so a date-stamped id and a bare alias of the same
  model are one model; the comparison errs towards refusing, and two models an operator means
  to be different are written as two ids neither of which is a prefix of the other.
- An assessment class the adapter does not map while the execution class is mapped: the reader
  would inherit whatever model the session happens to be running, which is no named reader.

An unmapped *execution* class beside a mapped assessor — what asking for a class stronger than
the assessor's does — is disclosed rather than guessed at: that worker inherits the session
model and the record carries the note saying so.

The routing is written to the durable per-case log before the first case runs and to
`round.json` before the smoke tier, so a killed round still records which classes were running.
`--from-progress` refuses a log whose cases were executed under a different routing rather than
merging them: a record built from two routings cannot say which class produced an observation.

The saving this buys is the issue's estimate, not a measurement: workers ran 0.7×–1.8× their 82K
output budget, so four targets cost 230K–590K output tokens per round, most of it authoring
rather than judgement (#338). It is worth nothing without the scripted cases (#336): dropping the
class on a worker that is still hand-driving the cases buys worse observations and more retries.

## Client surfaces

Each surface names the environment variable that moves its whole configuration home, which is
what makes a disposable home possible: `CLAUDE_CONFIG_DIR` for Claude Code, `CODEX_HOME` for
Codex. The Codex surface is driven headlessly with `codex exec --json` and read from the rollout
files under its home, following `adapters/codex/worker.py` and
[usage](usage.md#codex-rollouts).

**No Codex round has been driven through this runner.** Until one has been, its reading is
derived from those files rather than observed, so every Codex verdict is reported `unverified`
with the observation kept, exactly as an unobserved case is. On the first round that runs a Codex
target, qualify it by hand as well, compare the two, and pass `--home-confirmed` only once they
agree. Record that comparison with the round's observations.

## Credentials

The runner copies no credential and prints none. Each case runs in a disposable `HOME` that
inherits, **by name only**, the authentication variables this machine already uses — the
`ANTHROPIC_*` variables, the Bedrock and Vertex switches, `AWS_PROFILE` and the AWS region,
credentials-file and session variables (`AWS_ACCESS_KEY_ID`, `AWS_SESSION_TOKEN` and the
secret-key variable beside them), `GOOGLE_APPLICATION_CREDENTIALS` and `OPENAI_API_KEY`. `AUTH_PASSTHROUGH`
in the runner is the full list. A container that holds its credentials as environment variables
and has no profile to fall back on is qualified by exporting them to the wrapper that invokes the
runner; nothing else reaches the client.

The AWS file pointers are re-anchored at the operator's real home, because the probe's `HOME` is
disposable and an unset pointer hangs the provider lookup. On macOS each disposable home gets its
own default keychain first, so a client that stores an item raises no system dialog.

## Reading the result

A case is `passed` only when the runner observed the behaviour itself. An assertion that did not
hold is `failed`; anything the runner could not observe — no transcript, a turn that did not
finish, a model that declined the turn on its own judgement — is `unverified` with its reason,
never a pass. Every observation is redacted for home paths, host names and credential shapes
before it is written. The exit status is 0 only when every selected case passed.
