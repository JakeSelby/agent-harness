"""Which spelling of Codex's approval-reviewer key the installed client actually accepts.

The `auto` posture's promise is that Codex reviews its own approval requests. Codex expresses
that as one configuration key, and a key this client does not recognise is dropped in silence:
the posture then resolves as review by the user with nothing said. So the name is read from the
client rather than assumed, and a client that recognises neither spelling is reported instead of
being written to.

Two probes, in order, both offline and neither starting a model turn:

1. the client's own protocol schema (`codex app-server generate-json-schema`), whose `Config`
   definition lists the configuration fields this build deserialises;
2. failing that, `codex app-server --listen off --strict-config` against a throwaway
   `CODEX_HOME` holding one candidate key, which reports `unknown configuration field` for a
   name the build does not know and fails on the absent transport once the config has parsed.

Measured on macOS against codex-cli 0.154.0-alpha.6.2, 0.155.0-alpha.9, 0.155.1 and
0.156.0-alpha.9: every one of them deserialises `approvals_reviewer` (values `user`,
`auto_review`, `guardian_subagent`) and rejects `approval_reviewer` under `--strict-config`,
logging it as an ignored setting otherwise. No supported version wants the older spelling, so
both are never written; the stale one is removed instead.
"""
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

# Newest-accepted spelling first. Every name here is harness-owned wherever it is found in a
# Codex config: removing the one that is no longer wanted is part of writing the one that is.
REVIEWER_KEYS = ("approvals_reviewer", "approval_reviewer")
REVIEWER_VALUES = {"auto": "auto_review", "manual": "user"}
TIMEOUT = 30


class Reviewer:
    """What the installed client accepts, and the evidence for saying so.

    `status` is `detected` (the client named a key), `absent` (no client to ask),
    `unsupported` (the client recognises neither spelling) or `unprobed` (a client that could
    not be asked). `key` is None only when nothing should be written.
    """

    def __init__(self, status, key, detail, version=None):
        self.status = status
        self.key = key
        self.detail = detail
        self.version = version

    @property
    def reliable(self):
        return self.status in ("detected", "absent")

    def __repr__(self):  # pragma: no cover - diagnostics only
        return "Reviewer(%r, %r, %r)" % (self.status, self.key, self.detail)


def _run(argv, home, timeout=TIMEOUT):
    environment = dict(os.environ, CODEX_HOME=str(home))
    environment.pop("RUST_LOG", None)
    result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout,
                            env=environment)
    return result.returncode, (result.stdout or "") + (result.stderr or "")


def _version(executable, home):
    try:
        code, text = _run([executable, "--version"], home, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return None
    return text.strip().splitlines()[0] if code == 0 and text.strip() else None


def _from_schema(executable, home):
    """The key this build deserialises, read from its own emitted protocol schema."""
    with tempfile.TemporaryDirectory() as out:
        try:
            _run([executable, "app-server", "generate-json-schema", "--out", out], home)
        except (OSError, subprocess.SubprocessError):
            return None
        schema = Path(out) / "v2" / "ConfigReadResponse.json"
        if not schema.is_file():
            return None
        try:
            definitions = json.loads(schema.read_text(encoding="utf-8"))["definitions"]
            fields = definitions["Config"]["properties"]
        except (ValueError, KeyError, OSError):
            return None
    return [key for key in REVIEWER_KEYS if key in fields]


def _from_strict_config(executable, root):
    """The keys this build parses, asked one at a time under `--strict-config`.

    Silence is not acceptance: the probe counts a key as parsed only when the client gets far
    enough to complain about the transport this call deliberately withholds. Any other answer
    leaves the question open, which is reported rather than guessed at.
    """
    accepted = []
    for key in REVIEWER_KEYS:
        home = Path(root) / ("probe-" + key)
        home.mkdir(parents=True, exist_ok=True)
        (home / "config.toml").write_text('%s = "auto_review"\n' % key, encoding="utf-8")
        try:
            _, text = _run([executable, "app-server", "--listen", "off", "--strict-config"], home)
        except (OSError, subprocess.SubprocessError):
            return None
        if "unknown configuration field" in text and key in text:
            continue
        if "no transport configured" in text:
            accepted.append(key)
            continue
        return None
    return accepted


def detect(executable=None):
    """Ask the installed Codex client which approval-reviewer key it accepts.

    No client is not a failure: the newest supported spelling is written, because the config is
    for whatever client the user installs next. A client that answers neither probe is reported.
    """
    executable = executable or shutil.which("codex")
    if not executable:
        return Reviewer("absent", REVIEWER_KEYS[0],
                        "no codex client on PATH; wrote %s, the key the newest supported "
                        "version accepts" % REVIEWER_KEYS[0])
    with tempfile.TemporaryDirectory() as root:
        version = _version(executable, root)
        if version is None:
            return Reviewer("unprobed", REVIEWER_KEYS[0],
                            "codex at %s did not report a version; wrote %s unverified"
                            % (executable, REVIEWER_KEYS[0]))
        schema, source = _from_schema(executable, root), "its protocol schema"
        accepted = schema
        if not accepted:
            accepted = _from_strict_config(executable, root)
            source = "--strict-config"
        if accepted is None and schema is not None:
            accepted, source = schema, "its protocol schema"
        if accepted is None:
            return Reviewer("unprobed", REVIEWER_KEYS[0],
                            "%s could not be asked which approval-reviewer key it accepts; "
                            "wrote %s unverified" % (version, REVIEWER_KEYS[0]), version)
        if not accepted:
            return Reviewer("unsupported", None,
                            "%s accepts neither %s nor %s (%s), so no approval-reviewer key was "
                            "written; this client cannot route approvals automatically"
                            % (version, REVIEWER_KEYS[0], REVIEWER_KEYS[1], source), version)
        key = next(k for k in REVIEWER_KEYS if k in accepted)
        return Reviewer("detected", key, "%s accepts %s (%s)" % (version, key, source), version)
