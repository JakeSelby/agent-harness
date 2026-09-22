"""Cache-prefix stability, read back out of the usage ledger.

`primitives/rules/cache-hygiene.md` asks a session to hold its cached prefix mid-task, and
nothing reported whether it did. A change to the tool set, the MCP list, the model or the
effort dial turns the next turn's cache reads into cache writes, and the only visible symptom
is a larger bill. The figure here is `cache_write / (cache_read + cache_write)` over a
session's own rows: the share of the prefix the provider had to re-write rather than serve.

It measures and does not enforce. Nothing in this module denies, warns or blocks a prefix
change; `harness usage --by prefix` is retrospective and read-only.

Two things are deliberately not inferred:

- **Zero is never used for unknown.** A row that carries no cache fields, one whose two cache
  fields are both zero, and one reporting reads against no writes at all are all reported as
  `unknown`. The last is the Codex shape: it exports no per-turn cache-write figures
  (`adapters/codex/capabilities.json`), and a 0% miss ratio would read as a session that held
  its prefix perfectly rather than as a runtime that cannot say.
- **The step is located no finer than the ledger records.** The only within-session slicing an
  existing row carries is its `days` map, which holds the same token fields and that day's turn
  count. So the step is found between day slices and named by the turn index the stepping slice
  opens on, which is the finest index the ledger can honestly support without a new event.
"""

# The rise in miss ratio between two consecutive slices that counts as a step rather than
# drift. A held prefix wanders by a few points as turns differ in size; twenty points is the
# shape of a prefix that was re-written, not one that grew.
MISS_STEP = 0.2


def _count(row, name):
    """A row's token field as a non-negative int, or None when it is absent or unreadable."""
    value = row.get(name)
    if value is None:
        return None
    try:
        value = int(value)
    except (TypeError, ValueError):
        return None
    return max(value, 0)


def miss_ratio(row):
    """`cache_write / (cache_read + cache_write)`, or None when the row cannot say.

    None covers four cases that all mean the same thing to a reader: a field is missing, a field
    is unreadable, nothing at all was served from or written to the cache, or the row reports
    reads with no writes. That last one is the Codex shape — millions of cached reads against a
    flat zero — and it is a gap in what the runtime exports, not a prefix written for free: a
    session that read a prefix wrote it first. Returning 0.0 for any of them would claim a
    perfectly held prefix, which is the opposite of what the row knows.
    """
    read, write = _count(row, "cache_read"), _count(row, "cache_write")
    if read is None or write is None or not write:
        return None
    return write / (read + write)


def step(row):
    """The sharpest rise in miss ratio between consecutive day slices, or None.

    Returns `{"turn", "day", "before", "after"}`, where `turn` is the 1-based index of the
    first turn of the slice whose ratio rose. Slices that cannot state a ratio break the chain
    rather than counting as zero, so a quiet day between two busy ones cannot manufacture a
    step; the comparison is always against the last slice that had a ratio.
    """
    days = row.get("days")
    if not isinstance(days, dict):
        return None
    found, turn, previous = None, 1, None
    for day in sorted(days):
        slice_ = days[day]
        if not isinstance(slice_, dict):
            continue
        ratio = miss_ratio(slice_)
        if ratio is not None:
            if previous is not None and ratio - previous[1] >= MISS_STEP:
                rise = ratio - previous[1]
                if found is None or rise > found["rise"]:
                    found = {"turn": turn, "day": day, "before": previous[1],
                             "after": ratio, "rise": rise}
            previous = (day, ratio)
        turn += max(_count(slice_, "turns") or 0, 0)
    if found is not None:
        found.pop("rise", None)
    return found


def figure(row):
    """One session's cache-prefix line: identity, totals, ratio and step."""
    models = row.get("models") if isinstance(row.get("models"), list) else []
    if not models and row.get("model"):
        models = [row["model"]]
    return {
        "session_id": row.get("session_id") or "(unknown)",
        "repo": row.get("repo") or "(no repo)",
        "models": [name for name in models if isinstance(name, str) and name],
        "ended": row.get("ended") or "",
        "turns": _count(row, "turns"),
        "cache_read": _count(row, "cache_read"),
        "cache_write": _count(row, "cache_write"),
        "ratio": miss_ratio(row),
        "step": step(row),
    }


def figures(ledger, cutoff=""):
    """The per-session figures for the rows in the window, oldest session first.

    Only session rows are read. A Claude Code subagent's tokens are already inside its
    session's row, and a row's prefix is a property of the session's own context, not of a
    delegated run that started from an empty one.
    """
    found = []
    for row in ledger:
        if not isinstance(row, dict):
            continue
        if (row.get("kind") or "session") != "session":
            continue
        if (row.get("ended") or "") < cutoff:
            continue
        found.append(figure(row))
    found.sort(key=lambda item: (item["ended"], item["session_id"]))
    return found


def _cell(value, width, unknown="unknown"):
    return "{:>{}}".format(unknown if value is None else "{:,}".format(value), width)


def report(ledger, cutoff, days, say):
    """`harness usage --by prefix`: the miss ratio per session, and where it jumped."""
    found = figures(ledger, cutoff)
    if not found:
        say("no sessions recorded in the last {} day(s)".format(days))
        return 0
    head = ("{:<20}{:<16}{:<22}{:>7}{:>14}{:>14}{:>9}  {}"
            .format("session", "repo", "models", "turns", "cache_read", "cache_write",
                    "miss", "step"))
    say("The miss ratio measures cache-prefix stability; nothing here denies a prefix change.")
    say(head)
    say("-" * len(head))
    unknown = 0
    for item in found:
        if item["ratio"] is None:
            unknown += 1
            ratio = "{:>9}".format("unknown")
        else:
            ratio = "{:>9.0%}".format(item["ratio"])
        jump = item["step"]
        detail = "-" if jump is None else ("turn {} ({}): {:.0%} -> {:.0%}"
                                           .format(jump["turn"], jump["day"],
                                                   jump["before"], jump["after"]))
        say("{:<20}{:<16}{:<22}{}{}{}{}  {}"
            .format(item["session_id"][:19], item["repo"][:15],
                    ("+".join(item["models"]) or "(unknown)")[:21],
                    _cell(item["turns"], 7, "?"), _cell(item["cache_read"], 14),
                    _cell(item["cache_write"], 14), ratio, detail))
    say("-" * len(head))
    stepped = sum(1 for item in found if item["step"] is not None)
    say("{} session(s), {} with a mid-session step, {} reporting no cache figures"
        .format(len(found), stepped, unknown))
    return 0
