# Changelog fragments

One file per change, so branches in flight never edit the same section of `CHANGELOG.md`.
Fragments begin after 0.13.0: entries for 0.13.0 itself are written under `## [Unreleased]` in
`CHANGELOG.md` as before, and a branch cut while `VERSION` is older than 0.13.0 may still satisfy
the lint that way.

- **Name:** `<issue-or-pr>.<kind>.md`, where the number is the delivery issue (or the pull request
  when there is no issue) and the kind is `added`, `changed`, `removed` or `fixed`. Anything else
  in this directory, apart from this file, fails `bin/harness lint`.
- **Body:** the entry itself, in the changelog's prose style: full sentences, what changed and
  why. Wrap it as you would in `CHANGELOG.md`; the bullet and the trailing `(#N)` are added at
  assembly when the body does not already end with it.
- **Waiver:** a change under `bin/`, `lib/`, `adapters/`, `primitives/`, `policy/`, `docs/` or
  `scripts/` with nothing to announce adds `<issue-or-pr>.none.md` whose body says, in at least
  20 characters, why. It is a file rather than a pull request body line so that a local lint, a
  pull request run and a merge queue run all see the same answer. Waivers are never rendered.

At release time, `python3 scripts/release_notes.py --changelog <version>` inserts a
`## [<version>] — <date>` section under an empty `## [Unreleased]`, with Added, Changed, Removed
and Fixed blocks in that order and entries in ascending number within each, then deletes the
fragments it consumed. `--dry-run` prints the result and changes nothing. It refuses an empty
set, a malformed name, a version that already has a section, and an Unreleased section that still
holds hand-written entries.
