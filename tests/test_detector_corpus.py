# SPDX-License-Identifier: MIT
"""The labelled corpus for this repository's own detectors, and the floor it is scored at.

`scripts/detector_corpus.py` is what CI runs; these tests hold the three things a green job
would otherwise not prove: that every repository detector has a labelled positive and a
labelled negative, that the committed transcripts are the ones `build_sessions.py` writes, and
that the whole thing scores at or above the 0.9 floor with every below-floor detector recorded
rather than waved through.

Run: python3 -m unittest discover tests
"""
import importlib.util
import io
import json
import re
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CORPUS = REPO / "tests" / "fixtures" / "detector-corpus"
FLOOR = 0.9
MINIMUM = 5  # positives and negatives per repository detector, per the issue


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RD = load(REPO / "claude" / "hooks" / "rule-detectors.py", "corpus_rule_pack")
SCORER = load(REPO / "scripts" / "detector_corpus.py", "corpus_scorer")
BUILDER = load(CORPUS / "build_sessions.py", "corpus_builder")
OWN = [d.id for d in RD._REGISTRY if d.id not in set(g.id for g in RD._GENERIC)]


def labels():
    """The repository corpus as loaded data, by the same reader the scorer uses."""
    from ruleprobe.declarative import load as load_yaml

    document, _lines = load_yaml(str(CORPUS / "labels.yaml"))
    return document


def counted():
    """`{detector_id: (positives, negatives)}` over every session in the repository corpus."""
    out = {}
    for session in labels()["sessions"]:
        for label in session["labels"]:
            for key, index in (("fire", 0), ("near", 1)):
                for detector_id in label.get(key) or []:
                    tally = out.setdefault(detector_id, [0, 0])
                    tally[index] += 1
    return dict((k, tuple(v)) for k, v in out.items())


class LabelCoverageTests(unittest.TestCase):
    """Every detector this repository wrote is labelled on both sides."""

    def test_each_repository_detector_has_a_positive_and_a_negative(self):
        tallies = counted()
        self.assertEqual(len(OWN), 11)
        for detector_id in OWN:
            positives, negatives = tallies.get(detector_id, (0, 0))
            self.assertGreater(positives, 0, msg=detector_id)
            self.assertGreater(negatives, 0, msg=detector_id)

    def test_the_corpus_labels_no_detector_the_registry_does_not_hold(self):
        for detector_id in counted():
            self.assertIn(detector_id, RD.DETECTORS, msg=detector_id)

    def test_every_detector_but_the_costly_one_carries_five_of_each(self):
        """`research/search-over-cap` needs more than two hundred searches for one positive
        and fires at most once per session, so its cases are four whole transcripts rather
        than five of each; every other detector carries the five the issue asks for."""
        for detector_id, (positives, negatives) in counted().items():
            if detector_id == "research/search-over-cap":
                self.assertEqual((positives, negatives), (2, 2))
                continue
            self.assertGreaterEqual(positives, MINIMUM, msg=detector_id)
            self.assertGreaterEqual(negatives, MINIMUM, msg=detector_id)


class SessionTests(unittest.TestCase):
    """The committed transcripts are the ones the builder writes, and hold nothing real."""

    def test_the_committed_sessions_are_what_the_builder_writes(self):
        written = tempfile.mkdtemp(prefix="corpus-build-")
        original = BUILDER.SESSIONS
        try:
            BUILDER.SESSIONS = written
            BUILDER.build()
            for path in sorted(Path(written).glob("*.jsonl")):
                committed = CORPUS / "sessions" / path.name
                self.assertTrue(committed.is_file(), msg=path.name)
                self.assertEqual(path.read_bytes(), committed.read_bytes(), msg=path.name)
            self.assertEqual(len(list(Path(written).glob("*.jsonl"))),
                             len(list((CORPUS / "sessions").glob("*.jsonl"))))
        finally:
            BUILDER.SESSIONS = original
            shutil.rmtree(written, ignore_errors=True)

    def test_no_session_carries_a_home_path_or_an_address(self):
        for path in sorted((CORPUS / "sessions").glob("*.jsonl")):
            body = path.read_text(encoding="utf-8")
            self.assertNotIn("/Users/", body, msg=path.name)
            self.assertNotIn("/home/", body, msg=path.name)
            for address in re.findall(r"[\w.+-]+@[\w.-]+", body):
                self.assertTrue(address.endswith(".invalid"), msg=address)


class FloorTests(unittest.TestCase):
    """The gate CI runs, run here, in process."""

    def score(self, argv):
        out = io.StringIO()
        with redirect_stdout(out):
            status = SCORER.main(argv)
        return status, out.getvalue()

    def test_the_corpus_scores_at_the_floor(self):
        status, printed = self.score(["--floor", str(FLOOR)])
        self.assertEqual(status, 0, msg=printed)
        self.assertNotIn("no labelled example", printed)

    def test_every_detector_in_the_registry_is_scored(self):
        _status, printed = self.score(["--floor", str(FLOOR), "--json"])
        data = json.loads(printed)
        self.assertEqual(data["unscored"], [])
        self.assertEqual(set(data["detectors"]), set(RD.DETECTORS))
        for detector_id, row in data["detectors"].items():
            self.assertTrue(row["scored"], msg=detector_id)

    def test_a_detector_under_the_floor_is_recorded_with_its_measured_score(self):
        """The floor is kept and the miss is written down, not lowered away. The recorded
        pair is compared with the measurement, so this fails if either side moves."""
        _status, printed = self.score(["--floor", str(FLOOR), "--json"])
        data = json.loads(printed)
        self.assertEqual(data["failed"], [])
        self.assertEqual(data["stale"], [])
        recorded = dict((entry["detector"], entry)
                        for entry in labels().get("known_below_floor") or [])
        self.assertEqual(sorted(recorded), sorted(
            line.split(" ")[0] for line in data["known_below_floor"]))
        for detector_id, entry in recorded.items():
            row = data["detectors"][detector_id]
            self.assertEqual(round(row["precision"], 2), round(entry["precision"], 2))
            self.assertEqual(round(row["recall"], 2), round(entry["recall"], 2))
            self.assertTrue(entry.get("note"), msg=detector_id)


if __name__ == "__main__":
    sys.exit(unittest.main())
