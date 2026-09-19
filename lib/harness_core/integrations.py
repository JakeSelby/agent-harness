"""User-selected implementation bindings and pinned viewer references.

Adapters own viewer state. This module resolves executables and records their acknowledged
references; inspecting configuration never executes an adapter.
"""
import json
import os
import re
import subprocess
import tempfile
import time
import uuid
from copy import deepcopy
from pathlib import Path
from . import catalog, reconcile

VERSION = 1
LIMIT = 1024 * 1024
SESSION_LIMIT = 4 * LIMIT
CAPABILITY = "architecture-viewer"
OPERATIONS = {"describe", "validate", "open", "replace-document", "status", "close"}
OPTIONAL_OPERATIONS = {"request-regeneration", "claim-regeneration", "complete-generation", "cancel-generation", "cancel"}
OPERATIONS |= OPTIONAL_OPERATIONS
SESSION_OPERATIONS = {"replace-document", "status", "close"} | OPTIONAL_OPERATIONS


class IntegrationError(ValueError):
    def __init__(self, code, message, indeterminate=False):
        super().__init__(message)
        self.code = code
        self.indeterminate = indeterminate


def fail(code, message):
    raise IntegrationError(code, message)


def identifier(value):
    try:
        return catalog.identifier(value)
    except ValueError as exc:
        fail("invalid-configuration", str(exc))


def encoded(value, limit=LIMIT):
    try:
        content = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, RecursionError):
        fail("invalid-input", "integration data must be finite JSON")
    if len(content) > limit:
        fail("resource-limit", "integration data exceeds its size limit")
    return content


def read_json(path, limit=LIMIT):
    try:
        with Path(path).open("rb") as stream:
            raw = stream.read(limit + 1)
        if len(raw) > limit:
            fail("resource-limit", "integration data exceeds its size limit")
        value = json.loads(raw, parse_constant=lambda value: fail("invalid-input", "nonfinite JSON"))
        if not isinstance(value, dict):
            fail("invalid-input", "integration data must be an object")
        return value
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        fail("invalid-input", "cannot read integration JSON: " + str(exc))


def descriptor(value):
    if not isinstance(value, dict):
        fail("invalid-configuration", "adapter descriptor must be an object")
    allowed = {"capability", "contract_version", "argv", "settings", "name", "version", "capabilities"}
    if set(value) - allowed:
        fail("invalid-configuration", "unknown adapter descriptor fields")
    identifier(value.get("capability"))
    if type(value.get("contract_version")) is not int or value["contract_version"] != VERSION:
        fail("unsupported-contract", "adapter contract_version must be 1")
    argv = value.get("argv")
    if (not isinstance(argv, list) or not argv or
            any(not isinstance(x, str) or not x or "\0" in x for x in argv) or
            not Path(argv[0]).is_absolute()):
        fail("invalid-configuration", "adapter argv requires an absolute executable and literal arguments")
    if not isinstance(value.get("settings", {}), dict):
        fail("invalid-configuration", "adapter settings must be an object")
    for key in ("name", "version"):
        if key in value and (not isinstance(value[key], str) or not value[key]):
            fail("invalid-configuration", key + " must be a nonempty string")
    caps = value.get("capabilities", [])
    if not isinstance(caps, list) or any(not isinstance(x, str) or not x for x in caps):
        fail("invalid-configuration", "capabilities must be an array of names")
    encoded(value)
    return deepcopy(value)


def merge_slots(defaults, user):
    result = deepcopy(defaults)
    if not isinstance(result, dict) or not isinstance(user, dict):
        fail("invalid-configuration", "integrations must be an object")
    for key, value in user.items():
        identifier(key)
        if not isinstance(value, dict):
            fail("invalid-configuration", "integration selection must be an object")
        result[key] = dict(result.get(key, {}), **value)
    return result


def selection(config, capability=CAPABILITY, implementation=None, adapter=None):
    identifier(capability)
    slots = config.get("integrations", {})
    if not isinstance(slots, dict) or not isinstance(slots.get(capability, {}), dict):
        fail("invalid-configuration", "integrations must contain selection objects")
    value = dict(slots.get(capability, {}))
    if set(value) - {"implementation", "adapter"}:
        fail("invalid-configuration", "unknown integration selection fields")
    if implementation is not None:
        value["implementation"] = implementation
    if adapter is not None:
        value["adapter"] = adapter
    mode = value.get("implementation", "builtin")
    if mode not in ("builtin", "custom"):
        fail("invalid-configuration", "implementation must be builtin or custom")
    if value.get("adapter") is not None:
        identifier(value["adapter"])
    if mode == "custom" and not value.get("adapter"):
        fail("missing-adapter", "custom implementation requires a registered adapter")
    return dict(value, implementation=mode)


