# Testing stance: required

**"Build feature X" always means:** build the feature, make every existing test pass, and write
tests covering every new capability. Tests are never a separate step, never optional, never a
suggestion. They are part of the definition of done.

## What requires a test

- Every new function, method, or service that contains logic.
- Every new API endpoint: request and response shape, auth enforcement, error cases.
- Every new UI component with behaviour: interactions, conditional rendering, data display.
- Every new hook or utility.
- **Every bug fix**, with a regression test proving the bug is gone.

## What "tests passing" means before finishing

Run the suite for the affected module. Fix any failures, both pre-existing failures in files
you touched and new ones from your changes. New tests must be green.

## Placement

Follow the co-location convention of the repo you are in. Read a neighbouring test before
writing a new one.

## No exceptions

There is no circumstance where shipping code without tests is acceptable — not for speed, not
for "simple" changes, not for "I'll add them later". Later never comes.
