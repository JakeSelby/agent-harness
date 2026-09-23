#!/usr/bin/env python3
"""Score every rule detector against a labelled corpus and fail under the floor.

Two corpora, one registry. The vendored `ruleprobe` wheel ships a labelled corpus for the six
generic detectors it also ships; `tests/fixtures/detector-corpus/` labels the eleven in
`claude/hooks/rule-detectors.py` that are about this repository's own rules. Both are scored
with the whole registry, so a repository detector that fires on the engine's corpus is a false
positive there too, and a precision or recall under the floor is a non-zero exit.

A detector with no label anywhere is a failure rather than a pass: `ruleprobe corpus` passes
over an unmeasured detector because it cannot know whose corpus it is scoring, but in here
every row `harness usage --rules` prints is meant to have a known precision and recall, and a
new detector arriving without an example is the gap this job exists to show.

    python3 scripts/detector_corpus.py [--floor 0.9] [--json]
"""
import argparse
import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "claude" / "hooks" / "rule-detectors.py"
REPO_CORPUS = ROOT / "tests" / "fixtures" / "detector-corpus"


def rule_pack():
    """The rule pack module, which puts the vendored wheel on `sys.path` as it loads."""
    spec = importlib.util.spec_from_file_location("harness_rule_detectors", str(PACK))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ungated(pack):
    """The whole registry with every stance gate removed.

    The scorer runs a session with no stances, so a gated detector would be disabled over the
    corpus and every positive it was labelled for would read as a miss. What the corpus
    measures is the detector's judgment; whether a stance turns it on is configuration, and
    `tests/test_rule_detectors.py` holds that half.
    """
    from ruleprobe.registry import Registry

    return Registry([pack.Detector(d.id, d.rule, d.event, d.fn, None)
                     for d in pack.DETECTORS.values()])


def wheel_corpus(into):
    """Where the engine's own corpus is, unpacked under `into` when it needs to be.

    The wheel is imported straight off `sys.path` and never installed, so its corpus is a
    member of a zip file and not a directory anything can walk. The scorer takes a path, so
    the corpus is extracted for the run and thrown away after it.
    """
    import zipfile

    import ruleprobe

    inside = Path(ruleprobe.__file__).resolve().parent / "corpus"
    if inside.is_dir():
        return str(inside)
    for parent in inside.parents:
        if parent.is_file():
            with zipfile.ZipFile(str(parent)) as archive:
                names = [n for n in archive.namelist() if n.startswith("ruleprobe/corpus/")]
                archive.extractall(into, names)
            return str(Path(into) / "ruleprobe" / "corpus")
    raise RuntimeError("the vendored wheel holds no corpus: %s" % inside)


class CorpusRecordError(Exception):
    """A `known_below_floor` entry that cannot be checked against a measurement."""


def known_below_floor(path):
    """`{detector_id: (floor, precision, recall)}` the repository corpus records as known bad.

    A detector that cannot reach the floor on an honest corpus keeps the floor and is written
    down here with the score it measured and the floor it was measured against, rather than
    the floor being lowered to meet it. All three are compared, not merely looked up, so an
    entry that no longer describes the detector fails the job in either direction: a
    regression and a quiet improvement are both news. Running at a lower floor than the entry
    names leaves it dormant rather than stale - the record is still true of the 0.9 gate CI
    runs, whatever a one-off `--floor 0.8` asked for.
    """
    from ruleprobe.declarative import load

    document, _lines = load(str(path))
    return dict((entry["detector"], (float(entry["floor"]), float(entry["precision"]),
                                     float(entry["recall"])))
                for entry in document.get("known_below_floor") or [])


def measured(score):
    """A score's precision and recall to two places, or a readable failure.

    A `known_below_floor` entry for a detector the corpus does not label, or for an id that no
    longer exists, arrives here as an unscored row or as no row at all. An unscored row still
    answers 1.0 to both questions - a detector that never fired and never missed - so rounding
    it would record a perfect score for something nobody measured. That is a corpus to fix,
    not a number to round.
    """
    if score is None or not score.scored or score.precision is None or score.recall is None:
        raise CorpusRecordError(
            "%s has no measured score; a known_below_floor entry names a detector the corpus "
            "does not label" % (score.detector if score is not None else "the detector"))
    return (round(score.precision, 2), round(score.recall, 2))


