# Interchangeable architecture viewers

Viewer implementation, agent runtime, and model provider are independent choices. The
architecture-viewer integration resolves a distribution's builtin adapter by default. A custom
adapter is an explicit user selection. Installation and sync never start a viewer.

This distribution currently has no builtin viewer adapter. Inspection reports it unavailable;
the selector does not substitute a custom viewer. A builtin adapter uses the same contract below,
installed at integrations/architecture-viewer/builtin.json with an explicit id.

## Select an implementation

Register a JSON descriptor with id, capability, contract_version, argv, and optional settings:

~~~json
{
  "id": "upstream-uml-viewer",
  "capability": "architecture-viewer",
  "contract_version": 1,
  "argv": ["/absolute/path/to/python3", "/absolute/path/to/harness/integrations/architecture-viewer/upstream.py"],
  "settings": {
    "viewer_executable": "/absolute/path/to/uml-viewer",
    "state_root": "/absolute/path/to/private-viewer-state",
    "allowed_roots": ["/absolute/path/to/an-additional-approved-root"]
  }
}
~~~

Use an installed standalone uml-viewer candidate exposing protocol 1. Java belongs to that
optional viewer, not the harness. Existing versions without the public client are incompatible.
No upstream source or dependencies are bundled here.

~~~sh
harness integrations register --file adapter.json
harness config set integrations.architecture-viewer.adapter upstream-uml-viewer
harness config set integrations.architecture-viewer.implementation custom
harness integrations show architecture-viewer --json
harness integrations doctor architecture-viewer
harness config set integrations.architecture-viewer.implementation builtin
~~~

Registration preserves the current selection. show inspects configuration and executable
availability without execution; doctor explicitly calls the adapter's describe operation.
Neither result qualifies a native runtime or establishes live model parity.

Precedence is distribution default, user configuration, then invocation override. Project
configuration remains stance-only: a repository cannot nominate an executable adapter.
Selecting an external executable authorizes ordinary local execution; descriptors are not a
sandbox. argv is a literal argument array, never a shell command. Descriptors and pinned session
records store settings, so settings must not contain credentials; adapters read secrets from the
environment or an operating-system secret store when needed.

## Invoke and continue

The authoritative procedure is the architecture-viewer skill, shared by all runtime bindings.
Each command accepts an operation input JSON file. For the upstream adapter:

~~~json
{
  "project_root": "/absolute/path/to/project",
  "source_roots": ["/absolute/path/to/project/src"],
  "document": {
    "path": "/absolute/path/to/snapshot.json",
    "sha256": "the SHA-256 of those exact file bytes"
  },
  "required_capabilities": ["open", "replace-document", "status", "close"]
}
~~~

The profile and every source, metrics, or output root must resolve inside project_root. A user can
pre-authorize another existing directory in the adapter's settings.allowed_roots. Resolution
rejects `..`, missing paths, and symlinks that escape those roots before the adapter reads the
profile or invokes the viewer.

~~~sh
harness viewer validate --input open.json
harness viewer open --input open.json --implementation custom --adapter upstream-uml-viewer
harness viewer status --session UUID
harness viewer replace-document --session UUID --input replacement.json --request-id REQUEST_UUID
harness viewer close --session UUID
~~~

Replacement input includes document and a nonnegative expected_revision from the latest
acknowledgement. Publish a new immutable snapshot before submitting. The upstream public client
owns digest checking, revision conflicts, receipts, retries and cancellation; the harness does
not reproduce its session coordinator.

An opened reference pins the adapter executable, settings and opaque session identity. Changing
defaults or registrations cannot redirect status, update or close. A timeout after mutation is
indeterminate: inspect the recorded session and upstream receipt before retrying the identical
request. Never automatically replay generation or reopen an uncertain session.

Session operations persist their request ID before dispatch; indeterminate CLI errors include
that ID for an identical retry. Known acknowledgements survive local observation-write errors,
which appear separately as persistence_warning. If open returns reference_persisted: false,
retain its complete acknowledgement and repair local storage before relying on that reference.
Pinned records contain minimal continuation metadata and are bounded to 4 MiB, independently of
the 1 MiB limit on each adapter request and response.

