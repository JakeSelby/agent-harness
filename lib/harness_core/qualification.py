"""Which capability class executes a qualification target, and which class reads what it wrote.

Ten of the eleven required cases are now scripts (#336): a target's worker runs a script, reads
JSON and writes findings, which is not work that needs the strong tier. What does need it is the
assessment — the published procedure requires a reviewer to assess the observations, and a
cheaper worker that produced the evidence must never be the only reader of it.

So a round carries two classes per target, not one: an execution class, `standard` by default,
and an assessment class, `strong`, which is a floor and not a preference. The pair is resolved
through the target runtime's `adapters/<runtime>/bindings.json` and written into the evidence
record, so the record says which class produced an observation and which class must read it.
A cheap execution class that resolves to the assessment class's own model is refused rather than
recorded: a round whose executor is its own reader buys the saving by dropping the reviewer.

The resolution reads the adapter's own table. A personal `tiers.<runtime>` override in a user's
configuration is not applied, because a round runs from a frozen clone and the record names the
class alongside the adapter's model for it; pass `tiers` to lay an overlay on top.
"""
import importlib.util
import re
from pathlib import Path

from . import catalog

TIER_CLASSES = catalog.TIER_CLASSES
EXECUTION_DEFAULT = "standard"
ASSESSMENT_DEFAULT = "strong"
# The weakest class allowed to assess a round's observations. `docs/compatibility.md` requires a
# reviewer; #340's decision 6 keeps that reviewer strong-class while the executor gets cheaper.
ASSESSMENT_FLOOR = "strong"
UNMAPPED = ("the %s adapter maps no %s class, so the %s worker inherits the session model; "
            "the record names the class, not a model")
_RELEASE_SUFFIX = re.compile(r"(?:[-@](?:20\d{6}|20\d{2}-\d{2}-\d{2})|-v\d+(?::\d+)?)$")
_NORMALISERS = {}


def _normaliser(root):
    """`pricing.normalise_model` from the checkout, or the fallback below.

    One spelling of a model id has a definition already, in the pricing hook; a second copy of
    it would drift from the ledger's. The hook lives under two names, `policy/hooks` being the
    real one and `claude/hooks` the projection, and a tree carrying only the projection still
    resolves. A tree carrying neither falls back, because a missing hook must not turn the
    same-model refusal off.
    """
    key = str(root)
    if key not in _NORMALISERS:
        _NORMALISERS[key] = _loaded(root) or _normalise_model
    return _NORMALISERS[key]


def _loaded(root):
    path = next((p for p in (Path(root) / "policy" / "hooks" / "pricing.py",
                             Path(root) / "claude" / "hooks" / "pricing.py") if p.is_file()), None)
    if path is None:
        return None
    try:
        spec = importlib.util.spec_from_file_location("harness_pricing", str(path))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.normalise_model
    except Exception:
        return None


def _normalise_model(model):
    """The fallback spelling: lower case, no window bracket, no vendor prefix, no release suffix."""
    name = re.sub(r"\[[^\]]*\]", "", (model or "").strip().lower()).split("/")[-1]
    while True:
        head, dot, rest = name.partition(".")
        if not (dot and rest and head.isalpha()):
            break
        name = rest
    while True:
        trimmed = _RELEASE_SUFFIX.sub("", name)
        if trimmed == name:
            break
        name = trimmed
    return name.strip("-").strip()


def _words(name):
    return [part for part in re.split(r"[^a-z0-9]+", name) if part]


def same_model(first, second, normalise=_normalise_model):
    """Whether two adapter entries name one model, once spelling and aliasing are allowed for.

    Two classes mapped to `opus` and to a dated `claude-opus-4-5-20260101` are one model bought
    twice, and comparing the strings would miss it. So the ids are normalised the way the ledger
    normalises them, and an alias — every word of one id appearing, in order and adjacent, in the
    other — counts as the same model. The comparison guards a refusal, so it errs towards
    refusing: `gpt-5` and `gpt-5.6-terra` are treated as one model, and an operator who means two
    writes two ids that are not one another's prefix.
    """
    left, right = normalise(first), normalise(second)
    if left == right:
        return True
    if not left or not right:
        return False
    short, long = sorted((_words(left), _words(right)), key=len)
    return any(long[i:i + len(short)] == short for i in range(len(long) - len(short) + 1))


