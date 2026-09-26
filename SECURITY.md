# Security policy

## What counts as a security issue here

This repository installs files into your home directory and merges keys into your Claude Code
and VS Code settings. Report privately if you find:

- `bin/harness` touching, moving or deleting anything outside the paths recorded in its
  manifest, or outside the keys listed in `claude/OWNERSHIP.json`.
- `claude/hooks/allow-readonly-bash.py` approving a command that can write, delete, exfiltrate
  or execute untrusted content.
- A credential, token or private hostname anywhere in the tree or its history.
- A rule or skill whose text could be used to make an agent bypass a permission gate.

## Supported versions

Only `main` and the latest tagged release receive fixes.

## How to report

Use GitHub's private vulnerability reporting for this repository (the **Security** tab →
**Report a vulnerability**). Do not open a public issue for anything that could be exploited.
You will get an acknowledgement within a week and a fix or a decision within thirty days.

## First lines of defence already in place

`bin/harness lint` runs in CI, in a pre-commit hook in the checkout, and by hand. It carries no
list of real values: it matches personal-data shapes and secret patterns everywhere in the tree
with no file exempt, and reads the maintainer's own terms from an untracked file outside the
repository. GitHub secret scanning with push protection is enabled. The read-only hook is
tested against a corpus of write-capable commands (`tests/test_allow_readonly_bash.py`) and
never returns a deny, so a bug in it can only fall through to the normal permission prompt.
`claude/hooks/grade-bash.py` is graded the same way: a false low grade is a missed prompt, never
worse than the native permission flow, and a false high grade costs one extra prompt or, where no
prompt exists, one re-run: with the confirm marker in `bypassPermissions`, and in `auto` after the
user replies `approve <code>` as the whole message. That approval is recorded only from a prompt
that is nothing but approve tokens, so text an agent can place in a notification turn cannot carry
one, and it covers one run of one command in one session for thirty minutes. The store is closed to
the agent's file-tool writes, and a Bash command that names it grades 3.

That store is an interlock, not containment. Any process running as the user can forge any local
state, this store and the governance policy files included; a `python3 -c` that builds the path at
run time is not graded, and the hook does not try to grade arbitrary code. The approval channel
stops a cooperating agent from running an irreversible command by mistake. It does not hold back a
hostile one: that is the sandbox's job, and an agent you do not trust belongs in one.
The stop gate runs a repository's own `## Gate` commands only in a folder trusted through
Claude Code's dialog or `harness trust`, so a clone cannot run code on the first Stop. The
`bypass` permission posture requires an explicit acknowledgement in the config file and is
documented as unsuitable for any machine that touches regulated data.
