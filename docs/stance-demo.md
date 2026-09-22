# One personal switch, two runtime projections

Nine stance axes ship, and three of them bind to enforcement: `autonomy` decides which
shell-command grade stops and asks, `delegation` routes a spawn, and `cost` resolves a class, an
effort and a budget per role. The other six are prose that swaps cleanly in both projections. The
switch demonstrated below is `delegation`, one of the three.

The demonstration describes deterministic adapter behavior. It is not a native client
qualification result; use the [catalog](compatibility.md) for that evidence.

```sh
harness config set stances.delegation off
harness stances --json
harness sync
```

The resolved source is `primitives/stances/delegation/off.md`. Claude's selected rule link and
Codex's generated instructions carry that same policy. With native hooks active, a Claude `Agent`
event and a Codex `spawn_agent` event normalize to the same shared spawn policy: ask before the
spawn, so only an explicit user request permits it. `tests/test_lifecycle.py` exercises both native
envelopes.

```sh
harness config set stances.delegation tiered
harness stances --json
harness sync
```

Both projections now carry `primitives/stances/delegation/tiered.md`: bounded gathering is allowed;
judgment stays with the session. Each shared role names a capability class and each adapter's
`tiers` table maps the classes to its own native models, so neither adapter interprets the
other's names. Both map all four. A class an adapter leaves out resolves upward or inherits the
session model, and a `role_bindings` override of `model` to `inherit` does the same per role.

For communication, switch `stances.voice` from `answer-card` to `scannable`: the resolved text
changes from the answer/why/catch contract to verdict-first sections and explicit status labels.
The same source drives both projections, but only native behavioral tests can measure compliance.

## Author a switch of your own

Create `stances/feedback/direct.md` and `stances/feedback/gentle.md` in an external primitive root:

```markdown
# Feedback stance: direct
Lead with the conclusion. Name the evidence and the next useful action.
```

```markdown
# Feedback stance: gentle
Explain the observation first, then suggest one concrete next action.
```

Register the absolute root in `primitive_roots`, select `stances.feedback=direct`, inspect with
`harness stances --json`, then sync. Switching to `gentle` changes both projections without a
provider-specific copy. A new prose stance is advisory in both adapters; it does not acquire
new enforced controls by its name. The [authoring contract](primitive-authoring.md) covers project
and session precedence, invalid selections, duplicate authorities and conflict constraints.
