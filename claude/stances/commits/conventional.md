# Commits stance: Conventional Commits, gated pushes

- **Conventional Commits for every commit**, in every repo: `type(scope): summary`, with
  `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `ci` as the usual types.
- **Before pushing, run the repo's quality gate on `HEAD`** in the exact checkout you are about
  to push. The gate is whatever the repo's agent instructions name; if they name nothing, run
  what CI runs.
- **Never push to a default branch directly.** Branch first, open a PR, merge through it. A
  repo's own instructions may override this for repos without a review gate.
- **No attribution trailers.** Commit messages carry the change, not the tool.
- **`AGENTS.md` and `CLAUDE.md` are one file, symlinked**, so different agents cannot drift.