References and observations are private data under the harness state directory. Put their paths,
source/document identities and latest acknowledged revision in a neutral task handoff's artifacts
and verification fields. They transfer no approvals or native permissions. Uninstall preserves
user configuration, adapter registrations, references and external viewer installations.

## Adapter contract 1

An adapter reads one bounded JSON object on stdin and writes one JSON result on stdout, exiting.
Required request keys are contract_version, request_id (canonical UUID), operation, implementation
(registered id), settings, and input. The result repeats the first four keys, adds status
(ok, error, or indeterminate), and supplies result (object) or error (object with code).
Success requires exit zero. Inputs and outputs are bounded to 1 MiB; calls have a deadline.

Required operations are describe, validate, open, replace-document, status, and close. describe
reports capabilities as an array of names. open returns result.session as an opaque nonempty
object, plus the viewer's document identity, epoch/revision/digest and actual capabilities.
Session operations receive that object in input.session. Failed results must not invent an
acknowledgement. Unsupported required capabilities fail before open.

Optional request-regeneration, claim-regeneration, complete-generation and cancel-generation
operations require regeneration-request capability. They use consumer, regeneration_id and
claim_id where appropriate. cancel takes target_request_id and requires cancel capability.
A request records intent for the current authorized workflow owner; it never authorizes source
edits or launches an agent. Incomplete, expired and stale work stays explicit.

The upstream adapter calls only the installed public describe/validate/open/status/control CLI.
It sends JSON envelopes to that client and emits EDN projection files. It does not parse EDN,
import private viewer namespaces, compute layout or own document revisions.

## Architecture-diagram profile 1

The profile is deliberately narrower than a review snapshot. Required envelope fields are
profile: architecture-diagram, schema_version: 1, and document_id. Arrays nodes, relations and
packages may be empty. title is optional. Unknown required fields are rejected; optional
objects carry explicitly omittable data and every omission is reported.

- Nodes have id, kind and label; optional package_id, source, metrics and optional. Supported
  kinds are class, module, interface, abstract, enum and external.
- Packages have id and label. Nested package membership is unsupported and rejected.
- Relations have id, from, to and kind, with optional label. Supported kinds are association,
  dependency, aggregation, composition, inheritance and implements.
- Source locators have repository-relative path, optional positive line and Clojure namespace.
  Namespace navigation uses the authorized source roots. Generic path/line navigation is not
  advertised; the locator survives in the mapping artifact with an omission diagnostic.
- Metrics are coverage (0–1), cc, crap, killed and survived. Each is an object with availability
  and, only when measured, value. Missing/unsupported/failed observations remain absent from the
  rendering. Nonfinite, negative and fractional count values reject.

Mapping version 1 hashes exact node and package identities into stable EDN keyword IDs, preserving
case distinctions and identity through label changes. Relation IDs map to their projected
endpoints/kind/index. Package membership is direct; namespace is a source locator, not an invented
hierarchy. Mapping artifacts preserve original source locators. Authored metrics retain their
units; missing metrics never become zeros. Evidence, intent and review acceptance remain in the
original richer snapshot and are not inferred from the diagram.

## Verification boundaries

Unit and process contract tests run without any model account. Native skill discovery and actual
viewer interaction require separate tests in each runtime. Cross-viewer conformance compares
identities and acknowledged outcomes, not pixels or identical feature sets. xAI-backed Grok
parity additionally requires authenticated inference access; offline tests cannot establish it.

Run the optional installed-candidate check with Java available and a graphical desktop:

~~~sh
python3 scripts/viewer_acceptance.py --viewer /absolute/path/to/uml-viewer --evidence /tmp/viewer-result.json
~~~

It opens a real window in isolated state, tests replacement, identical retry, stale revision,
pinned continuation after configuration changes, and close. It does not change live configuration
or qualify an agent runtime. The ordinary unit suite neither starts a viewer nor calls a model.
