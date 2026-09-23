"""Which framework a native spawn belongs to, read from a declared integration descriptor.

A framework that drives an agent session spawns subagents of its own, and the name it gives them
is whatever the client's model writes at the call. Confinement cannot be built on that name: the
routed instruction to run a constrained role through `harness role run` is a request in a prompt,
and a client that paraphrases the brief and names no role walks straight past a guard that only
reads `subagent_type` (#291).

So a framework declares itself instead. `policy/integrations/<id>.json` names the framework, the
version it is pinned to, how its spawns are recognised, which harness role each spawn maps to, and
the input roots a confined worker needs. The spawn hook classifies from that mapping, and a
`harness-role:` line in the brief stays what it always was: an optimisation that saves the
classifier the work, not the thing enforcement depends on.

Recognition is corroborated, because a false refusal is not a smaller mistake than a missed one:
a brief that is wrongly classified is work the session cannot get done, and the classifier has no
way to hear that it was wrong.

* **agents** — a spawn whose `subagent_type` is one of the framework's own layer names. Nothing but
  the framework puts that name there, so this alone is enough.
* **identifiers** — a literal only the framework's routed text carries, such as the path of one of
  its prompt files. Never enough alone: a brief that edits the override templates, or that asks a
  worker to read one of those files, quotes the same path. An identifier needs a phrase beside it.
* **phrases** — whole sentences of the framework's own prompt text, distinctive enough that
  quoting one is a coincidence and quoting `corroboration` of them is not. Single generic nouns
  are not phrases: "unified diff" and "list of findings" are what an ordinary fix-up brief says
  after a review, and refusing those was the first thing this classifier got wrong.

The `harness-role:` line is not a signal here: it is a standalone line the marker guard already
reads, and restating it as loose text would refuse prose that merely quotes it.

Input roots are declaration, never a signal: `_bmad/` names the framework but appears in any brief
about editing it. They travel into the refusal instead, so the sentence that refuses a spawn also
says which roots the isolated worker has to be given.

A descriptor that will not parse or will not validate is not enforcement that quietly stopped: the
loader keeps why it was ignored, and the spawn hook says so once per session.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DESCRIPTORS = ROOT / "policy" / "integrations"
SCHEMA_VERSION = 1
# A brief is normalised before it is searched, and only its head is searched: the framework's own
# instructions are at the top of every routed brief, and a hook runs on a tool call.
CLASSIFY_MAX = 20000
IDENTIFIER = re.compile(r"[a-z][a-z0-9-]*\Z")
# What a signal has to be before it is allowed to contribute to a refusal. A short or one-word
# string is something an unrelated brief says by accident, and the descriptor author does not
# find that out; the loader does, here.
MIN_IDENTIFIER = (12, 1)
MIN_PHRASE = (24, 4)
_CACHE = []


def normalise(text):
    """A brief reduced to what wording variance cannot hide: whitespace, case and length."""
    return " ".join(text.split()).casefold()[:CLASSIFY_MAX] if isinstance(text, str) else ""


def _too_slight(value, limits):
    characters, words = limits
    return len(value.strip()) < characters or len(value.split()) < words


def _signal_problems(where, spawn, roots):
    """What is wrong with one spawn entry's signals: shape, weight, and overlap with input roots."""
    found = []
    for field, limits in (("agents", (2, 1)), ("identifiers", MIN_IDENTIFIER), ("phrases", MIN_PHRASE)):
        values = spawn.get(field, [])
        if not isinstance(values, list) or not all(isinstance(v, str) and v.strip() for v in values):
            found.append(where + "." + field + " must be a list of non-empty strings")
            continue
        for value in values:
            if _too_slight(value, limits):
                found.append(where + "." + field + ": `" + value + "` is too slight to identify a "
                             "spawn; " + field + " need at least " + str(limits[0]) + " characters "
                             "and " + str(limits[1]) + " word(s)")
            if field == "identifiers" and any(_covers(root, value) for root in roots):
                found.append(where + ".identifiers: `" + value + "` is an input root or a bare "
                             "directory under one, which any brief about the framework quotes")
    if not spawn.get("phrases"):
        found.append(where + " declares no phrases: agents and identifiers alone cannot tell the "
                     "framework's own work from a brief that quotes one of its paths")
    return found


def _covers(root, value):
    """Whether `value` is an input root, or a bare directory inside one rather than a file in it."""
    root, value = root.strip().strip("/").casefold(), value.strip().strip("/").casefold()
    if not root or not value:
        return False
    if value == root or not (value.startswith(root + "/") or root.startswith(value + "/")):
        return value == root
    tail = value[len(root) + 1:] if value.startswith(root + "/") else ""
    return "." not in tail.rsplit("/", 1)[-1]


