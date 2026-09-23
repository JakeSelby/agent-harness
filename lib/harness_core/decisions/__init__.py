"""Decision providers that answer the seam in `harness_core.decision` over a transport.

The contract itself — `Action`, `Decision`, `DecisionProvider`, and the `none` and `local`
providers that need no transport — lives in `harness_core.decision`. A module here implements
that contract against something outside this process, so a provider that must import the
contract cannot be imported by it: `decision.select_provider` loads these lazily by name.
"""
