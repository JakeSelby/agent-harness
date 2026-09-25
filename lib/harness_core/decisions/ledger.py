"""The usage-ledger row a provider call leaves behind: what it cost, and nothing about what it
asked.

A provider that leaves the machine spends tokens and wall-clock time, and both belong beside the
session spend the ledger already holds — a judgment that costs dollars and is never priced reads
as free, and a call that adds a second to every hook reads as a fast machine. So each call writes
one `kind: "decision"` row into `~/.local/state/agent-harness/usage.jsonl` through the ledger's
own writer, and `harness usage --by provider` prices it from `policy/prices.json` like any other
row. The write is an append under the ledger lock rather than the rewrite `upsert` does: a row
nothing ever replaces must not cost a hook a read and a rewrite of the whole file, and the lock
is what keeps it from interleaving with a session record being refreshed.

What the row may carry is the same allowlist question `controls.py` answers for the wire, decided
the same way: the row is built key by key from a fixed list, so a field nobody named has no way
in. It holds the decision point, the mode, the status, the model ids, the pack and request
hashes, the token counts and the latency. It never holds the outbound state, an answer's prose,
a prompt, a file path or an environment value — `row()` reads none of them, and
`test_jev_decision_rows.py` asserts a row built from a context full of them carries none.

A call whose usage nobody reported is `partial`, which is how the pricing table already spells
"unknown": an unpriced row is named in the report's footer, where a zero would have said the
judgment was free.
"""
import hashlib
import os
import re
import time
from typing import Any, Dict, List, Optional

from .. import decision

KIND = "decision"
# A decision row is written by the harness itself rather than by a client session, so it names
# no runtime of its own. Present because `row_key` reads it on every row.
RUNTIME = "harness"

# The token columns every ledger row is priced on. A Jev response reports `input_tokens` and
# `output_tokens` and there is no third field in its usage contract, so the two cache columns
# are zero rather than unknown: nothing was served from a cache because no cache was offered.
CACHE_COLUMNS = ("cache_read", "cache_write")

_COUNTER = [0]


def _ident(request_hash: Optional[str], now: float) -> str:
    """A key no concurrent call can collide with.

    Two identical requests in one session hash the same, and an `upsert` keyed on that hash
    would keep one row and drop the other; the process, the clock and a counter make the two
    separate records they are.
    """
    _COUNTER[0] += 1
    seed = "|".join([str(request_hash or ""), str(os.getpid()), repr(now), str(_COUNTER[0])])
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


# The one counterparty shape a row may keep verbatim: the slug `decision.counterparty()`
# derives. Both halves are bounded, because a row is kept for months and a branch name has no
# length anyone enforces.
SLUG = re.compile(r"^repo:[A-Za-z0-9._-]{1,64}/[A-Za-z0-9._/-]{1,96}$")


def _counterparty(value: Any) -> str:
    """The counterparty as a row may keep it: the slug shape, or a digest of anything else.

    `counterparty` is a caller's string and part of what goes out in the request, so an
    absolute path can arrive here — and a path on this machine is exactly what a row kept for
    months must not hold. A counterparty this module cannot recognise is a short digest, which
    still groups a report and names nothing.
    """
    slug = str(value or "")
    if SLUG.match(slug):
        return slug
    return "sha256:" + hashlib.sha256(slug.encode("utf-8", "replace")).hexdigest()[:16]


def _repo(counterparty: str) -> str:
    """The repository name inside a kept `repo:<name>/<branch>` slug, or the slug as kept."""
    if not counterparty.startswith("repo:"):
        return counterparty
    return counterparty[len("repo:"):].split("/")[0]


