# SPDX-License-Identifier: MIT
"""What `transcript-hygiene/model-wrote-no-cap` measures, and why it is named that (#324).

`brief-guard` appends a word cap to every uncapped `Agent` brief, yet the detector's hit rate
did not move when the hook shipped. The cause is the transcript's own shape: the `tool_use`
block holds the input the model wrote, and the hook's `updatedInput` is written to a separate
`attachment` line of type `hook_success` that the scan skips. The fixture below is that shape,
synthesised — one spawn whose recorded brief has no cap and whose delivered brief has one.

Run: python3 -m unittest discover tests
"""
import importlib.machinery
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
NEW_ID = "transcript-hygiene/model-wrote-no-cap"
OLD_ID = "transcript-hygiene/brief-without-cap"
AUTHORED = "Find every call site of parse_row and tell me which ones pass a dict."
STAMP = "2026-09-20T12:00:00.000Z"
TOOL_USE_ID = "toolu_synthetic_0001"


def _load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader))
    loader.exec_module(module)
    return module


harness = _load("harness_cli_cap", REPO / "bin" / "harness")
usage_log = _load("usage_log_cap", REPO / "claude" / "hooks" / "usage-log.py")
rd = _load("rule_detectors_cap", REPO / "claude" / "hooks" / "rule-detectors.py")
guard = _load("brief_guard_cap", REPO / "claude" / "hooks" / "brief-guard.py")

DELIVERED = AUTHORED + guard.BOUND


def transcript(path):
    """One spawn as Claude Code records it: the authored `tool_use`, then the hook's own line."""
    entries = [
        {"type": "user", "sessionId": "s-1", "cwd": "", "timestamp": STAMP,
         "message": {"role": "user", "content": "find the call sites"}},
        {"type": "assistant", "sessionId": "s-1", "cwd": "", "timestamp": STAMP,
         "message": {"id": "m1", "model": "model-a", "content": [
             {"type": "tool_use", "id": TOOL_USE_ID, "name": "Agent",
              "input": {"subagent_type": "general-purpose", "prompt": AUTHORED}}]}},
        # The hook's edit. Claude Code writes it as its own entry, with the rewritten input
        # inside the hook's stdout, and never rewrites the `tool_use` block above.
        {"type": "attachment", "sessionId": "s-1", "cwd": "", "timestamp": STAMP,
         "attachment": {"type": "hook_success", "hookName": "PreToolUse:Agent",
                        "hookEvent": "PreToolUse", "toolUseID": TOOL_USE_ID, "content": "",
                        "stdout": json.dumps({"hookSpecificOutput": {
                            "hookEventName": "PreToolUse",
                            "updatedInput": {"subagent_type": "general-purpose",
                                             "prompt": DELIVERED}}})}},
    ]
    path.write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")
    return path


class TheFixtureIsTheCase(unittest.TestCase):
    def test_the_delivered_brief_really_does_carry_a_cap(self):
        """Otherwise the test below would pass for the wrong reason."""
        self.assertIsNone(rd.WORD_CAP_RE.search(AUTHORED))
        self.assertTrue(rd.WORD_CAP_RE.search(DELIVERED))


class WhatTheDetectorSees(unittest.TestCase):
    def scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            return usage_log.scan(transcript(Path(tmp) / "session.jsonl"), "s-1", "")

    def test_a_capped_delivery_is_still_a_hit(self):
        """The metric counts what the model wrote. A hook cannot move it, by design."""
        record = self.scan()
        self.assertNotIn("rules_error", record)
        self.assertEqual(record["rules"].get(NEW_ID), 1)

    def test_the_hook_line_reaches_no_event_at_all(self):
        """The evidence for the cause: the delivered brief is in the file and not in the events."""
        with tempfile.TemporaryDirectory() as tmp:
            path = transcript(Path(tmp) / "session.jsonl")
            self.assertIn(guard.BOUND.strip()[:40], path.read_text())
            events = [e for e in _events(path) if e.get("kind") == "tool_use"]
        self.assertEqual([e["input"]["prompt"] for e in events], [AUTHORED])


def _events(path):
    """The event list the detectors run over, taken from the scan's own reader."""
    captured = []
    real_run = rd.run

    def spy(events, stances=None, strict=False, errors=None):
        captured.extend(events)
        return real_run(events, stances, strict=strict, errors=errors)

    rd.run = spy
    real_detectors = usage_log.detectors
    usage_log.detectors = lambda: rd
    try:
        usage_log.scan(path, "s-1", "")
    finally:
        rd.run = real_run
        usage_log.detectors = real_detectors
    return captured


