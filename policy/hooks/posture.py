#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""The one place a stance and the model ladder are resolved.

Not a hook: nothing registers it, and it reads no event. It sits beside the hooks because
they are standalone scripts run as subprocesses and share code by loading a sibling file
(`rule-detectors.py` is the precedent); `lifecycle.py` loads this same file by path, so the
dispatcher and the hooks cannot drift into two answers for one question.

`resolve(env)` returns the stance ladder `docs/primitive-authoring.md` documents, in order: the
built-in defaults, the user config under `HARNESS_HOME` or `$HOME`, the file named by
`HARNESS_PROJECT_CONFIG` (which may select stances and nothing else), then `HARNESS_STANCE_*`
for the session. `strict` says what an unusable file means: the dispatcher wants the error,
a hook wants the spawn to run anyway, so it passes `strict=False` and takes the layers it
could read.

It also resolves the active `cost` variant's JSON sidecar — switches, per-role and per-band
rows, the default band — over its `extends` chain. Schema and authoring:
`docs/primitive-authoring.md`. No number lives here: an unreadable or absent sidecar yields an
empty table and a warning, never a guessed default.

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
EFFORTS = ("low", "medium", "high")
BANDS = ("A", "B", "C")
# The variant every other one falls back to, and the one a sidecar-less variant resolves to.
BASE_COST_VARIANT = DEFAULT_STANCES["cost"]
SIDECAR_SCHEMA_VERSION = 1
MAX_EXTENDS_DEPTH = 5
SWITCH_VALUES = {
    "session_effort": ("low", "medium", "high", "default"),
    "fast_mode": ("never", "off-unless-asked", "allowed"),
    "compaction": ("clear-only", "clear-at-task-end", "compact-allowed"),
    "turn_feed": ("off", "thresholds", "every-turn"),
}
SWITCH_KEYS = tuple(SWITCH_VALUES) + ("max_parallel", "budget_multiplier", "nudge_at")
ROW_KEYS = ("class", "effort", "budget_output_tokens", "budget_tool_calls")
BUDGET_KEYS = ("budget_output_tokens", "budget_tool_calls")
SIDECAR_KEYS = ("schema_version", "extends", "switches", "default_band", "rows")


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
    """The user's configuration. No file is the defaults; a file that cannot be read is not.

    A config that exists but will not open or will not parse is a selection nobody can see, so
    strict callers hear about it rather than running under defaults the user did not choose.
    """
    path = config_path(env)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, NotADirectoryError):
        return {}
    except (OSError, ValueError):
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
        # A `stances` value that is not an object selects nothing, as it always has; only a key
        # the project may not set is worth failing a tool call over.
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


def _identifier(value):
    return (isinstance(value, str) and value and value[0].isalpha() and value.islower()
            and all(c.isalnum() or c == "-" for c in value) and value.isascii())


def _positive_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def _budget(value):
    return value is None or (isinstance(value, int) and not isinstance(value, bool) and value >= 0)