def problems(data, role_check=None):
    """Everything wrong with one descriptor, as sentences. Empty means it is usable.

    Validation lives here rather than in the loader's exception handler so the shipped descriptors
    can be checked by a test, and so the loader can say which descriptor it ignored and why.

    `role_check` answers whether a role is one an isolated worker must run; it defaults to the
    lifecycle's own answer, because a descriptor mapping a spawn to a role the spawn guard would
    not constrain is a mapping that can never refuse anything.
    """
    found = []
    if not isinstance(data, dict):
        return ["descriptor is not an object"]
    if data.get("schema_version") != SCHEMA_VERSION:
        found.append("schema_version must be " + str(SCHEMA_VERSION))
    for field in ("id", "name"):
        value = data.get(field)
        if not (isinstance(value, str) and value.strip()):
            found.append(field + " must be a non-empty string")
    if not IDENTIFIER.match(str(data.get("id", ""))):
        found.append("id must be lowercase, starting with a letter")
    version = data.get("version")
    if not (isinstance(version, dict) and isinstance(version.get("pinned"), str) and version["pinned"].strip()):
        found.append("version.pinned must name the framework release this descriptor was read from")
    roots = data.get("input_roots", [])
    if not (isinstance(roots, list) and all(isinstance(r, str) and r.strip() for r in roots)):
        found.append("input_roots must be a list of paths")
        roots = []
    corroboration = data.get("corroboration", 2)
    if not (isinstance(corroboration, int) and not isinstance(corroboration, bool) and corroboration >= 2):
        found.append("corroboration must be an integer of at least 2")
    spawns = data.get("spawns")
    if not (isinstance(spawns, list) and spawns):
        return found + ["spawns must be a non-empty list"]
    if role_check is None:
        role_check = _constrained
    for index, spawn in enumerate(spawns):
        where = "spawns[" + str(index) + "]"
        if not isinstance(spawn, dict):
            found.append(where + " is not an object")
            continue
        for field in ("id", "role"):
            if not IDENTIFIER.match(str(spawn.get(field, ""))):
                found.append(where + "." + field + " must be a lowercase identifier")
        if IDENTIFIER.match(str(spawn.get("role", ""))) and not role_check(spawn["role"]):
            found.append(where + ".role `" + spawn["role"] + "` is not a role an isolated worker "
                         "must run, so this mapping could never refuse anything")
        found += _signal_problems(where, spawn, roots)
    return found


def _constrained(role):
    """Whether the spawn guard holds `role` to an isolated worker. False when it cannot be asked."""
    try:
        from . import lifecycle
        return lifecycle.constrained_role(role) is not None
    except Exception:
        return False


def _read(directory):
    """`(usable, ignored)` for one directory. `ignored` is `(path, reason)` for anything skipped."""
    try:
        paths = sorted(directory.glob("*.json"))
        stats = [p.stat() for p in paths]
    except OSError:
        return [], [], ()
    signature = tuple((str(p), st.st_mtime_ns, st.st_size) for p, st in zip(paths, stats))
    usable, ignored = [], []
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            ignored.append((path.name, type(exc).__name__ + ": " + str(exc)))
            continue
        found = problems(data)
        if found:
            ignored.append((path.name, found[0] if len(found) == 1
                            else found[0] + " (and " + str(len(found) - 1) + " more)"))
        else:
            usable.append(data)
    return usable, ignored, signature


def _loaded(directory=None):
    """The cached `(usable, ignored)` for a directory, reread when any descriptor's bytes change."""
    directory = Path(directory) if directory else DESCRIPTORS
    usable, ignored, signature = _read(directory)
    if _CACHE and _CACHE[0][0] == signature:
        return _CACHE[0][1]
    del _CACHE[:]
    _CACHE.append((signature, (usable, ignored)))
    return usable, ignored


def descriptors(directory=None):
    """Every usable descriptor. A broken one is left out, and `ignored` says which and why."""
    return _loaded(directory)[0]


def ignored(directory=None):
    """`(file, reason)` for every descriptor the loader could not use."""
    return _loaded(directory)[1]


def _score(spawn, text, agent):
    """`(agents, identifiers, phrases)` this spawn entry matched."""
    agents = 1 if agent and agent in [a.casefold() for a in spawn.get("agents", [])] else 0
    identifiers = sum(1 for value in spawn.get("identifiers", []) if normalise(value) in text)
    phrases = sum(1 for value in spawn.get("phrases", []) if normalise(value) in text)
    return agents, identifiers, phrases


def _recognised(score, corroboration):
    """Whether this much evidence refuses a spawn. The rule, in one place, for the one caller."""
    agents, identifiers, phrases = score
    if agents:
        return True
    if identifiers and phrases:
        return True
    return phrases >= corroboration


def classify(prompt, subagent_type=None, directory=None, accept=None):
    """The framework spawn this call is, or None.

    `accept` filters the roles a match may map to, so a spawn the guard would go on to allow
    anyway cannot outscore one it would refuse. The best-scoring surviving entry wins, which is
    what classifies a brief carrying both a framework's general review wording and its specific
    audit wording as the audit.
    """
    text = normalise(prompt)
    agent = subagent_type.strip().casefold() if isinstance(subagent_type, str) else ""
    best = None
    for data in descriptors(directory):
        for spawn in data["spawns"]:
            if accept is not None and not accept(spawn["role"]):
                continue
            score = _score(spawn, text, agent)
            if not _recognised(score, data.get("corroboration", 2)):
                continue
            if best is None or score > best[0]:
                best = (score, {"framework": data["id"], "framework_name": data["name"],
                                "spawn": spawn["id"], "role": spawn["role"],
                                "version": data["version"]["pinned"],
                                "input_roots": list(data.get("input_roots", []))})
    return best[1] if best else None


def origin(match):
    """The sentences a refusal opens with: what was recognised, and what the worker will need."""
    said = ("This spawn carries the " + match["framework_name"] + " " + match["version"] + " `"
            + match["spawn"] + "` work, which this installation runs as the constrained `"
            + match["role"] + "` role whatever the spawn called itself.")
    roots = match.get("input_roots") or []
    if roots:
        said += (" The isolated worker needs the framework's input roots as read roots: "
                 + ", ".join(roots) + ".")
    return said