class TheRename(unittest.TestCase):
    def test_the_registry_carries_the_new_id_only(self):
        self.assertIn(NEW_ID, rd.DETECTORS)
        self.assertNotIn(OLD_ID, rd.DETECTORS)
        self.assertEqual(rd.RENAMED, {OLD_ID: NEW_ID})

    def test_an_old_ledger_row_reports_under_the_new_id(self):
        """A rename must not split the series: one line, the summed hits, both sessions."""
        rows = [
            {"rules": {OLD_ID: 4}, "repo": "one", "stances": {"delegation": "tiered"}},
            {"rules": {NEW_ID: 2}, "repo": "one", "stances": {"delegation": "tiered"}},
        ]
        self.assertNotIn(OLD_ID, harness.rule_ids(rows))
        self.assertIn(NEW_ID, harness.rule_ids(rows))

        line = [ln for ln in self.report(rows, "rule").splitlines() if NEW_ID[:38] in ln]
        self.assertEqual(len(line), 1, line)
        self.assertNotIn(OLD_ID, self.report(rows, "rule"))
        # hits, sessions with a hit, sessions measured
        self.assertEqual(line[0].split()[1:4], ["6", "2", "2"])

        for by, key in (("repo", "one"), ("stance", "delegation=tiered")):
            with self.subTest(by=by):
                out = self.report(rows, by)
                self.assertNotIn(OLD_ID, out)
                grouped = [ln for ln in out.splitlines() if ln.startswith(key)]
                self.assertEqual(len(grouped), 1, out)
                self.assertIn(NEW_ID + " 6", grouped[0])
                self.assertEqual(grouped[0].split()[1:3], ["2", "6"])

    def test_the_ledger_file_itself_is_not_rewritten(self):
        """The fold is a read; a record keeps the id it was written under."""
        row = {"rules": {OLD_ID: 4}}
        self.report([row], "rule")
        self.assertEqual(row["rules"], {OLD_ID: 4})

    @staticmethod
    def report(rows, by):
        """The report's lines, taken from `say` rather than from stdout: another test in the
        run may have left `HARNESS_QUIET` set, which silences printing but not this."""
        lines = []
        real_say = harness.say
        harness.say = lines.append
        try:
            harness.rule_report([dict(r) for r in rows], by, 30)
        finally:
            harness.say = real_say
        return "\n".join(lines)


class HookAndDetectorAgree(unittest.TestCase):
    """A bound the detector cannot see is not a bound, and a brief the hook leaves alone must be
    one the detector counts as capped. Both read `rule-detectors`, so this pins the parity."""

    CASES = [
        AUTHORED,
        "Summarise it. Keep it short.",
        "Fix the 3 tool calls in parser.py.",
        "Summarise it in at most 200 words.",
        "Return a 300 word cap summary.",
        "Reply with no more than 50 words.",
        "400 words or fewer, please.",
        "Answer within 150 words.",
        "This brief carries a 250-word cap.",
        "≤ 400 words.",
    ]

    def test_the_hook_appends_exactly_where_the_detector_hits(self):
        for prompt in self.CASES:
            with self.subTest(prompt=prompt[:40]):
                tool_input = {"subagent_type": "general-purpose", "prompt": prompt}
                fires = bool(rd.run([{"kind": "tool_use", "turn": 1, "id": "tu1",
                                      "name": "Agent", "input": tool_input}], {}, strict=True))
                self.assertEqual(guard.needs_bound(rd, tool_input), fires)

    def test_an_agent_whose_definition_carries_the_cap_is_exempt_on_both_sides(self):
        for kind in sorted(rd.CAPPED_AGENTS):
            with self.subTest(agent=kind):
                tool_input = {"subagent_type": kind, "prompt": AUTHORED}
                self.assertFalse(guard.needs_bound(rd, tool_input))
                self.assertEqual(rd.run([{"kind": "tool_use", "turn": 1, "id": "tu1",
                                          "name": "Agent", "input": tool_input}], {},
                                        strict=True), {})

    def test_the_hook_is_registered_on_the_agent_event(self):
        template = json.loads((REPO / "claude" / "settings.template.json").read_text())
        commands = [h.get("command", "")
                    for entry in template["hooks"]["PreToolUse"]
                    if entry.get("matcher") == "Agent"
                    for h in entry.get("hooks", [])]
        self.assertTrue(any("brief-guard.py" in c for c in commands), commands)


if __name__ == "__main__":
    unittest.main()
