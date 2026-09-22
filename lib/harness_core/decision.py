"""The shared decision-provider seam: one contract for "may this action proceed, and how".

Three operations, transport-agnostic, so a local policy file and a remote control plane answer
the same questions in the same shape:

    decide(action, counterparty, context) -> Decision
    record(action_outcome) -> None
    learn(approval_stream) -> None

`Action` carries an action class and, when the caller knows it, the grade `grade-bash.py`
already assigns a command (0 reversible, 3 irreversible). `counterparty` is the
`repo:<name>/<branch>` slug the usage ledger already derives, so a policy written against a
repository and branch matches whatever asks the question.

Two providers ship here. `none` is the default and governs nothing: every action is allowed at
autonomy level 3. `local` reads a per-repository policy file and resolves a level from it.
Nothing in this module reaches the network, and nothing in this module is consulted by a hook
yet: `grade-bash.py` still answers the permission question on its own. The binding is a later
story, and until it lands this seam changes no behaviour at all.

`Decision.outcome` has three values — `allow`, `ask`, `deny`. Neither provider here ever denies;
`deny` exists because a provider that can refuse must have somewhere to say so, and a consumer
written against the contract should handle it from the first day.
"""
import importlib.util
import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

ROOT = Path(__file__).resolve().parents[2]

# The classes a caller may ask about. Closed on purpose: a typo in a policy file that silently
# governs nothing is worse than a policy file that refuses to load.
ACTION_CLASSES = ("coding.shell_exec", "coding.git_commit", "coding.git_push", "coding.deploy",
                  "coding.file_write")
OUTCOMES = ("allow", "ask", "deny")
LEVELS = (1, 2, 3)
ACTION_OUTCOMES = ("completed", "skipped", "failed")

# What each autonomy variant implies when no policy names a level for the action. The same
# thresholds `grade-bash.py` grades under, so a repository with no policy file behaves exactly
# as the stance in force already says it should.
STANCE_LEVELS = {"execute": 3, "confirm-writes": 2, "ask": 1}
# Unresolvable stance: the strictest variant, for `grade-bash.py`'s reason — a gate that cannot
# read its own configuration must not widen authority on the strength of not knowing.
STRICTEST_LEVEL = 1
# A deploy is never fully autonomous, whatever a policy file says. A cap in the file may lower
# this and may not raise it.
BUILTIN_CAPS = {"coding.deploy": 2}
# An action whose grade the caller does not know is judged at 1, never at 3 — `grade-bash.py`'s
# rule for a command it cannot recognise, for the same reason.
UNKNOWN_GRADE = 1

POLICY_FILE = Path(".agent-harness") / "governance.json"
POLICY_KEYS = ("defaults", "pairs", "caps")
# The point name these rows carry in the decision ledger. Deliberately not in
# `decisions.POINTS`: that tuple names the hook points whose rows the report expects to exist,
# and no hook writes these yet.
LEDGER_POINT = "decision-provider"


class PolicyError(ValueError):
    """A governance policy file that cannot be honoured as written.

    Raised rather than shrugged off: a malformed policy is a governance question nobody has
    answered, and reading it as "no policy" would quietly grant whatever it meant to withhold.
    Every call site turns this into one line naming the file and the fault.
    """


@dataclass(frozen=True)
class Action:
    """What is about to happen: an action class, and the grade of it where one is known."""

    action_class: str
    grade: Optional[int] = None

    def effective_grade(self) -> int:
        return UNKNOWN_GRADE if self.grade is None else self.grade

    def as_dict(self) -> Dict[str, Any]:
        return {"action_class": self.action_class, "grade": self.grade}


@dataclass(frozen=True)
class ActionOutcome:
    """How an action that was decided on actually turned out."""

    action_class: str
    counterparty: str
    outcome: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Decision:
    """One provider's answer.

    `injected_cognition` is the part a runtime may put in front of an agent or a person:
    `rule_matches` names every policy line that bore on the answer, verbatim enough to quote,
    and the two messages are text for the agent and for the user, or None when there is none.
    """

    outcome: str
    autonomy_level: int
    provider: str
    reason: str
    injected_cognition: Dict[str, Any] = field(default_factory=lambda: dict(empty_cognition()))

    def as_dict(self) -> Dict[str, Any]:
        return {"outcome": self.outcome, "autonomy_level": self.autonomy_level,
                "injected_cognition": self.injected_cognition, "provider": self.provider,
                "reason": self.reason}


def empty_cognition() -> Dict[str, Any]:
    return {"rule_matches": [], "agent_message": None, "user_message": None}


# ------------------------------------------------------------------ the shared ledger

