# Commits stance: Conventional Commits, gated pushes, attributed

- **Conventional Commits for every commit**, in every repo: `type(scope): summary`, with
  `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `ci` as the usual types.
- **Before pushing, run the repo's quality gate on `HEAD`** in the exact checkout you are about
  to push. The gate is whatever the repo's agent instructions name; if they name nothing, run
  what CI runs.
- **Never push to a default branch directly.** Branch first, open a PR, merge through it. A
  repo's own instructions may override this for repos without a review gate.
- **Keep the agent's attribution trailer.** When the tool you run in provides a
  `Co-Authored-By` line for commits and a generated-with line for PR descriptions, leave them
  in place; they are how a reader knows an agent wrote it.
- **`AGENTS.md` and `CLAUDE.md` are one file, symlinked**, so different agents cannot drift.
  Check which side is the real file before editing, and never let a script assume.
