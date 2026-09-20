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

    tiered         rewrite `model` to one tier below the session model; the weakest class on
                   the ladder is the floor; refuse the top tier by request
    session-model  leave it alone
    off            ask before every spawn, named or not

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


def is_bare(tool_input):
    kind = tool_input.get("subagent_type")
    return not tool_input.get("model") and (not kind or kind == "general-purpose")


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
    ladder = posture.ladder() if posture else []
    if len(ladder) < 2:
        print(json.dumps({"systemMessage": f"{HOOK}: the adapter's class table names no tier to move a "
                          "spawn to, so this one runs as written; check the harness installation"}))
        return
    if tier_of(tool_input.get("model"), ladder) == ladder[0]:
        kind = tool_input.get("subagent_type")
        named = bool(kind) and kind != "general-purpose"
        declared = defined_tier(kind, payload.get("cwd"), ladder) if named else None
        if declared == ladder[0]:
            return  # the role declares the top class itself; the request only repeats it
        updated = dict(tool_input, model=declared or ladder[1])
        emit({"updatedInput": updated},
             system_message=f"{HOOK}: {ladder[0]} is reached through a role that declares it, not by request; "
                            f"{kind if named else 'this spawn'} runs on {updated['model']}")
        return
    if not is_bare(tool_input):
        return
    session = transcript_model(payload.get("transcript_path"))
    current = tier_of(session, ladder)
    if session and current is None:
        # A lineup change the ladder has not caught up with must not pass for "nothing to do".
        print(json.dumps({"systemMessage": f"{HOOK}: the session model {session} is not on the ladder "
                          f"({', '.join(ladder)}), so this bare subagent stays on it; name a model or a role"}))
        return
    if current is None or current == ladder[-1]:
        return
    below = ladder[ladder.index(current) + 1]
    updated = dict(tool_input)
    updated["model"] = below
    emit({"updatedInput": updated},
         system_message=f"{HOOK}: bare subagent runs on {below}, one tier below the session's {current}")


if __name__ == "__main__":
    main()