_HOOK_MODULES: Dict[str, Any] = {}


def _hook_module(name: str, root: Optional[Path] = None):
    """A module from the hook directory, loaded by file, or None when it is not there.

    `claude/hooks` is a symlink to `policy/hooks`; both names are tried for the reason
    `catalog.posture_module` gives. Loading the hook's own file is what keeps one writer for
    the decision ledger and one derivation of the counterparty slug.
    """
    root = ROOT if root is None else Path(root)
    key = str(root) + "/" + name
    if key in _HOOK_MODULES:
        return _HOOK_MODULES[key]
    path = next((p for p in (root / "policy" / "hooks" / (name + ".py"),
                             root / "claude" / "hooks" / (name + ".py")) if p.is_file()), None)
    if path is None:
        return None
    try:
        spec = importlib.util.spec_from_file_location("harness_" + name.replace("-", "_"),
                                                      str(path))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception:
        return None
    _HOOK_MODULES[key] = module
    return module


def counterparty(cwd: Optional[str] = None) -> str:
    """`repo:<name>/<branch>` for a working directory, the slug the usage ledger already uses.

    Derived by `usage-log.py`'s own git helper and its own expressions, so a policy keyed on a
    counterparty matches the repository and branch the ledger will later name. Outside a
    repository, `repo:unknown/local`: a policy must not silently match a directory that only
    happens to share a basename with one.
    """
    cwd = str(Path(cwd).expanduser()) if cwd else os.getcwd()
    module = _hook_module("usage-log")
    if module is None or not os.path.isdir(cwd):
        return "repo:unknown/local"
    top = module.git(cwd, "rev-parse", "--show-toplevel")
    if not top:
        return "repo:unknown/local"
    branch = module.git(cwd, "rev-parse", "--abbrev-ref", "HEAD")
    return "repo:" + os.path.basename(top) + "/" + (branch or "unknown")


def _ledger():
    return _hook_module("decisions")


def ledger_path(target: Optional[str] = None) -> Optional[Path]:
    module = _ledger()
    if module is None:
        return None
    return Path(target) if target else module.path()


def append_outcome(action_outcome: ActionOutcome, target: Optional[str] = None) -> Optional[str]:
    """Write one action outcome to the decision ledger. Returns its id, or None.

    The existing `decisions.jsonl`, through the existing writer, never a second file: a reader
    of the ledger sees provider activity beside the hook decisions it already holds. Never
    raises, for the reason that module gives — a log that can change an answer is worse than no
    log — so a caller gets None and carries on.
    """
    module = _ledger()
    if module is None:
        return None
    text = json.dumps({"action": action_outcome.action_class,
                       "counterparty": action_outcome.counterparty,
                       "metadata": action_outcome.metadata}, sort_keys=True)
    return module.record(LEDGER_POINT, action_outcome.outcome, text=text,
                         key=action_outcome.action_class + "|" + action_outcome.counterparty
                             + "|" + text,
                         target=str(target) if target else None)


def append_event(name: str, detail: Dict[str, Any], target: Optional[str] = None) -> bool:
    """Write one `event` row to the decision ledger. Never raises; says whether it wrote.

    An event carries no `decision_id`, so `decisions.read_rows` skips it and
    `harness usage --by decision` never counts provider bookkeeping as a judgment nobody
    labelled. `read_events` below reads them back.
    """
    module = _ledger()
    if module is None:
        return False
    try:
        if not module.enabled():
            return False
        # The ledger's own append: one line, one write, and no second file to keep in step.
        module._append({"kind": "event", "point": LEDGER_POINT, "event": name,
                        "ts": module.now_ts(), "detail": detail,
                        "harness_version": module.harness_version()},
                       str(target) if target else None)
        return True
    except Exception:
        return False


def read_events(target: Optional[str] = None) -> List[Dict[str, Any]]:
    """Every `event` row in the ledger, oldest first. An unreadable file is no events."""
    path = ledger_path(target)
    if path is None:
        return []
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    events = []
    for line in text.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("kind") == "event":
            events.append(row)
    return events


