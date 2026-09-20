#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""PreToolUse on `Agent`: append a return bound to a brief that states none.

`delegation.md` says to bound the brief, and `transcript-hygiene/brief-without-cap` measures
that it is not: 536 hits across 30 percent of sessions. Asking the orchestrator to write the
cap does not work, so the hook writes it instead.

Adapted from unclebob/swarm-forge, whose handoff helper fills the commit SHA from the sender's
HEAD while the constitution says "do not type a SHA". The agent cannot get a field wrong that
it never writes.

What counts as a bound, and which agents are exempt, come from `rule-detectors.py` rather than
a second copy here. If the hook and the detector disagreed, the hook would append text the
detector still counts as missing and the number would never move.
"""
import importlib.util
import json
import sys
from pathlib import Path

HOOK = "harness:brief-guard"
HOOKS = Path(__file__).resolve().parent

# Written so it matches the detector's own cap pattern; a bound the detector cannot see is
# not a bound. `tests/test_brief_guard.py` asserts that parity.
BOUND = ("\n\nReturn at most 400 words: a one-line verdict first, then only what changes a "
         "decision. Write anything longer to a file and return its path, not its contents.")


def sibling(name):
    """A module beside this hook, or None. A hook must never block a spawn because an import failed."""
    try:
        spec = importlib.util.spec_from_file_location(
            "harness_" + name.replace("-", "_"), str(HOOKS / (name + ".py")))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception:
        return None


def detectors():
    """The detector module, or None."""
    return sibling("rule-detectors")


def stance():
    """The selected `delegation` stance, resolved by `posture.py` for every hook alike."""
    module = sibling("posture")
    return module.selected("delegation", "tiered", strict=False) if module else "tiered"


def needs_bound(module, tool_input):
    """True when this brief carries no cap and the agent's own definition carries none either."""
    kind = tool_input.get("subagent_type")
    if isinstance(kind, str) and kind.strip() in module.CAPPED_AGENTS:
        return False
    prompt = tool_input.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return False
    return not module.WORD_CAP_RE.search(prompt)


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
    if stance() == "off":
        # `tier-agent-spawns` already asks before any spawn here; two hooks answering one
        # event is worse than one.
        return
    module = detectors()
    if module is None or not needs_bound(module, tool_input):
        return
    updated = dict(tool_input)
    updated["prompt"] = tool_input["prompt"].rstrip() + BOUND
    print(json.dumps({
        "hookSpecificOutput": {"hookEventName": "PreToolUse", "updatedInput": updated},
        "systemMessage": f"{HOOK}: the brief stated no return bound, so a 400-word cap was added",
    }))


if __name__ == "__main__":
    main()
