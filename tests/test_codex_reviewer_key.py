# SPDX-License-Identifier: MIT
"""The approval-reviewer key sync writes into Codex's config, and its ownership.

Codex renamed the field to `approvals_reviewer`; the older `approval_reviewer` is rejected under
`--strict-config` and dropped in silence otherwise, so a posture written under the wrong name
resolves as review by the user with nothing said. Every case here runs against a fake `codex` on
PATH — no real client is invoked and no model turn is possible — and the fake answers the two
probes the real one does: its emitted protocol schema and a `--strict-config` parse.

Run: python3 -m unittest discover tests
"""
import contextlib
import io
import json
import os
import stat
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from test_harness import harness, CFG, TempHome
from harness_core import codex_client, reconcile

NEW, OLD = codex_client.REVIEWER_KEYS

FAKE = '''#!/usr/bin/env python3
"""A stand-in Codex client: it accepts the key names this fixture was built for."""
import json
import os
import sys

ACCEPTS = {accepts!r}
MODE = {mode!r}
VERSION = {version!r}

argv = sys.argv[1:]
if argv[:1] == ["--version"]:
    if MODE == "silent-version":
        sys.exit(1)
    print(VERSION)
    sys.exit(0)
if argv[:2] == ["app-server", "generate-json-schema"]:
    if MODE in ("no-schema", "opaque"):
        sys.exit(2)
    out = argv[argv.index("--out") + 1]
    os.makedirs(os.path.join(out, "v2"), exist_ok=True)
    properties = {{"approval_policy": {{}}}}
    for key in ACCEPTS:
        properties[key] = {{"description": "reviewer"}}
    with open(os.path.join(out, "v2", "ConfigReadResponse.json"), "w") as handle:
        json.dump({{"definitions": {{"Config": {{"properties": properties}}}}}}, handle)
    sys.exit(0)
if argv[:1] == ["app-server"]:
    if MODE == "opaque":
        sys.stderr.write("this build has no app-server\\n")
        sys.exit(2)
    text = ""
    path = os.path.join(os.environ.get("CODEX_HOME", ""), "config.toml")
    if os.path.exists(path):
        text = open(path).read()
    for line in text.splitlines():
        name = line.split("=")[0].strip()
        if name and name not in ACCEPTS and name != "approval_policy":
            sys.stderr.write("Error: %s:1:1: unknown configuration field `%s`\\n" % (path, name))
            sys.exit(1)
    sys.stderr.write("Error: no transport configured; use --listen or enable remote control\\n")
    sys.exit(1)
sys.exit(2)
'''


@contextlib.contextmanager
def loud():
    prior = os.environ.pop("HARNESS_QUIET", None)
    buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(buffer):
            yield buffer
    finally:
        if prior is not None:
            os.environ["HARNESS_QUIET"] = prior


class FakeClient:
    """Put a `codex` answering the probes a chosen way at the front of PATH."""

    def __init__(self, case, accepts=(NEW,), mode="schema", version="codex-cli 0.155.1"):
        self.directory = Path(tempfile.mkdtemp())
        case.addCleanup(self._cleanup)
        if accepts is not None:
            executable = self.directory / "codex"
            executable.write_text(FAKE.format(accepts=list(accepts), mode=mode, version=version),
                                  encoding="utf-8")
            executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
        self.prior = os.environ.get("PATH", "")
        # No client means none at all: keeping the rest of PATH would find one the machine has.
        os.environ["PATH"] = (str(self.directory) if accepts is None
                              else str(self.directory) + os.pathsep + self.prior)
        case.addCleanup(self._restore)

    def _restore(self):
        os.environ["PATH"] = self.prior

    def _cleanup(self):
        import shutil
        shutil.rmtree(self.directory, ignore_errors=True)


