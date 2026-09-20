#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""PreToolUse hook: apply the delegation stance to every subagent spawn, whoever wrote the brief.

The stance's tiers travel as frontmatter on the agents the harness ships, so they reach any
spawn that names one. A spawn that names nothing — no `subagent_type`, or `general-purpose`,
and no `model` — is what a planning framework or a plugin produces when its skill text says
"launch a subagent", and nothing else in the harness reaches it. This hook does. A call that
names an agent definition or passes `model` is left as it was, with one exception: the
strongest class is reached through a role that declares it, never by request. A spawn that
asks for it by `model` gets the model its agent definition names instead, or the class below
when there is no definition to read — so neither an orchestrator nor a framework's skill text
("run reviewers at the session's capability") can put ad-hoc work on the scarcest tier. The
request is rewritten, never removed: a rewrite survives composition with other hooks.

What a bare spawn gets depends on the `delegation` stance, which `posture.py` resolves for
every hook alike:

    tiered         route it to the cost variant's default band worker, on that band's class;
                   with no default band, rewrite `model` to one tier below the session model,
                   the weakest class on the ladder being the floor; refuse the top tier by request
    session-model  leave it alone
    off            ask before every spawn, named or not

The band workers exist because the `Agent` tool has no effort input: a spawn that names nothing
inherits the session's effort, and only an agent definition can carry the posture's. So a spawn
with no `subagent_type`, or `general-purpose`, is rewritten to `worker-a`, `worker-b` or
`worker-c` — the variant's `default_band` — and the orchestrator that wanted a different band
spawns that worker by name. A machine whose worker definitions are not installed is not routed
at all: a `subagent_type` the tool cannot resolve would fail the spawn.

The ladder is the adapter's `bindings.json` class table, strongest class first, matched as
substrings of the model ids a transcript records; no model name is written here.

A repository that carries a planning framework is tiered like any other. The framework keeps
its personas, prompts and review structure; model and effort are the harness's to choose, and
the framework's override templates name the harness's roles where the recipe allows, which is
what carries tools and effort.

A spawn issued while the cost variant's `max_parallel` subagents are already in flight carries a
note saying so, with this spawn's budget and the fan-out's, counted from the same transcript
tail. It is a stance and not a limit: the note never denies, never asks, and never changes the
call. A variant whose `max_parallel` is null has no width to exceed and gets no note.

The session model is read from the newest main-line assistant record in the transcript, which
Claude Code writes once a response has started executing tools, so a spawn in a session's very
first response is left alone: nothing else says what the session runs on (the `model` key in
settings is a default the session may not be using). A session model the ladder does not know
is left untouched rather than guessed, and the hook says so, because a new model name would
otherwise switch tiering off without a sound. Never fails: every error falls through and the
call runs as written.

Test: printf '%s' '{"tool_name":"Agent","tool_input":{"prompt":"x"}}' | HARNESS_STANCE_DELEGATION=off python3 tier-agent-spawns.py
"""
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

HOOKS = Path(__file__).resolve().parent
DEFAULT_STANCE = "tiered"
TAIL_BYTES = 1 << 20
HOOK = "tier-agent-spawns hook"
AGENT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")


def sibling(name):
    """A module beside this hook, or None. A hook must never stop a spawn because an import failed."""
    try:
        spec = importlib.util.spec_from_file_location(
            "harness_" + name.replace("-", "_"), str(HOOKS / (name + ".py")))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception:
        return None


def tier_of(model, ladder):
    """The ladder name inside a model id or alias, or None for anything the ladder lacks."""
    if not isinstance(model, str):
        return None
    low = model.lower()
    for name in ladder:
        if name in low:
            return name
    return None


def tail(path):
    """The last `TAIL_BYTES` of a transcript as text, or None. The first line may be cut in half."""
    if not path:
        return None
    try:
        with open(path, "rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - TAIL_BYTES))
            return fh.read().decode("utf-8", "replace")
    except Exception:
        return None


def transcript_model(path):
    """The model on the newest main-line assistant record, reading only the transcript's tail."""
    tail_text = tail(path)
    if tail_text is None:
        return None
    for line in reversed(tail_text.splitlines()):
        if '"assistant"' not in line:
            continue
        try:
            record = json.loads(line)
        except Exception:
            continue
        if not isinstance(record, dict) or record.get("type") != "assistant" or record.get("isSidechain"):
            continue
        message = record.get("message")
        model = message.get("model") if isinstance(message, dict) else None
        # Placeholder records ("<synthetic>") name no model; anything else is the session's, known or not.
        if isinstance(model, str) and model and not model.startswith("<"):
            return model
    return None


