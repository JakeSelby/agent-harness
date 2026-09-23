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

Recognition has two strengths, because a false refusal nobody can explain is worse than the
evasion it prevents:

* **identifiers** — an agent name the framework's own definitions use, or a literal string only
  its routed text carries, such as a path to one of its prompt files. One is enough. The
  `harness-role:` line is not one of them: it is a standalone line the marker guard already
  reads, and restating it here as loose text would refuse prose that merely quotes it.
* **phrases** — ordinary wording from the framework's brief, which a paraphrase keeps some of and
  an unrelated brief may borrow one of. `corroboration` of them together are enough; fewer say
  nothing, which is what keeps a brief that merely mentions review from being refused.

Input roots are declaration, never a signal: `_bmad/` names the framework but appears in any brief
about editing it, and refusing those would be the false positive this module exists to avoid.
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
_CACHE = []


def normalise(text):
    """A brief reduced to what wording variance cannot hide: whitespace, case and length."""
    return " ".join(text.split()).casefold()[:CLASSIFY_MAX] if isinstance(text, str) else ""


def problems(data):
    """Everything wrong with one descriptor, as sentences. Empty means it is usable.

    Validation lives here rather than in the loader's exception handler so the shipped
    descriptors can be checked by a test: a descriptor the classifier silently skips is
    enforcement that quietly stopped.
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
    if not isinstance(data.get("input_roots", []), list):
        found.append("input_roots must be a list of paths")
    corroboration = data.get("corroboration", 2)
    if not (isinstance(corroboration, int) and not isinstance(corroboration, bool) and corroboration >= 2):
        found.append("corroboration must be an integer of at least 2")
    spawns = data.get("spawns")
    if not (isinstance(spawns, list) and spawns):
        return found + ["spawns must be a non-empty list"]
    for index, spawn in enumerate(spawns):
        where = "spawns[" + str(index) + "]"
        if not isinstance(spawn, dict):
            found.append(where + " is not an object")
            continue
        for field in ("id", "role"):
            if not IDENTIFIER.match(str(spawn.get(field, ""))):
                found.append(where + "." + field + " must be a lowercase identifier")
        for field in ("agents", "identifiers", "phrases"):
            values = spawn.get(field, [])
            if not isinstance(values, list) or not all(isinstance(v, str) and v.strip() for v in values):
                found.append(where + "." + field + " must be a list of non-empty strings")
        if not (spawn.get("agents") or spawn.get("identifiers")):
            found.append(where + " declares no identifier: a spawn recognised only by ordinary "
                                 "wording cannot be told from a brief that borrows it")
    return found


def descriptors(directory=None):
    """Every usable descriptor, newest read cached for the process.

    A descriptor that will not parse or will not validate is skipped rather than raised: this is
    read on the spawn path, and a hook that raises denies the call it was asked about.
    """
    directory = Path(directory) if directory else DESCRIPTORS
    try:
        paths = sorted(directory.glob("*.json"))
        signature = tuple((str(p), p.stat().st_mtime, p.stat().st_size) for p in paths)
    except OSError:
        paths, signature = [], ()
    if _CACHE and _CACHE[0][0] == signature:
        return _CACHE[0][1]
    usable = []
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not problems(data):
            usable.append(data)
    del _CACHE[:]
    _CACHE.append((signature, usable))
    return usable


def _score(spawn, text, agent):
    """`(identifiers, phrases)` this spawn entry matched. Identifiers outrank any count of phrases."""
    identifiers = 1 if agent and agent in [a.casefold() for a in spawn.get("agents", [])] else 0
    identifiers += sum(1 for value in spawn.get("identifiers", []) if normalise(value) in text)
    phrases = sum(1 for value in spawn.get("phrases", []) if normalise(value) in text)
    return identifiers, phrases


def classify(prompt, subagent_type=None, directory=None):
    """The framework spawn this call is, or None.

    The best-scoring entry across every descriptor wins, so a brief that carries one framework's
    general review wording and another's specific audit wording is classified as the audit.
    """
    text = normalise(prompt)
    agent = subagent_type.strip().casefold() if isinstance(subagent_type, str) else ""
    best = None
    for data in descriptors(directory):
        for spawn in data["spawns"]:
            identifiers, phrases = _score(spawn, text, agent)
            if not identifiers and phrases < data.get("corroboration", 2):
                continue
            score = (identifiers, phrases)
            if best is None or score > best[0]:
                best = (score, {"framework": data["id"], "framework_name": data["name"],
                                "spawn": spawn["id"], "role": spawn["role"],
                                "version": data["version"]["pinned"],
                                "input_roots": list(data.get("input_roots", []))})
    return best[1] if best else None


def origin(match):
    """The sentence a refusal opens with, naming what the harness recognised and on what evidence."""
    return ("This spawn carries the " + match["framework_name"] + " " + match["version"] + " `"
            + match["spawn"] + "` work, which this installation runs as the constrained `"
            + match["role"] + "` role whatever the spawn called itself.")
