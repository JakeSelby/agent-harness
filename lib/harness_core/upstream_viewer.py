"""Thin adapter to the standalone uml-viewer public CLI, without private viewer imports."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from . import integrations as api, viewer_profile


def private(directory):
    directory = Path(directory)
    if directory.is_symlink():
        api.fail("path-denied", "adapter storage cannot be a symlink")
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    return directory


def immutable(path, data):
    try:
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        if path.is_symlink() or path.read_bytes() != data:
            api.fail("snapshot-conflict", "immutable snapshot content changed")
        return
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def call(executable, *args):
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        proc = subprocess.Popen([executable, *args, "--json"], stdin=subprocess.DEVNULL, stdout=out, stderr=err)
        deadline = time.monotonic() + 20
        try:
            while proc.poll() is None:
                if os.fstat(out.fileno()).st_size > api.LIMIT or os.fstat(err.fileno()).st_size > api.LIMIT:
                    raise api.IntegrationError("resource-limit", "upstream result too large", True)
                if time.monotonic() >= deadline:
                    raise api.IntegrationError("upstream-timeout", "inspect session before retrying", True)
                time.sleep(0.01)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
        out.seek(0)
        raw = out.read(api.LIMIT + 1)
        if len(raw) > api.LIMIT or os.fstat(err.fileno()).st_size > api.LIMIT:
            api.fail("resource-limit", "upstream result too large")
    try:
        result = json.loads(raw, parse_constant=lambda _: api.fail("invalid-response", "nonfinite upstream JSON"))
    except (ValueError, UnicodeError):
        api.fail("invalid-response", "upstream public client did not return JSON")
    if not isinstance(result, dict):
        api.fail("invalid-response", "upstream public client returned a nonobject")
    if proc.returncode and result.get("status") not in ("rejected", "indeterminate"):
        api.fail("upstream-failed", "upstream client failed without a structured error")
    return result


def normalized(value):
    if isinstance(value, dict):
        return {key.replace("-", "_"): normalized(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalized(item) for item in value]
    return value


def translated(result):
    status = result.get("status")
    if status in ("rejected", "indeterminate"):
        return {"status": "indeterminate" if status == "indeterminate" else "error",
                "error": normalized(result.get("error", {"code": "upstream-failed"})), "result": normalized(result)}
    if status not in ("valid", "ok", "applied", "closed", "restarting", "pending", "claimed", "completed", "cancelled", "too-late"):
        if status is not None or result.get("lifecycle") not in ("starting", "ready", "closed", "restarting"):
            raise api.IntegrationError("invalid-response", "upstream returned an unknown outcome; inspect before retrying", True)
    return {"status": "ok", "result": normalized(result)}


def authorized_context(payload, settings=None):
    root = payload.get("project_root")
    if not isinstance(root, str) or not Path(root).is_absolute() or not Path(root).is_dir():
        api.fail("invalid-input", "project_root must name an existing absolute directory")
    project = Path(root).resolve()
    values = (settings or {}).get("allowed_roots", [])
    if (not isinstance(values, list) or
            any(not isinstance(value, str) or not Path(value).is_absolute() or not Path(value).is_dir()
                for value in values)):
        api.fail("invalid-configuration", "settings.allowed_roots must contain existing absolute directories")
    return project, [project] + [Path(value).resolve() for value in values]


def authorized_path(value, field, roots, directory=False):
    if not isinstance(value, str) or not Path(value).is_absolute():
        api.fail("invalid-input", field + " must be absolute")
    try:
        path = Path(value).resolve(strict=True)
    except (OSError, RuntimeError):
        api.fail("invalid-input", field + " does not exist")
    if not any(path == root or root in path.parents for root in roots):
        api.fail("path-denied", field + " is outside the authorized roots")
    if directory and not path.is_dir():
        api.fail("invalid-input", field + " must be a directory")
    if not directory and not path.is_file():
        api.fail("invalid-input", field + " must be a file")
    return path


def snapshot(payload, storage, roots=None):
    doc = payload.get("document")
    if not isinstance(doc, dict) or not isinstance(doc.get("path"), str) or not Path(doc["path"]).is_absolute():
        api.fail("invalid-input", "document.path must be an absolute profile JSON path")
    roots = roots or authorized_context(payload)[1]
    path = authorized_path(doc["path"], "document.path", roots)
    with path.open("rb") as stream:
        raw = stream.read(api.LIMIT + 1)
    if len(raw) > api.LIMIT:
        api.fail("resource-limit", "profile exceeds 1 MiB")
    if hashlib.sha256(raw).hexdigest() != doc.get("sha256"):
        api.fail("digest-mismatch", "profile content changed")
    try:
        profile = json.loads(raw)
    except (ValueError, UnicodeError):
        api.fail("invalid-document", "profile is not JSON")
    edn, mapping, omitted = viewer_profile.project(profile)
    digest = hashlib.sha256(edn).hexdigest()
    directory = private(storage / "snapshots")
    target = directory / (digest + ".edn")
    immutable(target, edn)
    map_path = directory / (digest + "." + doc["sha256"] + ".mapping.json")
    immutable(map_path, api.encoded(mapping))
    return {"path": str(target), "sha256": digest, "profile_sha256": doc["sha256"],
            "mapping": str(map_path), "omitted": omitted, "document_id": profile["document_id"]}


def root_arguments(payload, storage, settings=None, context=None):
    project, roots = context or authorized_context(payload, settings)
    result = ["--project-root", str(project), "--diagram-root", str(storage / "snapshots")]
    for key, flag in (("source_roots", "--source-root"), ("output_roots", "--output-root")):
        values = payload.get(key, [])
        if not isinstance(values, list):
            api.fail("invalid-input", key + " must contain absolute paths")
        for value in values:
            result.extend([flag, str(authorized_path(value, key, roots, directory=True))])
    if payload.get("metrics_root") is not None:
        result.extend(["--metrics-root", str(authorized_path(payload["metrics_root"], "metrics_root",
                                                             roots, directory=True))])
    if payload.get("consumer") is not None:
        result.extend(["--consumer", viewer_profile.text(payload["consumer"], "consumer")])
    return result


def open_viewer(executable, request, payload, storage, context):
    args = root_arguments(payload, storage, request.get("settings"), context)
    projected = snapshot(payload, storage, context[1])
    run = private(storage / "runs" / request["request_id"])
    session_dir = run / "session"
    with api.reconcile.lock(run):
        if (session_dir / "descriptor.edn").exists():
            api.fail("open-already-attempted", "inspect the existing session; opening is never automatically replayed")
        stdout_path, stderr_path = run / "stdout.log", run / "stderr.log"
        with stdout_path.open("wb") as out, stderr_path.open("wb") as err:
            os.chmod(stdout_path, 0o600)
            os.chmod(stderr_path, 0o600)
            proc = subprocess.Popen([executable, "open", "--json", "--session-dir", str(session_dir),
                                     "--file", projected["path"], *args], stdin=subprocess.DEVNULL,
                                    stdout=out, stderr=err, start_new_session=True)
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if stdout_path.stat().st_size > api.LIMIT or stderr_path.stat().st_size > api.LIMIT:
                raise api.IntegrationError("resource-limit", "viewer startup output exceeded limit; inspect owned session", True)
            for line in stdout_path.read_bytes().splitlines():
                try:
                    ready = json.loads(line)
                except (ValueError, UnicodeError):
                    continue
                if isinstance(ready, dict) and ready.get("status") == "rejected":
                    return translated(ready)
                if isinstance(ready, dict) and ready.get("lifecycle") == "ready":
                    if not isinstance(ready.get("session-id"), str) or not isinstance(ready.get("epoch"), str):
                        raise api.IntegrationError("invalid-response", "invalid upstream readiness identity", True)
                    return {"status": "ok", "result": {
                        "session": {"directory": str(session_dir), "id": ready["session-id"],
                                    "epoch": ready["epoch"], "project_root": str(context[0])},
                        "epoch": ready["epoch"], "revision": ready["revision"], "document_id": ready["document-id"], "sha256": ready["sha256"],
                        "capabilities": ready["capabilities"], "projection": projected}}
            if proc.poll() is not None:
                api.fail("open-failed", "viewer exited before readiness; inspect " + str(stderr_path))
            time.sleep(0.05)
    raise api.IntegrationError("open-timeout", "viewer readiness unknown; inspect " + str(session_dir), True)


def execute(request):
    if (not isinstance(request, dict) or type(request.get("contract_version")) is not int or
            request["contract_version"] != 1):
        api.fail("unsupported-contract", "adapter contract_version must be 1")
    request_id = request.get("request_id")
    try:
        if str(uuid.UUID(request_id)) != request_id:
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        api.fail("invalid-input", "request_id must be a canonical UUID")
    settings, payload = request.get("settings", {}), request.get("input", {})
    if not isinstance(settings, dict) or not isinstance(payload, dict):
        api.fail("invalid-input", "settings and input must be objects")
    executable = settings.get("viewer_executable")
    if not isinstance(executable, str) or not Path(executable).is_absolute():
        api.fail("implementation-unavailable", "settings.viewer_executable must be absolute")
    operation = request.get("operation")
    if operation == "describe":
        result = call(executable, "describe")
        if result.get("protocol-version") != 1:
            api.fail("unsupported-protocol", "upstream protocol 1 required")
        return {"status": "ok", "result": normalized(result)}
    base = settings.get("state_root")
    if base is None:
        base = Path(os.environ.get("HARNESS_HOME", str(Path.home()))) / ".local/state/agent-harness/upstream-viewer"
    if not isinstance(base, (str, Path)) or not Path(base).is_absolute():
        api.fail("invalid-input", "state_root must be absolute")
    storage = private(base)
    context = authorized_context(payload, settings) if operation in ("validate", "open") else None
    if operation == "validate":
        projected = snapshot(payload, storage, context[1])
        result = translated(call(executable, "validate", "--file", projected["path"]))
        result.setdefault("result", {})["projection"] = projected
        return result
    if operation == "open":
        return open_viewer(executable, request, payload, storage, context)
    session = payload.get("session")
    if (not isinstance(session, dict) or not all(isinstance(session.get(k), str) and session[k]
                                               for k in ("directory", "id", "epoch"))):
        api.fail("invalid-session", "upstream session reference is incomplete")
    directory = Path(session["directory"])
    if not directory.is_absolute() or not str(directory.resolve()).startswith(str(storage.resolve()) + os.sep):
        api.fail("invalid-session", "session is outside adapter storage")
    if operation == "status":
        current = call(executable, "status", "--session", str(directory))
        if current.get("status") in ("rejected", "indeterminate"):
            return translated(current)
        if current.get("session-id") != session["id"] or current.get("epoch") != session["epoch"]:
            api.fail("session-lost", "upstream session was restarted")
        return translated(current)
    operations = {"replace-document": "display", "close": "close", "cancel": "cancel",
                  "request-regeneration": "regen", "claim-regeneration": "claim",
                  "complete-generation": "complete-generation", "cancel-generation": "cancel-generation"}
    if operation not in operations:
        api.fail("unsupported-operation", "unsupported viewer operation")
    control = {"protocol-version": 1, "session-id": session["id"], "epoch": session["epoch"],
               "request-id": request_id, "op": operations[operation]}
    projected = None
    if operation == "replace-document":
        project = payload.get("project_root")
        if project is None:
            project = session.get("project_root")
            if project is not None:
                payload["project_root"] = project
        context = authorized_context(payload, settings)
        projected = snapshot(payload, storage, context[1])
        control.update({"expected-revision": payload.get("expected_revision"),
                        "path": projected["path"], "sha256": projected["sha256"]})
    for key in ("consumer", "regeneration_id", "claim_id", "target_request_id"):
        if key in payload:
            control[key.replace("_", "-")] = payload[key]
    requests = private(storage / "requests" / session["epoch"])
    target = requests / (request_id + ".json")
    immutable(target, api.encoded(control))
    result = translated(call(executable, "control", "--session", str(directory), "--request-json", str(target)))
    if projected is not None:
        result.setdefault("result", {})["projection"] = projected
    return result


def main():
    request = {}
    try:
        raw = sys.stdin.buffer.read(api.LIMIT + 1)
        if len(raw) > api.LIMIT:
            api.fail("resource-limit", "adapter request exceeds 1 MiB")
        request = json.loads(raw)
        response = execute(request)
    except (ValueError, OSError) as exc:
        response = {"status": "indeterminate" if getattr(exc, "indeterminate", False) else "error",
                    "error": {"code": getattr(exc, "code", "invalid-input"), "message": str(exc)}}
    envelope = {key: request.get(key) for key in ("request_id", "operation", "implementation")} if isinstance(request, dict) else {}
    print(json.dumps(dict(envelope, contract_version=1, **response), allow_nan=False))
    return 0 if response["status"] == "ok" else 1
