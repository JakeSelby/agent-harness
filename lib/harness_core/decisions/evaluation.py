"""Replay the decision log through the Jev pack and say how well the judgment tracked it.

The labelled set is #370's decision log, not a synthetic one: real inputs, the answer the
deterministic hook gave, and the outcome the session later showed. `grade-bash` writes a row
only when the harness said `ask` or `deny`, so every label here answers one question — **did the
user actually want to be asked?** `ran` is the user letting the command through and is read as
`proceed`; `not_run` is the session ending without it and is read as `confirm`. Both readings
are weaker than they look and the report says so: an approval after a prompt is evidence the
prompt was unnecessary and not proof, and `decisions.py` says itself that a refusal, an
interrupted turn and a crash are indistinguishable in `not_run`.

Four choices the rest of the module follows from.

* **One replay, many thresholds.** Every case is asked at threshold zero, so a result carries
  the raw judgment and its confidence; the threshold is applied here afterwards. Fitting a
  threshold is then a sweep over one recorded set rather than one request per candidate.
* **A threshold is per decision point and there is no default.** Published routing work finds
  an optimal cutoff does not transfer between workloads, so a point with no dev cases is
  reported unfitted rather than given the global 0.8 as if it had been measured.
* **The split is seeded by content, never by `random`.** A case lands in `dev` or `heldout` by
  the first bytes of the hash of the text that was judged, so the same command is always on the
  same side, a re-run reproduces the split, and adding rows does not reshuffle the old ones.
* **An error is never a pass.** `unavailable`, `error` and an abstention are counted in their
  own column and are wrong for the purpose of accuracy; a report where they dominate says so in
  the headline rather than in a rate over the handful that answered.

Nothing here writes to the decision ledger, and with `--replay` nothing here opens a socket:
the client is `jev.ReplayClient` over a recorded fixture. `--live` is the opt-in path and needs
an explicit request ceiling; the allowlist it sends under is the user's own configuration, so an
evaluation cannot send a field the user never allowed a hook to send.
"""
import hashlib
import json
from typing import Any, Dict, List, Optional

from .. import decision
from . import controls, jev, packs

CONFIRM = "confirm"
PROCEED = "proceed"
ABSTAIN = "abstain"

DEV = "dev"
HELDOUT = "heldout"
SPLITS = (DEV, HELDOUT)
# Half and half. A held-out half of a log this size is small, and a smaller one would make the
# only number anybody should quote the noisier of the two.
DEV_SHARE = 50

# What a recorded outcome says about the judgment that preceded it. Anything else is unlabelled
# and is counted as such: a label this module invented would be a number nobody measured.
OUTCOME_LABELS = {"ran": PROCEED, "not_run": CONFIRM}
# The deterministic answers that mean "a person was put in the loop". `deny` is stronger than a
# confirmation, but on this axis — asked versus not asked — the two agree.
DETERMINISTIC_CONFIRM = ("ask", "deny")

# The decision log records the text a hook judged and not an action class, so the replay
# derives one per point. `grade-bash` is a shell command; the rest judge a turn or a brief,
# which is the nearest class the contract offers and is stated in the report as a derivation.
POINT_ACTIONS = {"grade-bash": "coding.shell_exec", "stop-gate": "coding.shell_exec",
                 "evasion-deny": "coding.shell_exec", "brief-guard": "coding.file_write",
                 "tier-agent-spawns": "coding.file_write"}
DEFAULT_ACTION = "coding.shell_exec"
# "an unknown grade is judged as 1", the same reading the pack's own grade scale states.
DEFAULT_GRADE = 1

CALIBRATION_BINS = 10
BOOTSTRAP_RESAMPLES = 200


class EvalError(ValueError):
    """A run this module will not make, or a report it will not write."""


# ------------------------------------------------------------------ the split


def split_for(content_hash: str, dev_share: int = DEV_SHARE) -> str:
    """`dev` or `heldout`, from the content hash alone. No clock, no `random`, no order."""
    if not isinstance(content_hash, str) or len(content_hash) < 8:
        raise EvalError("a split needs a content hash to be seeded by")
    return DEV if int(content_hash[:8], 16) % 100 < dev_share else HELDOUT


class _Stream:
    """A small LCG seeded from a digest, for the bootstrap below.

    `random` is seeded from the clock unless a caller remembers not to let it be, and a report
    that moves between runs is not the evidence this command exists to produce. The constants
    are Numerical Recipes' 32-bit LCG; the sample is an index, so its quality only has to be
    uniform over a few hundred cases.
    """

    def __init__(self, seed: str):
        self.state = int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8], 16)

    def below(self, ceiling: int) -> int:
        self.state = (1664525 * self.state + 1013904223) % (2 ** 32)
        return self.state % max(ceiling, 1)


