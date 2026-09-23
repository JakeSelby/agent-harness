# Recorded turns for the permission-controls case

Three real Claude Code CLI turns, recorded on 2026-09-22 with client 2.1.280 on macOS, model
`claude-haiku-4-5`. Each ran in an empty temporary directory with

```sh
claude -p "<prompt>" --model haiku --output-format json --permission-mode <mode>
```

and **no `--allowedTools`**, which is how the driver runs its probe turns: an allowed tool is
approved before the posture is consulted, so a pre-approved Bash call would make a denial
impossible under the manual posture.

Each turn is three files, trimmed to what the runner reads and with session and tool-use
identifiers replaced by fixture names. No value here was typed by hand:

- `<name>.json` — the client's own JSON result, including `permission_denials`.
- `<name>.transcript.jsonl` — the turn's user record, carrying the `permissionMode` the client
  itself reported for it.
- `recorded.json` — the sentinel state each run left behind, which is what says whether the write
  happened. It cannot be derived from the result, so it is recorded rather than assumed.

| File | Mode | Prompt | What the run did |
|---|---|---|---|
| `manual-denied.json` | `default` | write `./permission-probe.txt` with Bash | the client refused the Bash call and recorded it in `permission_denials`; the file was absent |
| `bypass-completed.json` | `bypassPermissions` | the same prompt | the file was created and the client answered `DONE` |
| `bypass-declined.json` | `bypassPermissions` | reply without using any tool | no tool ran, `permission_denials` was empty and the file was absent |

`bypass-declined.json` is synthetic in one respect, and it is the one fixture that is: the turn is
real, but its decline was induced. `bypass_verdict` exists to classify a model that declines the
acknowledged-bypass turn on its own judgement, seen about one run in five during 0.11.0
qualification (#309). Six probe runs on the day these were recorded all completed, so rather than
keep spending on an intermittent event the same result shape was recorded from a turn that ran no
tool: what the runner reads is exactly what a decline leaves behind — the bypass mode reported for
the turn, no denial, no sentinel. Replace it with a genuine decline the first time a live round
produces one.