class DetectionTests(unittest.TestCase):
    def test_the_schema_names_the_key_and_the_newest_spelling_wins(self):
        FakeClient(self, accepts=[OLD, NEW])
        found = codex_client.detect()
        self.assertEqual((found.status, found.key), ("detected", NEW))
        self.assertIn("protocol schema", found.detail)
        self.assertIn("0.155.1", found.detail)

    def test_a_client_that_only_knows_the_old_spelling_gets_the_old_spelling(self):
        FakeClient(self, accepts=[OLD])
        found = codex_client.detect()
        self.assertEqual((found.status, found.key), ("detected", OLD))

    def test_strict_config_answers_when_the_schema_does_not(self):
        FakeClient(self, accepts=[NEW], mode="no-schema")
        found = codex_client.detect()
        self.assertEqual((found.status, found.key), ("detected", NEW))
        self.assertIn("--strict-config", found.detail)

    def test_no_client_on_path_writes_the_newest_supported_spelling(self):
        FakeClient(self, accepts=None)
        found = codex_client.detect()
        self.assertEqual((found.status, found.key), ("absent", NEW))
        self.assertTrue(found.reliable)

    def test_a_client_accepting_neither_spelling_is_reported_and_written_nothing(self):
        FakeClient(self, accepts=[])
        found = codex_client.detect()
        self.assertEqual((found.status, found.key), ("unsupported", None))
        self.assertFalse(found.reliable)
        self.assertIn(NEW, found.detail)
        self.assertIn(OLD, found.detail)

    def test_a_client_that_cannot_be_asked_is_not_guessed_to_be_broken(self):
        FakeClient(self, accepts=[NEW], mode="opaque")
        found = codex_client.detect()
        self.assertEqual((found.status, found.key), ("unprobed", NEW))
        self.assertFalse(found.reliable)

    def test_never_both_spellings_at_once(self):
        # Writing both would be safe only if no supported version rejected either one. Codex
        # 0.154.0-alpha.6.2 through 0.156.0-alpha.9 reject the old spelling under
        # `--strict-config`, so the unwanted one is removed rather than kept as a belt.
        for accepts in ([NEW], [OLD], [OLD, NEW]):
            FakeClient(self, accepts=accepts)
            wanted = harness.codex_wanted(dict(CFG, permissions="auto"))
            written = [k for k in codex_client.REVIEWER_KEYS if wanted.get(k) is not None]
            self.assertEqual(len(written), 1, accepts)
            self.assertEqual(wanted[written[0]], "auto_review")
            self.assertIsNone(wanted[NEW if written[0] == OLD else OLD])

    def test_manual_asks_for_the_user_and_bypass_asks_for_neither_key(self):
        FakeClient(self)
        manual = harness.codex_wanted(dict(CFG, permissions="manual"))
        self.assertEqual(manual[NEW], "user")
        bypass = harness.codex_wanted(dict(CFG, permissions="bypass",
                                           permissions_bypass_acknowledged=True))
        self.assertIsNone(bypass[NEW])
        self.assertIsNone(bypass[OLD])
        self.assertEqual(bypass["approval_policy"], "never")


class OwnershipTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = self.root / "config.toml"

    def store(self):
        return reconcile.Store(self.root / "state")

    def test_a_stale_harness_key_is_removed_and_the_new_one_written(self):
        self.config.write_text('model = "mine"\n')
        first = self.store()
        first.toml(self.config, {OLD: "auto_review", NEW: None})
        self.assertIn(OLD, self.config.read_text())
        second = self.store()
        second.toml(self.config, {NEW: "auto_review", OLD: None})
        document = reconcile.tomlkit.parse(self.config.read_text())
        self.assertEqual(document[NEW], "auto_review")
        self.assertNotIn(OLD, document)
        self.assertEqual(document["model"], "mine")
        self.assertEqual(second.conflicts, [])
        self.assertNotIn(OLD, self.store().data["files"][str(self.config)]["keys"])

    def test_a_key_of_the_same_name_the_harness_never_wrote_is_left_alone(self):
        self.config.write_text('%s = "user"\ntheme = "dark"\n' % OLD)
        store = self.store()
        store.toml(self.config, {NEW: "auto_review", OLD: None})
        document = reconcile.tomlkit.parse(self.config.read_text())
        self.assertEqual(document[OLD], "user")
        self.assertEqual(document[NEW], "auto_review")
        self.assertEqual(document["theme"], "dark")

    def test_removal_restores_a_value_the_harness_replaced(self):
        self.config.write_text('%s = "user"\n' % OLD)
        store = self.store()
        store.toml(self.config, {OLD: "auto_review"})
        store.toml(self.config, {OLD: None})
        self.assertEqual(reconcile.tomlkit.parse(self.config.read_text())[OLD], "user")

    def test_a_reviewer_key_the_user_changed_is_preserved_not_silently_dropped(self):
        store = self.store()
        store.toml(self.config, {OLD: "auto_review"})
        self.config.write_text(self.config.read_text().replace("auto_review", "user"))
        store.toml(self.config, {OLD: None})
        self.assertTrue(store.conflicts)
        self.assertIn('"user"', self.config.read_text())

    def test_uninstall_removes_whichever_spelling_was_written(self):
        for key in codex_client.REVIEWER_KEYS:
            self.config.write_text('model = "mine"\n')
            store = self.store()
            store.toml(self.config, {key: "auto_review"})
            store.uninstall()
            self.assertNotIn(key, self.config.read_text(), key)
            self.assertIn('model = "mine"', self.config.read_text())
            (self.root / "state" / "ownership.json").unlink()