def validate_sidecar(data):
    """`(usable copy, findings)` for one sidecar object; every finding drops the value it names.

    Findings are warnings to the resolver and failures to lint, which is the whole point: a
    switch added in a later release must never break a variant somebody else authored, while a
    shipped variant with an unknown key is a mistake nobody should have to discover at runtime.
    """
    findings, clean = [], {}
    for key in sorted(data):
        if key not in SIDECAR_KEYS:
            findings.append("unknown key '" + key + "'")
    version = data.get("schema_version")
    if version != SIDECAR_SCHEMA_VERSION:
        findings.append("schema_version must be " + str(SIDECAR_SCHEMA_VERSION))
    extends = data.get("extends")
    if extends is not None:
        if _identifier(extends):
            clean["extends"] = extends
        else:
            findings.append("extends names a cost variant or is null")
    band = data.get("default_band")
    if band is not None:
        if band in BANDS:
            clean["default_band"] = band
        else:
            findings.append("default_band is one of " + ", ".join(BANDS))
    switches = data.get("switches", {})
    if "switches" in data and not isinstance(switches, dict):
        findings.append("switches is an object")
        switches = {}
    kept = {}
    for key in sorted(switches):
        value = switches[key]
        if key in SWITCH_VALUES:
            ok = value in SWITCH_VALUES[key]
        elif key == "max_parallel":
            ok = value is None or (isinstance(value, int) and not isinstance(value, bool) and value > 0)
        elif key == "budget_multiplier":
            ok = _positive_number(value)
        elif key == "nudge_at":
            ok = isinstance(value, list) and all(_positive_number(v) for v in value)
        else:
            findings.append("unknown switch '" + key + "'")
            continue
        if ok:
            kept[key] = value
        else:
            findings.append("switch '" + key + "' has an unusable value")
    if kept:
        clean["switches"] = kept
    rows = data.get("rows", {})
    if "rows" in data and not isinstance(rows, dict):
        findings.append("rows is an object")
        rows = {}
    resolved_rows = {}
    for name in sorted(rows):
        row = rows[name]
        if not (name in BANDS or _identifier(name)):
            findings.append("row '" + str(name) + "' is a role name or a band")
            continue
        if not isinstance(row, dict):
            findings.append("row '" + name + "' is an object")
            continue
        cells = {}
        for key in sorted(row):
            value = row[key]
            if key == "class":
                # `frontier` is never reachable by request; the delegation stance decides that,
                # and a variant is a request.
                ok = value in TIER_CLASSES[1:]
            elif key == "effort":
                ok = value in EFFORTS
            elif key in BUDGET_KEYS:
                ok = _budget(value)
            else:
                findings.append("row '" + name + "' has an unknown key '" + str(key) + "'")
                continue
            if ok:
                cells[key] = value
            else:
                findings.append("row '" + name + "' cell '" + key + "' has an unusable value")
        resolved_rows[name] = cells
    if resolved_rows:
        clean["rows"] = resolved_rows
    return clean, findings


def stance_roots(config=None, root=None):
    """The stance directories to search, the built-in one first, then a user's `primitive_roots`."""
    roots = [(root or ROOT) / "primitives" / "stances"]
    entries = config.get("primitive_roots") if isinstance(config, dict) else None
    for entry in entries if isinstance(entries, list) else []:
        if isinstance(entry, str) and entry.strip():
            path = Path(entry).expanduser()
            if path.is_absolute():
                roots.append(path / "stances")
    return roots


def sidecar_path(variant, roots):
    for source in roots:
        path = source / "cost" / (variant + ".json")
        if path.is_file():
            return path
    return None


