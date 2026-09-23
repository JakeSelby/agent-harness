"""Normalize lifecycle events and compose shared policies before native encoding."""
import contextlib
import difflib
import fnmatch
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
BASE_EVENTS = ("PreToolUse", "PostToolUse", "SessionStart", "Stop", "SessionEnd")
# The usage feed's own events. Only Claude Code carries them; `adapters/codex/capabilities.json`
# declares the gap rather than registering an event that runtime does not raise.
FEED_EVENTS = ("UserPromptSubmit", "SubagentStart", "SubagentStop")
EVENTS = {"claude-code": BASE_EVENTS + FEED_EVENTS, "codex": BASE_EVENTS}
ROLE_NAME = re.compile(r"[a-z][a-z0-9-]*")
# A brief may declare the role it belongs to. The line stands alone so the declaration cannot be
# produced by prose that happens to mention a role, and it travels with the text: a brief pasted
# into an unnamed spawn still carries it, which is the whole point.
ROLE_MARKER = re.compile(r"^[ \t]*harness-role:[ \t]*([a-z][a-z0-9-]*)[ \t]*$", re.M)
# What a session remembers about a spawn it refused, and how a later spawn is matched against it.
# Bounded on both axes: 32 entries of 2,000 normalised characters is far past any real fan-out,
# and a session record is not a place to accumulate transcript.
DENIED_KEY = "denied_spawns"
DENIED_MAX = 32
FINGERPRINT_MAX = 2000
PREFIX_MATCH = 400
SIMILARITY = 0.85


