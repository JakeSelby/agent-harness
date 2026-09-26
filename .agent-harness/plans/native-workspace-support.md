# Native workspace support from `.code-workspace` files

> **Verdict.** Makes the `.code-workspace` files in one configured folder the only definition of which repositories belong together, so a Claude or Codex session opened in any member folder gets the other members' paths and instructions. `citizen workspace open` passes members as `--add-dir`, and a new SessionStart policy hook supplies what no surface loads natively: desktop chats before a relaunch, and Codex, which ignores `AGENTS.md` in added folders.
> **Effort** about 2 days, two PRs, inside the 0.14.0 release · **Risk** medium — past the 10,000-character hook cap, desktop and Codex rely on the agent reading a bundle file · **Blast radius** session start-up while `workspaces_dir` is set; nothing while it is unset

> **Changed this round.** Milestone v0.14.0, shipping in the 0.14.0 release · decisions 1-3 take the recommendations · the 0.14.0 manual test plan gains the step 7 checks.

## At a glance

- **Outcome** — A session opened in any member folder, on the CLI, VS Code, the desktop app or Codex, knows its workspace's other folders and follows their instructions.
- **Approach** — Work out folder → workspace from the files at run time; launchers pass `--add-dir`; one hook fills the gaps and skips members the parent process already loads.
- **Touches** — This repository only: `bin/harness`, new `lib/harness_core/workspaces.py` and `policy/hooks/workspace-session.py`, hook registration, `claude/OWNERSHIP.json`, docs, `product.json`, FR-61; about 14 files over two PRs.
- **New deps** — None; the JSONC reader is about 30 lines of stdlib, spiked against six real workspace files.
- **Not in scope** — Writing `additionalDirectories` into settings; a stored map; path-scoped rules; the existing start-up block's own overflow risk (Deferred).
- **Exit test** — In a synthetic three-folder workspace, a headless root session answers each member's codeword, and one launched with the members as `--add-dir` shows the hook skipping them.
- **Open question** — None; the four decisions are settled and recorded in the addendum.

## System design

```text
*workspaces_dir ── .code-workspace files ─┐
*overrides file ── folder → workspace ────┼─▶ *resolver
HARNESS_WORKSPACE ── set by open ─────────┘      │ cwd → members
                  ┌──────────────────────────────┴───────┐
                  ▼                                      ▼
*citizen workspace list | open            *SessionStart hook (own entry)
                  │ --add-dir per member                 │ members not in argv
                  ▼                                      ▼
Claude Code ── CLAUDE.md, rules (*env var) ─▶ agent ◀── paths, instructions
Codex ──────── its own cwd's AGENTS.md ─────▶ agent     or a *bundle file
```

`*` = new or changed. VS Code and a relaunched desktop chat also pass members as `--add-dir`, so the hook finds them in the parent's arguments and skips them.

## Steps