def in_flight(path):
    """`Agent` calls in the transcript tail that no result has come back for yet.

    Parallel spawns issued in one assistant message all see the same tail, and the record
    carrying that message's `tool_use` blocks is written before the tools run, so siblings of
    this call are counted. One undercount remains and is not worth chasing: an `Agent` call
    whose record has not reached the tail — older than the 1 MiB window, or not yet flushed —
    is invisible, so a very wide fan-out reads low rather than high.
    """
    text = tail(path)
    if text is None:
        return 0
    started, finished = set(), set()
    for line in text.splitlines():
        if '"tool_use"' not in line and '"tool_result"' not in line:
            continue
        try:
            record = json.loads(line)
        except Exception:
            continue  # the tail's first line is usually cut in half
        if not isinstance(record, dict) or record.get("isSidechain"):
            continue
        message = record.get("message")
        blocks = message.get("content") if isinstance(message, dict) else None
        for block in blocks if isinstance(blocks, list) else []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use" and block.get("name") == "Agent":
                started.add(block.get("id"))
            elif block.get("type") == "tool_result":
                finished.add(block.get("tool_use_id"))
    return len(started - finished)


def fanout_note(payload, posture, role):
    """The line a spawn wider than the posture's parallel width carries, or None.

    Informational only: the width is a stance, not a limit, so this hook never denies a spawn
    for being the seventh. The table is read only once something is already in flight, because
    a width of one or more can never be exceeded by a single call.
    """
    count = in_flight(payload.get("transcript_path"))
    if count < 1 or posture is None:
        return None
    try:
        table = posture.cost_table()
        width = table.get("switches", {}).get("max_parallel")
        if not isinstance(width, int) or isinstance(width, bool) or count + 1 <= width:
            return None
        note = f"{count} subagents in flight against a posture width of {width}"
        row = (posture.row_for(table, role) if role else None) or {}
        tokens = row.get("budget_output_tokens")
        if isinstance(tokens, int) and not isinstance(tokens, bool):
            note += (f"; this spawn's budget is about {tokens:,} output tokens, about "
                     f"{count * tokens:,} across the fan-out")
        return note
    except Exception:
        return None


def with_note(message, note):
    """The one `systemMessage` a call prints: what the hook decided, then the fan-out note."""
    if not note:
        return message
    return (message + " · " + note) if message else (HOOK + ": " + note)


def agents_dirs(cwd):
    """`(project directories, the user's)` where Claude Code resolves an agent definition.

    Project before user, which is the tool's own precedence, and `CLAUDE_CONFIG_DIR` moves the
    user's one exactly as `bin/harness` reads it.
    """
    config = os.environ.get("CLAUDE_CONFIG_DIR")
    user = (Path(config) if config else Path.home() / ".claude") / "agents"
    return ([Path(cwd) / ".claude" / "agents"] if isinstance(cwd, str) and cwd else []), user


def definition(kind, cwd):
    """The frontmatter of the definition a spawn of this type would resolve, or None.

    One reader for every question this hook asks of an agent definition, so "which file would
    the tool use" is answered once. A file that exists but will not parse ends the search the
    way it always has: the tool would resolve it, so no weaker root stands in for it.
    """
    if not isinstance(kind, str) or not AGENT_NAME.fullmatch(kind):
        return None
    project, user = agents_dirs(cwd)
    for root in project + [user]:
        try:
            header = (root / (kind + ".md")).read_text(encoding="utf-8").split("---", 2)[1]
        except Exception:
            continue
        fields = {}
        for line in header.splitlines():
            key, sep, value = line.partition(":")
            if sep:
                fields.setdefault(key.strip(), value.strip())
        return fields
    return None


