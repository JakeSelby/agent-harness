"""The shared authoring catalog; runtime files are reproducible projections."""
import hashlib
import json
import re
from pathlib import Path

IDENTIFIER = re.compile(r"^[a-z][a-z0-9-]*$")
KINDS = {"rules": "rules", "stances": "stances", "skills": "skills",
         "roles": "roles", "workflows": "workflows", "presentation": "presentation"}


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
    return fields, body


def role_projection(root, runtime, path, overrides=None):
    fields, body = role_contract(root, path.stem)
    binding = json.loads((root / "adapters" / runtime / "bindings.json").read_text())["roles"][fields["name"]]
    allowed = {"model", "model_reasoning_effort"} if runtime == "codex" else {"model", "effort"}
    if set(overrides or {}) - allowed:
        raise ValueError("role bindings may change model and effort only")
    binding = dict(binding, **(overrides or {}))
    if runtime == "claude-code":
        values = {k: fields[k] for k in ("name", "description")}
        values.update(binding)
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
