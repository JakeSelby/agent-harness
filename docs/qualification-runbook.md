# Native qualification runbook

How an operator runs `scripts/native_acceptance.py` against a real client. What must be proved,
and what the evidence record must contain, is in [what is supported](compatibility.md); this page
is only the mechanics of a run.

## Before a run

- The checkout must be clean. Native evidence names a source commit, and the runner refuses a
  dirty tree rather than record a commit that does not describe what ran.
- The client must be installed and logged in for the account you intend to qualify, and
  `<client> --version` must report a version the runner can parse. [Target hosts](#target-hosts)
  says where each target's client comes from and how it logs in.
- Run `python3 scripts/smoke_tier.py --targets <ids>` first, naming the targets the round will
  run; with no `--targets` it checks every CLI target this host can run and reports the others
  as skipped. It spends no model turn, and the deterministic faults it catches — a client off
  `PATH`, a missing Codex login or Docker daemon, an unreachable credential, a drifted
  projection, a runner that misreads a transcript — are the ones that otherwise surface part-way
  through a paid round. It is advisory
  and never qualification; see [releasing](releasing.md#freeze-the-qualification-branch).
- Every probe is one short headless turn and costs money. Use the cheapest model the client
  offers; `--model` defaults to it.

## Target hosts

Which binary, login and host each required target uses is the contract in
[what is supported](compatibility.md#where-each-target-runs-and-what-it-needs). These are the
commands that establish it on the Mac every round has run on, in order, before anything is paid
for.

1. **Codex on `PATH`.** Link the ChatGPT desktop app's bundled binary and read its version, which
   the app moves forward on its own:

   ```sh
   ln -sf /Applications/ChatGPT.app/Contents/Resources/codex ~/.local/bin/codex
   codex --version
   ```

2. **Codex login.** `codex login` with the ChatGPT account the round runs under writes
   `~/.codex/auth.json`. A Codex round spends that ChatGPT plan's usage rather than API credit,
   so confirm the plan has headroom for the round, or budget a usage purchase, before starting
   rather than finding the limit mid-case.
3. **Claude Code credential.** Export an Anthropic API key, a cloud profile, or a subscription
   token from `claude setup-token`; the runner passes each by name — see [credentials](#credentials).
4. **Docker daemon**, for either Linux target. Start Docker Desktop and confirm `docker info`
   answers, then build the target image once per pinned client version:

   ```sh
   docker build -f scripts/linux-target.Dockerfile -t agent-harness-linux-target .
   ```

   It builds natively as linux/arm64 on Apple silicon, which is what the 0.11.x Linux records
   describe. Change `CODEX_VERSION` and `CLAUDE_CODE_VERSION` with `--build-arg` when a round
   pins newer clients.
5. **Check before paying.** The smoke tier's `credentials` check reads the targets you name and
   fails at once, naming the target, when a client is off `PATH`, the Codex login is missing or
   the Docker daemon does not answer:

   ```sh
   python3 scripts/smoke_tier.py --only credentials \
       --targets claude-code-cli-macos,codex-cli-macos,claude-code-cli-linux,codex-cli-linux
   ```

   A Linux target checks only the daemon from the Mac; its client and login are checked by the
   same command inside the container.

A Linux target is never run from the Mac. The runner refuses a target whose platform is not
the host's, because the record would carry one platform's name on another's outcome, and
`scripts/qualification_round.py` reports such a target as not run here and leaves it out of the
round rather than failing it (#708). It runs inside the container instead, against the round's
frozen clone mounted read-only and its records directory mounted writable, both from
[provisioning](#provisioning-the-round). On a Claude subscription, pass the token from
`claude setup-token` as `CLAUDE_CODE_OAUTH_TOKEN` (#672); this is the sequence that produced the
0.13.0 `claude-code-cli-linux` records:

```sh
docker run --rm -it -e CLAUDE_CODE_OAUTH_TOKEN \
    -v "$PWD/../round-v<version>/clone:/frozen:ro" \
    -v "$PWD/../round-v<version>/records:/records" \
    agent-harness-linux-target
# inside the container
git -c safe.directory='*' clone -q /frozen harness && cd harness
python3 scripts/smoke_tier.py --only credentials --targets claude-code-cli-linux
python3 scripts/native_acceptance.py --client claude-code-cli-linux --model sonnet \
    --out /records/claude-code-cli-linux.json
```

`sonnet` is the `standard` class's routed model in `adapters/claude-code/bindings.json`; the
runner started by hand has no round to route it, so it is named, and the record reads
`model_source: routing` because it matches. The API-key and cloud-profile forms, and a Codex
target:

```sh
docker run --rm -it -e ANTHROPIC_API_KEY \
    -v "$PWD/../round-v<version>/clone:/frozen:ro" \
    -v "$PWD/../round-v<version>/records:/records" \
    agent-harness-linux-target
# or, for Claude Code on a cloud profile instead of an API key
docker run --rm -it \
    -e CLAUDE_CODE_USE_BEDROCK -e AWS_PROFILE -e AWS_REGION \
    -e AWS_CONFIG_FILE=/aws/config -e AWS_SHARED_CREDENTIALS_FILE=/aws/credentials \
    -v "$HOME/.aws:/aws:ro" \
    -v "$PWD/../round-v<version>/clone:/frozen:ro" \
    -v "$PWD/../round-v<version>/records:/records" \
    agent-harness-linux-target
# inside the container
git -c safe.directory='*' clone -q /frozen harness && cd harness
codex login --device-auth
python3 scripts/smoke_tier.py --only credentials --targets codex-cli-linux,claude-code-cli-linux
python3 scripts/native_acceptance.py --client codex-cli-linux --model <cheapest> \
    --codex-session-login --out /records/codex-cli-linux.json
```

The writable clone exists because the runner refuses a tree it cannot prove clean, and the
`safe.directory` override is needed because the mount is owned by another user. `-e` names each
credential variable without its value. The profile form mounts the AWS directory read-only at a
path that is not the container user's home and points the file variables at it, because the
runner hands its disposable home only those pointers. `codex login --device-auth` gives the container its own
ChatGPT session, so no host login file is copied into it; whether the 0.11.x Linux rounds logged
in this way or used a copy of the host's login is not recorded.

**The runner's disposable `CODEX_HOME` carries the session login only under
`--codex-session-login`.** With the flag, each case's home gets an `auth.json` symlink to the
operator's login, read from `CODEX_HOME` or `~/.codex` before the disposable home replaces it, the
way `adapters/codex/worker.py` links it into a worker home. It is a link, never a copy, so a kept
home holds no credential and a token the client refreshes lands in the one login file. Every
string in that file is redacted from each observation, the progress log and the record. Without
the flag a runner-driven Codex case has no login. The flag is refused for a Claude Code target and
when no `auth.json` exists, before any case runs. Every Codex record to date was produced by hand;
the first runner-driven round is compared against a hand run as [client surfaces](#client-surfaces)
describes.

## Provisioning the round

A round needs a frozen clone of the commit it qualifies and somewhere to keep each target's
record. Provision both once, outside the checkout:

```sh
python3 scripts/qualification_provision.py --out ../round-v<version>
```

The clone is taken from this repository's own object store and is refused unless the tree is
clean and the clone lands on the commit named. No required case runs a framework workflow, so no
case needs anything else. On a minor release, `--bmad` also installs a BMad framework checkout
with the pinned installer from [bmad](bmad.md) for the optional integration suite in
[releasing](releasing.md#source-and-qualification), which is run by hand; it is the only step that
reaches the network, and `--print-env` prints the export that suite's operator needs.

## Running

```sh
python3 scripts/native_acceptance.py --client claude-code-cli-macos --dry-plan
python3 scripts/native_acceptance.py --client claude-code-cli-macos --cases cost-posture \
    --model haiku --out ../native-cost-posture.json
python3 scripts/qualification_round.py --round ../round-v<version> --plan
python3 scripts/qualification_round.py --round ../round-v<version> \
    --targets claude-code-cli-macos,claude-code-cli-linux
```

A round given no `--model` passes each target the model its execution class routes to, and each
evidence record and per-case row carries it as `model_run`, with the record's routing reading
`model_source: routing`; an operator's `--model` still wins, recorded as `model_source: operator`
beside the routed model (#721). On a Mac the Linux target in that example is reported as not run
here, and runs in the container from [target hosts](#target-hosts).

`--dry-plan` launches no client and names, per case, what a run would do. `--keep-home` leaves
each disposable home in place for debugging; without it every home is removed at the end of its
case. Write `--out` outside the checkout: the runner refuses to run against a dirty tree, and an
evidence file is added to the tree deliberately, after review.

`scripts/qualification_round.py` drives a provisioned round: the smoke tier once, then the
runner per target from the frozen clone, one record each. A smoke tier that fails or times out
stops the round before any target runs, and `round.json` records the tier's result, why the round
stopped and the targets it did not run; `--skip-smoke` records the tier as `skipped` and runs every
target. Past the tier it decides nothing and stops for nothing — a round collects every target's
defects before any of them is fixed, which is the rule in
[releasing](releasing.md#freeze-the-qualification-branch) — and it exits non-zero unless the tier
passed or was skipped and every case of every target passed. A target's earlier record is moved
aside before its runner is launched, so a runner that exits before writing one reports every case
`unverified` rather than the previous round's passes, and a target that runs past the round
deadline is recorded and carried rather than raised — the targets after it still run.

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
same table `citizen tiers` checks; a personal `tiers.<runtime>` override in a user configuration
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

A round started again with the same arguments at the same commit resumes from that log: a case
whose latest line is `passed` or `failed` is not run again, and the runner says so on stderr for
each one. A failure is kept so its evidence stays intact; an `unverified` case, which observed
nothing, and a case the kill interrupted both run again. The log's header carries the source
commit, client version and routing, so a verdict never skips a case for a different candidate. A
resume without `--home-confirmed` on a surface that needs it keeps no verdict, since it could only
read `unverified` itself, so every case runs again. To
retry a failed case at the same commit, give the round a fresh `--progress` log.

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

The runner copies no credential and prints none; the one it links, a Codex session login under
`--codex-session-login`, is described in [target hosts](#target-hosts). Each case runs in a disposable `HOME` that
inherits, **by name only**, the authentication variables this machine already uses — the
`ANTHROPIC_*` variables, `CLAUDE_CODE_OAUTH_TOKEN`, the Bedrock and Vertex switches, `AWS_PROFILE` and the AWS region,
credentials-file and session variables (`AWS_ACCESS_KEY_ID`, `AWS_SESSION_TOKEN` and the
secret-key variable beside them), `GOOGLE_APPLICATION_CREDENTIALS` and `OPENAI_API_KEY`. `AUTH_PASSTHROUGH`
in the runner is the full list. A container that holds its credentials as environment variables
and has no profile to fall back on is qualified by exporting them to the wrapper that invokes the
runner; nothing else reaches the client.

An interactive `claude login` never reaches the disposable home. On a Claude subscription with no
API key, run `claude setup-token` once — it mints a long-lived token for that subscription — and
export it as `CLAUDE_CODE_OAUTH_TOKEN` in the shell that invokes the runner, so the round spends
the subscription rather than on-demand credit. Export it for the round only; never write it to a file.

The AWS file pointers are re-anchored at the operator's real home, because the probe's `HOME` is
disposable and an unset pointer hangs the provider lookup. On macOS each disposable home gets its
own default keychain first, so a client that stores an item raises no system dialog.

## Reading the result

A case is `passed` only when the runner observed the behaviour itself. An assertion that did not
hold is `failed`; anything the runner could not observe — no transcript, a turn that did not
finish, a model that declined the turn on its own judgement — is `unverified` with its reason,
never a pass. Every observation is redacted for home paths, host names and credential shapes
before it is written. The exit status is 0 only when every selected case passed.