def row(point: Optional[str], mode: str, result: Dict[str, Any], action_class: str,
        counterparty: str, session_id: str = "", now: Optional[float] = None,
        started: Optional[float] = None, judgment: Optional[str] = None,
        severity: Optional[str] = None, base_outcome: Optional[str] = None,
        advised_outcome: Optional[str] = None) -> Dict[str, Any]:
    """One `kind: "decision"` row, built field by field from a result `jev.ask` returned.

    `started` is the call's own start, so a row spans the request rather than the instant it
    finished; with none, the latency on the result is subtracted from `now`.

    The four labels are the decision log's, repeated here rather than joined across two files:
    a call priced on this report is worth reading beside what it judged and what it would have
    changed, and a `shadow` row that named neither would measure nothing. They are labels from
    closed vocabularies — a choice, a level and two outcomes — and never an answer's prose.
    """
    now = time.time() if now is None else now
    usage = result.get("usage") if isinstance(result.get("usage"), dict) else None
    latency = result.get("latency_ms")
    latency = float(latency) if isinstance(latency, (int, float)) else 0.0
    began = now - latency / 1000.0 if started is None else started
    kept = _counterparty(counterparty)
    record = {
        "kind": KIND, "runtime": RUNTIME, "provider": "jev",
        "session_id": str(session_id or ""),
        "agent_id": _ident(result.get("request_hash"), now),
        "repo": _repo(kept), "counterparty": kept,
        "action_class": str(action_class or ""),
        "point": str(point) if point else None,
        "mode": str(mode or ""),
        "status": str(result.get("status") or ""),
        "judgment": judgment, "severity": severity,
        "base_outcome": base_outcome, "advised_outcome": advised_outcome,
        "error": result.get("error") if isinstance(result.get("error"), str) else None,
        "requested_model": result.get("requested_model") or "",
        "model": result.get("model") or "",
        "pack_hash": result.get("pack_hash"), "request_hash": result.get("request_hash"),
        "ms": round(latency, 3),
        "harness_version": _version(),
        "started": _stamp(began), "ended": _stamp(now),
    }
    if usage is None:
        # No usage means no bill anybody can compute. `partial` is what the price table already
        # reads as unknown, so the row is counted as unpriced rather than as zero dollars.
        record["partial"] = True
        record["input"] = None
        record["output"] = None
        for name in CACHE_COLUMNS:
            record[name] = None
        return record
    record["input"] = _count(usage.get("input_tokens"))
    record["output"] = _count(usage.get("output_tokens"))
    for name in CACHE_COLUMNS:
        record[name] = 0
    if record["input"] is None or record["output"] is None:
        record["partial"] = True
    return record


def _count(value: Any) -> Optional[int]:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _stamp(epoch: float) -> str:
    module = decision._hook_module("usage-log")
    if module is None:
        return time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(epoch))
    return module.stamp(epoch)


def _version() -> Optional[str]:
    module = decision._hook_module("usage-log")
    try:
        return module.harness_version() if module is not None else None
    except Exception:
        return None


def append(record: Dict[str, Any], target: Optional[str] = None) -> bool:
    """Write one decision row to the usage ledger. Never raises; says whether it wrote.

    Suppressed with `decision.events_suppressed`, and off entirely when `telemetry.decisions`
    is off: a user who turned provider logging off did not ask for the same call in a second
    file. A failed write costs the record and nothing else — a decision must never depend on a
    ledger, which is the rule `append_event` already follows.
    """
    if decision.suppressed():
        return False
    usage = decision._hook_module("usage-log")
    decisions = decision._ledger()
    if usage is None or decisions is None:
        return False
    try:
        if not decisions.enabled():
            return False
        usage.append_row(record, path=target)
        return True
    except Exception as exc:
        # A swallowed write is unknown, not absent: the failure lands in the errors file every
        # other ledger writer uses, so a run of empty reports has somewhere to be explained.
        try:
            usage.record_error(exc, path=target, where="decision-row")
        except Exception:
            pass
        return False


def rows(path=None) -> List[Dict[str, Any]]:
    """Every decision row in the usage ledger, oldest first. An unreadable file is no rows."""
    module = decision._hook_module("usage-log")
    if module is None:
        return []
    try:
        location = module.usage_path() if path is None else path
        with open(str(location), encoding="utf-8") as stream:
            text = stream.read()
    except (OSError, AttributeError):
        return []
    # The ledger's own reader, so a renamed field is folded here as it is everywhere else.
    return [row for row in module.ledger_rows(text) if row.get("kind") == KIND]
