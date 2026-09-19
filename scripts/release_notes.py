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
    lines = ["# " + product["headline"], "", product["description"], "", product["stances"], "", "## Compatibility", ""]
    lines += ["- " + row["id"] + ": " + row["status"] for row in data["clients"]]
    lines += ["", "Native restrictions remain authoritative. See the versioned compatibility catalog for evidence and gaps.",
              "", "## Migration", "", "Sync projects one shared catalog into selected runtimes. Review drift and adoption conflicts before applying.",
              "Read docs/runtime-installation.md for recovery and docs/bmad.md for task continuation."]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    print(notes(), end="")