1. **File the two stories** — `bmad-create-epics-and-stories` (update intent) under AH-E002 (#116), then `scripts/bmad_issue_sync.py new --parent 116 --milestone v0.14.0` for each.
   *Exit:* both issues are in `_bmad-output/issue-map.json` and `bmad_issue_sync.py audit` reports 0 findings.
2. **[Resolver and JSONC reader](#step-2--resolver-and-jsonc-reader)** — new `lib/harness_core/workspaces.py`: parse, map, resolve a cwd with decision 2's precedence.
   *Exit:* `python3 -m unittest tests.test_workspaces` passes, covering `//` inside strings, trailing commas, relative paths, subfolders, worktrees and ambiguity.
3. **[Config key, `list` and `open`](#step-3--config-key-list-and-open)** — `bin/harness`: `workspaces_dir` in `coerce_config_value`; `cmd_workspace` gains `list` and `open [--codex] [--dry-run]`.
   *Exit:* `open demo --dry-run` prints `claude` in the first folder with one `--add-dir` per other folder, and `--codex` prints `codex -C … --add-dir …`.
4. **PR 1 through `/build`** — `docs/workspaces.md` (map, overrides, `list`, `open`), FR-61 via `bmad-prd` update intent, `product.json` and changelog lines.
   *Exit:* the Gate block and every required check are green on PR 1, and its CodeRabbit review is worked through.
5. **[SessionStart hook](#step-5--sessionstart-hook)** — new `policy/hooks/workspace-session.py` with its own hook entry on both runtimes, so it has its own 10,000-character budget.
   *Exit:* `tests/test_workspace_session_hook.py` passes, including a fake parent process whose arguments carry `--add-dir`.
6. **[Own the env variable](#step-6--own-the-env-variable)** — `claude/OWNERSHIP.json` and the native-apply path, following the native telemetry precedent.
   *Exit:* tests show an identical hand-set value adopted silently, a different one left and reported, and removal on unset only when held.
7. **[Headless end-to-end check](#step-7--headless-end-to-end-check)** — a synthetic workspace, the worktree's hook registered through `--settings`.
   *Exit:* a root session answers both members' codewords; launched with the members as `--add-dir`, the hook lists them as loaded natively.
8. **PR 2 through `/build`, then `/land` both** — hook docs and a per-surface list in `docs/workspaces.md`, the spine's FR-61 binding via `bmad-architecture` update intent; step 7's checks join the 0.14.0 manual test plan.
   *Exit:* after `sync` and `config set workspaces_dir`, a new desktop chat in a single-workspace folder names its members and asks for a folder on first use.

## Decisions for the reviewer

**None — approve to proceed.** Decisions 1-3 took the recommendation and 4 is v0.14.0; the record is under Decisions taken in the addendum.

## Risks

- **The agent does not read the bundle file** — step 7 checks it headless; if it fails, switch to the index-only delivery before PR 2 opens.
- **Codex hooks are untrusted on this machine** — a `codex exec` probe got no harness start-up context; accepting hook trust once is the maintainer's step, and the new entry asks again after `sync`.
- **The 0.14.0 tag now waits on both PRs** — no qualification round has started; if PR 2 stalls, ship PR 1 in 0.14.0 and move story B to v0.15.0.

---

# Addendum

Everything the implementing agent needs and the reviewer does not. Nothing above the rule is repeated here.

## Skills, in order

`/build` runs step 1 with `bmad-create-epics-and-stories` (update intent) and `scripts/bmad_issue_sync.py new`, then implements each story with `bmad-build`, the delivery story as its spec. Step 4 amends FR-61 with `bmad-prd` (update intent); step 8 amends the spine with `bmad-architecture` (update intent). Review is `/build` step 6's CodeRabbit loop; merging is `/land`. This plan file is committed in PR 1.

- **Filing** — `python3 scripts/bmad_issue_sync.py new --title T --kind story --body-file F --parent 116 --milestone v0.14.0` from the implementation worktree. If `new` reports a failed reservation, run `reserve --issue N --kind story --parent 116`, then confirm the sub-issue link on #116.
- **Story A** — workspace map, `workspaces_dir`, `workspace list` and `workspace open` (steps 2-4).
- **Story B** — the workspace SessionStart hook, its registration, the env variable's ownership and the desktop grant (steps 5-8).
- Distill this addendum into each story's Design and Dev notes at build time.
- **Release.** Both stories ship in 0.14.0, whose qualification round (#563) has not started. Each PR adds a changelog line under Unreleased and a `product.json` feature line. In step 8, append step 7's checks, plus one desktop chat and one Codex session, as a workspace section of the 0.14.0 manual test plan draft (`.agent-harness/plans/v0-14-0-manual-testing.md`, untracked in the live checkout), and name it in the handoff.

## Decisions taken

Reviewed on 2026-09-26: the maintainer answered decision 4 and approved the rest as recommended.

1. **Past the hook cap, members' instructions go inline when the block fits, else in one bundle file** under the harness state folder, whose path is inlined with the member list and an instruction to read it first. Claude Code's own overflow swaps in a path it never asks the agent to read. Rejected: index only, each member read on first work there, which relies on the agent remembering.
2. **An override beats first position:** launch facts, then override, then single membership, then a unique first position, else list candidates. An explicit choice never loses to a heuristic, and an override of none opts a folder out. This refines the earlier accepted order, which put first position before the override; 8 of the 10 shared folders here need one either way.
3. **Desktop grants happen on first use of a member folder**, not at chat start: outside bypass mode each grant is a prompt, 11 in the largest workspace here, and the hook already supplies the instructions.
4. **Milestone v0.14.0**, shipping in the 0.14.0 release.

## Step 2 — Resolver and JSONC reader

- **Location.** `lib/harness_core/workspaces.py`, used by `bin/harness` and loaded by the hook by resolved path, as `policy/hooks/intent-overlap.py:24` loads `intents.py`.
- **Reader.** One pass that copies string literals intact (honouring `\` escapes), drops `//` to end of line and `/* … */`, then removes a comma followed only by whitespace before `}` or `]`; then `json.loads`. The spike's version passed a self-test with `//` inside a URL and an escaped quote.
- **Members.** `folders[].path`, resolved against the workspace file's directory after `expanduser`, then `realpath` (on macOS `/tmp` is `/private/tmp`). Skip `uri`-only folders. A workspace's name is its file stem. Keep folder order; report members that do not exist and skip them.
- **Overrides.** Optional `<workspaces_dir>/overrides.json`, read with the same reader: `{"<folder>": "<workspace name>" | null}`, folder paths resolved against `workspaces_dir`. `null` means attach nothing. An override naming an unknown workspace is reported by `list` and ignored.
- **Which member a cwd is.** The longest member path that equals the cwd or is its ancestor on a path boundary. If none matches and the cwd is a linked git worktree, retry with its main checkout (`git rev-parse --path-format=absolute --git-common-dir`, parent directory), because task worktrees live outside the permanent repositories.
- **Precedence**, per decision 2. Launch facts first: `HARNESS_WORKSPACE` in the environment, set by `open`; then a candidate whose other members are exactly the parent's `--add-dir` folders, which is how a VS Code window reveals the workspace it opened. Then override, single membership, unique first position. Otherwise return the candidates and attach nothing.
- **Cost.** No cache and no stored map; parse every file on each call. Six files parsed in well under the hook's 4-second budget.
- **Tests** in `tests/test_workspaces.py`: the reader's edge cases, relative and `~` paths, a `uri` folder, a missing folder, a subfolder cwd, a worktree cwd, each precedence rule, `null` override, an unknown override, and a folder first in two workspaces.

## Step 3 — Config key, `list` and `open`

- **Config.** Add `workspaces_dir` to `coerce_config_value` (`bin/harness:3431-3500`), modelled on `primitive_roots` (`:3477-3484`): an absolute path after `expanduser`. Update the refusal message that lists accepted keys (`:3497-3500`). Unset means the feature is off everywhere.
- **Parser and usage.** Replace "only `create` is supported" (`bin/harness:2945`) with `create | list | open`; update the usage line (`:26`) and the subparser (`:5512-5518`): `name` becomes optional for `list`, and `open` takes `--codex`, `--dry-run` and passthrough arguments after `--`.
- **`list`.** Per workspace: its members in order, marked missing where absent, and the characters of instructions the hook would supply. Then per shared folder: the workspace it resolves to and the rule that decided, or its candidates. Unknown overrides last. Exit 0; no `workspaces_dir` prints how to set it and exits 1.
- **`open <name>`.** Read `<workspaces_dir>/<name>.code-workspace`; the first existing member is the working directory and every other existing member gets `--add-dir <path>`. Set `HARNESS_WORKSPACE=<name>`, `chdir`, then `os.execvpe`. Passthrough arguments go before the `--add-dir` flags, because Claude's `--add-dir` is variadic and reads a trailing prompt as another folder (seen in the spike). `--codex` runs `codex -C <first> --add-dir <each other>`. `--dry-run` prints the shell-quoted command and the environment line instead of running it.
- **Tests** in `tests/test_workspace_cli.py`, under a temporary HOME like `tests/test_native_telemetry.py:221`: config validation, `list` output, both `--dry-run` forms, passthrough ordering, and a first test for `create`, which has none today.

## Step 5 — SessionStart hook

- **Registration.** `registration()` (`lib/harness_core/lifecycle.py:925-929`) emits a second SessionStart entry per runtime: the same adapter with argument `workspace` and marker `# harness:runtime-sessionstart-workspace`, timeout 10. `main()` routes that entry to `workspace-session` alone; the plain entry keeps `harness-session`. A separate entry gets its own 10,000-character cap, measured per hook in the spike. Check that sync's marker recognition (`bin/harness:591-608`, `reconcile.hook_marker`) and the Codex `hooks.json` writer (`bin/harness:1657-1659`) treat it as owned. Add the id beside `harness-session` in `catalog.HOOK_IDS` and `policy/hooks/manifests.json` so hook switches cover it.
- **Off switch.** Read `workspaces_dir` from the config path `policy/hooks/harness-session.py:296` uses. Unset, or a cwd that resolves to nothing: return `{}`. Candidates but no attachment: one line naming them and the overrides file.
- **Which members to supply.** Drop the session's own folder and missing folders. On Claude Code, a member counts as loaded natively only if all three hold: `CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD=1` in the hook's environment, the member appears as `--add-dir <path>` or `--add-dir=<path>` in the arguments of `CLAUDE_PID` (`ps -o command= -p`; `/proc/<pid>/cmdline` on Linux; compare the realpath and the literal path), and it has a `CLAUDE.md`. A member with only `AGENTS.md` is always supplied, since Claude never loads `AGENTS.md` from an added folder. On Codex (`HARNESS_RUNTIME=codex`) every member is supplied.
- **What is supplied.** Per member: `CLAUDE.md`, else `AGENTS.md`; then `CLAUDE.local.md` and each `.claude/rules/*.md` without `paths:` frontmatter; `@` imports expanded relative to their file, to depth 5, outside code fences. Path-scoped rules are listed by path only.
- **Delivery, decision 1.** Header: the workspace, then each member's path and whether it is loaded natively, supplied here, or missing. If the whole block is at most 9,000 characters, inline it. Otherwise write the instructions to `~/.local/state/agent-harness/workspaces/<name>.md` (temp file, then rename) and inline the header plus: read this file before your first action. The settings template gains the allow rule `Read(~/.local/state/agent-harness/workspaces/**)`; allow rules merge as a set (`bin/harness:583-587`).
- **Desktop, decision 3.** When `CLAUDE_CODE_ENTRYPOINT` is `claude-desktop`, add: before first reading or editing in a member folder, ask the app for it with the desktop folder-grant tool (`request_directory`, a deferred tool loaded through tool search); the app passes granted folders as `--add-dir` from the chat's next launch.
- **Workers.** Claude role workers launch with `--setting-sources ""` (`adapters/claude-code/worker.py:54-55`), so no user hook runs in them. Confirm the Codex worker loads no user `hooks.json` either; if it does, return `{}` when the worker's environment marker is present.
- **Budget.** Stay inside 4 seconds, as `harness-session.py:25` does; a failure returns `{}` and never blocks a session.
- **Tests** in `tests/test_workspace_session_hook.py`, running the adapter as a subprocess as `tests/test_handoff.py:94-108` does. A real fake parent: spawn `python3 -c "import time; time.sleep(30)" --add-dir <member>` and pass its pid as `CLAUDE_PID`. Cover: unset, single workspace, ambiguous, native skip, the `AGENTS.md`-only exception, variable unset (no skip), desktop entrypoint, Codex runtime, inline and bundle delivery. Extend `tests/test_hook_switches.py` and the reconciliation tests for the second entry on both runtimes and a re-run sync with no change.

## Step 6 — Own the env variable

- `claude/OWNERSHIP.json`: add `workspaces.env_keys: ["CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD"]`, owned while `workspaces_dir` is set, and widen the `never_touch` entry to "env except native_telemetry.env_keys and workspaces.env_keys" (`:30-34`).
- Reuse `apply_native_claude` (`bin/harness:745-786`) rather than a second path. Its rules already fit: a key holding exactly what the harness would write is taken over silently with a journal record; a different hand-set value is left and reported (`:774`); on unset, a key is removed only when the journal holds it.
- Consequence to document: once adopted, the maintainer's hand-set `=1` is removed when `workspaces_dir` is unset. That is ownership working, and `docs/workspaces.md` says so.
- **Tests** extend the `tests/test_native_telemetry.py` pattern: set, identical pre-existing, different pre-existing, unset while held, unset while not held.

## Step 7 — Headless end-to-end check

- Build `<tmp>/ws/` with `root/`, `member-a/CLAUDE.md` (codeword A), `member-b/AGENTS.md` (codeword B, no `CLAUDE.md`) and `demo.code-workspace` with relative paths, a comment and a trailing comma.
- Keep the real HOME for the CLI's login; point the hook at a temporary config through the override the tests use (`HARNESS_HOME`), with `workspaces_dir` set to `<tmp>/ws`.
- Register the worktree's adapter through a temporary `--settings` file holding only the new SessionStart entry. Pass the prompt before any `--add-dir`.
- Run 1, from `root/`: `claude -p "Which codewords do your instructions contain? Answer them, or NONE." --model haiku --settings <file>`. Expect A and B.
- Run 2: add `--add-dir member-a --add-dir member-b`. Expect A and B again, and the hook's header marking member-a loaded natively and member-b supplied.
- Run 3, bundle path: raise member-a's file past 9,000 characters with filler, codeword at the end, and allow the Read tool. Expect A, and the transcript showing the bundle file read.
- Codex, after the merge and once hook trust is accepted: `codex exec -C root` should answer A and B through the hook.

## Evidence and verification

Spiked on 2026-09-26 with Claude Code CLI 2.1.280 and Codex CLI 0.155.0-alpha.16.4, on the maintainer's Mac.

- **Workspace files.** Six local files parsed with the stdlib reader: 29 folders, 10 in several workspaces. First position settles 2 of the 10, one folder is first in two workspaces, and 7 are first in none. One workspace names a folder that no longer exists.
- **Member instructions.** 10 of 28 existing member folders have `CLAUDE.md` (3 are symlinks); none is `AGENTS.md`-only; 2 contain `@` imports; none has `.claude/rules/`.
- **SessionStart input** carries `session_id`, `transcript_path`, `cwd`, `hook_event_name` and `source`, and no added directories.
- **Hook environment** carries `CLAUDE_PID`, `CLAUDE_CODE_ENTRYPOINT` (`sdk-cli` headless, `claude-desktop` in the app), `CLAUDE_PROJECT_DIR` and the env variable; `ps -o command= -p $CLAUDE_PID` shows every `--add-dir` argument.
- **Native loading.** A headless `claude -p … --add-dir <member>` with the variable set answered the member's `CLAUDE.md` codeword.
- **Hook cap.** The hooks doc caps a hook's `additionalContext` at 10,000 characters; past it, Claude Code writes the text to a file and passes a path and a 2,000-character preview without asking the agent to read it. Two SessionStart hooks of about 8,900 characters each both reached the model inline, so the cap is per hook.
- **This repository's start-up block** measured 8,953 characters in the planning session.
- **Codex and added folders.** `codex exec --add-dir <member>` answered NONE for the member's `AGENTS.md` codeword; the positive control, `AGENTS.md` in its own working directory, answered it.
- **Codex SessionStart.** Recorded evidence shows its context reaching the model (`compatibility/evidence/codex-cli-macos-0.11.1.json`). A `codex exec` probe here got none; the user `hooks.json` has no trust record in Codex's config.
- **Desktop grant mid-chat.** The folder became a working directory without relaunching the chat's process. Neither its `CLAUDE.md` nor its rule appeared, at the grant or on reading a file in it. Whether the grant fires DirectoryAdded is unverified, since no hook was registered to see it.

## Context and background

Accepted before this plan: the map is worked out at run time from `workspaces_dir` plus an optional overrides file, and no map is stored; a folder in several workspaces attaches the one where it comes first, then an override, else nothing; in the desktop app Claude requests member folders through the folder-grant tool, and nothing writes `additionalDirectories` into settings. Desktop sidebar groups hold only a name and an order. `permissions.additionalDirectories` grants file access only. Folders added with `--add-dir`, `/add-dir` or the SDK load skills, commands and agents, and with the env variable set also `CLAUDE.md`, `.claude/rules/` and `CLAUDE.local.md`. The VS Code extension passes its other workspace folders to the SDK, which turns them into `--add-dir`. No hook can add a working directory.

## Deferred, and why

- **The start-up block's own overflow.** 8,953 of 10,000 characters here, and task data alone may reach 12,000 (`policy/hooks/harness-session.py:322`). Past the cap the whole block becomes a path and a preview. It predates this work and deserves its own issue.
- **Codex without hooks.** `open --codex` could pass instructions through a Codex configuration override instead of the hook; unverified, and plain `codex` sessions would still need the hook.
- **Path-scoped rules** load natively only when matching files are touched; the hook lists them by path.
- **An overrides command** such as `workspace pin`; the file is hand-edited for now.
- **A doctor line**; `workspace list` covers the diagnosis.
- **Start-up cost** is accepted, not reduced: about 9k tokens of instructions in the largest workspace here. `workspace list` prints each workspace's size, and an override of none opts a folder out.
