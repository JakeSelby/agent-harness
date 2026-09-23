"""Versioned question packs: content, a version, and the hash of the content.

A pack in `jev.py` is a plain dict, which is enough to send and not enough to measure. An
evaluation that says "this threshold holds" is a claim about one set of questions, so the set
needs a name and a version a later run can be compared against, and a hash that says whether
the words actually changed. `Pack` is those three, and the registry below is where a named
version is looked up.

Two properties the dict did not have. A pack is **frozen** at construction: the questions are
canonicalised once and every read deserialises a fresh copy, so nothing a caller holds — task
content, a context, a mutated response — can reach back and rewrite a criterion between the
hash being taken and the request being built. And a pack's **identity travels with the result**:
`identity()` is what `JevProvider` puts on the ledger row beside the request hash, so a row says
which version of which pack produced it rather than a hash nobody can resolve to words.
"""
import json
import re
from typing import Any, Dict, List, Optional

from . import jev

ID = re.compile(r"[a-z][a-z0-9-]{0,31}")
# `:` and not `@`: an `id@version` reads as an email address to the repository's own personal
# data lint, and a spelling that makes every mention of a pack a lint finding is the wrong one.
SEPARATOR = ":"
VERSION = re.compile(r"[0-9]{1,4}\.[0-9]{1,4}\.[0-9]{1,4}")


class Pack:
    """One named, versioned, frozen question pack.

    `decision=True` also requires the questions `JevProvider.decide` reads, so a pack that
    would leave that code reading a question nobody asked is refused here rather than at the
    first call.
    """

    def __init__(self, pack_id: str, version: str, questions: Any, decision: bool = True):
        if not isinstance(pack_id, str) or not ID.fullmatch(pack_id):
            raise jev.PackError("a pack id is a short lowercase identifier, not " + repr(pack_id))
        if not isinstance(version, str) or not VERSION.fullmatch(version):
            raise jev.PackError("pack " + pack_id + " needs a major.minor.patch version, not "
                                + repr(version))
        check = jev.require_decision_questions if decision else jev.validate_pack
        self._frozen = jev.canonical(check(questions))
        self.pack_id = pack_id
        self.version = version
        self.content_hash = jev.digest(json.loads(self._frozen.decode("utf-8")))

    @property
    def questions(self) -> Dict[str, Any]:
        """A fresh copy of the questions. Mutating what this returns changes no future read."""
        return json.loads(self._frozen.decode("utf-8"))

    def identity(self) -> Dict[str, Any]:
        return {"pack_id": self.pack_id, "pack_version": self.version,
                "pack_hash": self.content_hash}

    def key(self) -> str:
        return self.pack_id + SEPARATOR + self.version

    def verify(self, content_hash: str) -> None:
        """Raise unless this pack is still the words `content_hash` was taken over."""
        if content_hash != self.content_hash:
            raise jev.PackError("pack " + self.key() + " hashes " + self.content_hash
                                + ", not the " + str(content_hash) + " this result was fitted "
                                "against; a threshold does not carry across a pack edit")


REGISTRY = {}


def register(pack: Pack) -> Pack:
    if pack.key() in REGISTRY:
        raise jev.PackError("pack " + pack.key() + " is already registered; a published "
                            "version is never re-pointed, it is superseded by a new one")
    REGISTRY[pack.key()] = pack
    return pack


def _order(version: str):
    return tuple(int(part) for part in version.split("."))


def versions(pack_id: str) -> List[str]:
    """Every registered version of `pack_id`, oldest first."""
    return sorted((p.version for p in REGISTRY.values() if p.pack_id == pack_id), key=_order)


def get(pack_id: str, version: Optional[str] = None) -> Pack:
    """A registered pack. With no version, the highest one registered."""
    if version is None:
        known = versions(pack_id)
        if not known:
            raise jev.PackError("no pack named " + repr(pack_id) + "; known packs are "
                                + (", ".join(sorted(set(p.pack_id for p in REGISTRY.values())))
                                   or "none"))
        version = known[-1]
    pack = REGISTRY.get(pack_id + SEPARATOR + str(version))
    if pack is None:
        raise jev.PackError("pack " + repr(pack_id) + " has no version " + repr(version)
                            + "; registered versions are " + ", ".join(versions(pack_id)))
    return pack


def resolve(name: Optional[str]) -> Pack:
    """`pack_id`, `pack_id:version`, or None for the default decision pack."""
    if not name:
        return get(DECISION_ID)
    pack_id, _, version = str(name).partition(SEPARATOR)
    return get(pack_id, version or None)


DECISION_ID = "decision"
# 1.0.0 is the pack `jev.DECISION_PACK` shipped as. The words live there, not here: one pack is
# one set of words, and a copy would be a second one nobody edits in step.
DECISION_V1 = register(Pack(DECISION_ID, "1.0.0", jev.DECISION_PACK))
