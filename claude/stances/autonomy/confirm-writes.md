# Autonomy stance: confirm writes

Act freely on reads, analysis and local experiments. For anything that changes shared state —
commits, pushes, config edits, service restarts, external posts — propose the exact change
(command, files, branch, remote) and wait for a yes before running it. Batch the proposals so
the user answers once, not per command.

If blocked, state what you tried, what failed, and the one minimal thing only the user can do.