def load(name):
    spec = importlib.util.spec_from_file_location("harness_" + name.replace("-", "_"), POLICIES / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_DECISIONS = []


def decisions():
    """The decision log, or None when it cannot be loaded. Loaded once per process.

    Every caller treats None as "this decision is not logged" and carries on: the log records
    what the harness decided and must never be able to change it.
    """
    if not _DECISIONS:
        try:
            _DECISIONS.append(load("decisions"))
        except Exception:
            _DECISIONS.append(None)
    return _DECISIONS[0]


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
    """One dimension's variant, resolved by the same file the policy hooks load."""
    return load("posture").selected(name, fallback)


def investigating(runtime, event):
    """Whether this call is plan-mode investigation the selected posture already authorises.

    Plan mode exists to force a plan, questions and a wait before anything is executed. It is not
    a reason to drop research below the permission posture the user chose for every other mode,
    so under `bypass` or `auto` the harness answers for the commands native plan mode would
    otherwise prompt on. Under `manual` and `inherit` it answers nothing new, and Codex is left
    alone because its client rejects `allow` outright.

    Fails closed: a config that will not open is not a posture anybody selected.
    """
    if runtime != "claude-code" or event.get("permission_mode") != "plan":
        return False
    try:
        module = load("posture")
        return module.permissions() in module.OPEN_POSTURES
    except Exception:
        return False


def plan_allowed_tool(tool):
    """Whether `tool` matches a glob the user listed under `plan_allow_tools`.

    Nothing is inferred from the tool name itself: a PreToolUse payload says nothing about
    whether an MCP tool reads or writes, so the list is empty until the user fills it.
    """
    if not isinstance(tool, str) or not tool:
        return False
    try:
        patterns = load("posture").plan_allow_tools()
    except Exception:
        return False
    return any(fnmatch.fnmatchcase(tool, pattern) for pattern in patterns)


def constrained_role(name):
    """The contract of `name` when it is a shared role an isolated worker must run, else None."""
    if not (isinstance(name, str) and ROLE_NAME.fullmatch(name)):
        return None
    if not (ROOT / "primitives/roles" / (name + ".md")).is_file():
        return None
    from . import catalog
    try:
        fields, _ = catalog.role_contract(ROOT, name)
    except ValueError:
        return None
    return fields if fields["authority"] in ("read-only", "artifact-write") else None


# A worker that may both read a workspace and reach the network can carry what it read back out,
# so the isolated adapters hold every role to Read/Grep/Glob. Only `gatherer` is routinely asked
# for online evidence, so only its refusal has somewhere else to send that half of the work.
OFFLINE_NOTE = {"gatherer": "An isolated gatherer is offline — Read, Grep and Glob, no WebFetch or "
                            "WebSearch — so send a file or repository dimension to the worker and a web "
                            "dimension to an in-session band worker (worker-a, worker-b or worker-c)."}


def role_instruction(runtime, name, fields):
    """The one sentence that says how this role is actually run. Every refusal ends with it."""
    from . import catalog
    # The role's class picks the model; the session's is the fallback, never the default.
    mapped = fields is not None and "model" in catalog.role_binding(ROOT, runtime, fields)
    return ("Use harness role run " + name + " --runtime " + runtime
            + ("" if mapped else " --model <session-model>")
            + " --workspace <repo> --prompt-file <brief-file>. "
            "Planner workers also require --artifact <new-plan.md>; native role defaults are not confinement."
            + (" " + OFFLINE_NOTE[name] if name in OFFLINE_NOTE else ""))


def role_deny(runtime, name, fields):
    return {"hookSpecificOutput": {"permissionDecision": "deny",
            "permissionDecisionReason": "This constrained harness role requires an isolated worker. "
            + role_instruction(runtime, name, fields)}}


def marker_role(prompt):
    """`(name, fields)` for a brief that declares its role on a `harness-role:` line, else None.

    A marker naming something that is not a constrained shared role says nothing: the guard is a
    declaration the harness can verify, not a word the model can use to refuse arbitrary work.
    """
    if not isinstance(prompt, str):
        return None
    for name in ROLE_MARKER.findall(prompt):
        fields = constrained_role(name)
        if fields is not None:
            return name, fields
    return None


def fingerprint(prompt):
    """A brief reduced to what a re-spawn cannot vary: whitespace, case and length all removed."""
    return " ".join(prompt.split()).casefold()[:FINGERPRINT_MAX] if isinstance(prompt, str) else ""


def same_work(left, right):
    """Whether two fingerprints are the same brief. Equality, containment, then similarity.

    Containment is tested only on a prefix long enough to be evidence; a short brief that happens
    to appear inside a longer unrelated one is a false refusal, and a refusal nobody can explain
    is worse than the evasion it prevents.
    """
    if not left or not right:
        return False
    if left == right:
        return True
    for a, b in ((left, right), (right, left)):
        if len(a) >= PREFIX_MATCH and a[:PREFIX_MATCH] in b:
            return True
    return difflib.SequenceMatcher(None, left, right).ratio() >= SIMILARITY


def denied_spawns(session_id):
    """What this session has already refused as a constrained-role spawn; `[]` for anything else.

    State a hook cannot read is state that does not exist. The guard then behaves exactly as it
    did before it was written, because a spawn hook that raises is worse than one that forgets.
    """
    try:
        record = load("posture").read_session_record(session_id)
        entries = (record or {}).get(DENIED_KEY)
        return [e for e in entries if isinstance(e, dict) and isinstance(e.get("prompt"), str)] \
            if isinstance(entries, list) else []
    except Exception:
        return []


def remember_denial(session_id, name, prompt):
    """Add one refusal to the session's memory, newest last. Best effort, never raises."""
    text = fingerprint(prompt)
    if not text:
        return False
    try:
        posture = load("posture")
        record = posture.read_session_record(session_id) or {}
        entries = [e for e in denied_spawns(session_id) if e.get("prompt") != text]
        entries.append({"role": name, "prompt": text})
        return bool(posture.write_session_record(session_id, dict(record, **{DENIED_KEY: entries[-DENIED_MAX:]})))
    except Exception:
        return False


def evasion_deny(runtime, session_id, prompt):
    """The refusal a re-spawn of already-refused work gets, or None when this is not that."""
    text = fingerprint(prompt)
    for entry in reversed(denied_spawns(session_id)):
        if same_work(text, entry["prompt"]):
            name = entry.get("role") if isinstance(entry.get("role"), str) else ""
            module = decisions()
            if module is not None:
                # The fingerprint, not the brief: it is what the comparison actually ran on,
                # and a matched refusal is the one judgment here worth a label.
                module.record("evasion-deny", "deny", text, {"session_id": session_id}, runtime)
            return {"hookSpecificOutput": {"permissionDecision": "deny",
                    "permissionDecisionReason": "This work was refused as a native " + name
                    + " spawn in this session; dropping or changing the role name does not change that. "
                    + role_instruction(runtime, name, constrained_role(name))}}
    return None


def log_bash_decision(runtime, event, results, command=None, confirmed=False):
    """Record the permission answer the harness gave this command, when it gave one.

    Only `ask` and `deny` are graded rows. An approval is the harness declining to interrupt,
    and "it ran" says nothing about whether declining was right; a refusal or a prompt is the
    judgment a later label can grade. The row is written here rather than in `grade-bash.py`
    because this is where the answer is composed: the grader's threshold, the permission mode
    and plan-mode investigation all fold together into one answer, and only one is given.

    An allowed command goes to `record_allowed`, which keeps one in twenty of them as an
    ungraded negative. A confirmed command is not one of those: it reached here because the
    user answered a prompt the harness raised, so it is the earlier `ask` row's story.
    """
    module = decisions()
    if module is None:
        return
    answers = [r.get("hookSpecificOutput", {}).get("permissionDecision") for r in results]
    answer = next((choice for choice in ("deny", "ask") if choice in answers), None)
    if not answer:
        if not confirmed:
            module.record_allowed(command if command is not None
                                  else event["tool_input"]["command"], event, runtime)
        return
    command = event["tool_input"]["command"]
    module.record("grade-bash", answer, command, event, runtime,
                  key=module.match_key(event, command))


def log_bash_outcome(runtime, event):
    """Join `ran` to the decision this completed command belongs to, when there was one.

    The tool ran, so whatever the harness asked, the user let it through. A command nothing was
    asked about has no decision in the log and gets no record; a command that was asked about
    and never came back is closed as `not_run` at SessionEnd, because an outright refusal and
    an interrupted turn look identical from here.
    """
    module = decisions()
    if module is None:
        return
    command = (event.get("tool_input") or {}).get("command")
    if not isinstance(command, str) or not command:
        return
    identity = module.decision_id("grade-bash", module.match_key(event, command))
    module.observe_if_logged(identity, module.RAN, "grade-bash", event.get("session_id") or "")


def encode_pre(runtime, original, normalized, results):
    encoded = _encode_pre(runtime, original, normalized, results)
    # A policy's notice is the only trace of a rewrite the user would otherwise never see.
    notices = [r["systemMessage"] for r in results if isinstance(r.get("systemMessage"), str) and r["systemMessage"]]
    if notices and runtime == "claude-code":
        encoded = dict(encoded, systemMessage="\n".join(notices))
    return encoded


def _encode_pre(runtime, original, normalized, results):
    decisions = [r.get("hookSpecificOutput", {}).get("permissionDecision") for r in results]
    strongest = next((choice for choice in ("deny", "ask", "allow") if choice in decisions), None)
    reasons = [r.get("hookSpecificOutput", {}).get("permissionDecisionReason", "") for r in results]
    reason = "\n".join(x for x in reasons if x)
    fields = {"hookEventName": "PreToolUse"}
    # A Codex client rejects the whole hook output when it carries an unsupported `allow`, so a
    # plain approval says nothing and lets that runtime's own default stand.
    if strongest and not (runtime == "codex" and strongest == "allow"):
        fields["permissionDecision"] = "deny" if runtime == "codex" and strongest == "ask" else strongest
        fields["permissionDecisionReason"] = reason
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
                if reason:
                    fields["permissionDecisionReason"] = reason
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
            asked = bool(grade) and not confirmed and grade >= grader.THRESHOLDS.get(variant, 1)
            if asked:
                decision = "deny" if runtime == "codex" or event.get("permission_mode") in grader.DENY_MODES else "ask"
                results.append({"hookSpecificOutput": {"permissionDecision": decision,
                    "permissionDecisionReason": grader.reason(grade, verb, target, family, variant)}})
            # Grade 0 is proved read-only, so it is approved in every mode. Grades 1 and 2 are the
            # ones native plan mode prompts on: a script the grammar cannot read through, a
            # scratch redirect, a test run. Under an open posture the first is investigation and
            # the second is not, and the autonomy stance still outranks both when it already asked.
            plan = investigating(runtime, event)
            if grade == 0:
                results.append({"hookSpecificOutput": {"permissionDecision": "allow"}})
            elif plan and not asked and grade == 1:
                results.append({"hookSpecificOutput": {"permissionDecision": "allow",
                    "permissionDecisionReason": "Plan-mode investigation, run at the permission posture you selected."}})
            elif plan and not asked and not confirmed and grade == 2:
                results.append({"hookSpecificOutput": {"permissionDecision": "ask",
                    "permissionDecisionReason": "This reaches past the workspace, so it is execution rather than "
                    "planning. Plan mode widens investigation, not the build. "
                    + grader.reason(grade, verb, target, family, variant)}})
            results.append(invoke("filter-output", event))
            log_bash_decision(runtime, event, results, command, confirmed)
        elif tool == "Agent":
            delegation = selected("delegation", "tiered")
            inputs = event["tool_input"]
            role_name, prompt = inputs.get("subagent_type"), inputs.get("prompt")
            fields = constrained_role(role_name)
            if fields is not None:
                results.append(role_deny(runtime, role_name, fields))
            # Refusing the named spawn only moves the work: the same brief comes back with the role
            # name dropped, and nothing sees it. So the refusal is remembered for the session, and a
            # brief that declares its own role is refused however it is spawned. Neither guard runs
            # where the stance already denies every spawn.
            if delegation != "off":
                if fields is not None:
                    remember_denial(event.get("session_id"), role_name, prompt)
                else:
                    marked = marker_role(prompt)
                    if marked is not None:
                        results.append(role_deny(runtime, marked[0], marked[1]))
                    else:
                        evaded = evasion_deny(runtime, event.get("session_id"), prompt)
                        if evaded is not None:
                            results.append(evaded)
            if delegation == "off":
                results.append({"hookSpecificOutput": {"permissionDecision": "deny",
                    "permissionDecisionReason": "Delegation is off; perform the work inline or change the selected stance."}})
            else:
                if runtime == "claude-code":
                    results.append(invoke("tier-agent-spawns", event))
                results.append(invoke("brief-guard", event))
        elif tool == "WebFetch":
            results.append(invoke("allow-plan-webfetch", event))
        elif investigating(runtime, event) and plan_allowed_tool(tool):
            results.append({"hookSpecificOutput": {"permissionDecision": "allow",
                "permissionDecisionReason": "Plan-mode research tool named by plan_allow_tools, "
                "run at the permission posture you selected."}})
        return encode_pre(runtime, payload, event, results)
    if kind == "PostToolUse":
        contexts = []
        if tool == "Bash":
            log_bash_outcome(runtime, event)
        if selected("plan-ceremony", "review-card") == "review-card":
            for path in patch_paths(event):
                result = invoke("validate-plan-card", dict(event, tool_input={"file_path": path},
                                                          tool_response={"filePath": path}))
                context = result.get("hookSpecificOutput", {}).get("additionalContext")
                if context:
                    contexts.append(context)
        warning = invoke("neutralize-tool-output", event)
        if warning:
            contexts.append(warning.get("hookSpecificOutput", {}).get("additionalContext") or warning.get("systemMessage", ""))
        if runtime == "claude-code" and tool == "Agent":
            feed = invoke("usage-feed", event).get("hookSpecificOutput", {}).get("additionalContext")
            if feed:
                contexts.append(feed)
        return {"hookSpecificOutput": {"hookEventName": kind, "additionalContext": "\n".join(contexts)}} if any(contexts) else {}
    if kind in FEED_EVENTS:
        # A feed never denies, never blocks and never speaks for another policy, so it answers
        # its own two events alone.
        return invoke("usage-feed", event) if runtime == "claude-code" else {}
    if kind == "SessionStart":
        return invoke("harness-session", event)
    if kind == "Stop":
        return invoke("stop-gate", event)
    if kind == "SessionEnd":
        # Nothing will arrive for this session again, so an ask with no PostToolUse is settled:
        # the command did not run. Done before the usage worker is spawned, and bounded by the
        # session's own rows, so the 1.5-second SessionEnd budget pays for one read of a file
        # that only a permission prompt writes to.
        log = decisions()
        if log is not None:
            log.close_session(event.get("session_id") or "")
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
                      for event in EVENTS.get(runtime, BASE_EVENTS)}}


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