# ------------------------------------------------------------------ cases


def cases_from_rows(rows: List[Dict[str, Any]], point: Optional[str] = None,
                    dev_share: int = DEV_SHARE) -> List[Dict[str, Any]]:
    """Every joined decision row that can be replayed, as a case. Oldest first.

    A row with no input text cannot be replayed at all and is dropped; a row whose outcome is
    not one this module knows how to read is kept, unlabelled, so the report can say how much
    of the log is not yet evidence.
    """
    out = []
    for row in rows:
        if row.get("kind") == "outcome":
            continue
        name = str(row.get("point") or "")
        if point and name != point:
            continue
        text = row.get("input")
        if not isinstance(text, str) or not text.strip():
            continue
        content = row.get("input_sha256")
        if not isinstance(content, str) or len(content) < 8:
            content = hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()
        out.append({
            "point": name, "input": text, "content_hash": content,
            "split": split_for(content, dev_share),
            "deterministic_answer": row.get("deterministic_answer"),
            "label": OUTCOME_LABELS.get(str(row.get("outcome") or "")),
            "action_class": POINT_ACTIONS.get(name, DEFAULT_ACTION),
        })
    return out


def case_state(case: Dict[str, Any], allowlist: controls.Controls,
               counterparty: str) -> Dict[str, Any]:
    """The request state for one case, built by the provider's own state builder.

    Through `jev.decision_state`, not beside it: a field this configuration does not allow out
    must be as absent from a replayed request as from a live one, and the only way to be sure of
    that is to use the same code.
    """
    action = decision.Action(action_class=case["action_class"], grade=DEFAULT_GRADE)
    return jev.decision_state(action, counterparty, {"command": case["input"]}, allowlist)


def shadow_controls(state_fields=controls.STATE_FIELDS, configured: bool = False,
                    **kwargs) -> controls.Controls:
    """Controls with every point in `shadow` and nothing else changed.

    `shadow` is the only mode an evaluation may run under: it is the mode whose answer reaches
    the ledger and neither the model nor the user, which is what makes a measurement a
    measurement rather than a change of behaviour on a live machine.
    """
    return controls.Controls(default_mode="shadow",
                             modes=dict((point, "shadow") for point in controls.POINTS),
                             state_fields=state_fields, configured=configured, **kwargs)


def judge(cases: List[Dict[str, Any]], client, pack: packs.Pack,
          allowlist: Optional[controls.Controls] = None, counterparty: str = "repo:eval/replay",
          model: str = jev.DEFAULT_MODEL,
          budget: Optional[jev.Budget] = None) -> List[Dict[str, Any]]:
    """Ask the pack about every case, at threshold zero. Returns the cases with results on them.

    Threshold zero because the threshold is what this run is trying to fit: `jev.ask` would
    report a below-threshold answer as `unknown` and throw away the confidence the sweep needs.
    The status is recomputed here at each candidate instead.
    """
    allowlist = shadow_controls() if allowlist is None else allowlist
    if allowlist.mode_for("grade-bash") != "shadow":
        raise EvalError("an evaluation runs in shadow mode; these controls resolve to "
                        + allowlist.mode_for("grade-bash"))
    questions = pack.questions
    out = []
    with decision.events_suppressed():
        for case in cases:
            state = case_state(case, allowlist, counterparty)
            result = jev.ask(questions, state, client, model=model, budget=budget,
                             threshold=0.0)
            answer = result["answers"].get(jev.JUDGMENT) or {}
            out.append(dict(case, status=result["status"], error=result["error"],
                            model=result["model"], usage=result["usage"],
                            latency_ms=result["latency_ms"],
                            request_hash=result["request_hash"],
                            judgment=answer.get("choice"),
                            confidence=answer.get("confidence")))
    return out


# ------------------------------------------------------------------ metrics


def predict(result: Dict[str, Any], threshold: float) -> Optional[str]:
    """What acting on this judgment at `threshold` would have done, or None with no judgment.

    `abstain` is `unknown` or an answer below the threshold, which the provider reads the same
    way: the deterministic answer stands. It is never a pass.
    """
    judgment, confidence = result.get("judgment"), result.get("confidence")
    if judgment is None or confidence is None:
        return None
    if judgment == jev.UNKNOWN or confidence < threshold:
        return ABSTAIN
    return judgment