def defined_tier(kind, cwd, ladder):
    """The ladder name an agent definition's `model:` line carries, project before user, or None."""
    fields = definition(kind, cwd)
    return tier_of(fields.get("model"), ladder) if fields else None


def is_unnamed(tool_input):
    """A spawn that named no agent definition, whatever model it asked for."""
    kind = tool_input.get("subagent_type")
    return not kind or kind == "general-purpose"


def is_bare(tool_input):
    return not tool_input.get("model") and is_unnamed(tool_input)


def routable(kind, cwd):
    """`(the user's definition, notice)` for a worker a reroute would name; one of them is None.

    A reroute must land on the definition the harness synced and on no other. A project-level
    `.claude/agents/<worker>.md` outranks the user's, so a repository that ships one would put
    its own instructions on every unnamed spawn of anyone who cloned it: that file is a reason
    to route nothing, named out loud. A machine that has not synced the workers is the same
    answer for the plainer reason that the tool could not resolve the type at all.
    """
    if not isinstance(kind, str) or not AGENT_NAME.fullmatch(kind):
        return None, None
    project, user = agents_dirs(cwd)
    for root in project:
        path = root / (kind + ".md")
        if path.is_file():
            return None, ("this repository ships " + str(path) + ", which would outrank the "
                          "harness's " + kind + ", so this spawn is not routed to the variant's "
                          "default band")
    if not (user / (kind + ".md")).is_file():
        return None, ("no " + kind + " definition is installed, so this spawn is not routed to "
                      "the variant's default band; run `harness sync`")
    return definition(kind, cwd) or {}, None


def band_route(posture, models, cwd):
    """`(route, notice)` for a spawn that named nothing; a route is None when nothing routes it.

    The cost table is read here and nowhere else in this hook, so a spawn that named a role
    never pays for it. A variant with no `default_band` — and a table that would not resolve —
    routes nothing, which is what keeps 0.10.0 behaviour byte for byte.

    The effort a rerouted spawn actually runs at is the installed definition's, because effort
    is written at sync and the `Agent` tool takes none; the row's is what the selected variant
    would write at the next sync. The route carries both so the notice can name the difference.
    """
    try:
        table = posture.cost_table()
    except Exception:
        return None, None
    band = table.get("default_band")
    if band not in getattr(posture, "BANDS", ()):
        return None, None
    worker = posture.BAND_ROLES[band]
    fields, notice = routable(worker, cwd)
    if fields is None:
        return None, notice
    row = posture.row_for(table, worker) or {}
    return {"worker": worker, "row": row,
            "model": models.get(row.get("class")) if table.get("class_applies") else None,
            "effort": fields.get("effort") or row.get("effort"),
            "stale": bool(row.get("effort")) and fields.get("effort") != row.get("effort")}, None


def one_rung(payload, ladder):
    """Today's rule for a spawn that named nothing: `(model one class below, message)`.

    A model of None with a message is a spawn this hook decided not to move and said why; both
    None is a spawn it has nothing to say about — the session is already on the weakest class,
    or the transcript does not yet name a model.
    """
    session = transcript_model(payload.get("transcript_path"))
    current = tier_of(session, ladder)
    if session and current is None:
        # A lineup change the ladder has not caught up with must not pass for "nothing to do".
        return None, (f"the session model {session} is not on the ladder "
                      f"({', '.join(ladder)}), so this bare subagent stays on it; name a model or a role")
    if current is None or current == ladder[-1]:
        return None, None
    below = ladder[ladder.index(current) + 1]
    return below, f"bare subagent runs on {below}, one tier below the session's {current}"


def routed_message(route, model, requested):
    """The one line a reroute says: where the spawn went, on what, and how to choose next time."""
    detail = [("model " + requested + " as asked") if requested
              else (route["row"].get("class") or model)]
    if route.get("effort"):
        detail.append(route["effort"] + " effort")
    shown = ", ".join(part for part in detail if part)
    return (f"{HOOK}: unnamed subagent routed to {route['worker']}" + (f" ({shown})" if shown else "") +
            "; spawn worker-a, worker-b or worker-c to choose the band" +
            (" · the installed definition's effort is not the selected variant's; run "
             "`harness sync` to apply the selected posture" if route.get("stale") else ""))


