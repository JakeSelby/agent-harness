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


def transcript_model(path):
    """The model on the newest main-line assistant record, reading only the transcript's tail."""
    if not path:
        return None
    try:
        with open(path, "rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - TAIL_BYTES))
            tail = fh.read().decode("utf-8", "replace")
    except Exception:
        return None
    for line in reversed(tail.splitlines()):
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


def defined_tier(kind, cwd, ladder):
    """The ladder name an agent definition's `model:` line carries, project before user, or None."""
    if not isinstance(kind, str) or not AGENT_NAME.fullmatch(kind):
        return None
    roots = ([Path(cwd) / ".claude" / "agents"] if isinstance(cwd, str) and cwd else []) + [Path.home() / ".claude" / "agents"]
    for root in roots:
        try:
            lines = (root / (kind + ".md")).read_text(encoding="utf-8").split("---", 2)[1].splitlines()
        except Exception:
            continue
        for line in lines:
            key, _, value = line.partition(":")
            if key.strip() == "model":
                return tier_of(value, ladder)
        return None
    return None


def is_unnamed(tool_input):
    """A spawn that named no agent definition, whatever model it asked for."""
    kind = tool_input.get("subagent_type")
    return not kind or kind == "general-purpose"


def is_bare(tool_input):
    return not tool_input.get("model") and is_unnamed(tool_input)


def agent_installed(kind, cwd):
    """Whether an agent definition by that name exists where `defined_tier` reads.

    A reroute names a `subagent_type` the tool must be able to resolve, so a worker definition
    a machine has not synced yet is a reason not to reroute at all, never a failed spawn.
    """
    if not isinstance(kind, str) or not AGENT_NAME.fullmatch(kind):
        return False
    roots = ([Path(cwd) / ".claude" / "agents"] if isinstance(cwd, str) and cwd else []) + [Path.home() / ".claude" / "agents"]
    return any((root / (kind + ".md")).is_file() for root in roots)


def band_route(posture, models, cwd):
    """`(worker role, its model, its row, notice)` for a spawn that named nothing; parts may be None.

    The cost table is read here and nowhere else in this hook, so a spawn that named a role
    never pays for it. A variant with no `default_band` — and a table that would not resolve —
    routes nothing, which is what keeps 0.10.0 behaviour byte for byte.
    """
    try:
        table = posture.cost_table()
    except Exception:
        return None, None, None, None
    band = table.get("default_band")
    if band not in getattr(posture, "BANDS", ()):
        return None, None, None, None
    worker = posture.BAND_ROLES[band]
    if not agent_installed(worker, cwd):
        return None, None, None, ("no " + worker + " definition is installed, so this spawn is not "
                                  "routed to the variant's default band; run `harness sync`")
    row = posture.row_for(table, worker) or {}
    model = models.get(row.get("class")) if table.get("class_applies") else None
    return worker, model, row, None


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


def routed_message(worker, model, row, requested):
    """The one line a reroute says: where the spawn went, on what, and how to choose next time."""
    detail = [("model " + requested + " as asked") if requested else (row.get("class") or model)]
    if row.get("effort"):
        detail.append(row["effort"] + " effort")
    shown = ", ".join(part for part in detail if part)
    return (f"{HOOK}: unnamed subagent routed to {worker}" + (f" ({shown})" if shown else "") +
            "; spawn worker-a, worker-b or worker-c to choose the band")


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
    if len(ladder) < 2:
        # Only a call whose model this hook would have decided — a bare spawn, or one asking for
        # a class by name — is worth a notice; a named role with its own model is not this hook's.
        if is_bare(tool_input) or tool_input.get("model"):
            print(json.dumps({"systemMessage": f"{HOOK}: the adapter's class table names no tier to move a "
                              "spawn to, so this one runs as written; check the harness installation"}))
        return
    # Where a spawn that named nothing goes, which only the cost table knows. Built here and
    # only here, so a spawn naming a role never reads a sidecar.
    worker = model = row = notice = None
    if posture and is_unnamed(tool_input) and hasattr(posture, "row_for"):
        worker, model, row, notice = band_route(posture, models, payload.get("cwd"))
    if tier_of(tool_input.get("model"), ladder) == ladder[0]:
        kind = tool_input.get("subagent_type")
        named = bool(kind) and kind != "general-purpose"
        declared = defined_tier(kind, payload.get("cwd"), ladder) if named else None
        if declared == ladder[0]:
            return  # the role declares the top class itself; the request only repeats it
        updated = dict(tool_input, model=declared or ladder[1])
        message = (f"{HOOK}: {ladder[0]} is reached through a role that declares it, not by request; "
                   f"{kind if named else 'this spawn'} runs on {updated['model']}")
        if worker:
            # The band still decides where the work lands; the class it would have carried does
            # not, because a requested top class is demoted whoever asked for it.
            updated["subagent_type"] = worker
            message += ", as " + worker
        emit({"updatedInput": updated}, system_message=message)
        return
    if worker:
        updated = dict(tool_input, subagent_type=worker)
        requested = tool_input.get("model")
        message = None
        if not requested:
            if model:
                updated["model"] = model
            else:
                # The band names no class this adapter maps, so the spawn falls to today's rule.
                fallback, message = one_rung(payload, ladder)
                if fallback:
                    updated["model"] = fallback
        emit({"updatedInput": updated},
             system_message=routed_message(worker, updated.get("model"), row or {}, requested)
             + (" · " + message if message else ""))
        return
    if not is_bare(tool_input):
        return
    below, message = one_rung(payload, ladder)
    if below is None:
        if message:
            print(json.dumps({"systemMessage": f"{HOOK}: {message}"
                              + (" · " + notice if notice else "")}))
        return
    updated = dict(tool_input, model=below)
    emit({"updatedInput": updated},
         system_message=f"{HOOK}: {message}" + (" · " + notice if notice else ""))


if __name__ == "__main__":
    main()
