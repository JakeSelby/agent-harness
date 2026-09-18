"""Owned-file reconciliation with durable intent and conflict-preserving rollback."""
import contextlib
import json
import os
import sys
import tempfile
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "vendor" / "tomlkit-0.15.1-py3-none-any.whl"))
import tomlkit


def atomic_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".harness-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextlib.contextmanager
def lock(directory):
    import fcntl
    directory.mkdir(parents=True, exist_ok=True)
    with open(directory / "sync.lock", "a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("another harness configuration operation is running")
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def update_toml(text, wanted):
    document = tomlkit.parse(text)
    for key, value in wanted.items():
        document[key] = value
    return tomlkit.dumps(document)


def lookup(document, keys):
    node = document
    for key in keys:
        if not isinstance(node, dict) or key not in node:
            return {"present": False, "value": None}
        node = node[key]
    return {"present": True, "value": deepcopy(node)}


def assign(document, keys, item):
    node = document
    for key in keys[:-1]:
        if key not in node:
            if not item["present"]:
                return
            node[key] = {}
        if not isinstance(node[key], dict):
            raise ValueError("configuration parent is not an object: " + key)
        node = node[key]
    if item["present"]:
        node[keys[-1]] = item["value"]
    else:
        node.pop(keys[-1], None)


class Store:
    def __init__(self, directory, dry=False):
        self.path = directory / "ownership.json"
        self.dry = dry
        self.data = json.loads(self.path.read_text()) if self.path.exists() else {"schema_version": 1, "files": {}}
        self.conflicts = []

    def save(self):
        if not self.dry:
            atomic_text(self.path, json.dumps(self.data, indent=2) + "\n")

    def _write(self, path, text, record):
        # Persist intent first. Recovery accepts either the prior or intended content.
        self.data["files"][str(path)] = record
        self.save()
        if not self.dry:
            atomic_text(path, text)
            record.pop("pending_from", None)
            for owned in record.get("keys", {}).values():
                owned.pop("pending_from", None)
            self.save()

    def generated(self, path, text, adopt=False):
        path = Path(path)
        if path.is_symlink():
            self.conflicts.append(str(path) + ": symlink is not a generated-file target")
            return
        current = path.read_text() if path.exists() else None
        record = self.data["files"].get(str(path))
        if record and current != record["applied"] and ("pending_from" not in record or current != record["pending_from"]):
            self.conflicts.append(str(path) + ": generated content changed; preserve and reconcile it first")
            return
        if record is None and current is not None and not adopt:
            self.conflicts.append(str(path) + ": unmanaged file; adopt explicitly before replacing it")
            return
        prior = record["prior"] if record else current
        next_record = {"kind": "generated", "prior": prior, "applied": text, "pending_from": current}
        if current != text or record is None:
            self._write(path, text, next_record)

    def toml(self, path, wanted):
        path = Path(path)
        if path.is_symlink():
            self.conflicts.append(str(path) + ": configuration symlink is not managed")
            return
        text = path.read_text() if path.exists() else ""
        document = tomlkit.parse(text)
        record = self.data["files"].get(str(path), {"kind": "toml", "keys": {}, "created": not path.exists()})
        for key, value in wanted.items():
            current = document[key].unwrap() if key in document else None
            old = record["keys"].get(key)
            if old and current != old["applied"] and ("pending_from" not in old or current != old["pending_from"]):
                self.conflicts.append(str(path) + ": owned key changed: " + key)
                continue
            prior = old["prior"] if old else {"present": key in document, "value": current}
            record["keys"][key] = {"prior": prior, "applied": value, "pending_from": current}
            document[key] = value
        rendered = tomlkit.dumps(document)
        if rendered != text or str(path) not in self.data["files"]:
            self._write(path, rendered, record)

    def json(self, path, desired, owned_paths):
        path = Path(path)
        if path.is_symlink():
            self.conflicts.append(str(path) + ": configuration symlink is not managed")
            return
        current = json.loads(path.read_text()) if path.exists() else {}
        document = deepcopy(current)
        record = self.data["files"].get(str(path), {"kind": "json", "keys": {}, "created": not path.exists()})
        for keys in owned_paths:
            name = json.dumps(keys)
            live, wanted = lookup(current, keys), lookup(desired, keys)
            old = record["keys"].get(name)
            if old and live != old["applied"] and ("pending_from" not in old or live != old["pending_from"]):
                self.conflicts.append(str(path) + ": owned field changed: " + ".".join(keys))
                continue
            record["keys"][name] = {"prior": old["prior"] if old else live,
                                    "applied": wanted, "pending_from": live}
            assign(document, keys, wanted)
        if document != current or str(path) not in self.data["files"]:
            self._write(path, json.dumps(document, indent=2) + "\n", record)

    def release_json(self, path, keys):
        """Restore a field only while it still equals our last write, then stop owning it."""
        path = Path(path)
        record = self.data["files"].get(str(path))
        name = json.dumps(keys)
        if not record or record.get("kind") != "json" or name not in record["keys"]:
            return
        if path.is_symlink() or not path.is_file():
            self.conflicts.append(str(path) + ": cannot release missing or redirected field")
            return
        document = json.loads(path.read_text())
        old = record["keys"][name]
        live = lookup(document, keys)
        if live not in (old["applied"], old.get("pending_from")):
            # The user now owns this value. Preserve it and retire our stale claim.
            record["keys"].pop(name)
            self.save()
            self.conflicts.append(str(path) + ": user-edited field preserved; ownership released: " + ".".join(keys))
            return
        assign(document, keys, old["prior"])
        record["keys"][name] = dict(old, applied=old["prior"], pending_from=live)
        self._write(path, json.dumps(document, indent=2) + "\n", record)
        record["keys"].pop(name)
        self.save()

    def drift(self):
        findings = []
        for name, record in self.data["files"].items():
            path = Path(name)
            if not path.is_file() or path.is_symlink():
                findings.append("missing or redirected managed file: " + name)
                continue
            current = path.read_text()
            if record["kind"] == "generated":
                if current != record["applied"]:
                    findings.append("modified generated file: " + name)
            elif record["kind"] == "json":
                try:
                    doc = json.loads(current)
                    for key, value in record["keys"].items():
                        if lookup(doc, json.loads(key)) != value["applied"]:
                            findings.append("modified owned field: " + name + ":" + key)
                except Exception:
                    findings.append("invalid managed JSON: " + name)
            else:
                try:
                    doc = tomlkit.parse(current)
                    for key, value in record["keys"].items():
                        if key not in doc or doc[key].unwrap() != value["applied"]:
                            findings.append("modified owned key: " + name + ":" + key)
                except Exception:
                    findings.append("invalid managed TOML: " + name)
        return findings

    def uninstall(self):
        for name, record in list(self.data["files"].items()):
            path = Path(name)
            if path.is_symlink():
                self.conflicts.append(name + ": redirected path preserved")
                continue
            current = path.read_text() if path.exists() else None
            if record["kind"] == "generated":
                if current != record["applied"] and ("pending_from" not in record or current != record["pending_from"]):
                    self.conflicts.append(name + ": user changes preserved")
                    continue
                if not self.dry:
                    if record["prior"] is None:
                        path.unlink(missing_ok=True)
                    else:
                        atomic_text(path, record["prior"])
            elif record["kind"] == "json":
                try:
                    doc = json.loads(current or "{}")
                except Exception:
                    self.conflicts.append(name + ": invalid JSON preserved")
                    continue
                remaining = {}
                for key, values in record["keys"].items():
                    keys = json.loads(key)
                    live = lookup(doc, keys)
                    if live != values["applied"] and ("pending_from" not in values or live != values["pending_from"]):
                        self.conflicts.append(name + ": user changes preserved for " + key)
                        remaining[key] = values
                        continue
                    assign(doc, keys, values["prior"])
                if not self.dry:
                    atomic_text(path, json.dumps(doc, indent=2) + "\n")
                if remaining:
                    record["keys"] = remaining
                    self.save()
                    continue
            else:
                try:
                    doc = tomlkit.parse(current or "")
                except Exception:
                    self.conflicts.append(name + ": invalid TOML preserved")
                    continue
                remaining = {}
                for key, values in record["keys"].items():
                    live = doc[key].unwrap() if key in doc else None
                    if live != values["applied"] and ("pending_from" not in values or live != values["pending_from"]):
                        self.conflicts.append(name + ": user changes preserved for " + key)
                        remaining[key] = values
                        continue
                    prior = values["prior"]
                    if prior["present"]:
                        doc[key] = prior["value"]
                    elif key in doc:
                        del doc[key]
                if not self.dry:
                    if record["created"] and not doc and not tomlkit.dumps(doc).strip():
                        path.unlink(missing_ok=True)
                    else:
                        atomic_text(path, tomlkit.dumps(doc))
                if remaining:
                    record["keys"] = remaining
                    self.save()
                    continue
            del self.data["files"][name]
            self.save()
