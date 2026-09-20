#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""The one place a stance and the model ladder are resolved.

Not a hook: nothing registers it, and it reads no event. It sits beside the hooks because
they are standalone scripts run as subprocesses and share code by loading a sibling file
(`rule-detectors.py` is the precedent); `lifecycle.py` loads this same file by path, so the
dispatcher and the hooks cannot drift into two answers for one question.

`resolve(env)` returns the ladder `docs/primitive-authoring.md` documents, in order: the
built-in defaults, the user config under `HARNESS_HOME` or `$HOME`, the file named by
`HARNESS_PROJECT_CONFIG` (which may select stances and nothing else), then `HARNESS_STANCE_*`
for the session. `strict` says what an unusable file means: the dispatcher wants the error,
a hook wants the spawn to run anyway, so it passes `strict=False` and takes the layers it
could read.

Import-cheap on purpose: no work at import, JSON reads only, because the dispatcher loads
this on every tool call.
"""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PREFIX = "HARNESS_STANCE_"

# The dimensions `bin/harness` resolves and the variant each falls back to, which is
# `config.example.json`'s — the file the CLI layers the user config over, and a test holds the
# two together.
DEFAULT_STANCES = {
    "licensing": "permissive-commercial",
    "build-vs-buy": "capability-ceiling",
    "commits": "conventional-attributed",
    "plan-ceremony": "review-card",
    "delegation": "tiered",
    "testing": "required",
    "autonomy": "execute",
    "cost": "balanced", "voice": "scannable",
}
# Capability classes, strongest first; a test holds this equal to `catalog.TIER_CLASSES`, which
# is the definition. Named here so a hook can order an adapter's table without importing the
# library: a policy hook is a subprocess with no package on its path.
TIER_CLASSES = ("frontier", "strong", "standard", "light")


def home(env=None):
    env = os.environ if env is None else env
    return Path(env.get("HARNESS_HOME") or env.get("HOME") or Path.home())


def config_path(env=None):
    return home(env) / ".config" / "agent-harness" / "config.json"


def _stances_of(data):
    """The usable `{dimension: variant}` pairs of one layer; anything else is not a selection."""
    stances = data.get("stances") if isinstance(data, dict) else None
    if not isinstance(stances, dict):
        return {}
    return {name: value.strip() for name, value in stances.items()
            if isinstance(value, str) and value.strip()}


def _user_config(env, strict):
    path = config_path(env)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        return {}  # no config file is the defaults, in every mode
    except ValueError:
        if strict:
            raise
        return {}


def _project_config(env, strict):
    """The file `HARNESS_PROJECT_CONFIG` names, which may carry `stances` and nothing else."""
    named = env.get("HARNESS_PROJECT_CONFIG")
    if not named:
        return {}
    try:
        data = json.loads(Path(named).expanduser().read_text(encoding="utf-8"))
        if not isinstance(data, dict) or set(data) - {"stances"}:
            raise ValueError("project configuration cannot change runtime authority")
        if not isinstance(data.get("stances", {}), dict):
            raise ValueError("project stances must be an object")
        return data
    except (OSError, ValueError):
        if strict:
            raise
        return {}


def overrides(env=None):
    """The `{dimension: variant}` a session set through `HARNESS_STANCE_*`."""
    env = os.environ if env is None else env
    return {key[len(PREFIX):].lower().replace("_", "-"): value.strip()
            for key, value in env.items()
            if key.startswith(PREFIX) and isinstance(value, str) and value.strip()}


def resolve(env=None, strict=True):
    """The posture in force: `{"stances": {dimension: variant}}`, every dimension present.

    A missing config file is the default set and never an empty map, which would read as
    "no stance in force". Later steps widen the returned mapping; the key is stable.
    """
    env = os.environ if env is None else env
    stances = dict(DEFAULT_STANCES)
    stances.update(_stances_of(_user_config(env, strict)))
    stances.update(_stances_of(_project_config(env, strict)))
    stances.update(overrides(env))
    return {"stances": stances}


def selected(name, fallback=None, env=None, strict=True):
    """One dimension's variant, or `fallback` when nothing on the ladder names it."""
    return resolve(env, strict=strict)["stances"].get(name) or fallback


def ladder(runtime="claude-code", root=None):
    """The adapter's native models, strongest class first, or `[]` when it cannot be read.

    Model names belong to `adapters/<runtime>/bindings.json`, never to hook code: a lineup
    change is a data edit, and a caller that gets `[]` says so rather than guessing.
    """
    path = (root or ROOT) / "adapters" / runtime / "bindings.json"
    try:
        tiers = json.loads(path.read_text(encoding="utf-8"))["tiers"]
        return [tiers[name] for name in TIER_CLASSES
                if isinstance(tiers.get(name), str) and tiers[name].strip()]
    except Exception:
        return []
