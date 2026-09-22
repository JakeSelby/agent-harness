# SPDX-License-Identifier: MIT
"""A golden for what `harness usage --rules` reports: the rows and the counts.

The engine is the vendored `ruleprobe` wheel and the detectors that are about this
repository's rules are the pack in `claude/hooks/rule-detectors.py`. Between them they decide
every line of the report, so this file pins both halves: the exact set of detector ids, which
is the report's rows, and the hits one fixture session produces, which is its numbers. A
change to either is a deliberate change to a published table, not a refactor.
"""
import importlib.util
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "rule_pack_golden", REPO / "claude" / "hooks" / "rule-detectors.py")
rd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rd)

STANCES = {"commits": "conventional-attributed", "voice": "scannable"}

# Every row `usage --rules` prints for a ledger written by this registry.
ROWS = [
    "autonomy/confirmed-irreversible",
    "autonomy/denied-by-grade",
    "cache-hygiene/compact",
    "cache-hygiene/model-switch",
    "commits/missing-trailer",
    "commits/non-conventional",
    "decisions/no-alternatives",
    "delegation/executed-from-summary",
    "research/search-over-cap",
    "secrets/git-add-secret-file",
    "secrets/secret-in-write",
    "transcript-hygiene/model-wrote-no-cap",
    "transcript-hygiene/unfiltered-find",
    "transcript-hygiene/whole-file-cat",
    "verification/no-verify",
    "voice/banned-opener",
    "voice/second-table",
]

# The six the vendored engine ships; the rest of the rows are this repository's own.
GENERIC = [
    "cache-hygiene/compact",
    "cache-hygiene/model-switch",
    "secrets/secret-in-write",
    "transcript-hygiene/unfiltered-find",
    "transcript-hygiene/whole-file-cat",
    "verification/no-verify",
]

# One session touching eight detectors: the same shapes `tests/test_usage.py`'s fixture
# transcript carries, as the event list the SessionEnd worker builds from it.
SESSION = [
    {"kind": "assistant_text", "turn": 1, "text": "Reading the file now.",
     "final": False, "model": "model-a"},
    {"kind": "tool_use", "turn": 1, "id": "tu1", "name": "Bash",
     "input": {"command": "cat big.py"}},
    {"kind": "tool_result", "turn": 1, "tool_use_id": "tu1", "tool_name": "Bash",
     "text": "print('hello')"},
    {"kind": "user_prompt", "turn": 2},
    {"kind": "tool_use", "turn": 2, "id": "a1", "name": "Agent",
     "input": {"subagent_type": "general-purpose", "prompt": "Summarise the module."}},
    {"kind": "tool_use", "turn": 2, "id": "tu2", "name": "Bash",
     "input": {"command": 'git commit -m "fixed it"'}},
    {"kind": "compact", "turn": 2},
    {"kind": "tool_use", "turn": 2, "id": "tu3", "name": "Bash", "input": {"command": "find ."}},
    {"kind": "tool_use", "turn": 2, "id": "tu4", "name": "Bash",
     "input": {"command": "git push --no-verify"}},
    {"kind": "assistant_text", "turn": 2, "final": True, "model": "model-a",
     "text": "Great question — the module parses the manifest."},
]

HITS = {
    "cache-hygiene/compact": 1,
    "commits/missing-trailer": 1,
    "commits/non-conventional": 1,
    "transcript-hygiene/model-wrote-no-cap": 1,
    "transcript-hygiene/unfiltered-find": 1,
    "transcript-hygiene/whole-file-cat": 1,
    "verification/no-verify": 1,
    "voice/banned-opener": 1,
}


class RulePackGoldenTests(unittest.TestCase):
    def test_the_report_rows_are_the_registry(self):
        self.assertEqual(sorted(rd.DETECTORS), ROWS)

    def test_the_generic_half_is_the_engines_own_implementation(self):
        engine = {d.id: d.fn for d in rd.generic.DETECTORS}
        self.assertEqual(sorted(engine), GENERIC)
        for did, fn in engine.items():
            self.assertIs(rd.DETECTORS[did].fn, fn,
                          msg="%s is a second copy rather than the wheel's" % did)

    def test_the_engine_is_the_vendored_wheel(self):
        wheel = REPO / "lib" / "vendor" / "ruleprobe-0.1.0-py3-none-any.whl"
        self.assertTrue(wheel.is_file())
        self.assertIn(str(wheel), rd.generic.__file__)

    def test_one_fixture_session_yields_the_same_counts_it_always_did(self):
        hits = rd.run(SESSION, STANCES, strict=True)
        self.assertEqual({k: len(v) for k, v in hits.items()}, HITS)

    def test_every_hit_is_an_id_a_turn_and_a_tool_use_id(self):
        for did, hits in rd.run(SESSION, STANCES, strict=True).items():
            for one in hits:
                self.assertEqual(len(one), 3)
                self.assertEqual(one[0], did)


if __name__ == "__main__":
    unittest.main()
