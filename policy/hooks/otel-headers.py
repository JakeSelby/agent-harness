#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Print the OTLP headers a runtime should send, as one JSON object, and nothing else.

Claude Code reads the path to this script from the `otelHeadersHelper` setting, runs it about
every 29 minutes, and parses its standard output as `{"name": "value"}`. `harness sync` writes
that setting only when `telemetry.native` is on and a header source is configured.

Every value here is a credential, so a failure prints **nothing at all** and fails by exit
status: text on standard output would be parsed as a header, and text on standard error lands
in logs the value was deliberately kept out of. The sources are the ones the exporter uses and
no others — the named environment variable and the mode-600 file outside every work tree.

A variable reaches this script only if it reached the runtime that spawned it, which a
desktop-launched client may not have; `headers_file` is the source that does not depend on
that. See docs/telemetry.md.
"""
import importlib.util
import json
import sys
from pathlib import Path


def load():
    """The exporter's own settings and header rules, from the file beside this one."""
    path = Path(__file__).resolve().parent / "telemetry.py"
    spec = importlib.util.spec_from_file_location("harness_telemetry", str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    try:
        telemetry = load()
        config = telemetry.settings()
        if not config.get("native"):
            return 1
        values = telemetry.headers(config)
    except Exception:
        return 1
    if not values:
        return 1
    sys.stdout.write(json.dumps({str(k): str(v) for k, v in sorted(values.items())}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
