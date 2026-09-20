"""The shared authoring catalog; runtime files are reproducible projections."""
import hashlib
import json
import re
from pathlib import Path

IDENTIFIER = re.compile(r"^[a-z][a-z0-9-]*$")
KINDS = {"rules": "rules", "stances": "stances", "skills": "skills",
         "roles": "roles", "workflows": "workflows", "presentation": "presentation"}
# Capability classes, strongest first. A shared role names the class its work needs; each
# adapter's bindings.json maps the classes it has qualified onto its own native models.
TIER_CLASSES = ("frontier", "strong", "standard", "light")
EFFORTS = ("low", "medium", "high")


def identifier(value):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError("primitive identifiers use lowercase letters, digits and hyphens")
    return value


def frontmatter(path):
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError("missing frontmatter: " + str(path))
    _, header, body = text.split("---", 2)
    fields = {}
    for line in header.strip().splitlines():
        key, sep, value = line.partition(":")
        if not sep or key in fields:
            raise ValueError("invalid or duplicate frontmatter field: " + str(path))
        fields[key] = value.strip()
    return fields, body.lstrip("\n")


def resolve_stances(root, config):
    """Resolve built-in and user-authored choices without accepting path traversal."""
    roots = [root / "primitives" / "stances"]
    for entry in config.get("primitive_roots", []):
        custom = Path(entry).expanduser()
        if not custom.is_absolute():
            raise ValueError("primitive_roots must be absolute directories")
        roots.append(custom / "stances")
    available = {}
    for source in roots:
        if not source.is_dir():
            raise ValueError("missing stance source: " + str(source))
        for dimension in sorted(source.iterdir()):
            if dimension.is_dir():
                identifier(dimension.name)
                variants = available.setdefault(dimension.name, {})
                for path in sorted(dimension.glob("*.md")):
                    identifier(path.stem)
                    if path.stem in variants:
                        raise ValueError("duplicate stance authority: " + dimension.name + "/" + path.stem)
                    variants[path.stem] = path
    selected = config.get("stances", {})
    if not isinstance(selected, dict):
        raise ValueError("stances must be an object")
    result = {}
    for name, variant in selected.items():
        identifier(name)
        identifier(variant)
        if name not in available or variant not in available[name]:
            raise ValueError("stance '" + name + "' has no variant '" + variant +
                             "'; options: " + ", ".join(sorted(available.get(name, {}))))
        result[name] = available[name][variant]
    # A custom dimension is optional until selected; built-in defaults are not.
    defaults = json.loads((root / "config.example.json").read_text())["stances"]
    for name in defaults:
        if name not in result:
            raise ValueError("config has no variant for stance '" + name + "'")
    for source in roots:
        constraints = source.parent / "constraints.json"
        if not constraints.exists():
            continue
        for rule in json.loads(constraints.read_text()).get("stances", []):
            if not isinstance(rule.get("when"), dict) or not rule["when"]:
                raise ValueError("stance constraints require a nonempty when selection")
            if all(selected.get(k) == v for k, v in rule["when"].items()):
                if any(selected.get(k) != v for k, v in rule.get("requires", {}).items()):
                    raise ValueError("stance conflict: " + rule.get("reason", "required selection missing"))
                if any(selected.get(k) == v for k, v in rule.get("excludes", {}).items()):
                    raise ValueError("stance conflict: " + rule.get("reason", "excluded selection active"))
    return result