def validate_approvals(stream: Iterable[Any]) -> List[Dict[str, Any]]:
    """The approval records in `stream`, or a `PolicyError` naming the first bad one.

    Shape only: `{action, counterparty, approved: bool, at: iso8601}`. Nothing here learns from
    them yet — the providers that ship today cannot — and validating the shape is exactly what
    keeps the seam honest: a caller that hands over garbage is told so now rather than when
    something finally reads the file.
    """
    if isinstance(stream, (str, bytes, dict)) or stream is None:
        raise PolicyError("learn: the approval stream must be an iterable of records")
    records = []
    for index, item in enumerate(stream):
        where = "learn: record %d" % index
        if not isinstance(item, dict):
            raise PolicyError(where + " is not an object")
        for name in ("action", "counterparty", "at"):
            value = item.get(name)
            if not isinstance(value, str) or not value.strip():
                raise PolicyError(where + " needs a non-empty string `" + name + "`")
        if not isinstance(item.get("approved"), bool):
            raise PolicyError(where + " needs a boolean `approved`")
        if not _iso8601(item["at"]):
            raise PolicyError(where + " has `at` that is not an ISO 8601 timestamp: "
                              + item["at"])
        records.append(dict(item))
    return records


def _iso8601(value: str) -> bool:
    """Whether `value` is an ISO 8601 instant the stdlib on this floor can read.

    Python 3.9's `fromisoformat` does not accept a trailing `Z`, which is the spelling every
    row in this repository's ledgers uses, so the one substitution is made before parsing.
    """
    import datetime

    try:
        datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return False
    return True


# ------------------------------------------------------------------ the policy file


def stance_level(variant: Optional[str] = None, root: Optional[Path] = None) -> int:
    """The level the autonomy stance implies, or the strictest when nothing resolves it.

    Resolved through `posture.py`, the same file every hook asks, so the provider and the
    command gate cannot disagree about which variant is in force.
    """
    if variant is None:
        module = _hook_module("posture", root)
        try:
            variant = None if module is None else module.selected("autonomy", None)
        except Exception:
            variant = None
    return STANCE_LEVELS.get(variant or "", STRICTEST_LEVEL)


