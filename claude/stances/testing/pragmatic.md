# Testing stance: pragmatic

Write a test when it buys something: behaviour that has broken before, logic that is hard to reason
about by reading, a public contract others depend on, and every bug fix (a regression test proving
the bug is gone). Do not add tests that restate the implementation or only exercise a framework.
Before finishing, run the affected module's suite and fix what you broke. Follow the repo's
co-location convention, read a neighbouring test first, and say plainly in the report which new
behaviour is untested and why.
