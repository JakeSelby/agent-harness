# Testing stance: required

**"Build feature X" means: build it, make every existing test pass, and write tests covering every
new capability** — logic-bearing functions, methods and services, API endpoints (request and
response shape, auth enforcement, error cases), UI components with behaviour, hooks, utilities, and
every bug fix with a regression test. Run the affected module's suite and fix every failure,
pre-existing ones in files you touched included. Follow the repo's co-location convention, read a
neighbouring test first, and admit no exception — not speed, not "simple", not "later".
Whether the suite is any good is a separate question: `code-quality-instruments`.