def _level(value: Any, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value not in LEVELS:
        raise PolicyError(where + " must be an autonomy level of 1, 2 or 3, not " + repr(value))
    return value


def _class_map(block: Any, where: str) -> Dict[str, int]:
    if not isinstance(block, dict):
        raise PolicyError(where + " must be an object of action class to level")
    out = {}
    for name, value in block.items():
        if name not in ACTION_CLASSES:
            raise PolicyError(where + " names an unknown action class " + repr(name)
                              + "; known classes are " + ", ".join(ACTION_CLASSES))
        out[name] = _level(value, where + "." + name)
    return out


def load_policy(path: Path) -> Dict[str, Dict[str, Any]]:
    """The policy at `path`, validated, or the empty policy when the file is not there.

    A missing file is a repository that has chosen nothing, which resolves to the stance. A
    file that exists and cannot be honoured is a `PolicyError`.
    """
    path = Path(path)
    empty: Dict[str, Dict[str, Any]] = {"defaults": {}, "pairs": {}, "caps": {}}
    if not path.is_file():
        return empty
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PolicyError("governance policy " + str(path) + " cannot be read: " + str(exc))
    if not isinstance(raw, dict):
        raise PolicyError("governance policy " + str(path) + " must be a JSON object")
    unknown = sorted(set(raw) - set(POLICY_KEYS))
    if unknown:
        raise PolicyError("governance policy " + str(path) + " has unknown key(s) "
                          + ", ".join(unknown) + "; known keys are " + ", ".join(POLICY_KEYS))
    policy = dict(empty)
    policy["defaults"] = _class_map(raw.get("defaults", {}), "defaults")
    policy["caps"] = _class_map(raw.get("caps", {}), "caps")
    pairs = raw.get("pairs", {})
    if not isinstance(pairs, dict):
        raise PolicyError("governance policy " + str(path) + ": pairs must be an object keyed "
                          "by counterparty")
    policy["pairs"] = {slug: _class_map(block, "pairs." + str(slug))
                       for slug, block in pairs.items()}
    return policy


def cap_for(action_class: str, policy: Dict[str, Dict[str, Any]]) -> Optional[int]:
    """The ceiling on this action's level: the lower of the file's cap and the built-in one."""
    caps = [c for c in (policy.get("caps", {}).get(action_class),
                        BUILTIN_CAPS.get(action_class)) if c is not None]
    return min(caps) if caps else None


def outcome_for(level: int, grade: int) -> str:
    """`allow` or `ask`, by the thresholds `grade-bash.py` already grades under.

    Level 3 allows every grade; level 2 asks at grade 2 and up; level 1 asks at grade 1 and up.
    """
    if level >= 3:
        return "allow"
    return "ask" if grade >= level else "allow"


# ------------------------------------------------------------------ the providers


class DecisionProvider(ABC):
    """The contract every provider answers, whatever sits behind it."""

    name = ""

    @abstractmethod
    def decide(self, action: Action, counterparty: str,
               context: Optional[Dict[str, Any]] = None) -> Decision:
        """Whether this action may proceed, and what to put in front of the agent."""

    @abstractmethod
    def record(self, action_outcome: ActionOutcome) -> None:
        """Note how an action turned out. Never raises, never changes a decision."""

    @abstractmethod
    def learn(self, approval_stream: Iterable[Any]) -> None:
        """Take a stream of past approvals. May be a no-op; must reject a malformed stream."""


class NullProvider(DecisionProvider):
    """Governs nothing: every action is allowed at level 3.

    The default, and the behaviour of a harness with no governance at all — which is what every
    installation has today. It still records outcomes, so the ledger is populated before any
    policy exists to be measured against it.
    """

    name = "none"

    def __init__(self, target: Optional[str] = None):
        self.target = target

    def decide(self, action, counterparty, context=None):
        return Decision(outcome="allow", autonomy_level=3, provider=self.name,
                        reason="governance: none", injected_cognition=empty_cognition())

    def record(self, action_outcome):
        append_outcome(action_outcome, self.target)

    def learn(self, approval_stream):
        return None


class LocalProvider(DecisionProvider):
    """A per-repository policy file, resolved against the autonomy stance.

    `.agent-harness/governance.json`:

        {"defaults": {"coding.git_push": 2},
         "pairs": {"repo:agent-harness/main": {"coding.git_push": 1}},
         "caps": {"coding.deploy": 2}}

    Resolution is explicit pair, then class default, then the level the autonomy stance implies.
    A cap is a ceiling the resolved level never exceeds, and `coding.deploy` carries a built-in
    cap of 2 that a file may lower and may not raise: a deploy is never fully autonomous.
    """

    name = "local"

    def __init__(self, root: Optional[str] = None, policy_path: Optional[str] = None,
                 variant: Optional[str] = None, target: Optional[str] = None):
        self.root = Path(root) if root else Path.cwd()
        self.policy_path = Path(policy_path) if policy_path else self.root / POLICY_FILE
        self.variant = variant
        self.target = target
        self._policy = None

    def policy(self) -> Dict[str, Dict[str, Any]]:
        if self._policy is None:
            self._policy = load_policy(self.policy_path)
        return self._policy

    def decide(self, action, counterparty, context=None):
        policy = self.policy()
        matches = []
        pair = policy["pairs"].get(counterparty, {}).get(action.action_class)
        default = policy["defaults"].get(action.action_class)
        if pair is not None:
            level, source = pair, "pairs." + counterparty + "." + action.action_class
        elif default is not None:
            level, source = default, "defaults." + action.action_class
        else:
            level = stance_level(self.variant, self.root)
            source = "autonomy stance"
        matches.append(source + " = " + str(level))
        cap = cap_for(action.action_class, policy)
        if cap is not None and level > cap:
            matches.append("caps." + action.action_class + " = " + str(cap))
            level = cap
        grade = action.effective_grade()
        outcome = outcome_for(level, grade)
        reason = ("governance: local, level %d, grade %s -> %s (%s)"
                  % (level, "unknown" if action.grade is None else str(grade), outcome, source))
        cognition = empty_cognition()
        cognition["rule_matches"] = matches
        if outcome == "ask":
            cognition["agent_message"] = (
                action.action_class + " on " + counterparty + " is level " + str(level)
                + ": state the exact command and wait for an explicit yes.")
        return Decision(outcome=outcome, autonomy_level=level, provider=self.name,
                        reason=reason, injected_cognition=cognition)

    def record(self, action_outcome):
        append_outcome(action_outcome, self.target)

    def learn(self, approval_stream):
        records = validate_approvals(approval_stream)
        append_event("learn", {"records": len(records), "provider": self.name}, self.target)
        return None


PROVIDERS = {NullProvider.name: NullProvider, LocalProvider.name: LocalProvider}


def select_provider(config: Optional[Dict[str, Any]] = None, **kwargs) -> DecisionProvider:
    """The provider `governance.provider` names, `none` by default.

    An unknown name is refused rather than defaulted: a configuration that asks for governance
    nobody can supply must not come back as governance nobody applied.
    """
    block = (config or {}).get("governance")
    name = block.get("provider") if isinstance(block, dict) else None
    name = name if isinstance(name, str) and name.strip() else NullProvider.name
    if name not in PROVIDERS:
        raise PolicyError("governance.provider " + repr(name) + " is not a provider; "
                          "known providers are " + ", ".join(sorted(PROVIDERS)))
    cls = PROVIDERS[name]
    if cls is NullProvider:
        kwargs.pop("root", None)
        kwargs.pop("policy_path", None)
        kwargs.pop("variant", None)
    return cls(**kwargs)
