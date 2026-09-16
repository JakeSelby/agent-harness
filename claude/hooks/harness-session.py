#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""SessionStart hook: report harness drift and per-session HARNESS_* env overrides.

Silent when there is nothing to say, so a clean session costs no context. Never fails.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

STATE = Path.home() / ".local" / "state" / "agent-harness"
CONFIG = Path.home() / ".config" / "agent-harness" / "config.json"


def load(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def drift_line(repo):
    tool = Path(repo) / "bin" / "harness"
    if not tool.exists():
        return None
    try:
        out = subprocess.run(
            [sys.executable, str(tool), "diff", "--quiet"],
            capture_output=True, text=True, timeout=3,
        )
    except Exception:
        return None
    text = (out.stdout or "").strip()
    return text if out.returncode != 0 and text else None


def override_lines(config):
    lines = []
    stances = (config or {}).get("stances", {})
    for key, value in os.environ.items():
        if key.startswith("HARNESS_STANCE_"):
            name = key[len("HARNESS_STANCE_"):].lower().replace("_", "-")
            if stances.get(name) != value:
                lines.append(f"For this session the `{name}` stance is `{value}` "
                             f"(config says `{stances.get(name, 'unset')}`); follow the "
                             f"`{value}` variant under claude/stances/{name}/ in the harness "
                             "checkout instead of the linked one.")
        elif key == "HARNESS_PERMISSIONS":
            if (config or {}).get("permissions") != value:
                lines.append(f"For this session the permission posture is `{value}`.")
    return lines


def main():
    manifest = load(STATE / "manifest.json")
    config = load(CONFIG)
    lines = []
    if manifest and manifest.get("repo"):
        d = drift_line(manifest["repo"])
        if d:
            lines.append("agent-harness drift: " + d)
    lines.extend(override_lines(config))
    if not lines:
        return
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": "\n".join(lines),
        }
    }))


if __name__ == "__main__":
    main()
