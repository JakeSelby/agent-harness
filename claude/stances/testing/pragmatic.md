# Testing stance: pragmatic

Write a test when it buys something: behaviour that has broken before, logic that is hard to
reason about by reading, a public contract others depend on, and every bug fix (a regression
test proving the bug is gone). Do not add tests that restate the implementation or that only
exercise a framework.

Before finishing, run the suite for the affected module and fix what you broke. Follow the
repo's co-location convention and read a neighbouring test before writing a new one. Say plainly
in the report which new behaviour is untested and why.
