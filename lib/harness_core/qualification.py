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
from . import catalog

TIER_CLASSES = catalog.TIER_CLASSES
EXECUTION_DEFAULT = "standard"
ASSESSMENT_DEFAULT = "strong"
# The weakest class allowed to assess a round's observations. `docs/compatibility.md` requires a
# reviewer; #340's decision 6 keeps that reviewer strong-class while the executor gets cheaper.
ASSESSMENT_FLOOR = "strong"
UNMAPPED = ("the %s adapter maps no %s class, so the %s worker inherits the session model; "
            "the record names the class, not a model")


def _rank(name):
    return TIER_CLASSES.index(name)


def _checked(name, what):
    if name not in TIER_CLASSES:
        raise ValueError("%s class must be one of %s: %s" % (what, ", ".join(TIER_CLASSES), name))
    return name


def parse_class_map(values, targets, default):
    """`CLASS` or `TARGET=CLASS` arguments, later ones winning, as one class per target.

    A bare class moves every target the round is running; a qualified one moves the target it
    names, so a Codex round can be executed at a different class from a Claude Code one without
    two invocations.
    """
    chosen = dict((target, default) for target in targets)
    for value in values or []:
        target, _, name = str(value).partition("=")
        if not name:
            target, name = None, target
        if target is not None and target not in chosen:
            raise ValueError("unknown qualification target: " + target)
        _checked(name.strip(), "worker")
        for key in ([target] if target is not None else list(chosen)):
            chosen[key] = name.strip()
    return chosen


def resolve(root, runtime, execution=EXECUTION_DEFAULT, assessment=ASSESSMENT_DEFAULT,
            tiers=None):
    """The round's routing for one target, or `ValueError` naming why it is refused.

    An unmapped class is a disclosure and not a refusal: `native_model` never resolves downward,
    so the worker inherits the session model and the note says so. The refusal is a cheap
    execution class that lands on the assessment class's own model, however it came about — an
    adapter table mapping two classes to one identifier, or a cheap class the table does not map
    at all, which resolves upward. Executing at the floor or above is not refused: it buys no
    saving, and the reviewer it asks for is the one the procedure already requires.
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
    if _rank(execution) > _rank(ASSESSMENT_FLOOR) and executor == assessor:
        raise ValueError(
            "execution class %s and assessment class %s both resolve to %s on %s: a cheaper "
            "worker may produce the evidence, but it may not be the only reader of it"
            % (execution, assessment, executor or "the session model", runtime))
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
