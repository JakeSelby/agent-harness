# Verification gates

**Run the gates locally. Never open a PR on unverified work.** A PR that fails lint burns a
reviewer's attention on nothing.

- **Find the exact commands CI runs** — the workflow file is the source of truth, not the
  README — and run those, not an approximation.
- **Record the expected clean-tree output** in the repo's agent instructions the first time you
  run the gates: the exact "all checks passed" line, the test count, the known benign warning.
  Then any deviation is yours, and you can tell a pre-existing failure from one you caused.
- **Format is checked, not applied, in most CI.** Run the formatter before the gate, not after
  CI tells you.
- **Code to the floor.** If the project tests a minimum language or dependency version, use no
  API newer than that floor, or raise the floor in the same PR.
- **Every file in the diff traces to the declared issue.** One concern per PR; split before
  requesting review, not after.
- **Never bypass pre-commit hooks.** Never `git commit --no-verify`.
- **Tests hitting real services** are marked and excluded by default; prefer recorded fixtures
  so a test runs in CI without credentials. Adding a new live-only test is a regression.
- **Test auth anonymously**, with redirects not followed, and assert the status code directly.
  A test that follows redirects to a login page and asserts 200 proves nothing.