def _counted(results, threshold):
    correct = 0
    agreed = 0
    confusion = {}
    for result in results:
        call = predict(result, threshold)
        label = result.get("label")
        if label:
            row = confusion.setdefault(label, {})
            key = call if call is not None else "no_judgment"
            row[key] = row.get(key, 0) + 1
            if call == label:
                correct += 1
        deterministic = (CONFIRM if result.get("deterministic_answer") in DETERMINISTIC_CONFIRM
                         else PROCEED)
        if call == deterministic:
            agreed += 1
    return correct, agreed, confusion


def fit_threshold(results: List[Dict[str, Any]]) -> Optional[float]:
    """The threshold with the best accuracy on these results, or None when none can be fitted.

    Candidates are the confidences actually observed, so the sweep only ever tries a cutoff that
    changes an answer. Ties go to the higher threshold: two cutoffs that score the same on this
    split are not equally good, and the one that overrides fewer deterministic answers is the
    one whose mistakes are cheaper.
    """
    labelled = [r for r in results if r.get("label") and r.get("confidence") is not None]
    if not labelled:
        return None
    candidates = sorted(set([0.0] + [round(float(r["confidence"]), 6) for r in labelled]))
    best = None
    for threshold in candidates:
        correct = _counted(labelled, threshold)[0]
        score = correct / float(len(labelled))
        if best is None or score > best[0] + 1e-12 or (abs(score - best[0]) <= 1e-12
                                                       and threshold > best[1]):
            best = (score, threshold)
    return best[1]


def calibration(results: List[Dict[str, Any]], bins: int = CALIBRATION_BINS) -> Dict[str, Any]:
    """Bin the judged cases by confidence and compare each bin's confidence to its accuracy.

    The figure is the expected calibration error: the weighted mean of that gap. It is reported
    over the raw judgment rather than the thresholded one, because the question it answers is
    whether the number the service calls a confidence behaves like one — which has to be true
    before a threshold over it means anything.
    """
    judged = [r for r in results if r.get("label") and r.get("confidence") is not None
              and r.get("judgment") is not None]
    table = []
    for index in range(bins):
        low, high = index / float(bins), (index + 1) / float(bins)
        inside = [r for r in judged
                  if low <= r["confidence"] < high or (index == bins - 1 and r["confidence"] == 1)]
        if not inside:
            continue
        confidence = sum(r["confidence"] for r in inside) / float(len(inside))
        accuracy = sum(1 for r in inside if r["judgment"] == r["label"]) / float(len(inside))
        table.append({"low": round(low, 4), "high": round(high, 4), "cases": len(inside),
                      "confidence": round(confidence, 4), "accuracy": round(accuracy, 4)})
    error = _ece(judged, bins)
    return {"bins": table, "cases": len(judged),
            "ece": None if error is None else round(error, 4),
            "ci95": _ece_interval(judged, bins),
            "resamples": BOOTSTRAP_RESAMPLES if len(judged) > 1 else 0}


def _ece(judged, bins):
    if not judged:
        return None
    total = 0.0
    for index in range(bins):
        low, high = index / float(bins), (index + 1) / float(bins)
        inside = [r for r in judged
                  if low <= r["confidence"] < high or (index == bins - 1 and r["confidence"] == 1)]
        if not inside:
            continue
        confidence = sum(r["confidence"] for r in inside) / float(len(inside))
        accuracy = sum(1 for r in inside if r["judgment"] == r["label"]) / float(len(inside))
        total += len(inside) / float(len(judged)) * abs(accuracy - confidence)
    return total


def _ece_interval(judged, bins):
    """A percentile bootstrap interval on the calibration error, or None under two cases.

    An interval is the difference between "0.08" and "0.08, and a re-sample of this log could
    as easily have said 0.2". The resample stream is seeded from the cases themselves, so the
    interval is a property of the input and not of when the command was run.
    """
    if len(judged) < 2:
        return None
    ordered = sorted(judged, key=lambda r: r["content_hash"])
    stream = _Stream("|".join(r["content_hash"] for r in ordered))
    errors = []
    for _ in range(BOOTSTRAP_RESAMPLES):
        sample = [ordered[stream.below(len(ordered))] for _ in range(len(ordered))]
        value = _ece(sample, bins)
        if value is not None:
            errors.append(value)
    errors.sort()
    if not errors:
        return None
    low = errors[int(0.025 * (len(errors) - 1))]
    high = errors[int(0.975 * (len(errors) - 1))]
    return [round(low, 4), round(high, 4)]


