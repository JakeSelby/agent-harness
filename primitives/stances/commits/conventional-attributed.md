# Commits stance: Conventional Commits, gated pushes, attributed

**Conventional Commits for every commit**, in every repo: `type(scope): summary`. **Before pushing,
run the repo's quality gate on `HEAD`** in the exact checkout you will push — whatever its agent
instructions name, or what CI runs if they name nothing. **Never push to a default branch
directly:** branch, open a PR, merge through it, unless a repo without a review gate says
otherwise. **Keep the tool's `Co-Authored-By` and generated-with lines.** **`AGENTS.md` and
`CLAUDE.md` are one file, symlinked** — check which side is real before editing.
