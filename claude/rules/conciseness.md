# Comment and doc conciseness

## Explain a decision once

Pick the single most natural home for a design rationale — usually the module or class
docstring where the thing is defined, or the user-facing doc page for anything a user needs.
Every other file that touches the concept gets a short pointer back, not a restatement.

```python
# Bad — restates the full rationale in a consuming file
# We chunk at 999 rather than the documented 10,000 limit because early testing
# suggested the endpoint became unreliable above 1,000 records, and because ...

# Good — one line, points at the canonical explanation
# Chunked per `batch_size`; see the class docstring for the API's limits.
```

If a second doc explains the same concept as a first, it links to it.

## Don't narrate what the code already says

Comments explain a non-obvious *why*. If a comment would be an accurate one-line summary of
the next line of code, delete it.

## Docstrings follow the house pattern

Match the surrounding style exactly. Read a neighbouring function before writing a new one.
Do not add docstrings purely to satisfy a linter that isn't running; add them where a user of
the public API needs them.

## No private-context references in shipped code

Code, tests, and docs must stand on their own to a stranger. No references to planning docs,
other repos, internal ticket numbers, or evaluation notes. Public issue and PR numbers are fine
and useful — they are resolvable by any reader.

## PR descriptions

Lead with what and why in a few bullets, plus a link to the issue. Fill in the template's
sections and delete none, but keep each short. A long PR description with heavy heading and
bold formatting is harder to review, not more informative. Long explanatory content belongs in
the issue or in `docs/`, referenced from the PR body.