def _percentile(values, share):
    if not values:
        return None
    ordered = sorted(values)
    index = min(int(share * (len(ordered) - 1) + 0.5), len(ordered) - 1)
    return round(ordered[index], 3)


def metrics(results: List[Dict[str, Any]], threshold: Optional[float],
            bins: int = CALIBRATION_BINS, usd_per_mtok: Optional[float] = None,
            timed: bool = False) -> Dict[str, Any]:
    """Everything the report says about one point on one split.

    `accuracy` counts a case correct only when the judgment named the label. An error, an
    unavailable case and an abstention are each in `unusable` and none of them is a pass, so a
    run that mostly failed reads as a low accuracy rather than as a high one over the few that
    answered; `accuracy_judged` is the same rate over the cases that did answer, for reading the
    two apart.
    """
    labelled = [r for r in results if r.get("label")]
    judged = [r for r in labelled if r.get("judgment") is not None]
    correct, agreed, confusion = (_counted(labelled, threshold) if threshold is not None
                                  else (0, 0, {}))
    tokens = [r["usage"]["input_tokens"] for r in results
              if isinstance(r.get("usage"), dict)]
    latencies = [r["latency_ms"] for r in results if isinstance(r.get("latency_ms"), (int, float))]
    output = [r["usage"]["output_tokens"] for r in results if isinstance(r.get("usage"), dict)]
    cost = None
    if usd_per_mtok is not None and results:
        cost = round((sum(tokens) + sum(output)) / 1e6 * usd_per_mtok / len(results) * 1000, 4)
    return {
        "cases": len(results), "labelled": len(labelled),
        "unlabelled": len(results) - len(labelled),
        "threshold": threshold,
        "accuracy": (round(correct / float(len(labelled)), 4)
                     if threshold is not None and labelled else None),
        "accuracy_judged": (round(sum(1 for r in judged
                                      if predict(r, threshold) == r["label"]) / float(len(judged)),
                                  4)
                            if threshold is not None and judged else None),
        "agreement_deterministic": (round(agreed / float(len(results)), 4)
                                    if threshold is not None and results else None),
        "confusion": confusion,
        "calibration": calibration(results, bins),
        "unusable": {
            "unavailable": sum(1 for r in results if r.get("status") == "unavailable"),
            "error": sum(1 for r in results if r.get("status") == "error"),
            "abstained": sum(1 for r in results if r.get("judgment") == jev.UNKNOWN),
            "errors_seen": sorted(set(str(r["error"]) for r in results if r.get("error"))),
        },
        "input_tokens": sum(tokens), "output_tokens": sum(output),
        "usd_per_1000_decisions": cost,
        # Null unless the client was the live one: a replay's latency is this runner's, and a
        # number that answers a different question from the one its name asks is worse than
        # none. It is also what keeps a replayed report byte-identical between runs.
        "latency_ms": {"p50": _percentile(latencies, 0.5) if timed else None,
                       "p95": _percentile(latencies, 0.95) if timed else None,
                       "measured": bool(timed)},
        "models": sorted(set(str(r["model"]) for r in results if r.get("model"))),
    }


def flip_rate(passes: List[List[Dict[str, Any]]]) -> Dict[str, Any]:
    """The share of cases whose judgment was not the same in every pass.

    Over a replay this is zero by construction and the report says which source it came from: a
    recorded response cannot disagree with itself, so a zero here is evidence about the runner
    and not about the service.
    """
    if len(passes) < 2:
        return {"passes": len(passes), "rate": None, "cases": 0}
    first = passes[0]
    flipped = 0
    for index in range(len(first)):
        seen = set(str(run[index].get("judgment")) for run in passes if index < len(run))
        if len(seen) > 1:
            flipped += 1
    return {"passes": len(passes), "cases": len(first),
            "rate": round(flipped / float(len(first)), 4) if first else None}


# ------------------------------------------------------------------ the run


