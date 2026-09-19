#!/usr/bin/env python3
"""Render release notes from the same product and compatibility authorities as the site."""
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
from harness_core import compatibility


def notes(root=ROOT):
    product = json.loads((root / "product.json").read_text())
    data = compatibility.catalog(root)
    migration = json.loads((root / "compatibility" / "migration.json").read_text())
    version = (root / "VERSION").read_text().strip()
    if (migration.get("schema_version") != 1 or migration.get("harness_version") != version or
            not isinstance(migration.get("summary"), str) or not migration["summary"] or
            not isinstance(migration.get("actions"), list) or not migration["actions"] or
            any(not isinstance(item, str) or not item for item in migration["actions"]) or
            not isinstance(migration.get("recovery"), list) or not migration["recovery"] or
            any(not isinstance(item, str) or not item for item in migration["recovery"])):
        raise ValueError("migration metadata must match VERSION and contain actions and recovery")
    policy = "https://github.com/JakeSelby/agent-harness/blob/v%s/docs/compatibility-policy.md" % version
    lines = ["# " + product["headline"], "", product["description"], "", product["stances"], "", "## Compatibility", ""]
    lines += ["- " + row["id"] + ": " + row["status"] for row in data["clients"]]
    lines += ["", "Native restrictions remain authoritative. See the versioned compatibility catalog for evidence and gaps.",
              "", "## Compatibility policy", "",
              "Stable interfaces, preview boundaries, deprecation, migration and failed-release recovery are defined in the [versioned compatibility policy](%s)." % policy,
              "", "## Migration", "", migration["summary"], ""]
    lines += ["- " + item for item in migration["actions"]]
    lines += ["", "### Recovery", ""] + ["- " + item for item in migration["recovery"]]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    print(notes(), end="")
