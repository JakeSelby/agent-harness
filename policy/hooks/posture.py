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

`cost_table(env)`, and `resolve(env, table=True)`, additionally resolve the active `cost`
variant's JSON sidecar — switches, per-role and per-band rows, the default band — over its
`extends` chain. Schema and authoring: `docs/primitive-authoring.md`. It is opt-in because it
reads more files than a stance question needs. No number lives here: an unusable sidecar yields
the base variant's table and a warning, never a guessed default.

Import-cheap on purpose: no work at import, JSON reads only, because the dispatcher loads
this on every tool call.
"""
import importlib.util
import json
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PREFIX = "HARNESS_STANCE_"
# How long a session record is worth keeping. A session that has not started in a fortnight
# will never spawn again, and its record is three fields nobody reads.
SESSION_TTL_DAYS = 14
SESSION_ID_MAX = 128
# How stale a record may get before a spawn that read it moves its mtime out of the sweep's way.
SESSION_REFRESH_SECONDS = 86400
# The user-config key naming tool-name globs plan mode may use, and the postures under which a
# widened plan-mode authority is what the user already asked for everywhere else.
PLAN_TOOLS_KEY = "plan_allow_tools"
OPEN_POSTURES = ("bypass", "auto")

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
# The role a band's row renders and reroutes to. A band classes the *work*, so it needs an agent
# definition to carry its class and effort into a native spawn; these three are those definitions,
# and this map is the only place the naming is written.
BAND_ROLES = {band: "worker-" + band.lower() for band in BANDS}
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
BUDGET_KEYS = ("budget_output_tokens", "budget_tool_calls")
# The unit each budgeted key is stated in, in the order the sentence states them.
BUDGET_UNITS = dict(zip(BUDGET_KEYS, ("output tokens", "tool calls")))
# Ceilings that only rule out a number no machine could mean. A budget is soft, so the cap is
# about arithmetic that stays finite, not about an opinion on how much is too much.
MAX_MULTIPLIER = 100
MAX_BUDGET = 10 ** 9
MAX_NUDGES = 8
SIDECAR_KEYS = ("schema_version", "extends", "switches", "default_band", "rows")


def home(env=None):
    env = os.environ if env is None else env
    return Path(env.get("HARNESS_HOME") or env.get("HOME") or Path.home())


def config_path(env=None):
    return home(env) / ".config" / "agent-harness" / "config.json"


def user_agents_dir(env=None):
    """Where the tool resolves a user-level agent definition; `CLAUDE_CONFIG_DIR` moves it.

    The one place that rule is written, so the hook that reroutes a spawn and the hook that
    records what a session can resolve are never looking at two different directories.
    """
    env = os.environ if env is None else env
    config = env.get("CLAUDE_CONFIG_DIR")
    return (Path(config) if config else Path(env.get("HOME") or Path.home()) / ".claude") / "agents"


def installed_agents(env=None):
    """The user-level agent definitions on disk now, sorted; `[]` when the directory is unreadable."""
    try:
        return sorted(path.stem for path in user_agents_dir(env).glob("*.md") if path.is_file())
    except OSError:
        return []


def state_dir(env=None):
    return home(env) / ".local" / "state" / "agent-harness"


def sessions_dir(env=None):
    """The session registry: one record per session, written when its process started.

    Claude Code loads its agent registry once, when the session process starts, and does not
    reload it. So a definition on disk is not evidence that a running session can resolve the
    type it names — a session that began before `harness sync` installed the band workers
    cannot spawn one, and rerouting to it turns a spawn that would have worked into one that
    fails. The SessionStart policy writes what the registry held; the spawn hook reroutes only
    to a name it finds there.
    """
    return state_dir(env) / "sessions"


def _session_id(value):
    """A session identifier safe to make a file name of: no separator, no traversal, bounded."""
    return (isinstance(value, str) and value.isascii() and 0 < len(value) <= SESSION_ID_MAX
            and value[0].isalnum() and all(c.isalnum() or c in "._-" for c in value))


def session_record_path(session_id, env=None):
    return sessions_dir(env) / (session_id + ".json") if _session_id(session_id) else None


def read_session_record(session_id, env=None):
    """One session's record, or None for no record, an unreadable one, or anything but an object."""
    path = session_record_path(session_id, env)
    if path is None:
        return None
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return record if isinstance(record, dict) else None