def report(rows: List[Dict[str, Any]], client, pack: Optional[packs.Pack] = None,
           point: Optional[str] = None, dev_share: int = DEV_SHARE,
           bins: int = CALIBRATION_BINS, repeats: int = 1,
           allowlist: Optional[controls.Controls] = None,
           budget: Optional[jev.Budget] = None,
           usd_per_mtok: Optional[float] = None,
           source: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """The whole evaluation as a JSON-safe dict. Carries no clock, so a re-run is byte-identical.

    Per point: the threshold fitted on `dev`, then that threshold's metrics on `dev` and on
    `heldout`. A point with no labelled dev case is reported with a null threshold and null
    rates — unfitted is a finding, and a global default dressed up as a measurement is not.
    """
    pack = packs.get(packs.DECISION_ID) if pack is None else pack
    cases = cases_from_rows(rows, point, dev_share)
    if not cases:
        raise EvalError("no replayable decision rows" + (" at " + point if point else "")
                        + "; the log holds no row with input text")
    passes = [judge(cases, client, pack, allowlist, budget=budget)
              for _ in range(max(int(repeats), 1))]
    results = passes[0]
    timed = getattr(client, "name", "") != jev.ReplayClient.name
    points = {}
    for name in sorted(set(r["point"] for r in results)):
        group = [r for r in results if r["point"] == name]
        dev = [r for r in group if r["split"] == DEV]
        held = [r for r in group if r["split"] == HELDOUT]
        threshold = fit_threshold(dev)
        points[name] = {
            "action_class": POINT_ACTIONS.get(name, DEFAULT_ACTION),
            "threshold": threshold,
            "threshold_fitted_on": DEV if threshold is not None else None,
            "unfitted_reason": None if threshold is not None else
                               "no labelled case on the dev split",
            DEV: metrics(dev, threshold, bins, usd_per_mtok, timed),
            HELDOUT: metrics(held, threshold, bins, usd_per_mtok, timed),
        }
    return {
        "pack": pack.identity(),
        "source": dict({"rows": len(rows), "cases": len(cases),
                        "labelled": sum(1 for c in cases if c["label"]),
                        "point": point or "(all)"}, **(source or {})),
        "split": {"dev_share": dev_share, "seed": "input_sha256", "method": "content hash"},
        "flip": flip_rate(passes),
        "points": points,
        "caveats": list(CAVEATS),
    }


CAVEATS = (
    "`grade-bash` logs a row only where the harness answered `ask` or `deny`, so this set is "
    "the prompts, never the commands that were allowed through without one.",
    "`ran` is the user approving a command that was asked about: evidence the prompt was "
    "unnecessary, not proof of it.",
    "`not_run` does not separate a refusal from an interrupted turn or a crashed session.",
    "A confidence is the service's own number and is not a probability of correctness; the "
    "calibration figure is what says how far the two are apart on this set.",
    "A threshold is fitted per decision point on the dev split and holds for this pack version "
    "and this workload alone.",
    "Latency under `--replay` measures this runner, not the service.",
)


def render(data: Dict[str, Any], split: str = HELDOUT) -> List[str]:
    """The report as lines, for a terminal. The file is the artifact; this is the glance.

    `split` chooses which side the rates are read off; the file always carries both, because a
    run that wrote only the split it was asked for could not be checked for overfitting later.
    """
    split = split if split in SPLITS else HELDOUT
    pack = data["pack"]
    lines = ["pack " + pack["pack_id"] + packs.SEPARATOR + pack["pack_version"]
             + " (" + pack["pack_hash"][:12] + ")",
             "cases " + str(data["source"]["cases"]) + ", labelled "
             + str(data["source"]["labelled"]) + ", split "
             + str(data["split"]["dev_share"]) + "/" + str(100 - data["split"]["dev_share"])
             + " by " + data["split"]["seed"] + "; rates on " + split]
    head = ("%-20s%10s%9s%9s%9s%8s" % ("point", "threshold", "accuracy", "agree", "ece",
                                       "unusbl"))
    lines += [head, "-" * len(head)]
    for name in sorted(data["points"]):
        block = data["points"][name]
        shown = block[split]
        unusable = sum(v for k, v in shown["unusable"].items() if isinstance(v, int))
        lines.append("%-20s%10s%9s%9s%9s%8d" % (
            name[:20],
            "-" if block["threshold"] is None else "%.3f" % block["threshold"],
            _cell(shown["accuracy"]), _cell(shown["agreement_deterministic"]),
            _cell(shown["calibration"]["ece"]), unusable))
    if data["flip"]["rate"] is not None:
        lines.append("flip rate over %d passes: %.3f" % (data["flip"]["passes"],
                                                         data["flip"]["rate"]))
    return lines


def _cell(value):
    return "-" if value is None else "%.3f" % value


def write(data: Dict[str, Any], path) -> str:
    """Write the report and return the path. Sorted and indented, so a diff of two runs reads."""
    target = str(path)
    with open(target, "w", encoding="utf-8") as stream:
        stream.write(json.dumps(data, indent=2, sort_keys=True) + "\n")
    return target
