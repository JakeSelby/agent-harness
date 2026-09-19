# Sandboxing

Native sandbox settings are runtime-specific. The Claude configuration examples below do not
configure Codex. Consult [runtime controls](runtime-controls.md) and [compatibility](compatibility.md)
for enforcement gaps before relying on a role or permission boundary.

Permission modes answer "may this run?". They are the wrong question for an agent left alone: by
the time a loop is unattended, nobody is there to answer. Isolation answers a different question —
"what can this reach once it is already running?" — and the operating system enforces the
answer on every child process, whatever the model decided to run.

That makes it a posture, not a rule. How much isolation you want depends on what you are running
and who wrote it, and the two useful settings sit far apart.

## The two shapes

- **The built-in sandbox.** A `sandbox` block in `~/.claude/settings.json` fences Bash commands at
  the OS level: writes confined to the working directory, network denied except an allowlist,
  credential paths and variables denied outright. Every tool keeps working, so it is cheap enough
  to leave on for daily work.
- **A container.** The agent runs inside it, with only the worktree bind-mounted and the host
  config mounted read-only. A harder boundary bought with coarser tooling: no network means no web
  tools, no MCP over the network, no package installs, and no model API unless you allow that one
  host. Right for loops that run while you sleep and for anything parsing untrusted input.

The `sandbox` skill carries the exact keys, the quoted defaults, the `docker run` line and the
failure modes of each. Neither shape isolates branches; `worktree-per-agent` does that, and the two
compose.

## Why the harness writes none of it

`sandbox.*` is not an owned key and not a posture key. It is user-level configuration with a real
blast radius: a sync that widened `allowedDomains` or dropped a `denyRead` entry would quietly undo
a security boundary the user set, and a sync that narrowed one would break their builds with no
error anyone could trace. `OWNERSHIP.json` already covers this case by default — "Everything not
listed as owned is left exactly as found" — so the keys stay yours.

Configure them yourself, in your own settings file or per session with `--settings`. The skill
exists to tell you which keys to write; it does not write them for you.