def catalog(root):
    entries = []
    for kind, directory in KINDS.items():
        source = root / "primitives" / directory
        pattern = "*/SKILL.md" if kind == "skills" else "*/*.md" if kind == "stances" else "*.md"
        for path in sorted(source.glob(pattern)):
            ident = str(path.relative_to(source).with_suffix(""))
            if kind == "skills":
                ident = path.parent.name
            entries.append({"id": ident, "kind": kind, "source": str(path.relative_to(root)),
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    return {"schema_version": 1, "version": (root / "VERSION").read_text().strip(),
            "primitives": entries}


def role_contract(root, name):
    identifier(name)
    path = root / "primitives" / "roles" / (name + ".md")
    if not path.is_file():
        raise ValueError("unknown harness role: " + name)
    fields, body = frontmatter(path)
    if fields.get("name") != name or fields.get("authority") not in ("read-only", "artifact-write", "workspace-write"):
        raise ValueError("invalid shared role name or authority: " + name)
    if fields.get("context") != "fresh" or fields.get("delegation") != "none":
        raise ValueError("unsupported role context or delegation contract: " + name)
    if fields.get("tier") not in TIER_CLASSES:
        raise ValueError("shared role tier must be one of " + ", ".join(TIER_CLASSES) + ": " + name)
    return fields, body


def native_model(tiers, tier):
    """The adapter's model for a class, or the nearest stronger class it maps; None if neither.

    An unmapped class never resolves downward: a weaker model than the role asked for is a
    silent failure, while None makes the caller inherit the session model and say so.
    """
    for name in reversed(TIER_CLASSES[:TIER_CLASSES.index(tier) + 1]):
        if name in tiers:
            return tiers[name]
    return None


def adapter_tiers(root, runtime, tiers=None):
    """The adapter's class table with a user's `tiers.<runtime>` entries laid over it."""
    data = json.loads((root / "adapters" / runtime / "bindings.json").read_text())
    merged = dict(data.get("tiers", {}), **(tiers or {}))
    if set(merged) - set(TIER_CLASSES) or not all(
            isinstance(v, str) and v.strip() and not v.startswith("-") and not any(c.isspace() for c in v)
            for v in merged.values()):
        raise ValueError("adapter tiers map " + ", ".join(TIER_CLASSES) + " to native model identifiers")
    return data, merged


def tier_findings(tiers, models):
    """What a provider's model catalog says is wrong with a class table, as (class, model, problem).

    `models` is the provider's own list: `slug`, `priority` (lower is stronger) and `upgrade`, the
    successor it names once a model is superseded. A versioned id keeps resolving after its
    successor ships, so without this the table goes stale silently.
    """
    known = {m.get("slug"): m for m in models if isinstance(m, dict)}
    findings, last = [], None
    for name in TIER_CLASSES:
        model = tiers.get(name)
        if model is None:
            continue
        entry = known.get(model)
        if entry is None:
            findings.append((name, model, "not in the provider's catalog"))
            continue
        successor = entry.get("upgrade")
        successor = successor.get("model") or successor.get("slug") if isinstance(successor, dict) else successor
        if successor:
            findings.append((name, model, "superseded by " + str(successor)))
        priority = entry.get("priority")
        if isinstance(priority, int):
            if last is not None and priority < last:
                findings.append((name, model, "the catalog ranks it above the class before it"))
            last = priority
    return findings


def role_binding(root, runtime, fields, overrides=None, tiers=None):
    """A role's native binding: the adapter's entry, its class resolved to a model, then overrides."""
    data, tiers = adapter_tiers(root, runtime, tiers)
    effort_key = "model_reasoning_effort" if runtime == "codex" else "effort"
    if set(overrides or {}) - {"model", effort_key}:
        raise ValueError("role bindings may change model and effort only")
    binding = dict(data["roles"][fields["name"]], **(overrides or {}))
    if binding.get(effort_key, EFFORTS[0]) not in EFFORTS:
        raise ValueError("role effort must be one of " + ", ".join(EFFORTS) + ": " + fields["name"])
    model = binding.pop("model", None) or native_model(tiers, fields["tier"])
    # An `inherit` override is the way back to the session model, for a provider without these ids.
    return dict({"model": model} if model and model != "inherit" else {}, **binding)


def role_projection(root, runtime, path, overrides=None, tiers=None):
    fields, body = role_contract(root, path.stem)
    binding = role_binding(root, runtime, fields, overrides, tiers)
    if runtime == "claude-code":
        values = {k: fields[k] for k in ("name", "description")}
        values.update(dict({"model": "inherit"}, **binding))
        return "---\n" + "".join(k + ": " + v + "\n" for k, v in values.items()) + "---\n\n" + body
    if runtime != "codex":
        raise ValueError("unsupported runtime: " + runtime)
    values = {k: fields[k] for k in ("name", "description")}
    values["developer_instructions"] = body
    values["sandbox_mode"] = "workspace-write" if fields["authority"] == "workspace-write" else "read-only"
    values.update(binding)
    # JSON strings/arrays are valid for this restricted TOML value set.
    return "# Generated from primitives/roles; edit the shared source.\n" + "".join(
        k + " = " + json.dumps(v, ensure_ascii=False) + "\n" for k, v in values.items())


def projections(root):
    files = {}
    for role in sorted((root / "primitives" / "roles").glob("*.md")):
        files["claude/agents/" + role.name] = role_projection(root, "claude-code", role)
    for workflow in sorted((root / "primitives" / "workflows").glob("*.md")):
        files["claude/commands/" + workflow.name] = workflow.read_text().replace("{{arguments}}", "$ARGUMENTS")
    files["claude/CLAUDE.md"] = (root / "primitives" / "instructions.md").read_text() + "\n@~/.claude/CLAUDE.personal.md\n"
    files["claude/CLAUDE.personal.template.md"] = (root / "primitives" / "personal.template.md").read_text()
    from . import compatibility
    for name in ("README.md", "docs/compatibility.md"):
        path = root / name
        if not path.exists() or "<!-- harness:compatibility:start -->" not in path.read_text():
            continue
        data = compatibility.catalog(root)
        lines = []
        for status in ("qualified", "unqualified", "planned", "unsupported"):
            clients = [row["id"] for row in data["clients"] if row["status"] == status]
            if clients:
                lines.append("**" + status.capitalize() + ":** " + ", ".join("`" + name + "`" for name in clients) + ".")
        block = "<!-- harness:compatibility:start -->\n" + "\n\n".join(lines) + "\n<!-- harness:compatibility:end -->"
        files[name] = re.sub(r"<!-- harness:compatibility:start -->.*?<!-- harness:compatibility:end -->", block, path.read_text(), flags=re.S)
    return files


def projection_drift(root):
    return [name for name, content in projections(root).items()
            if not (root / name).is_file() or (root / name).read_text() != content]
