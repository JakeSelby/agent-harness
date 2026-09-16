# Verification gates

- **Run the gates locally; never open a PR on unverified work.** Why: `docs/how-it-works.md`.
- **Find the exact commands CI runs** — the workflow file, not the README — and run those.
- **Record the expected clean-tree output** in the repo's agent instructions on the first run.
- **Run the formatter before the gate**; most CI checks format rather than applying it.
- **Code to the floor:** use no API newer than the minimum version tested, or raise it in the PR.
- **Every file in the diff traces to the declared issue.** One concern per PR; split before review.
- **Never bypass pre-commit hooks**, and never `git commit --no-verify`.
- **Mark and exclude live-service tests**; prefer recorded fixtures. A new one is a regression.
- **Test auth anonymously**, with redirects not followed, asserting the status code directly.