def write_session_record(session_id, record, env=None):
    """Replace one session's record atomically; `True` when it was written.

    The directory is the session's own business and nobody else's, so it is 0700 and the file
    is 0600 from the moment it exists rather than after a chmod a reader could race.
    """
    path = session_record_path(session_id, env)
    if path is None or not isinstance(record, dict):
        return False
    temp = path.with_name(path.name + "." + str(os.getpid()) + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(str(path.parent), 0o700)
        with os.fdopen(os.open(str(temp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600),
                       "w", encoding="utf-8") as handle:
            json.dump(record, handle)
        os.replace(str(temp), str(path))
        return True
    except OSError:
        try:
            os.unlink(str(temp))
        except OSError:
            pass
        return False


def session_agents(session_id, env=None):
    """The agent names this session's registry held, or None when nothing recorded them.

    An absent or unusable `agents` key is None, which every caller reads as unknown, and
    unknown is never routable. That is what lets a record exist purely to remember a notice
    without ever authorising a reroute.
    """
    record = read_session_record(session_id, env)
    names = record.get("agents") if record else None
    return [name for name in names if isinstance(name, str)] if isinstance(names, list) else None


def refresh_session_record(session_id, env=None, older_than=SESSION_REFRESH_SECONDS):
    """Keep a session in use out of another session's sweep. `True` when the mtime was moved.

    A session open longer than the TTL would otherwise have its record pruned under it and stop
    routing halfway through, so reading the record is evidence the session is alive. A day's
    granularity, because this runs on a spawn and the sweep measures a fortnight.
    """
    path = session_record_path(session_id, env)
    try:
        if path is not None and time.time() - path.stat().st_mtime > older_than:
            os.utime(str(path), None)
            return True
    except OSError:
        pass
    return False


def note_once(session_id, key, env=None):
    """`True` the first time this session is told `key`; `False` once anything remembers it.

    A session with no record is exactly the session these notices are for, so one is created
    to hold the memory — with no `agents` key, which reads as unknown and can never authorise
    a reroute. A hook is a process per event, so nothing but the record remembers: when it
    cannot be written this says nothing at all, because a notice repeated on every spawn is a
    worse failure than one never given.
    """
    record = read_session_record(session_id, env)
    if record is None:
        return write_session_record(session_id, {"notified": [key], "at": int(time.time())}, env)
    seen = record.get("notified")
    seen = sorted({name for name in seen if isinstance(name, str)}) if isinstance(seen, list) else []
    if key in seen:
        return False
    return write_session_record(session_id, dict(record, notified=sorted(seen + [key])), env)


def prune_session_records(keep=None, days=SESSION_TTL_DAYS, env=None):
    """Drop records older than `days`, never `keep`'s. Best effort: a sweep never fails a session."""
    cutoff, removed = time.time() - days * 86400, 0
    try:
        paths = sorted(sessions_dir(env).glob("*.json"))
    except OSError:
        return 0
    for path in paths:
        if keep is not None and path.stem == keep:
            continue
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
                removed += 1
        except OSError:
            continue
    return removed


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


def _number(value, low, high, integer=False):
    """A finite in-range number. `True` is not 1 here, and neither NaN nor an infinity is a value.

    JSON admits `Infinity` and `NaN`, and Python's `json` reads them, so a multiplier arriving
    from a file can be either; both would raise out of the arithmetic below rather than warn.
    """
    if isinstance(value, bool) or not isinstance(value, int if integer else (int, float)):
        return False
    if value != value or value in (float("inf"), float("-inf")):
        return False
    return low <= value <= high


def validate_sidecar(data, roles=None):
    """`(usable copy, findings)` for one sidecar object; every finding drops the value it names.

    Findings are warnings to the resolver and failures to lint, which is the whole point: a
    switch added in a later release must never break a variant somebody else authored, while a
    shipped variant with an unknown key is a mistake nobody should have to discover at runtime.

    `roles` is the role catalog when the caller has one, so a row naming no role and no band is
    reported rather than silently applying to nothing.
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
            ok = value is None or _number(value, 1, MAX_BUDGET, integer=True)
        elif key == "budget_multiplier":
            ok = _number(value, 0, MAX_MULTIPLIER) and value > 0
        elif key == "nudge_at":
            ok = (isinstance(value, list) and len(value) <= MAX_NUDGES
                  and all(_number(v, 0, MAX_MULTIPLIER) and v > 0 for v in value))
        elif key == "session_nudge_at":
            # Context sizes, not multiples: whole tokens, because that is what a transcript
            # counts in and a fractional token is a number nobody measured.
            ok = (isinstance(value, list) and len(value) <= MAX_NUDGES
                  and all(_number(v, 0, MAX_BUDGET, integer=True) and v > 0 for v in value))
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
        if roles is not None and name not in BANDS and name not in roles:
            # A row naming nothing applies to nothing, which is a typo nobody would see.
            findings.append("row '" + name + "' names no role and no band")
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
                ok = value is None or _number(value, 0, MAX_BUDGET, integer=True)
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


def primitive_roots(config=None, root=None, kind="stances"):
    """The primitive directories of one kind, the built-in one first, then a user's roots."""
    roots = [(root or ROOT) / "primitives" / kind]
    entries = config.get("primitive_roots") if isinstance(config, dict) else None
    for entry in entries if isinstance(entries, list) else []:
        if isinstance(entry, str) and entry.strip():
            path = Path(entry).expanduser()
            if path.is_absolute():
                roots.append(path / kind)
    return roots


def stance_roots(config=None, root=None):
    return primitive_roots(config, root, "stances")


def sidecar_path(variant, roots):
    """The first root holding `cost/<variant>.json`, or None. Never reads outside a root.

    The variant name arrives from a config file or `HARNESS_STANCE_COST`, so it is held to the
    same identifier rule as the `.md` it accompanies, and the file it names must still resolve
    inside the root it was found in: a symlink out of the tree is a read nobody asked for.
    """
    if not _identifier(variant):
        return None
    for source in roots:
        path = source / "cost" / (variant + ".json")
        if not path.is_file():
            continue
        try:
            real, base = path.resolve(), source.resolve()
        except OSError:
            continue
        if real == base or base in real.parents:
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


def _frontmatter(path):
    """A role file's frontmatter fields, or `{}`; the same `key: value` shape `catalog` parses."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    if not text.startswith("---\n") or text.count("---") < 2:
        return {}
    fields = {}
    for line in text.split("---", 2)[1].strip().splitlines():
        key, sep, value = line.partition(":")
        if sep:
            fields[key.strip()] = value.strip()
    return fields


def role_catalog(config=None, root=None):
    """`(every role name, the names whose frontmatter says `posture: fixed`)`.

    A verifier's class and effort are its contract, so a variant row may budget it but never
    down-class it, and the role file is the one place that says so. Roles a user added through
    `primitive_roots` count the same as shipped ones; a missing catalog is two empty sets, which
    is how an installed hook with no checkout beside it behaves.
    """
    names, fixed = set(), set()
    for directory in primitive_roots(config, root, "roles"):
        for path in sorted(directory.glob("*.md")) if directory.is_dir() else []:
            fields = _frontmatter(path)
            if not fields:
                continue
            names.add(path.stem)
            if fields.get("posture") == "fixed":
                fixed.add(path.stem)
    return names, fixed


def fixed_roles(config=None, root=None):
    return role_catalog(config, root)[1]


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


def table_for(stances=None, config=None, strict=True, root=None):
    """The active cost variant resolved: switches, rows, default band, chain and warnings.

    Budgets carry both figures: `base_*` is what the variant wrote and `budget_*` is that times
    the resolved `budget_multiplier`, so a reader never multiplies twice. A link that cannot be
    followed — no sidecar, unreadable, a schema this release does not know, a name that is not
    an identifier — resolves to the base variant rather than to an empty table.
    """
    stances = dict(DEFAULT_STANCES) if stances is None else stances
    variant = stances.get("cost") or BASE_COST_VARIANT
    roots = stance_roots(config, root)
    roles, fixed = role_catalog(config, root)
    warnings, chain, layers, seen = [], [], [], set()
    name = variant
    while name:
        if name in seen:
            warnings.append("extends cycle at cost variant '" + str(name) + "'")
            break
        if len(chain) >= MAX_EXTENDS_DEPTH:
            warnings.append("extends chain deeper than " + str(MAX_EXTENDS_DEPTH) +
                            " variants, stopped at '" + str(name) + "'")
            break
        seen.add(name)
        data = None
        if not _identifier(name):
            warnings.append("cost variant '" + str(name) + "' is not a primitive identifier")
        else:
            path = sidecar_path(name, roots)
            if path is None:
                warnings.append("cost variant '" + name + "' has no sidecar")
            else:
                data = _load_sidecar(path, strict, warnings)
                version = data.get("schema_version") if data is not None else None
                if data is not None and version != SIDECAR_SCHEMA_VERSION:
                    warnings.append(name + ".json: schema_version " + json.dumps(version) +
                                    " is not one this release reads")
                    data = None
        if data is None:
            if name != BASE_COST_VARIANT and BASE_COST_VARIANT not in seen:
                # An unusable link is the base variant's table, not an empty one.
                name = BASE_COST_VARIANT
                continue
            break
        clean, findings = validate_sidecar(data, roles or None)
        warnings.extend(name + ".json: " + finding for finding in findings)
        chain.append({"variant": name, "source": str(path)})
        layers.append(clean)
        name = clean.get("extends")
    resolved = {}
    for layer in reversed(layers):
        resolved = _merge(resolved, layer)
    switches = resolved.get("switches", {})
    multiplier = switches.get("budget_multiplier", 1)
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


def _selection(config, env, strict):
    stances = dict(DEFAULT_STANCES)
    stances.update(_stances_of(config))
    stances.update(_stances_of(_project_config(env, strict)))
    stances.update(overrides(env))
    return stances


def resolve(env=None, strict=True, table=False):
    """The posture in force: `{"stances": {dimension: variant}}`, every dimension present.

    A missing config file is the default set and never an empty map, which would read as
    "no stance in force". The cost table is opt-in with `table=True`, because most callers are
    hot-path hooks answering one question and walking sidecars for them would be pure cost.
    """
    env = os.environ if env is None else env
    config = _user_config(env, strict)
    stances = _selection(config, env, strict)
    if not table:
        return {"stances": stances}
    return dict(table_for(stances, config, strict=strict), stances=stances)


def cost_table(env=None, strict=False, root=None):
    """The active cost variant's table for a caller that has only an environment.

    Non-strict by default: an unusable sidecar somewhere on the chain is a warning in the table,
    never a reason for the work in hand to stop.
    """
    env = os.environ if env is None else env
    config = _user_config(env, strict)
    return table_for(_selection(config, env, strict), config, strict=strict, root=root)


def selected(name, fallback=None, env=None, strict=True):
    """One dimension's variant, or `fallback` when nothing on the ladder names it.

    Reads the stance ladder only: a hook asking one question should not pay for the cost table.
    """
    env = os.environ if env is None else env
    return _selection(_user_config(env, strict), env, strict).get(name) or fallback


def permissions(env=None, strict=False):
    """The permission posture the user selected, or `inherit` when the config names none.

    Non-strict by default: a posture nobody can read is not a posture the user chose, and a
    caller that widens authority on it would be doing so on a file it could not open.
    """
    env = os.environ if env is None else env
    value = _user_config(env, strict).get("permissions")
    return value.strip() if isinstance(value, str) and value.strip() else "inherit"


def plan_allow_tools(env=None, strict=False):
    """The tool-name globs the user allows during plan mode, `fnmatch` style. Empty by default.

    Nothing is inferred: a PreToolUse payload carries no read-only hint for an MCP tool, so the
    only thing that can say a tool is safe to investigate with is the user naming it. A value
    that is not a list of non-empty strings names nothing.
    """
    env = os.environ if env is None else env
    value = _user_config(env, strict).get(PLAN_TOOLS_KEY)
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def row_for(table, role):
    """The row that governs one role: its own, or its band's when it is a band worker.

    The bands exist so a variant can price work it cannot name a role for, and the band workers
    are the roles that carry a band into a spawn. A row keyed by the role beats the band's,
    because naming the role is the more specific thing a variant can say.
    """
    rows = table.get("rows") if isinstance(table, dict) else None
    rows = rows if isinstance(rows, dict) else {}
    if role in rows:
        return rows[role]
    for band, name in BAND_ROLES.items():
        if name == role:
            return rows.get(band)
    return None


def _sibling(name):
    """A module beside this file, or None. Resolving a posture must never raise on an import."""
    try:
        spec = importlib.util.spec_from_file_location(
            "harness_" + name.replace("-", "_"), str(Path(__file__).resolve().parent / (name + ".py")))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception:
        return None


def budget_figures(row):
    """The halves of one row's soft budget worth stating, keyed as the row keys them.

    A null half is left out rather than written as "no budget", which would read as permission to
    spend without limit, and a half under one unit goes with it: "about 0 output tokens" would
    read as an instruction to do nothing, which is a budget nobody wrote.
    """
    if not isinstance(row, dict):
        return {}
    return {key: row[key] for key in BUDGET_KEYS
            if isinstance(row.get(key), int) and not isinstance(row[key], bool) and row[key] >= 1}


def budget_sentence(row):
    """The sentence one row's soft budget is stated in, or None when the row prices nothing.

    The one wording for every brief the harness writes: a native spawn's, appended by
    `brief-guard`, and an isolated role worker's, appended by `harness role run`. An agent cannot
    see the cost variant that priced it, so the row's figures are stated in the brief — every
    number from the table and none of the words. It is soft, because a hard cap would truncate
    the work rather than the spend.
    """
    parts = ["about {:,} {}".format(value, BUDGET_UNITS[key])
             for key, value in budget_figures(row).items()]
    if not parts:
        return None
    return ("\n\nExpected spend: " + " and ".join(parts) + ". Past that, finish if you are "
            "close; otherwise return what you have and say why.")


def budget_stated(text, detectors=None):
    """True when this brief already prices itself, or when nothing here can tell.

    What counts as a stated budget belongs to `rule-detectors.py` and not to a second copy per
    caller: a sentence the detector still reads as missing would be appended forever and the
    number would never move. A registry that will not load, or one without the pattern, is
    "cannot tell", which appends nothing.
    """
    module = _sibling("rule-detectors") if detectors is None else detectors
    pattern = getattr(module, "BUDGET_RE", None)
    return pattern is None or bool(pattern.search(text or ""))


def tier_models(runtime="claude-code", root=None):
    """The adapter's `{class: native model}`, strongest class first, or `{}` when unreadable.

    Model names belong to `adapters/<runtime>/bindings.json`, never to hook code: a lineup
    change is a data edit, and a caller that gets nothing says so rather than guessing.
    """
    path = (root or ROOT) / "adapters" / runtime / "bindings.json"
    try:
        tiers = json.loads(path.read_text(encoding="utf-8"))["tiers"]
        return {name: tiers[name] for name in TIER_CLASSES
                if isinstance(tiers.get(name), str) and tiers[name].strip()}
    except Exception:
        return {}


def ladder(runtime="claude-code", root=None):
    """The adapter's native models, strongest class first, or `[]` when it cannot be read."""
    return list(tier_models(runtime, root).values())
