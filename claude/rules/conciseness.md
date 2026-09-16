# Comment and doc conciseness

- **Explain a decision once,** in the docstring where the thing is defined or on the user-facing doc
  page. Every other file gets a pointer, not a restatement; a second doc links to the first.
- **Do not narrate what the code already says.** A comment explains a non-obvious *why*.
- **Docstrings match the surrounding style** — read a neighbouring function first. Do not add them
  for a linter that is not running; add them where a user of the public API needs them.
- **Shipped code, tests and docs stand on their own to a stranger.** No planning docs, other repos,
  internal ticket numbers or evaluation notes; public issue and PR numbers are fine.
- **PR descriptions lead with what and why** in bullets plus the issue link; fill every template
  section, delete none, keep each short. Examples: `harness-authoring`.
