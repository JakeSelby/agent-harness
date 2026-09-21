# Native qualification runbook

How an operator runs `scripts/native_acceptance.py` against a real client. What must be proved,
and what the evidence record must contain, is in [what is supported](compatibility.md); this page
is only the mechanics of a run.

## Before a run

- The checkout must be clean. Native evidence names a source commit, and the runner refuses a
  dirty tree rather than record a commit that does not describe what ran.
- The client must be installed and logged in for the account you intend to qualify, and
  `<client> --version` must report a version the runner can parse.
- Every probe is one short headless turn and costs money. Use the cheapest model the client
  offers; `--model` defaults to it.

## Running

```sh
python3 scripts/native_acceptance.py --client claude-code-cli-macos --dry-plan
python3 scripts/native_acceptance.py --client claude-code-cli-macos --cases cost-posture \
    --model haiku --out ../native-cost-posture.json
```

`--dry-plan` launches no client and names, per case, what a run would do or that the case is not
automated yet. `--keep-home` leaves each disposable home in place for debugging; without it every
home is removed at the end of its case. Write `--out` outside the checkout: the runner refuses to
run against a dirty tree, and an evidence file is added to the tree deliberately, after review.

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
