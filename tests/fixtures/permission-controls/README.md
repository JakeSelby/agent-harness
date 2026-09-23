# Recorded turns for the permission-controls case

Three real Claude Code CLI results, cut from headless runs on 2026-09-22 with client 2.1.280 on
macOS, model `claude-haiku-4-5`. Each was produced in an empty temporary directory with

```sh
claude -p "<prompt>" --model haiku --output-format json --permission-mode <mode>
```

and trimmed to the keys the runner reads, with the session and tool-use identifiers replaced by
fixture names. Nothing else was edited; no value here was typed by hand.

| File | Mode | Prompt | What the run did |
|---|---|---|---|
| `manual-denied.json` | `default` | write `./permission-probe.txt` with Bash | the client refused the Bash call and recorded it in `permission_denials`; the file was absent |
| `bypass-completed.json` | `bypassPermissions` | the same prompt | the file was created and the client answered `DONE` |
| `bypass-declined.json` | `bypassPermissions` | reply without using any tool | no tool ran, `permission_denials` was empty and the file was absent |

`bypass-declined.json` stands in for the decline `bypass_verdict` exists to classify — a model
that declines the acknowledged-bypass turn on its own judgement, seen about one run in five
during 0.11.0 qualification (#309). Four probe runs on the day these were recorded all completed,
so rather than wait for the intermittent decline the same result shape was recorded from a turn
that ran no tool: the runner sees exactly what a decline leaves behind — the bypass mode in
force, no denial, no sentinel. Replace it with a cut from a genuine decline the first time a live
round produces one.
