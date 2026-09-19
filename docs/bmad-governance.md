# BMad repository governance

This file is the single policy source loaded by agent-harness's BMad workflow customizations.
The repository instructions remain authoritative when they are stricter.

- GitHub issues are the delivery authority. Create the issue before changing tracked files, use
  one delivery issue per PR, and keep one concern in each PR.
- Run implementation in a managed worktree. Run BMad's installed scripts from the shared checkout
  and pass the implementation worktree as an explicit input.
- Public BMad artifacts live under `_bmad-output`; never redirect this repository's artifacts to a
  private or central planning repository.
- Publish synthesized evidence and decisions, not raw conversations, tool logs, memory exports,
  secrets, private paths or irrelevant personal information.
- Label claims as implemented, validated, proposed, historical or unknown. Do not treat generated
  configuration, green unit tests or a prior release as proof of current native-client behavior.
- Every managed work item has one immutable typed BMad ID and a bidirectional GitHub mapping.
  Reparenting never changes the ID; reconstructed history must say that it is reconstructed.
- Preserve issue and repository history. Add amendments rather than rewriting dated evidence, and
  do not replace original issue prose when maintaining traceability metadata.
- Before review, run `python3 bin/harness lint`, `python3 -m unittest discover -s tests`, and
  `bin/harness generate --check`. Never bypass hooks.
- Ordinary issues and PRs use the repository's native voice without generated framework footers.
  README and planning documentation may credit BMad explicitly.
