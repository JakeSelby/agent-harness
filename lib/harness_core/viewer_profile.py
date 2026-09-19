"""Narrow architecture projection; EDN validation and rendering belong to the viewer."""
import hashlib
import json
import math
from pathlib import PurePosixPath
from .integrations import fail

RELATIONS = {"association", "dependency", "aggregation", "composition", "inheritance", "implements"}
METRICS = {"coverage", "cc", "crap", "killed", "survived"}


def text(value, field):
    if not isinstance(value, str) or not value.strip() or len(value) > 65536:
        fail("invalid-document", field + " must be nonempty text")
    return value


def fields(value, allowed, field):
    if not isinstance(value, dict):
        fail("invalid-document", field + " must be an object")
    unknown = set(value) - set(allowed)
    if unknown:
        fail("unsupported-field", field + ": " + ", ".join(sorted(unknown)))


def identity(value, prefix):
    return prefix + hashlib.sha256(value.encode("utf-8")).hexdigest()


def quoted(value):
    return json.dumps(value, ensure_ascii=True)


def metrics(value, path, omitted):
    if not isinstance(value, dict):
        fail("invalid-document", path + " must be an object")
    result = []
    for key, record in value.items():
        if key not in METRICS:
            fail("unsupported-metric", path + "." + key)
        fields(record, {"availability", "value"}, path + "." + key)
        availability = record.get("availability")
        if not isinstance(availability, str):
            fail("invalid-document", path + "." + key + " requires availability")
        if availability in {"missing", "unsupported", "failed"}:
            if "value" in record:
                fail("invalid-document", "unmeasured metrics cannot have values")
            omitted.append(path + "." + key + ": " + record["availability"])
            continue
        number = record.get("value")
        if (record.get("availability") != "measured" or type(number) not in (int, float) or
                number < 0 or number > 1.7976931348623157e308 or not math.isfinite(number) or
                (key == "coverage" and number > 1) or
                (key in {"killed", "survived"} and (type(number) is not int or number > 2 ** 63 - 1))):
            fail("invalid-document", path + "." + key + " has an invalid measurement")
        result.append(":" + key + " " + json.dumps(number, allow_nan=False))
    return " ".join(result)


def project(document):
    fields(document, {"profile", "schema_version", "document_id", "title", "nodes", "relations", "packages", "optional"}, "document")
    if document.get("profile") != "architecture-diagram" or type(document.get("schema_version")) is not int or document["schema_version"] != 1:
        fail("unsupported-schema", "expected architecture-diagram version 1")
    document_id = text(document.get("document_id"), "document_id")
    for key in ("nodes", "relations", "packages"):
        if not isinstance(document.get(key, []), list):
            fail("invalid-document", key + " must be an array")
    nodes, relations, packages = document.get("nodes", []), document.get("relations", []), document.get("packages", [])
    if len(nodes) + len(relations) + len(packages) > 2000:
        fail("resource-limit", "architecture profile exceeds 2000 entities")
    if not isinstance(document.get("optional", {}), dict):
        fail("invalid-document", "optional must be an object")
    omitted = ["optional." + name for name in document.get("optional", {})]
    mapping = {"version": 1, "document_id": document_id, "nodes": {}, "packages": {}, "relations": {}}
    package_nodes = {None: []}
    package_labels = {None: "Architecture"}
    for package in packages:
        fields(package, {"id", "label"}, "package")
        pid = text(package.get("id"), "package.id")
        if pid in package_nodes:
            fail("invalid-document", "duplicate package identity")
        mapping["packages"][pid] = identity(pid, "p-")
        package_nodes[pid] = []
        package_labels[pid] = text(package.get("label"), "package.label")
    foreign = []
    for index, node in enumerate(nodes):
        path = "nodes[" + str(index) + "]"
        fields(node, {"id", "kind", "label", "package_id", "source", "metrics", "optional"}, path)
        nid = text(node.get("id"), path + ".id")
        if nid in mapping["nodes"]:
            fail("invalid-document", "duplicate node identity")
        kind = node.get("kind")
        if not isinstance(kind, str) or kind not in {"class", "module", "interface", "abstract", "enum", "external"}:
            fail("unsupported-node-kind", path + ".kind")
        pid = node.get("package_id")
        if pid is not None:
            text(pid, path + ".package_id")
        if pid not in package_nodes or (kind == "external" and pid is not None):
            fail("invalid-document", "unknown or incompatible package membership")
        mapped = identity(nid, "n-")
        mapping["nodes"][nid] = mapped
        bits = [":id :" + mapped, ":name " + quoted(text(node.get("label"), path + ".label"))]
        if kind in {"interface", "abstract", "enum"}:
            bits.append(":stereotype :" + kind)
        if kind == "external":
            bits.append(":foreign true")
        if "source" in node:
            source = node["source"]
            fields(source, {"path", "line", "namespace"}, path + ".source")
            locator = text(source.get("path"), path + ".source.path")
            if PurePosixPath(locator).is_absolute() or ".." in PurePosixPath(locator).parts or "\\" in locator:
                fail("path-denied", "source locator must be repository-relative")
            if "line" in source and (type(source["line"]) is not int or source["line"] < 1):
                fail("invalid-document", "source line must be positive")
            if "namespace" in source:
                bits.append(":ns " + quoted(text(source["namespace"], path + ".source.namespace")))
            omitted.append(path + ".source.path/line: retained in mapping; no generic navigation")
            mapping.setdefault("sources", {})[nid] = source
        if "metrics" in node:
            bits.append(metrics(node["metrics"], path + ".metrics", omitted))
        if "optional" in node:
            if not isinstance(node["optional"], dict):
                fail("invalid-document", path + ".optional must be an object")
            omitted.extend(path + ".optional." + name for name in node["optional"])
        rendered = "{" + " ".join(bits) + "}"
        (foreign if kind == "external" else package_nodes[pid]).append(rendered)
    edges = []
    for edge in relations:
        fields(edge, {"id", "from", "to", "kind", "label"}, "relation")
        rid = text(edge.get("id"), "relation.id")
        if rid in mapping["relations"]:
            fail("invalid-document", "duplicate relation identity")
        kind = edge.get("kind")
        if not isinstance(kind, str) or kind not in RELATIONS:
            fail("unsupported-relation", "unsupported relation kind")
        for end in ("from", "to"):
            if not isinstance(edge.get(end), str) or edge[end] not in mapping["nodes"]:
                fail("invalid-document", "relation references unknown node")
        mapped = {end: mapping["nodes"][edge[end]] for end in ("from", "to")}
        mapping["relations"][rid] = dict(mapped, kind=kind, index=len(edges))
        label = " :label " + quoted(text(edge["label"], "relation.label")) if "label" in edge else ""
        edges.append("{:from :" + mapped["from"] + " :to :" + mapped["to"] + " :kind :" + kind + label + "}")
    rendered_packages = ["{:id :" + (mapping["packages"][pid] if pid is not None else "unassigned") +
                         " :label " + quoted(package_labels[pid]) + " :classes [" + " ".join(items) + "]}"
                         for pid, items in package_nodes.items() if items or pid is not None]
    title = text(document.get("title", document_id), "title")
    edn = ("{:schema-version 1 :document-id " + quoted(document_id) + " :id :architecture :title " + quoted(title) +
           " :packages [" + " ".join(rendered_packages) + "] :foreign [" + " ".join(foreign) +
           "] :edges [" + " ".join(edges) + "]}\n")
    return edn.encode("utf-8"), mapping, omitted