def resolve(root, config, capability=CAPABILITY, implementation=None, adapter=None, source="user"):
    selected = selection(config, capability, implementation, adapter)
    mode = selected["implementation"]
    if adapter is not None and mode != "custom":
        fail("invalid-input", "an invocation adapter requires custom implementation")
    result = {"capability": capability, "implementation": mode,
              "selection_source": "invocation" if implementation is not None or adapter is not None else source,
              "contract_version": VERSION, "availability": "unavailable", "qualification": "unverified"}
    if mode == "builtin":
        path = Path(root) / "integrations" / capability / "builtin.json"
        if not path.is_file():
            return dict(result, reason="builtin implementation has no installed adapter", adapter=None)
        item = read_json(path)
        adapter_id = item.pop("id", None)
        identifier(adapter_id)
    else:
        adapter_id = selected["adapter"]
        registry = config.get("integration_adapters", {})
        if not isinstance(registry, dict) or adapter_id not in registry:
            fail("missing-adapter", "custom adapter is not registered: " + adapter_id)
        item = registry[adapter_id]
    item = descriptor(item)
    if item["capability"] != capability:
        fail("incompatible-adapter", "adapter belongs to another capability")
    executable = Path(item["argv"][0])
    available = executable.is_file() and os.access(str(executable), os.X_OK)
    return dict(result, adapter=adapter_id, descriptor=item,
                availability="available" if available else "unavailable",
                reason=None if available else "adapter executable is missing or not executable")


def register(path, item):
    item = deepcopy(item)
    adapter_id = item.pop("id", None)
    identifier(adapter_id)
    item = descriptor(item)
    path = Path(path)
    with reconcile.lock(path.parent):
        if path.is_symlink():
            fail("invalid-configuration", "configuration cannot be a symlink")
        config = read_json(path) if path.exists() else {}
        registry = config.setdefault("integration_adapters", {})
        if not isinstance(registry, dict):
            fail("invalid-configuration", "integration_adapters must be an object")
        registry[adapter_id] = item
        reconcile.atomic_text(path, encoded(config).decode() + "\n")
    return adapter_id


def require_available(binding):
    if binding["availability"] != "available":
        fail("implementation-unavailable", binding["reason"])


def invoke(binding, operation, payload=None, request_id=None, timeout=30):
    """Execute a bounded JSON adapter call; a timeout never implies cancellation."""
    require_available(binding)
    if operation not in OPERATIONS:
        fail("unsupported-operation", "unknown viewer operation")
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not 0 < timeout <= 300:
        fail("invalid-input", "timeout must be greater than zero and at most 300 seconds")
    request_id = request_id or str(uuid.uuid4())
    try:
        if str(uuid.UUID(request_id)) != request_id:
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        fail("invalid-input", "request_id must be a canonical UUID")
    if payload is not None and not isinstance(payload, dict):
        fail("invalid-input", "operation input must be an object")
    item = descriptor(binding["descriptor"])
    request = {"contract_version": VERSION, "request_id": request_id, "operation": operation,
               "implementation": binding["adapter"], "settings": item.get("settings", {}),
               "input": payload or {}}
    mutating = operation in ({"open", "replace-document", "close"} | OPTIONAL_OPERATIONS)
    with tempfile.TemporaryFile() as stdin, tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        stdin.write(encoded(request))
        stdin.seek(0)
        try:
            proc = subprocess.Popen(item["argv"], stdin=stdin, stdout=stdout, stderr=stderr,
                                    cwd=str(Path(item["argv"][0]).parent), shell=False)
        except OSError as exc:
            fail("adapter-unavailable", str(exc))
        deadline = time.monotonic() + timeout
        try:
            while proc.poll() is None:
                if os.fstat(stdout.fileno()).st_size > LIMIT or os.fstat(stderr.fileno()).st_size > LIMIT:
                    raise IntegrationError("resource-limit", "adapter output exceeds 1 MiB", mutating)
                if time.monotonic() >= deadline:
                    raise IntegrationError("adapter-timeout", "adapter outcome unknown; inspect before retrying", mutating)
                time.sleep(0.01)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
        stdout.seek(0)
        raw = stdout.read(LIMIT + 1)
        if len(raw) > LIMIT or os.fstat(stderr.fileno()).st_size > LIMIT:
            raise IntegrationError("resource-limit", "adapter output exceeds 1 MiB", mutating)
        try:
            response = json.loads(raw, parse_constant=lambda _: fail("invalid-response", "nonfinite JSON"))
        except (ValueError, UnicodeError, RecursionError):
            raise IntegrationError("invalid-response", "adapter did not return valid JSON", mutating)
    if (not isinstance(response, dict) or type(response.get("contract_version")) is not int or
            response["contract_version"] != VERSION or response.get("request_id") != request_id or
            response.get("operation") != operation or response.get("implementation") != binding["adapter"]):
        raise IntegrationError("invalid-response", "adapter response identity mismatch", mutating)
    if response.get("status") not in ("ok", "error", "indeterminate"):
        raise IntegrationError("invalid-response", "unknown adapter result status", mutating)
    if response["status"] == "ok":
        if proc.returncode != 0 or not isinstance(response.get("result"), dict):
            raise IntegrationError("invalid-response", "success requires zero exit and an object result", mutating)
    elif not isinstance(response.get("error"), dict) or not isinstance(response["error"].get("code"), str):
        raise IntegrationError("invalid-response", "failure requires a structured error", mutating)
    return response


