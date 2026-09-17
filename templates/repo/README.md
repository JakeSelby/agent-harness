# Repo starter

What a repository needs so agents work well in it, given that the global rules already load
from the harness.

1. Copy `AGENTS.md` to the repo root and fill in the placeholders. Delete sections that do not
   apply; do not restate global rules.
2. `ln -s AGENTS.md CLAUDE.md` so Claude Code and Codex read the same file. On Windows, write
   `@AGENTS.md` as the only line of `CLAUDE.md` instead.
3. Copy `settings.json` to `.claude/settings.json` and replace the allow rules with the exact
   commands agents run in this repo.
4. Put file-kind-specific rules in `.claude/rules/<topic>.md` with a `paths:` frontmatter glob.
5. Run the quality gate once on a clean tree and paste its final line into `AGENTS.md`, so any
   later failure is attributable.
6. Install the commit hook, which refuses a subject that is not a Conventional Commit:

   ```sh
   install -m 755 hooks/commit-msg .git/hooks/commit-msg
   ```

   It reads the `commits` stance, so `off` and `as-you-go` pass everything, and it warns rather
   than fails when `conventional-attributed` finds no `Co-Authored-By:` trailer. A git hook sees
   the final message whatever wrote it, which a hook parsing `git commit` off the command line
   does not.

The deny rules in `settings.json` stop agents reading files they should never load. Keep the
secrets entries in every repo, and prune the generated-directory entries to what this repo
actually generates, adding any it generates that the template does not list.

If the repo already has `.cursor/rules/` or another agent's instruction files, migrate the
generic content into the harness with the `harness-authoring` skill and leave only repo facts
here. Two copies of a rule drift.
