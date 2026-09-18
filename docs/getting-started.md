# Getting started

A walk from nothing installed to a first useful session, for someone who has not used a coding
agent before. If you already run Claude Code daily, the README's install block is all you need.

## What this is, and what it is not

The harness is **configuration for Claude Code**. It is not an AI, it does not talk to a model,
and it does not give you access to one. Claude Code is Anthropic's command-line agent; this
repository decides how it behaves once you have it — how it writes answers, when it asks before
doing something, what it checks before claiming a thing works.

Installing it changes `claude`. You still run `claude`.

## Before you start

| You need | Why | How to check |
| --- | --- | --- |
| A Claude account on a plan that includes Claude Code, or API billing set up | The harness configures the tool; it does not pay for it or provide access | Sign in at [claude.ai](https://claude.ai) and confirm your plan |
| macOS or Linux | `install` uses Homebrew on macOS and falls back to the vendors' installers on Linux | `uname -s` prints `Darwin` or `Linux` |
| `git` | The harness is a git checkout, and staying current means pulling it | `git --version` |
| Python 3.9 or newer | `bin/harness` and all eleven hooks are Python | `python3 --version` |

**Windows is not supported.** `bin/harness install` and `bin/harness sync` both refuse to run
there rather than half-working. Use WSL2 and follow the Linux path inside it; that has not been
tested, so treat it as unsupported too.

Optional, and installed for you on macOS: `gh` (only needed to open pull requests), VS Code, and
Codex. Nothing breaks without them.

## Install

```sh
git clone https://github.com/JakeSelby/agent-harness.git ~/repos/agent-harness
cd ~/repos/agent-harness
bin/harness install
```

On macOS that adds the Homebrew packages, VS Code and its extensions, Claude Code and Codex, then
links the harness into `~/.claude`. On Linux it adds Claude Code and Codex and links; install `gh`
and an editor yourself. It ends with a list of the logins it cannot do for you — run each one it
names.

Then tell it who you are:

```sh
bin/harness init          # asks your name, what you do, and one preference at a time
bin/harness sync          # applies what you answered
```

`init` is the only configuration step. Two of its questions decide most of the rest:

- **How much to explain** — `beginner` makes the agent say what each step and command does and
  define terms as it uses them; `expert` skips fundamentals.
- **What the work is** — `general` turns off the commit, test and licensing ceremony that only
  makes sense when you are shipping software; `software` keeps it.

Everything it asks has a default, and you can change any answer later with
`bin/harness config set stances.testing off`, or by running `init --force` again.

Check it worked:

```sh
bin/harness doctor        # versions, logins, links, and whether anything has drifted
```

## Your first session

Open a terminal, move to a folder with something in it — notes, a spreadsheet, photos, a project —
and start the agent:

```sh
cd ~/some-folder
claude
```

Then type, in plain English. Three that show what changes:

- *"What is in this folder? Group it by what the files are for."* — it reads narrowly rather than
  dumping every file into the conversation, and the answer leads with the verdict.
- *"Rename every screenshot to the date it was taken."* — it proposes the change, and asks before
  anything irreversible. A rename is graded; a `rm -rf` is refused outright in a mode with no
  prompt.
- *"Plan how to sort ten years of tax documents. Don't do it yet."* — you get a one-screen plan
  ending in numbered decisions, and it waits for you to reply `build`.

Type `/context` to see which rules are loaded, and `/hooks` to see what is watching. Ctrl-C twice
leaves.

## What the harness changed about the answers

- **Verdict first.** The outcome is in the first line. Action items are collected under one
  heading rather than scattered through paragraphs.
- **It says when something failed.** A test that did not pass is reported as not passing. "Fixed"
  means verified.
- **It asks before irreversible things** and refuses them outright when there is no way to ask.
- **Plans are one screen** and end in numbered decisions, so you approve or redirect rather than
  reading a document.

## The five commands

Typed with a slash at the start of a message. Four of the five assume you are working on software
in a git repository, and say so before starting rather than failing halfway:

| Command | What it does | Needs a code project |
| --- | --- | --- |
| `/research` | Answers a question by reading in parallel and returning one digest | No |
| `/plan` | Writes a reviewable plan and stops until you approve it | No |
| `/handoff` | Writes down where you got to, for the next session | No |
| `/review` | Reviews changes twice, for scope and for quality | Yes |
| `/build` | Implements an approved plan and opens a pull request | Yes, and a GitHub account |

## What it costs

Every message spends tokens against your plan's rate-limit window, and work that fans out to
several sub-agents at once spends several times as much in the same window. `/research` and
`/build` are the expensive commands.

The `cost` preference is the dial: `frugal` keeps fan-out small, `balanced` is the default, `max`
spends freely for hard problems. Change it with `bin/harness config set cost frugal`.

`bin/harness usage` summarises what your sessions have spent, from a local file. Nothing is sent
anywhere — see [usage.md](usage.md).

## When something looks wrong

```sh
bin/harness doctor        # what is installed, what is logged in, what has drifted
bin/harness diff          # settings changed outside the harness, and templates not yet applied
bin/harness uninstall     # put everything back; your config and the checkout are left alone
```

`uninstall` is a real undo: it removes the links, strips the settings keys the harness owns, and
restores any file it moved aside. Nothing you wrote is touched.

## Where to go next

- [preferences.md](preferences.md) — every preference, what it changes, and the defaults
- [how-it-works.md](how-it-works.md) — the layers, and why each exists
- [sandboxing.md](sandboxing.md) — fencing a long unattended run
- The README's table — every rule, skill, hook and command, with where it lives