def session_path(directory, reference):
    try:
        if str(uuid.UUID(reference)) != reference:
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        fail("invalid-session", "session reference must be a canonical UUID")
    directory = Path(directory)
    if directory.is_symlink():
        fail("invalid-session", "session storage cannot be a symlink")
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = directory / (reference + ".json")
    if path.is_symlink():
        fail("invalid-session", "session reference cannot be a symlink")
    return path


def observation(response):
    """Keep continuation evidence without duplicating arbitrary adapter response data."""
    result = {key: response[key] for key in ("request_id", "operation", "implementation", "status", "error") if key in response}
    details = response.get("result", {})
    details = details if isinstance(details, dict) else {}
    result["result"] = {key: value for key, value in details.items()
                        if key in {"revision", "document_id", "epoch", "sha256", "status"}}
    return result


def save_record(path, record):
    reconcile.atomic_text(path, encoded(record, limit=SESSION_LIMIT).decode() + "\n")


def observe_session(path, response):
    try:
        with reconcile.lock(path.parent):
            record = read_json(path, limit=SESSION_LIMIT)
            record["last_observation"] = observation(response)
            save_record(path, record)
    except (ValueError, OSError) as exc:
        return "Acknowledgement retained; local observation was not saved: " + str(exc)
    return None


def viewer(root, config, directory, operation, payload=None, reference=None,
           implementation=None, adapter=None, request_id=None, timeout=30):
    """Pin the adapter when opening; later selection changes cannot redirect a session."""
    if payload is not None and not isinstance(payload, dict):
        fail("invalid-input", "operation input must be an object")
    payload = deepcopy(payload or {})
    if not isinstance(payload, dict) or "session" in payload:
        fail("invalid-input", "session is supplied by the pinned reference, not operation input")
    if operation in SESSION_OPERATIONS:
        if implementation is not None or adapter is not None:
            fail("invalid-input", "existing sessions cannot change implementation")
        path = session_path(directory, reference)
        record = read_json(path, limit=SESSION_LIMIT)
        if record.get("schema_version") != VERSION or record.get("reference") != reference:
            fail("invalid-session", "invalid session reference record")
        binding = record.get("binding")
        if (not isinstance(binding, dict) or not isinstance(binding.get("descriptor"), dict) or
                not isinstance(binding.get("adapter"), str) or binding.get("capability") != CAPABILITY or
                binding.get("contract_version") != VERSION):
            fail("invalid-session", "corrupt pinned adapter reference")
        identifier(binding["adapter"])
        item = descriptor(binding["descriptor"])
        if item["capability"] != CAPABILITY:
            fail("invalid-session", "pinned adapter belongs to another capability")
        # Availability is checked now without resolving the current selection.
        exe = Path(binding["descriptor"]["argv"][0])
        binding["availability"] = "available" if exe.is_file() and os.access(str(exe), os.X_OK) else "unavailable"
        binding["reason"] = "pinned adapter executable is unavailable"
        if not isinstance(record.get("session"), dict):
            fail("indeterminate-session", "open was not acknowledged; inspect the adapter before reopening")
        payload["session"] = record["session"]
    else:
        if reference is not None:
            fail("invalid-input", "this operation does not accept a session reference")
        binding = resolve(root, config, implementation=implementation, adapter=adapter)
    if operation == "replace-document":
        if type(payload.get("expected_revision")) is not int or payload["expected_revision"] < 0:
            fail("invalid-input", "replacement requires a nonnegative expected_revision")
        document = payload.get("document")
        if (not isinstance(document, dict) or not isinstance(document.get("sha256"), str) or
                not re.fullmatch(r"[a-f0-9]{64}", document["sha256"])):
            fail("invalid-input", "replacement requires document sha256")
    required = payload.pop("required_capabilities", [])
    if not isinstance(required, list) or any(not isinstance(x, str) for x in required):
        fail("invalid-input", "required_capabilities must be an array of names")
    if operation in SESSION_OPERATIONS and (required or operation in OPTIONAL_OPERATIONS):
        caps = record.get("capabilities", [])
        needed = set(required) | ({"regeneration-request"} if operation in OPTIONAL_OPERATIONS - {"cancel"} else {operation})
        if not needed.issubset(caps):
            fail("unsupported-capability", "session lacks: " + ", ".join(sorted(needed - set(caps))))
    elif operation in {"open", "validate"} or required:
        described = invoke(binding, "describe", timeout=timeout)
        if described["status"] != "ok":
            return described
        caps = described["result"].get("capabilities")
        if not isinstance(caps, list) or any(not isinstance(x, str) for x in caps):
            fail("invalid-response", "describe requires capability names")
        needed = set(required) | ({"regeneration-request"} if operation in OPTIONAL_OPERATIONS - {"cancel"} else {operation})
        if not needed.issubset(caps):
            fail("unsupported-capability", "missing capabilities: " + ", ".join(sorted(needed - set(caps))))
    if operation != "open":
        if operation in SESSION_OPERATIONS:
            request_id = request_id or str(uuid.uuid4())
            with reconcile.lock(Path(directory)):
                record = read_json(path, limit=SESSION_LIMIT)
                record["last_attempt"] = {"operation": operation, "request_id": request_id}
                save_record(path, record)
        try:
            response = invoke(binding, operation, payload, request_id, timeout)
        except IntegrationError as exc:
            if operation in SESSION_OPERATIONS:
                exc.request_id = request_id
                exc.persistence_warning = observe_session(path, {
                    "request_id": request_id, "operation": operation,
                    "status": "indeterminate" if exc.indeterminate else "error",
                    "error": {"code": exc.code, "message": str(exc)}})
            raise
        if operation in SESSION_OPERATIONS:
            warning = observe_session(path, response)
            if warning:
                response = dict(response, persistence_warning=warning)
        return response
    require_available(binding)
    reference = str(uuid.uuid4())
    request_id = request_id or str(uuid.uuid4())
    path = session_path(directory, reference)
    record = {"schema_version": VERSION, "reference": reference, "binding": binding,
              "open_request_id": request_id, "session": None}
    save_record(path, record)
    try:
        response = invoke(binding, operation, payload, request_id, timeout)
        if response["status"] == "ok":
            session = response["result"].get("session")
            if not isinstance(session, dict) or not session:
                raise IntegrationError("invalid-response", "open requires an opaque session object", True)
            result = response["result"]
            if (type(result.get("revision")) is not int or result["revision"] < 0 or
                    not isinstance(result.get("document_id"), str) or not result["document_id"] or
                    not isinstance(result.get("epoch"), str) or not result["epoch"] or
                    not isinstance(result.get("sha256"), str) or not re.fullmatch(r"[a-f0-9]{64}", result["sha256"]) or
                    not isinstance(result.get("capabilities"), list) or any(not isinstance(x, str) for x in result["capabilities"])):
                raise IntegrationError("invalid-response", "open acknowledgement is incomplete", True)
            record["session"] = session
            record["capabilities"] = result["capabilities"]
            if not set(required).issubset(result["capabilities"]):
                record["open_result"] = observation(response)
                raise IntegrationError("unsupported-capability", "opened session lacks required capabilities; inspect and close the pinned session", True)
        record["open_result"] = observation(response)
        try:
            save_record(path, record)
        except (ValueError, OSError) as exc:
            return dict(response, session_reference=reference, reference_persisted=False,
                        persistence_warning="Retain this acknowledgement; session reference was not saved: " + str(exc))
    except IntegrationError as exc:
        record["open_error"] = {"code": exc.code, "indeterminate": exc.indeterminate}
        wrapped = IntegrationError(exc.code, str(exc) + "; session reference: " + reference, exc.indeterminate)
        wrapped.request_id = request_id
        try:
            save_record(path, record)
        except (ValueError, OSError) as storage_error:
            wrapped.persistence_warning = str(storage_error)
        raise wrapped
    return dict(response, session_reference=reference)
