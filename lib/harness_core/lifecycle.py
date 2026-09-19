"""Normalize lifecycle events and compose shared policies before native encoding."""
import contextlib
import importlib.util
import io
import json
import os
import re
import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POLICIES = ROOT / "policy" / "hooks"
ALIASES = {"exec_command": "Bash", "shell_command": "Bash", "shell": "Bash",
           "spawn_agent": "Agent", "write_file": "Write", "edit_file": "Edit"}


def load(name):
    spec = importlib.util.spec_from_file_location("harness_" + name.replace("-", "_"), POLICIES / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def normalize(payload):
    event = dict(payload)
    name = str(event.get("tool_name", "")).rsplit(".", 1)[-1]
    event["tool_name"] = ALIASES.get(name, name)
    inputs = event.get("tool_input") or {}
    if not isinstance(inputs, dict):
        raise ValueError("tool_input must be an object")
    inputs = dict(inputs)
    if event["tool_name"] == "Bash":
        command = inputs.get("command", inputs.get("cmd"))
        if isinstance(command, list):
            command = shlex.join(command)
        if not isinstance(command, str):
            raise ValueError("shell command is missing")
        inputs["command"] = command
    if event["tool_name"] == "Agent":
        inputs["prompt"] = inputs.get("prompt", inputs.get("message", ""))
        inputs["subagent_type"] = inputs.get("subagent_type", inputs.get("agent_type"))
    event["tool_input"] = inputs
    return event


def invoke(name, event):
    module = load(name)
    output = io.StringIO()
    old = sys.stdin
    try:
        sys.stdin = io.StringIO(json.dumps(event))
        with contextlib.redirect_stdout(output):
            module.main()
    finally:
        sys.stdin = old
    text = output.getvalue().strip()
    return json.loads(text) if text else {}


def selected(name, fallback):
    override = os.environ.get("HARNESS_STANCE_" + name.upper().replace("-", "_"))
    if override:
        return override
    file = Path(os.environ.get("HARNESS_HOME", str(Path.home()))) / ".config" / "agent-harness" / "config.json"
    cfg = json.loads(file.read_text()) if file.exists() else {}
    project_file = os.environ.get("HARNESS_PROJECT_CONFIG")
    if project_file:
        project = json.loads(Path(project_file).read_text())
        if set(project) - {"stances"}:
            raise ValueError("project configuration cannot change runtime authority")
        if name in project.get("stances", {}):
            return project["stances"][name]
    return cfg.get("stances", {}).get(name, fallback)


def encode_pre(runtime, original, normalized, results):
    decisions = [r.get("hookSpecificOutput", {}).get("permissionDecision") for r in results]
    strongest = next((choice for choice in ("deny", "ask", "allow") if choice in decisions), None)
    reasons = [r.get("hookSpecificOutput", {}).get("permissionDecisionReason", "") for r in results]
    fields = {"hookEventName": "PreToolUse"}
    if strongest:
        fields["permissionDecision"] = "deny" if runtime == "codex" and strongest == "ask" else strongest
        fields["permissionDecisionReason"] = "\n".join(x for x in reasons if x)
    if strongest in ("deny", "ask"):
        return {"hookSpecificOutput": fields}
    changes = {}
    for result in results:
        changes.update({key: value for key, value in result.get("hookSpecificOutput", {}).get("updatedInput", {}).items()
                        if normalized["tool_input"].get(key) != value})
    if changes:
        updated = dict(original.get("tool_input") or {})
        before = normalized["tool_input"]
        for key, value in changes.items():
            if before.get(key) == value:
                continue
            native_key = key
            if key == "command" and "cmd" in updated:
                native_key = "cmd"
            elif key == "prompt" and "message" in updated:
                native_key = "message"
            elif key == "subagent_type" and "agent_type" in updated:
                native_key = "agent_type"
            updated[native_key] = value
        # Codex requires allow for rewrites. Do not manufacture an approval to format output.
        can_rewrite = runtime == "claude-code" or strongest == "allow" or normalized["tool_name"] == "Agent"
        if can_rewrite and updated != original.get("tool_input"):
            fields["updatedInput"] = updated
            if runtime == "codex":
                fields["permissionDecision"] = "allow"
    return {"hookSpecificOutput": fields} if len(fields) > 1 else {}


def patch_paths(event):
    inputs = event["tool_input"]
    paths = [inputs.get("file_path"), inputs.get("path")]
    response = event.get("tool_response")
    if isinstance(response, dict):
        paths.append(response.get("filePath"))
    if event["tool_name"] == "apply_patch":
        patch = inputs.get("command", inputs.get("patch", ""))
        if isinstance(patch, str):
            paths.extend(re.findall(r"^\*\*\* (?:Add File|Update File|Move to): (.+)$", patch, re.M))
    return sorted(set(str(Path(event.get("cwd") or os.getcwd()) / p) for p in paths if p))


def dispatch(runtime, payload):
    if runtime not in ("claude-code", "codex"):
        raise ValueError("unknown runtime")
    event = normalize(payload)
    kind, tool = event.get("hook_event_name"), event.get("tool_name")
    if kind == "PreToolUse":
        results = []
        if tool == "Bash":
            grader = load("grade-bash")
            if grader.ro is None:
                raise RuntimeError("command classifier unavailable")
            # Shared stance resolution includes explicit project and session selections.
            variant = selected("autonomy", "execute")
            command, confirmed = grader.strip_marker(event["tool_input"]["command"])
            grade, verb, target, family = grader.grade_text(command, event.get("cwd", ""))
            if not confirmed and grade >= grader.THRESHOLDS.get(variant, 1) and grade:
                decision = "deny" if runtime == "codex" or event.get("permission_mode") in grader.DENY_MODES else "ask"
                results.append({"hookSpecificOutput": {"permissionDecision": decision,
                    "permissionDecisionReason": grader.reason(grade, verb, target, family, variant)}})
            if grade == 0:
                results.append({"hookSpecificOutput": {"permissionDecision": "allow"}})
            results.append(invoke("filter-output", event))
        elif tool == "Agent":
            delegation = selected("delegation", "tiered")
            role_name = event["tool_input"].get("subagent_type")
            if isinstance(role_name, str) and re.fullmatch(r"[a-z][a-z0-9-]*", role_name):
                source = ROOT / "primitives/roles" / (role_name + ".md")
                if source.is_file():
                    from . import catalog
                    fields, _ = catalog.role_contract(ROOT, role_name)
                    if fields["authority"] in ("read-only", "artifact-write"):
                        results.append({"hookSpecificOutput": {"permissionDecision": "deny",
                            "permissionDecisionReason": "This constrained harness role requires an isolated worker. Use harness role run "
                            + role_name + " --runtime " + runtime + " --model <session-model> --workspace <repo> --prompt-file <brief-file>. "
                            "Planner workers also require --artifact <new-plan.md>; native role defaults are not confinement."}})
            if delegation == "off":
                results.append({"hookSpecificOutput": {"permissionDecision": "deny",
                    "permissionDecisionReason": "Delegation is off; perform the work inline or change the selected stance."}})
            else:
                if runtime == "claude-code":
                    results.append(invoke("tier-agent-spawns", event))
                results.append(invoke("brief-guard", event))
        elif tool == "WebFetch":
            results.append(invoke("allow-plan-webfetch", event))
        return encode_pre(runtime, payload, event, results)
    if kind == "PostToolUse":
        contexts = []
        if selected("plan-ceremony", "review-card") == "review-card":
            for path in patch_paths(event):
                result = invoke("validate-plan-card", dict(event, tool_input={"file_path": path}))
                context = result.get("hookSpecificOutput", {}).get("additionalContext")
                if context:
                    contexts.append(context)
        warning = invoke("neutralize-tool-output", event)
        if warning:
            contexts.append(warning.get("hookSpecificOutput", {}).get("additionalContext") or warning.get("systemMessage", ""))
        return {"hookSpecificOutput": {"hookEventName": kind, "additionalContext": "\n".join(contexts)}} if any(contexts) else {}
    if kind == "SessionStart":
        return invoke("harness-session", event)
    if kind == "Stop":
        return invoke("stop-gate", event)
    if kind == "SessionEnd":
        module = load("usage-log")
        old = sys.stdin
        try:
            sys.stdin = io.StringIO(json.dumps(event))
            module.main([])
        finally:
            sys.stdin = old
    return {}


def registration(root, runtime):
    command = "python3 " + shlex.quote(str(root / "adapters" / runtime / "hook.py"))
    return {"hooks": {event: [{"hooks": [{"type": "command", "command": command + " # harness:runtime-" + event.lower(),
                                         "timeout": 300 if event == "Stop" else 2 if event == "SessionEnd" else 10}]}]
                      for event in ("PreToolUse", "PostToolUse", "SessionStart", "Stop", "SessionEnd")}}


def main(runtime):
    os.environ["HARNESS_RUNTIME"] = runtime
    kind = ""
    try:
        payload = json.load(sys.stdin)
        kind = payload.get("hook_event_name", "")
        result = dispatch(runtime, payload)
    except Exception as exc:
        message = "Harness policy is unverified: " + type(exc).__name__ + ": " + str(exc)
        if kind == "PreToolUse":
            result = {"hookSpecificOutput": {"hookEventName": kind, "permissionDecision": "deny", "permissionDecisionReason": message}}
        elif kind == "Stop":
            result = {"decision": "block", "reason": message}
        else:
            result = {"systemMessage": message}
    if result:
        print(json.dumps(result))
