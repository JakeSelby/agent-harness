# SPDX-License-Identifier: MIT
"""Write `decisions.json`, the replay fixture `test_jev_decision_provider.py` reads.

Run from the repository root after any change to the decision pack or the state builder, both
of which move the request hash every entry is keyed by:

    python3 tests/fixtures/jev/record.py

The responses are hand-authored to the documented response shape, not captured from the
service: no key is configured in this repository and no test may make a request. The one live
request that would let the repository claim API compatibility has not been made; until it has,
these fixtures prove the parser, not the vendor.
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "lib"))

from harness_core import decision  # noqa: E402
from harness_core.decisions import jev  # noqa: E402

COUNTERPARTY = "repo:agent-harness/main"
LEVELS = jev.DECISION_PACK["severity"]["levels"]


def _scores(level, top):
    rest = round((1 - top) / (len(LEVELS) - 1), 4)
    return dict((name, top if name == level else rest) for name in LEVELS)


def _score(level, top):
    return {"type": "score", "level": level, "probabilities": _scores(level, top)}


def _judgment(choice, top):
    rest = round((1 - top) / 2, 4)
    return {"type": "choice", "choice": choice,
            "probabilities": dict((name, top if name == choice else rest)
                                  for name in jev.DECISION_PACK["judgment"]["options"])}


def _response(judgment, top, level, score_top, model=jev.DEFAULT_MODEL):
    return {"model": model,
            "answers": {"judgment": _judgment(judgment, top), "severity": _score(level, score_top)},
            "usage": {"input_tokens": 1180, "output_tokens": 42}}


CASES = [
    ("proceed", "coding.shell_exec", 1, {"command": "python3 -m unittest discover -s tests"},
     _response("proceed", 0.94, "none", 0.9)),
    ("confirm", "coding.git_push", 3, {"command": "git push --force origin main"},
     _response("confirm", 0.97, "severe", 0.88)),
    ("unknown", "coding.file_write", 2, {"summary": "rewrite of a file nobody named"},
     _response("unknown", 0.91, "moderate", 0.86)),
    ("hesitant", "coding.deploy", 3, {"command": "./deploy.sh production"},
     _response("confirm", 0.55, "high", 0.84)),
    ("malformed", "coding.git_commit", 2, {"command": "git commit -m 'x'"},
     {"model": jev.DEFAULT_MODEL, "answers": {"judgment": _judgment("proceed", 0.9)},
      "usage": {"input_tokens": 12, "output_tokens": 1}}),
]


def build():
    entries = []
    for name, action_class, grade, context, response in CASES:
        action = decision.Action(action_class=action_class, grade=grade)
        state = jev.decision_state(action, COUNTERPARTY, context)
        request = jev.build_request(jev.DECISION_PACK, state)
        entries.append({"name": name, "action_class": action_class, "grade": grade,
                        "counterparty": COUNTERPARTY, "context": context,
                        "request_hash": jev.digest(request), "response": response})
    return {"pack_hash": jev.pack_hash(jev.DECISION_PACK), "model": jev.DEFAULT_MODEL,
            "source": "hand-authored to the documented response shape; no live request",
            "entries": entries}


if __name__ == "__main__":
    path = Path(__file__).resolve().parent / "decisions.json"
    path.write_text(json.dumps(build(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(path)
