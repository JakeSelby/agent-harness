# Digest: claude-md-doctor (read 2026-09-23)

- **Source:** https://github.com/agent-clinic/claude-md-doctor (README;
  `skills/claude-md-doctor/SKILL.md` steps 4b and 4d; the docstring of
  `skills/claude-md-doctor/scripts/backtest.py`). Accessed 2026-09-23. MIT licence.
- **Claim:** it backtests every rule in CLAUDE.md or AGENTS.md against Claude Code session
  transcripts and reports each rule's opportunities, compliance and a verdict (healthy, ignored,
  inert). Confidence: high (README).
- **Claim:** the model writes the rulebook of regex matchers at each checkup (step 4b); the replay
  engine is deterministic; the model sample-verifies every fire and fixes a matcher on a false
  positive before results count (step 4d). Nothing in the skill holds the matchers fixed between
  checkups. Confidence: high (SKILL.md and backtest.py).
- **Claim:** it triages each violation by cause and proposes a hook, linter or judge class per rule;
  it installs nothing itself. Confidence: high (README).
- **Claim:** Claude Code transcripts only; no other runtime named. Confidence: medium (absence in
  README).
