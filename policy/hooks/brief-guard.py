#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""PreToolUse on `Agent`: append a return bound, and the posture's soft budget, to a brief
that states neither.

`delegation.md` says to bound the brief, and `transcript-hygiene/brief-without-cap` measures
that it is not: 536 hits across 30 percent of sessions. Asking the orchestrator to write the
cap does not work, so the hook writes it instead.

Adapted from unclebob/swarm-forge, whose handoff helper fills the commit SHA from the sender's
HEAD while the constitution says "do not type a SHA". The agent cannot get a field wrong that
it never writes.

What counts as a bound, and which agents are exempt, come from `rule-detectors.py` rather than
a second copy here. If the hook and the detector disagreed, the hook would append text the
detector still counts as missing and the number would never move.

The budget is the same argument for spend. A subagent cannot see the cost variant that priced
it, so the row's expected output tokens and tool calls are stated in the brief, once, in wording
fixed here: every number comes from the table and none of the words do. It is soft — the
sentence says to finish if close and otherwise return — because a hard cap would truncate the
work rather than the spend. A row with no budgets, a table that will not build, and a brief that
already prices itself all mean no sentence, which is what keeps a null variant byte-identical.

A spawn that named a role is priced on every runtime. A spawn that named none is priced by the
band worker it is about to be routed to, so it is priced only where that reroute happens — Claude
Code, whose hook rewrites `subagent_type`. On any other runtime nothing routes such a spawn, and
a budget naming a band it will not run in is worse than none.
"""
import importlib.util
import json
import os
import sys
from pathlib import Path

HOOK = "harness:brief-guard"
HOOKS = Path(__file__).resolve().parent
# The runtime whose spawn hook reroutes an unnamed spawn to a band worker. The coordinator sets
# `HARNESS_RUNTIME`; a hook run by hand has no coordinator and is this one.
ROUTING_RUNTIME = "claude-code"

# Written so it matches the detector's own cap pattern; a bound the detector cannot see is
# not a bound. `tests/test_brief_guard.py` asserts that parity.
BOUND = ("\n\nReturn at most 400 words: a one-line verdict first, then only what changes a "
         "decision. Write anything longer to a file and return its path, not its contents.")
CAP_NOTE = "the brief stated no return bound, so a 400-word cap was added"
BUDGET_NOTE = "the brief stated no spend, so the cost variant's soft budget was added"
# The units a row prices, in the order the sentence states them; a null cell is left out rather
# than written as "no budget", which would read as permission to spend without limit.
UNITS = (("budget_output_tokens", "output tokens"), ("budget_tool_calls", "tool calls"))


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


def effective_role(payload, tool_input, posture, router, table, variant):
    """The role whose row prices this spawn, or None when nothing prices it.

    A spawn that named a definition is priced by that role. A spawn that named none is priced
    by the band worker it is about to be routed to — which this hook cannot read off the event,
    because the coordinator hands both hooks the original call and not each other's rewrite. So
    the route is computed by calling `tier-agent-spawns`' own `band_route`, on the one table
    `table()` builds: a second answer to "where does an unnamed spawn go", or a second table,
    would sooner or later price the wrong band. Which spawns count as unnamed is that hook's
    predicate too, so a `subagent_type` of whitespace cannot be priced here and routed nowhere.

    A spawn nothing routes — another runtime, no default band, a worker that is not installed
    or not in this session's registry, a repository that ships its own, a delegation stance
    that is not `tiered` — is priced by nothing, as it was before.
    """
    if router is None:
        return None
    if not router.is_unnamed(tool_input):
        return tool_input.get("subagent_type")
    if variant != "tiered" or os.environ.get("HARNESS_RUNTIME", ROUTING_RUNTIME) != ROUTING_RUNTIME:
        return None
    models = posture.tier_models()
    if len(models) < 2:
        return None
    route, _ = router.band_route(posture, models, payload.get("cwd"), table(),
                                 payload.get("session_id"))
    return route["worker"] if route else None


def budget_sentence(row):
    """The sentence one row's soft budget is stated in, or None when the row prices nothing.

    A half under one unit is left out with the nulls: "about 0 output tokens" would read as an
    instruction to do nothing, which is a budget nobody wrote.
    """
    if not isinstance(row, dict):
        return None
    parts = []
    for key, unit in UNITS:
        value = row.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 1:
            parts.append("about {:,} {}".format(value, unit))
    if not parts:
        return None
    return ("\n\nExpected spend: " + " and ".join(parts) + ". Past that, finish if you are "
            "close; otherwise return what you have and say why.")


def budget_for(payload, tool_input, module, variant):
    """The budget sentence this brief is missing, or None. Never raises: a spawn outranks a row.

    The cost table is read here and nowhere else in this hook, at most once, and never for a
    spawn nothing would price: a table is a walk of every sidecar on the `extends` chain, and
    this hook runs on a tool call. Any failure building it is simply no sentence.
    """
    pattern = getattr(module, "BUDGET_RE", None)
    if pattern is None or pattern.search(tool_input.get("prompt") or ""):
        return None
    posture, router = sibling("posture"), sibling("tier-agent-spawns")
    if posture is None or router is None:
        return None
    built = []

    def table():
        if not built:
            built.append(posture.cost_table())
        return built[0]

    try:
        role = effective_role(payload, tool_input, posture, router, table, variant)
        if not role:
            return None
        return budget_sentence(posture.row_for(table(), role))
    except Exception:
        return None


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
        # `tier-agent-spawns` already asks before any spawn here; two hooks answering one
        # event is worse than one.
        return
    module = detectors()
    prompt = tool_input.get("prompt")
    if module is None or not isinstance(prompt, str) or not prompt.strip():
        return
    # The bound first and the budget after it, so a brief that is missing both reads as the
    # shape of the return and then what it may spend getting there.
    added, notes = "", []
    if needs_bound(module, tool_input):
        added, notes = BOUND, [CAP_NOTE]
    budget = budget_for(payload, tool_input, module, variant)
    if budget:
        added, notes = added + budget, notes + [BUDGET_NOTE]
    if not added:
        return
    updated = dict(tool_input)
    updated["prompt"] = prompt.rstrip() + added
    print(json.dumps({
        "hookSpecificOutput": {"hookEventName": "PreToolUse", "updatedInput": updated},
        "systemMessage": f"{HOOK}: " + " · ".join(notes),
    }))


if __name__ == "__main__":
    main()