def _rank(name):
    return TIER_CLASSES.index(name)


def _checked(name, what):
    if name not in TIER_CLASSES:
        raise ValueError("%s class must be one of %s: %s" % (what, ", ".join(TIER_CLASSES), name))
    return name


def parse_class_map(values, targets, default, flag="--execution-class", known=None):
    """`CLASS` or `TARGET=CLASS` arguments, later ones winning, as one class per target.

    A bare class moves every target the round is running; a qualified one moves the target it
    names, so a Codex round can be executed at a different class from a Claude Code one without
    two invocations. `known` is every target this runner has, which is what tells a client left
    out of `--targets` from a client that does not exist: the first is a round the operator has
    not asked for, the second is a typo, and they are different mistakes.
    """
    chosen = dict((target, default) for target in targets)
    for value in values or []:
        target, sign, name = str(value).partition("=")
        target, name = target.strip(), name.strip()
        if not sign:
            target, name = None, target
        if target is not None:
            if not target:
                raise ValueError("%s: no target named before '=': %s" % (flag, value))
            if target not in chosen:
                raise ValueError("%s: %s" % (flag, (
                    "%s is not in this round's --targets" % target if target in (known or ())
                    else "unknown qualification target: " + target)))
            if not name:
                raise ValueError("%s: no class given for target %s" % (flag, target))
        if not name:
            raise ValueError("%s: no class given" % flag)
        try:
            _checked(name, "worker")
        except ValueError as error:
            raise ValueError("%s: %s" % (flag, error))
        for key in ([target] if target is not None else list(chosen)):
            chosen[key] = name
    return chosen


def resolve(root, runtime, execution=EXECUTION_DEFAULT, assessment=ASSESSMENT_DEFAULT,
            tiers=None):
    """The round's routing for one target, or `ValueError` naming why it is refused.

    The refusal is a cheap execution class that lands on the assessment class's own model,
    however it came about — an adapter table mapping two classes to one identifier, two
    spellings of one model, or a cheap class the table does not map at all, which resolves
    upward. An assessor the table does not map while the executor is pinned is refused too: the
    reader would inherit whatever model the session happens to be running, which is no named
    reader at all. Executing at the floor or above is not refused: it buys no saving, and the
    reviewer it asks for is the one the procedure already requires. What remains a disclosure
    rather than a refusal is an unmapped *executor* beside a mapped assessor, which is what
    asking for a class stronger than the assessor's does.
    """
    _checked(execution, "execution")
    _checked(assessment, "assessment")
    if _rank(assessment) > _rank(ASSESSMENT_FLOOR):
        raise ValueError(
            "assessment class %s is weaker than %s: a cheaper tier may execute the scripted "
            "cases, but the round's observations are assessed by a %s-class reader"
            % (assessment, ASSESSMENT_FLOOR, ASSESSMENT_FLOOR))
    table = catalog.adapter_tiers(root, runtime, tiers)[1]
    executor = catalog.native_model(table, execution)
    assessor = catalog.native_model(table, assessment)
    if _rank(execution) > _rank(ASSESSMENT_FLOOR):
        if assessor is None:
            raise ValueError(
                "the %s adapter maps no %s class, so the reader of what a %s worker produced "
                "would be whatever model the session is running: name a mapped assessment class"
                % (runtime, assessment, executor or "session-model"))
        if same_model(executor, assessor, _normaliser(root)):
            raise ValueError(
                "execution class %s and assessment class %s both resolve to %s on %s: a cheaper "
                "worker may produce the evidence, but it may not be the only reader of it"
                % (execution, assessment, assessor, runtime))
    notes = []
    for name, model, what in ((execution, executor, "execution"),
                              (assessment, assessor, "assessment")):
        if model is None:
            notes.append(UNMAPPED % (runtime, name, what))
    routing = {"execution_class": execution, "execution_model": executor,
               "assessment_class": assessment, "assessment_model": assessor}
    if notes:
        routing["notes"] = notes
    return routing


def describe(routing):
    """One line an operator reads in a plan or a round summary."""
    return "execution %s (%s), assessment %s (%s)" % (
        routing["execution_class"], routing["execution_model"] or "session model",
        routing["assessment_class"], routing["assessment_model"] or "session model")
