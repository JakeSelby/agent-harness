"""Every observation in a written record names the case it belongs to.

The record is written with sorted keys, which reorders `cases` and leaves `observations` alone, so
a list kept in run order paired most observations with the wrong case. No client runs here: the
cases are fed in the catalog's run order, and what is read is the record as it is written.
"""
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from test_native_acceptance import CLIENT, MODULE
from test_native_acceptance_cases import MODULE_FOR

REQUIRED = MODULE.catalog()["required_cases"]
HEADER = {"kind": "native", "client": CLIENT, "source_commit": "a" * 40}


def said(name):
    return "A native session did " + name + "."


def line(name, observation=True):
    item = dict(HEADER, case=name, result="passed")
    if observation:
        item["observation"] = said(name)
    return item


def written(data):
    """The record as `main` writes it and a reader loads it back."""
    return json.loads(json.dumps(data, indent=2, sort_keys=True))


def pairs(data):
    """Each case with the observation that names it, read by prefix and never by position."""
    found = {}
    for text in data["observations"]:
        case, _, rest = text.partition(": ")
        if case in data["cases"]:
            found[case] = rest
    return found


class PairingTests(unittest.TestCase):
    def test_the_catalog_runs_cases_out_of_alphabetical_order(self):
        # The defect needs both orders to differ; if they ever agree this suite proves less.
        self.assertNotEqual(list(REQUIRED), sorted(REQUIRED))

    def test_every_observation_names_its_case_in_the_written_order(self):
        data = written(MODULE.build_record([line(name) for name in REQUIRED]))
        self.assertEqual(list(data["cases"]), sorted(REQUIRED))
        self.assertEqual(data["observations"],
                         [name + ": " + said(name) for name in data["cases"]])
        self.assertEqual(pairs(data), dict((name, said(name)) for name in REQUIRED))

    def test_a_case_without_an_observation_is_still_represented(self):
        silent = REQUIRED[1]
        items = [line(name, observation=name != silent) for name in REQUIRED]
        data = written(MODULE.build_record(items))
        self.assertEqual(len(data["observations"]), len(data["cases"]))
        self.assertEqual(pairs(data)[silent], MODULE.NO_OBSERVATION)
        for name in REQUIRED:
            if name != silent:
                self.assertEqual(pairs(data)[name], said(name))

    def test_an_observation_that_already_names_its_case_is_not_named_twice(self):
        name = REQUIRED[0]
        item = dict(line(name), observation=name + ": " + said(name))
        self.assertEqual(MODULE.build_record([item])["observations"], [name + ": " + said(name)])

    def test_the_latest_line_for_a_case_wins_with_its_own_observation(self):
        name = REQUIRED[0]
        items = [dict(line(name), result="failed", observation="the spawn was not routed"),
                 line(name)]
        data = MODULE.build_record(items)
        self.assertEqual(data["observations"], [name + ": " + said(name)])

    def test_a_round_note_carries_no_case_prefix(self):
        # The round runner appends its own notes unprefixed; a reader tells them apart because
        # no case name opens them.
        driver = MODULE_FOR("qualification_round")
        data = driver.nothing_observed("the runner wrote no record for this target")
        data["observations"].append("the target ran past the round deadline of 1s")
        self.assertEqual(pairs(data), {})


class RebuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.progress = Path(self.tmp.name) / "round.partial.jsonl"

    def test_a_rebuild_from_an_old_log_pairs_by_case(self):
        # Durable-log lines hold bare observations; the rebuild names each one's case.
        def runner(client, name, model, keep, confirmed=False):
            return {"case": name, "result": "passed", "observation": said(name),
                    "seconds": 0.1, "sessions": 1}

        with patch.object(MODULE, "client_version", return_value="9.9.9"), \
                patch.object(MODULE, "git",
                             side_effect=lambda *args: "" if args[0] == "status" else "a" * 40), \
                patch.dict(MODULE.CASES, dict((name, (None, "stub")) for name in REQUIRED),
                           clear=True):
            MODULE.record(CLIENT, REQUIRED, "cheapest", False, runner=runner,
                          progress=self.progress)
        logged = [json.loads(raw) for raw in self.progress.read_text().splitlines()]
        self.assertIn(said(REQUIRED[0]), [item.get("observation") for item in logged])
        out = Path(self.tmp.name) / "record.json"
        with patch.object(MODULE, "probe", side_effect=AssertionError("a case ran")), \
                redirect_stdout(io.StringIO()):
            MODULE.main(["--client", CLIENT, "--from-progress", "--model", "cheapest",
                         "--progress", str(self.progress), "--out", str(out)])
        data = json.loads(out.read_text())
        self.assertEqual(pairs(data), dict((name, said(name)) for name in REQUIRED))


if __name__ == "__main__":
    unittest.main()
