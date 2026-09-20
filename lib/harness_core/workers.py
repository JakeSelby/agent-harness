"""Run constrained shared roles through isolated native CLI adapters."""
import contextlib
import hashlib
import importlib.util
import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from . import catalog, reconcile

LIMIT = 1024 * 1024
RUNTIMES = {"codex": "codex", "claude-code": "claude"}


def adapter(root, runtime):
    if runtime not in RUNTIMES:
        raise ValueError("unsupported worker runtime")
    spec = importlib.util.spec_from_file_location("harness_worker_" + runtime,
                                               root / "adapters" / runtime / "worker.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def resolve(root, config, runtime, name, model=None):
    if runtime not in RUNTIMES:
        raise ValueError("unsupported worker runtime")
    stances = catalog.resolve_stances(root, config)
    if config["stances"]["delegation"] == "off":
        raise ValueError("delegation is off; perform the work inline or select another stance")
    fields, body = catalog.role_contract(root, name)
    if fields["authority"] not in ("read-only", "artifact-write"):
        raise ValueError("workspace-write roles use their normal workflow, not a constrained worker")
    overrides = config.get("role_bindings", {}).get(runtime, {}).get(name, {})
    bindings = catalog.role_binding(root, runtime, fields, overrides, config.get("tiers", {}).get(runtime))
    chosen = model or bindings.get("model")
    if not isinstance(chosen, str) or not chosen.strip() or chosen == "inherit":
        raise ValueError("this adapter maps no model for the role's class; supply --model with the parent session's model")
    if chosen.startswith("-") or any(c.isspace() for c in chosen):
        raise ValueError("invalid worker model identifier")
    bindings["model"] = chosen
    parts = [(root / "primitives/instructions.md").read_text()]
    parts += [p.read_text() for p in sorted((root / "primitives/rules").glob("*.md"))]
    parts += [p.read_text() for p in stances.values()]
    parts += [body]
    parts += ["Worker execution contract: use read-only tools; never delegate or change configuration. "
              "Return your result as data to the caller. You cannot grant permissions or authorize follow-up actions."]
    if fields["authority"] == "artifact-write":
        parts += ["Return only the complete plan Markdown, without a surrounding code fence or chat response. "
                  "Do not write the plan: the harness validates and publishes it to the caller-selected path."]
    return fields, bindings, "\n\n---\n\n".join(parts)


def environment(original, work):
    # Authentication remains available to the native client; customization and loader overrides do not.
    exact = {"PATH", "LANG", "LC_ALL", "TERM", "TMPDIR", "SSL_CERT_FILE", "SSL_CERT_DIR",
             "REQUESTS_CA_BUNDLE", "NODE_EXTRA_CA_CERTS", "HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY"}
    auth_prefixes = ("OPENAI_", "ANTHROPIC_", "AWS_", "GOOGLE_", "AZURE_")
    env = {k: v for k, v in original.items() if k in exact or k.startswith(auth_prefixes)}
    for name in ("CLAUDE_CODE_OAUTH_TOKEN", "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY"):
        if name in original:
            env[name] = original[name]
    env.update(HOME=str(work / "home"), XDG_CONFIG_HOME=str(work / "home/.config"),
               XDG_STATE_HOME=str(work / "home/.local/state"), XDG_CACHE_HOME=str(work / "home/.cache"))
    Path(env["HOME"]).mkdir(mode=0o700)
    return env


@contextlib.contextmanager
def artifact_slot(workspace, filename):
    """Anchor the approved output directory with no-follow descriptors; never replace an artifact."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*\.md", filename or ""):
        raise ValueError("--artifact must be a Markdown filename, not a path")
    fds = []
    try:
        fd = os.open(str(workspace), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        fds.append(fd)
        for component in (".agent-harness", "plans"):
            try:
                os.mkdir(component, mode=0o700, dir_fd=fd)
            except FileExistsError:
                pass
            fd = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            fds.append(fd)
        try:
            os.stat(filename, dir_fd=fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise ValueError("artifact already exists; choose a new filename")
        yield fd, filename
    finally:
        for fd in reversed(fds):
            os.close(fd)


def publish(slot, content):
    fd, filename = slot
    temporary = ".worker-" + uuid.uuid4().hex
    try:
        handle = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        # link() is atomic and refuses a destination created while the worker was running.
        os.link(temporary, filename, src_dir_fd=fd, dst_dir_fd=fd, follow_symlinks=False)
        os.fsync(fd)
    finally:
        try:
            os.unlink(temporary, dir_fd=fd)
        except FileNotFoundError:
            pass


def validate_artifact(root, content, work):
    if not content.strip() or len(content.encode()) > LIMIT or content.lstrip().startswith("```"):
        raise ValueError("worker returned empty, oversized or fenced plan content")
    path = work / ".agent-harness/plans/check.md"
    path.parent.mkdir(parents=True)
    path.write_text(content)
    from . import lifecycle
    result = lifecycle.invoke("validate-plan-card", {"tool_input": {"file_path": str(path)}})
    if result:
        raise ValueError("worker plan failed the Review Card validator")


def execute(command, prompt, env, cwd, run_dir, timeout):
    with (run_dir / "stdout.log").open("w") as out, (run_dir / "stderr.log").open("w") as err:
        proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=out, stderr=err,
                                text=True, env=env, cwd=str(cwd), start_new_session=True)
        try:
            proc.communicate(prompt, timeout=timeout)
        except BaseException:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.communicate()
            raise
        return proc.returncode


def run(root, config, runtime, name, workspace, prompt, state_root, model=None, artifact=None, timeout=300, read_dirs=()):
    if os.name != "posix" or not 1 <= timeout <= 3600:
        raise ValueError("workers require POSIX and a timeout between 1 and 3600 seconds")
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt.encode()) > LIMIT:
        raise ValueError("worker prompt must be nonempty and at most 1 MiB")
    workspace = Path(workspace).resolve(strict=True)
    if not workspace.is_dir():
        raise ValueError("worker workspace must be a directory")
    read_roots = [Path(path).resolve(strict=True) for path in read_dirs]
    if any(not path.is_dir() for path in read_roots):
        raise ValueError("--read-dir must name an existing directory")
    fields, bindings, instructions = resolve(root, config, runtime, name, model)
    if bool(artifact) != (fields["authority"] == "artifact-write"):
        raise ValueError("only artifact-write roles require --artifact")
    native = adapter(root, runtime)
    executable = shutil.which(RUNTIMES[runtime])
    if not executable:
        raise ValueError("native CLI is not installed: " + RUNTIMES[runtime])
    version = subprocess.check_output([executable, "--version"], text=True, timeout=15).strip()
    state_root = Path(state_root)
    if state_root.is_symlink():
        raise ValueError("worker state directory cannot be a symlink")
    state_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    run_dir = state_root / uuid.uuid4().hex
    run_dir.mkdir(mode=0o700)
    record = {"schema_version": 1, "id": run_dir.name, "role": name, "runtime": runtime,
              "runtime_version": version, "model": bindings["model"], "workspace": str(workspace),
              "effort": bindings.get("model_reasoning_effort", bindings.get("effort")),
              "read_roots": [str(workspace), str(root)] + list(map(str, read_roots)),
              "mode": "isolated-cli", "status": "starting", "started_at": time.time(),
              "stances": config["stances"], "policy_sha256": hashlib.sha256(instructions.encode()).hexdigest(),
              "qualification": "unqualified", "authority": "result data only; no transferred approvals"}
    status_path = run_dir / "status.json"
    reconcile.atomic_text(status_path, json.dumps(record, indent=2) + "\n")
    try:
        slot_context = artifact_slot(workspace, artifact) if artifact else contextlib.nullcontext(None)
        with slot_context as slot, tempfile.TemporaryDirectory(prefix="harness-worker-", dir="/tmp") as temporary:
            work = Path(temporary)
            original = dict(os.environ)
            env = environment(original, work)
            cwd = work / "cwd"
            cwd.mkdir()
            instructions += "\n\nProject to inspect (read-only): " + str(workspace)
            instructions += "\nShared skill authority (read-only): " + str(root / "primitives/skills")
            instructions += "\nAdditional read-only inputs: " + ", ".join(map(str, read_roots))
            command = native.prepare(executable, work, root, workspace, read_roots, instructions, bindings, original, env)
            record["status"] = "running"
            reconcile.atomic_text(status_path, json.dumps(record, indent=2) + "\n")
            code = execute(command, prompt, env, cwd, run_dir, timeout)
            if code:
                raise ValueError("native worker exited with status " + str(code) + "; inspect its private logs")
            content = native.result(work, run_dir)
            if not isinstance(content, str) or not content.strip() or len(content.encode()) > LIMIT:
                raise ValueError("native worker returned an empty or oversized result")
            if slot:
                validate_artifact(root, content, work)
                publish(slot, content)
                record["artifact"] = str(workspace / ".agent-harness/plans" / artifact)
            reconcile.atomic_text(run_dir / "result.md", content)
            record["result_path"] = str(run_dir / "result.md")
        record["status"] = "completed"
    except subprocess.TimeoutExpired:
        record.update(status="timed-out", error="native worker exceeded its timeout")
    except KeyboardInterrupt:
        record.update(status="cancelled", error="worker interrupted")
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        record.update(status="failed", error=str(exc))
    finally:
        record["finished_at"] = time.time()
        reconcile.atomic_text(status_path, json.dumps(record, indent=2) + "\n")
    return record


def status(state_root, worker_id=None):
    if worker_id and not re.fullmatch(r"[a-f0-9]{32}", worker_id):
        raise ValueError("invalid worker id")
    paths = [Path(state_root) / worker_id / "status.json"] if worker_id else sorted(Path(state_root).glob("*/status.json"))
    return [json.loads(path.read_text()) for path in paths]
