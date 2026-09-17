#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""PreToolUse hook: apply the delegation stance to every subagent spawn, whoever wrote the brief.

The stance's tiers travel as frontmatter on the agents the harness ships, so they reach any
spawn that names one. A spawn that names nothing — no `subagent_type`, or `general-purpose`,
and no `model` — is what a planning framework or a plugin produces when its skill text says
"launch a subagent", and nothing else in the harness reaches it. This hook does. A call that
names an agent definition or passes `model` is left exactly as it was: the definition or the
caller already decided.

What a bare spawn gets depends on the `delegation` stance, read from
`HARNESS_STANCE_DELEGATION` or `~/.config/agent-harness/config.json`:

    tiered         rewrite `model` to one tier below the session model; `haiku` is the floor
    session-model  leave it alone
    off            ask before every spawn, named or not

The session model is read from the newest main-line assistant record in the transcript, which
Claude Code writes once a response has started executing tools, so a spawn in a session's very
first response is left alone: nothing else says what the session runs on (the `model` key in
settings is a default the session may not be using), and an unknown tier is left untouched
rather than guessed. Never fails: every error falls through and the call runs as written.

Test: printf '%s' '{"tool_name":"Agent","tool_input":{"prompt":"x"}}' | HARNESS_STANCE_DELEGATION=off python3 tier-agent-spawns.py
"""
import json
import os
import sys
from pathlib import Path

CONFIG = Path.home() / ".config" / "agent-harness" / "config.json"
LADDER = ["fable", "opus", "sonnet", "haiku"]
DEFAULT_STANCE = "tiered"
TAIL_BYTES = 1 << 20
HOOK = "tier-agent-spawns hook"


def load(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def stance():
    value = os.environ.get("HARNESS_STANCE_DELEGATION")
    if value:
        return value
    config = load(CONFIG) or {}
    return (config.get("stances") or {}).get("delegation") or DEFAULT_STANCE


def tier_of(model):
    """The ladder name inside a model id or alias, or None for anything the ladder lacks."""
    if not isinstance(model, str):
        return None
    low = model.lower()
    for name in LADDER:
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
        if tier_of(model):
            return model
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
    variant = stance()
    if variant == "off":
        emit({
            "permissionDecision": "ask",
            "permissionDecisionReason": f"the delegation stance is off: confirm this spawn or do the work inline ({HOOK})",
        })
        return
    if variant != "tiered" or not is_bare(tool_input):
        return
    current = tier_of(transcript_model(payload.get("transcript_path")))
    if current is None or current == LADDER[-1]:
        return
    below = LADDER[LADDER.index(current) + 1]
    updated = dict(tool_input)
    updated["model"] = below
    emit({"updatedInput": updated},
         system_message=f"{HOOK}: bare subagent runs on {below}, one tier below the session's {current}")


if __name__ == "__main__":
    main()
