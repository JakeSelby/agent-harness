# SPDX-License-Identifier: MIT
"""The always-loaded budget, in one place, so the per-stance tests cannot drift apart.

Three stance tests used to carry their own `BUDGET = 196`. They assert the same thing — that a
change to a rule or a stance did not grow the layer Claude Code re-reads on every turn — so they
read it from here. The caps themselves live in `bin/harness`; this module only names the ratchet
the tests hold the tree to, and proves it sits under the cap.
"""
import importlib.machinery
import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def load_harness():
    loader = importlib.machinery.SourceFileLoader("harness", str(REPO / "bin" / "harness"))
    spec = importlib.util.spec_from_loader("harness", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


_harness = load_harness()

# The binding cap is tokens (issue #430); the line count is the secondary guard. Both come from
# `bin/harness` so there is exactly one definition of each.
TOKEN_CAP = _harness.ALWAYS_LOADED_TOKEN_CAP
LINE_CAP = _harness.ALWAYS_LOADED_CAP

# The ratchet is the line cap itself. It used to sit four lines under it so that the diff spending
# the last of the headroom had to say so; that happened once and the gap has done its job. The cap
# that binds is tokens (#430); the line cap is the secondary guard docs/how-it-works.md describes,
# and a second budget below it only made the secondary guard look like the primary one.
LINE_BUDGET = LINE_CAP


def measured(repo=REPO):
    """(lines, est_tokens) for the always-loaded layer of `repo`, worst case over stances."""
    lines, _ = _harness.always_loaded_lines(repo)
    tokens, _ = _harness.always_loaded_tokens(repo)
    return lines, tokens


def breakdown(repo=REPO):
    """A message naming both measures and every group, for an assertion that fails."""
    lines, tokens = measured(repo)
    rows = "; ".join(f"{name} {n}" for name, n in _harness.always_loaded_lines(repo)[1])
    return f"{lines} lines / ~{tokens} tokens: {rows}"