def merge(parts):
    """One `Score` per detector over every corpus scored."""
    from ruleprobe.validity import Score

    out = {}
    for scores in parts:
        for detector_id, score in scores.items():
            out.setdefault(detector_id, Score(detector_id)).add(score)
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--floor", type=float, default=None, metavar="F",
                        help="fail when a detector's precision or recall is under this")
    parser.add_argument("--json", action="store_true",
                        help="print the merged scores as JSON instead of the tables")
    args = parser.parse_args(argv)

    pack = rule_pack()
    from ruleprobe.validity import (CorpusError, DEFAULT_FLOOR, below_floor, score_corpus,
                                    scores_as_dict, validity_table)

    floor = DEFAULT_FLOOR if args.floor is None else args.floor
    registry = ungated(pack)
    unpacked = tempfile.mkdtemp(prefix="detector-corpus-")
    scores_per_corpus, tables = [], []
    try:
        corpora = [("the wheel's corpus", wheel_corpus(unpacked)),
                   ("this repository's corpus", str(REPO_CORPUS))]
        for title, directory in corpora:
            try:
                scores = score_corpus(registry=registry, directory=directory)
            except CorpusError as exc:
                sys.stderr.write("corpus: %s\n" % exc)
                return 2
            scores_per_corpus.append(scores)
            tables.append("%s\n%s" % (title, validity_table(scores, floor)))
    finally:
        shutil.rmtree(unpacked, ignore_errors=True)

    scores = merge(scores_per_corpus)
    try:
        known = known_below_floor(REPO_CORPUS / "labels.yaml")
        failing = set(below_floor(scores, floor))
        waived, dormant, stale = [], [], []
        for detector_id, record in sorted(known.items()):
            recorded_floor, pair = record[0], (round(record[1], 2), round(record[2], 2))
            now = measured(scores.get(detector_id))
            if now != pair:
                stale.append("%s measures p=%.2f r=%.2f, not the recorded p=%.2f r=%.2f"
                             % ((detector_id,) + now + pair))
            elif now[0] >= recorded_floor and now[1] >= recorded_floor:
                stale.append("%s is recorded as below a %.2f floor and is not"
                             % (detector_id, recorded_floor))
            elif detector_id in failing:
                waived.append("%s p=%.2f r=%.2f" % ((detector_id,) + now))
            else:
                dormant.append("%s is recorded below %.2f, which the %.2f floor in force does "
                               "not ask about" % (detector_id, recorded_floor, floor))
    except CorpusRecordError as exc:
        sys.stderr.write("corpus: %s\n" % exc)
        return 2
    unscored = sorted(did for did, score in scores.items() if not score.scored)
    failed = [did for did in sorted(failing) if did not in known]

    if args.json:
        data = scores_as_dict(scores, floor)
        data.update({"unscored": unscored, "failed": failed,
                     "known_below_floor": sorted(waived), "dormant": sorted(dormant),
                     "stale": sorted(stale)})
        print(json.dumps(data, indent=2, sort_keys=True))
    else:
        print("\n\n".join(tables))
        print("\nboth corpora, %d detectors" % len(scores))
        print(validity_table(scores, floor))
        for line in waived:
            print("\nknown below the %.2f floor, and recorded as such: %s" % (floor, line))
        for line in dormant:
            print("\n%s" % line)
        if unscored:
            print("\n%d detector(s) with no labelled example: %s"
                  % (len(unscored), ", ".join(unscored)))
        for line in stale:
            print("\nthe known_below_floor entry is out of date: %s" % line)
        if failed:
            print("\n%d detector(s) under the %.2f floor: %s"
                  % (len(failed), floor, ", ".join(failed)))
    return 1 if failed or unscored or stale else 0


if __name__ == "__main__":
    sys.exit(main())