class SyncTests(TempHome):
    def doctor(self):
        """Doctor's report without the installed clients: no test launches a real one, and
        `claude doctor` under a temporary HOME raises a macOS keychain dialog."""
        which = harness.shutil.which

        def hidden(name, *args, **kwargs):
            return None if name == "claude" else which(name, *args, **kwargs)

        with unittest.mock.patch.object(harness, "_version_of", return_value="stub"), \
                unittest.mock.patch.object(harness.shutil, "which", side_effect=hidden), \
                loud() as out:
            harness.cmd_doctor(harness.argparse.Namespace())
        return out.getvalue()

    def sync(self):
        return harness.cmd_sync(harness.argparse.Namespace(dry_run=False, adopt=True,
                                                           adopt_codex=False, print_only=False))

    def configure(self, **values):
        path = self.home / ".config" / "agent-harness" / "config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(dict(CFG, **values)), encoding="utf-8")

    def codex_config(self):
        return reconcile.tomlkit.parse((self.home / ".codex" / "config.toml").read_text())

    def test_sync_writes_the_accepted_spelling_and_drops_the_stale_one_next_time(self):
        self.configure(permissions="auto")
        legacy = FakeClient(self, accepts=[OLD])
        self.assertEqual(self.sync(), 0)
        self.assertEqual(self.codex_config()[OLD], "auto_review")
        legacy._restore()
        FakeClient(self, accepts=[NEW])
        self.assertEqual(self.sync(), 0)
        document = self.codex_config()
        self.assertEqual(document[NEW], "auto_review")
        self.assertNotIn(OLD, document)

    def test_a_client_accepting_neither_spelling_produces_a_notice_and_a_doctor_finding(self):
        self.configure(permissions="auto")
        FakeClient(self, accepts=[])
        with loud() as out:
            self.assertEqual(self.sync(), 0)
        self.assertIn("notice  codex approval review", out.getvalue())
        self.assertNotIn(NEW, self.codex_config())
        self.assertNotIn(OLD, self.codex_config())
        text = self.doctor()
        self.assertIn("codex approval reviewer", text)
        self.assertIn("promises automatic approval review", text)

    def test_an_accepted_spelling_is_quiet_and_doctor_reports_the_evidence(self):
        self.configure(permissions="auto")
        FakeClient(self, accepts=[NEW])
        with loud() as out:
            self.assertEqual(self.sync(), 0)
        self.assertNotIn("codex approval review:", out.getvalue())
        text = self.doctor()
        self.assertIn("codex approval reviewer: codex-cli 0.155.1 accepts " + NEW, text)
        self.assertNotIn("promises automatic approval review", text)

    def test_doctor_in_a_temporary_home_never_launches_the_installed_claude(self):
        self.configure(permissions="auto")
        tripwire = Path(tempfile.mkdtemp())
        self.addCleanup(__import__("shutil").rmtree, tripwire, ignore_errors=True)
        executable = tripwire / "claude"
        executable.write_text("#!/bin/sh\ntouch '%s'\n" % (tripwire / "launched"), encoding="utf-8")
        executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
        with unittest.mock.patch.dict(os.environ, {"PATH": str(tripwire) + os.pathsep + os.environ["PATH"]}):
            self.doctor()
        self.assertFalse((tripwire / "launched").exists())

    def test_unrelated_user_keys_survive_the_rename(self):
        self.configure(permissions="auto")
        codex = self.home / ".codex"
        codex.mkdir(parents=True)
        (codex / "config.toml").write_text('model = "mine"\n\n[projects."/a"]\ntrust_level = "trusted"\n')
        FakeClient(self, accepts=[NEW])
        self.assertEqual(self.sync(), 0)
        document = self.codex_config()
        self.assertEqual(document["model"], "mine")
        self.assertEqual(document["projects"]["/a"]["trust_level"], "trusted")
        self.assertEqual(document[NEW], "auto_review")


if __name__ == "__main__":
    unittest.main()