def say(message):
    """A record carrying nothing but a message, for a call this hook decided not to change."""
    if message:
        print(json.dumps({"systemMessage": message}))


def emit(fields, system_message=None):
    fields["hookEventName"] = "PreToolUse"
    out = {"hookSpecificOutput": fields}
    if system_message:
        out["systemMessage"] = system_message
    print(json.dumps(out))


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    if not isinstance(payload, dict) or payload.get("tool_name") != "Agent":
        return
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return
    posture = sibling("posture")
    variant = posture.selected("delegation", DEFAULT_STANCE, strict=False) if posture else DEFAULT_STANCE
    if variant == "off":
        emit({
            "permissionDecision": "ask",
            "permissionDecisionReason": f"the delegation stance is off: confirm this spawn or do the work inline ({HOOK})",
        })
        return
    if variant != "tiered":
        return
    # Strongest class first, from the adapter's bindings. Without it there is no tier to move a
    # spawn to, so the call runs as written and says why, exactly as an unknown model does.
    models = posture.tier_models() if posture and hasattr(posture, "tier_models") else {}
    ladder = list(models.values())
    kind = tool_input.get("subagent_type")
    named = bool(kind) and kind != "general-purpose"
    if len(ladder) < 2:
        # Only a call whose model this hook would have decided — a bare spawn, or one asking for
        # a class by name — is worth a notice; a named role with its own model is not this hook's.
        message = None
        if is_bare(tool_input) or tool_input.get("model"):
            message = (f"{HOOK}: the adapter's class table names no tier to move a spawn to, so "
                       "this one runs as written; check the harness installation")
        say(with_note(message, fanout_note(payload, posture, kind if named else None)))
        return
    # Where a spawn that named nothing goes, which only the cost table knows. Built here and
    # only here, so a spawn naming a role never reads a sidecar for its route.
    route = notice = None
    if posture and is_unnamed(tool_input) and hasattr(posture, "row_for"):
        route, notice = band_route(posture, models, payload.get("cwd"))
    # The fan-out note prices whichever role this spawn ends up being: the one it named, or the
    # worker it is routed to.
    note = fanout_note(payload, posture, route["worker"] if route else (kind if named else None))
    top = tier_of(tool_input.get("model"), ladder) == ladder[0]
    if top and not route:
        declared = defined_tier(kind, payload.get("cwd"), ladder) if named else None
        if declared == ladder[0]:
            # The role declares the top class itself; the request only repeats it.
            say(with_note(None, note))
            return
        updated = dict(tool_input, model=declared or ladder[1])
        emit({"updatedInput": updated},
             system_message=with_note(
                 f"{HOOK}: {ladder[0]} is reached through a role that declares it, not by request; "
                 f"{kind if named else 'this spawn'} runs on {updated['model']}"
                 + (" · " + notice if notice else ""), note))
        return
    if route:
        updated = dict(tool_input, subagent_type=route["worker"])
        # A request for the top class is not a model this spawn named: it is a request the hook
        # refuses, and refusing it by demoting one rung would let an unnamed spawn beat a band
        # priced below that rung. So the band's own class decides, exactly as if none were asked.
        requested = None if top else tool_input.get("model")
        message = None
        if not requested:
            updated.pop("model", None)
            if route["model"]:
                updated["model"] = route["model"]
            else:
                # The band names no class this adapter maps, so the spawn falls to today's rule.
                fallback, message = one_rung(payload, ladder)
                if fallback:
                    updated["model"] = fallback
        emit({"updatedInput": updated},
             system_message=with_note(
                 routed_message(route, updated.get("model"), requested)
                 + (" · " + message if message else "")
                 + (f" · {ladder[0]} is reached through a role that declares it, not by request"
                    if top else ""), note))
        return
    if not is_bare(tool_input):
        say(with_note(None, note))
        return
    below, message = one_rung(payload, ladder)
    if below is None:
        say(with_note(f"{HOOK}: {message}" + (" · " + notice if notice else "") if message else None,
                      note))
        return
    updated = dict(tool_input, model=below)
    emit({"updatedInput": updated},
         system_message=with_note(f"{HOOK}: {message}" + (" · " + notice if notice else ""), note))


if __name__ == "__main__":
    main()
