# Your primitives, your working style

Personal stances are harness-defined switches for how your agents work. They are not a native
Claude Code or Codex feature. One selected variant supplies policy to both runtime adapters;
native restrictions still apply. Guidance is not proof that a runtime enforces a preference.

## Select and inspect a stance

```sh
bin/harness config set stances.voice answer-card
bin/harness stances
bin/harness sync --dry-run
```

After reviewing the changes, `bin/harness sync` installs the selection. Claude Code reads the
selected stance through its linked rules; Codex reads the same text in generated instructions.
Use `HARNESS_STANCE_VOICE=scannable bin/harness stances --json` to inspect a session selection.
Setting an environment variable on a running agent does not itself rewrite its loaded context.

Resolution order is distribution defaults, user configuration, the optional file explicitly
named by `HARNESS_PROJECT_CONFIG`, then `HARNESS_STANCE_*` session values. Project files can
select stances only. They cannot change identity, runtime targets or permission configuration.

## Define a personal stance

Create a directory outside the checkout, such as `~/.config/agent-harness/primitives`, and add
its absolute expanded path to the `primitive_roots` array in your user configuration. Create
`stances/feedback/direct.md` there with this content:

```markdown
# Feedback stance: direct

Lead with the conclusion. Name the specific evidence and the next useful action.
```

Add `stances/feedback/gentle.md` with your alternative policy, then select it with
`bin/harness config set stances.feedback gentle`. `bin/harness stances --json` shows its
source and full resolved behavior. Custom dimensions are optional until selected. Identifiers
use lowercase letters, digits and hyphens. Duplicate dimension/variant definitions, unknown
selections and path traversal are errors, not fallback behavior.

Optional `constraints.json` alongside `stances/` can reject incompatible choices:

```json
{"stances": [{"when": {"feedback": "direct"}, "excludes": {"voice": "off"},
  "reason": "Direct feedback requires an active voice policy"}]}
```

Each rule has a nonempty `when` selection and optional `requires` and `excludes` selections.
All `when` entries must match to activate the rule; every requirement must match and no
excluded choice may be selected. Validation runs before sync changes files.

## A cost variant with numbers in it

A `cost` variant is prose in `<variant>.md` and, optionally, data in `<variant>.json` beside it.
The sidecar is what the harness resolves; the prose is what your agent reads. In your primitive
root — `~/.config/agent-harness/primitives`, say — write `stances/cost/careful.md` with your
policy, then `stances/cost/careful.json`:

```json
{"schema_version": 1, "extends": "balanced",
 "switches": {"session_effort": "high", "budget_multiplier": 1.4},
 "rows": {"gatherer": {"effort": "medium"}}}
```

`extends` names another cost variant and may chain up to five deep; cycles stop resolution with
a warning. Each layer is merged over the one it extends, switch by switch and row cell by row
cell, so the example above changes three values and inherits every other one. A link that cannot
be followed — no sidecar, unreadable JSON, a `schema_version` the installed release does not
read, a name that is not a primitive identifier — resolves to `balanced`'s table with a warning,
so a variant is never silently empty.

`default_band` names the band an unnamed spawn is routed to, and omitting it everywhere on the
chain routes nothing at all.

A row is keyed by a role name or by a band — `A`, `B` or `C` — and may set `class`, `effort`,
`budget_output_tokens` and `budget_tool_calls`; any of them may be omitted, and a null budget
means unbudgeted. `budget_multiplier` scales both budgets, and `harness stances --json` reports
the base figure and the scaled one. `class` never names the top class: reaching it by request is
exactly what the `delegation` stance forbids, and it only applies at all when that stance
resolves to `tiered`. A role whose frontmatter says `posture: fixed` — the verifiers — keeps its
own class and effort whatever a row says, and takes the row's budgets.

Unknown keys are ignored with a warning rather than an error, so a switch added in a later
release never breaks a variant you wrote. Run `bin/harness stances --json` to see the resolved
table, its `extends_chain`, each sidecar's path, and any warnings.

## Contribute shared primitives

Author rules, stances, skills, roles, workflows and presentation under `primitives/`.
Role instructions and authority are shared; native model/tool settings belong in
`adapters/<runtime>/bindings.json`. Workflow bodies use `{{arguments}}`; the Claude command
projection translates that to its native argument syntax. Existing `claude/` source paths are
compatibility links or generated views, not another authoring home.

Run `bin/harness generate` after editing roles, workflows or base instruction templates.
`bin/harness generate --check` and lint reject projection drift. `bin/harness catalog` emits
stable kind/ID/source/digest records for documentation and integration readers. Installation
coverage and runtime enforcement are separate from successful source generation.
