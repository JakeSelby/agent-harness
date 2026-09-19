#!/usr/bin/env python3
"""Opt-in local contract check against an installed standalone viewer (opens a window)."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--viewer", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    records = []
    report = {"status": "failed", "viewer": str(args.viewer.resolve()), "operations": records}
    try:
        with tempfile.TemporaryDirectory(prefix="harness-viewer-acceptance-") as temp:
            home = Path(temp)
            env = dict(os.environ, HARNESS_HOME=temp)
            cfg_path = home / ".config/agent-harness/config.json"
            cfg_path.parent.mkdir(parents=True)
            cfg = {"integrations": {"architecture-viewer": {"implementation": "custom", "adapter": "candidate"}},
                   "integration_adapters": {"candidate": {"capability": "architecture-viewer", "contract_version": 1,
                       "argv": [sys.executable, str(root / "integrations/architecture-viewer/upstream.py")],
                       "settings": {"viewer_executable": str(args.viewer.resolve()), "state_root": str(home / "viewer")}}}}
            cfg_path.write_text(json.dumps(cfg))

            def invoke(*command):
                proc = subprocess.run([sys.executable, str(root / "bin/harness"), *command], env=env,
                                      capture_output=True, text=True, timeout=40)
                result = json.loads(proc.stdout)
                records.append({"command": list(command), "exit": proc.returncode, "result": result})
                return result

            def require(condition, message):
                if not condition:
                    raise AssertionError(message)

            inputs = []
            for number, label in enumerate(("Before", "After")):
                profile = {"profile": "architecture-diagram", "schema_version": 1, "document_id": "acceptance",
                           "nodes": [{"id": "a", "kind": "class", "label": label},
                                     {"id": "b", "kind": "interface", "label": "Port"}],
                           "relations": [{"id": "uses", "from": "a", "to": "b", "kind": "dependency"}]}
                document = home / ("document-%d.json" % number)
                raw = json.dumps(profile).encode()
                document.write_bytes(raw)
                payload = {"project_root": temp, "document": {"path": str(document), "sha256": hashlib.sha256(raw).hexdigest()}}
                if number:
                    payload["expected_revision"] = 0
                input_file = home / ("input-%d.json" % number)
                input_file.write_text(json.dumps(payload))
                inputs.append(str(input_file))
            require(invoke("viewer", "validate", "--input", inputs[0])["status"] == "ok", "validation failed")
            opened = invoke("viewer", "open", "--input", inputs[0])
            require(opened["status"] == "ok", "open failed")
            reference = opened["session_reference"]
            try:
                require(opened["result"]["revision"] == 0, "unexpected initial revision")
                request = str(uuid.uuid4())
                for _ in range(2):
                    result = invoke("viewer", "replace-document", "--session", reference, "--input", inputs[1], "--request-id", request)
                    require(result["status"] == "ok" and result["result"]["revision"] == 1, "replacement or identical retry failed")
                    require(result["result"]["sha256"] == result["result"]["projection"]["sha256"] and
                            result["result"]["sha256"] != opened["result"]["sha256"], "replacement content identity did not change")
                stale = invoke("viewer", "replace-document", "--session", reference, "--input", inputs[1])
                require(stale["status"] == "error" and stale["error"]["code"] == "stale-revision", "stale write was accepted")
                cfg["integrations"]["architecture-viewer"]["implementation"] = "builtin"
                cfg["integration_adapters"] = {}
                cfg_path.write_text(json.dumps(cfg))
                observed = invoke("viewer", "status", "--session", reference)
                require(observed["status"] == "ok" and observed["result"]["revision"] == 1, "pinned continuation failed")
            finally:
                close_id = str(uuid.uuid4())
                closed = invoke("viewer", "close", "--session", reference, "--request-id", close_id)
                require(closed["status"] == "ok", "close failed")
                repeated = invoke("viewer", "close", "--session", reference, "--request-id", close_id)
                require(repeated["status"] == "ok" and repeated["result"] == closed["result"], "terminal close receipt could not be recovered")
            report["status"] = "passed"
    except (OSError, ValueError, KeyError, AssertionError, subprocess.TimeoutExpired) as exc:
        report["error"] = str(exc)
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(json.dumps(report, indent=2) + "\n")
    print(report["status"])
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