def _load_sidecar(path, strict, warnings):
    """The sidecar's object, or None with a warning; unreadable is an error only in strict mode."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        if strict:
            raise
        warnings.append(str(path) + " is not readable JSON: " + str(exc))
        return None
    if not isinstance(data, dict):
        if strict:
            raise ValueError(str(path) + " is not a JSON object")
        warnings.append(str(path) + " is not a JSON object")
        return None
    return data


def fixed_roles(root=None):
    """Role names whose frontmatter carries `posture: fixed`; a missing catalog is an empty set.

    A verifier's class and effort are its contract, so a variant row may budget it but never
    down-class it. The role file is the one place that says so.
    """
    names = set()
    directory = (root or ROOT) / "primitives" / "roles"
    for path in sorted(directory.glob("*.md")) if directory.is_dir() else []:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if not text.startswith("---\n"):
            continue
        header = text.split("---", 2)[1]
        if any(line.strip() == "posture: fixed" for line in header.splitlines()):
            names.add(path.stem)
    return names


def _merge(base, layer):
    """`layer` over `base`, one level into `switches` and two into `rows`."""
    merged = dict(base)
    for key in ("extends", "default_band"):
        if key in layer:
            merged[key] = layer[key]
    merged["switches"] = dict(base.get("switches", {}), **layer.get("switches", {}))
    rows = {name: dict(cells) for name, cells in base.get("rows", {}).items()}
    for name, cells in layer.get("rows", {}).items():
        rows[name] = dict(rows.get(name, {}), **cells)
    merged["rows"] = rows
    return merged


def _round_to(value, step):
    return int((value + step / 2) // step) * step


def cost_table(stances=None, config=None, strict=True, root=None):
    """The active cost variant resolved: switches, rows, default band, chain and warnings.

    Budgets carry both figures: `base_*` is what the variant wrote and `budget_*` is that times
    the resolved `budget_multiplier`, so a reader never multiplies twice.
    """
    stances = dict(DEFAULT_STANCES) if stances is None else stances
    variant = stances.get("cost") or BASE_COST_VARIANT
    roots = stance_roots(config, root)
    warnings, chain, layers, seen = [], [], [], set()
    name, first = variant, True
    while name:
        if name in seen:
            warnings.append("extends cycle at cost variant '" + name + "'")
            break
        if len(chain) >= MAX_EXTENDS_DEPTH:
            warnings.append("extends chain deeper than " + str(MAX_EXTENDS_DEPTH) +
                            " variants, stopped at '" + name + "'")
            break
        seen.add(name)
        path = sidecar_path(name, roots)
        data = _load_sidecar(path, strict, warnings) if path else None
        if data is None:
            if first and name != BASE_COST_VARIANT:
                # No sidecar of its own means the base variant's table, not an empty one.
                name, first = BASE_COST_VARIANT, False
                continue
            if path is None:
                warnings.append("cost variant '" + name + "' has no sidecar")
            break
        clean, findings = validate_sidecar(data)
        warnings.extend(name + ".json: " + finding for finding in findings)
        chain.append({"variant": name, "source": str(path)})
        layers.append(clean)
        name, first = clean.get("extends"), False
    resolved = {}
    for layer in reversed(layers):
        resolved = _merge(resolved, layer)
    switches = resolved.get("switches", {})
    multiplier = switches.get("budget_multiplier", 1)
    fixed = fixed_roles(root)
    rows = {}
    for row_name, cells in sorted(resolved.get("rows", {}).items()):
        row = {"class": cells.get("class"), "effort": cells.get("effort")}
        if row_name in fixed:
            # The role keeps its frontmatter tier and its bindings effort; only budgets apply.
            row["class"], row["effort"], row["posture"] = None, None, "fixed"
        for key, step in zip(BUDGET_KEYS, (100, 1)):
            base = cells.get(key)
            row["base_" + key] = base
            row[key] = None if base is None else _round_to(base * multiplier, step)
        rows[row_name] = row
    return {"cost_variant": variant, "switches": switches, "rows": rows,
            "default_band": resolved.get("default_band"), "extends_chain": chain,
            "class_applies": stances.get("delegation") == "tiered", "warnings": warnings}


def _selection(env, strict):
    stances = dict(DEFAULT_STANCES)
    stances.update(_stances_of(_user_config(env, strict)))
    stances.update(_stances_of(_project_config(env, strict)))
    stances.update(overrides(env))
    return stances


def resolve(env=None, strict=True):
    """The posture in force: the stances, and the active cost variant's resolved table.

    A missing config file is the default set and never an empty map, which would read as
    "no stance in force". Later steps widen the returned mapping; the keys are stable.
    """
    env = os.environ if env is None else env
    stances = _selection(env, strict)
    table = cost_table(stances, _user_config(env, strict), strict=strict)
    return dict(table, stances=stances)


def selected(name, fallback=None, env=None, strict=True):
    """One dimension's variant, or `fallback` when nothing on the ladder names it.

    Reads the stance ladder only: a hook asking one question should not pay for the cost table.
    """
    env = os.environ if env is None else env
    return _selection(env, strict).get(name) or fallback


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
