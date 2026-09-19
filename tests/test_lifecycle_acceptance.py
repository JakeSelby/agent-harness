"""The release lifecycle runner validates immutable inputs and preservation evidence."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from test_harness import REPO


def load():
    path = REPO / "scripts" / "lifecycle_acceptance.py"
    spec = importlib.util.spec_from_file_location("lifecycle_acceptance", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LifecycleAcceptanceTests(unittest.TestCase):
    def test_baseline_pin_is_complete_and_resolves_to_immutable_release(self):
        module = load()
        data = module.baseline()
        self.assertEqual(module.git(REPO, "rev-parse", data["tag"] + "^{commit}"), data["commit"])
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "baseline.tar"
            module.archive_baseline(REPO, archive, data)
            self.assertEqual(module.hashlib.sha256(archive.read_bytes()).hexdigest(),
                             data["archive"]["sha256"])

    def test_baseline_rejects_incomplete_metadata(self):
        module = load()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "compatibility").mkdir()
            (root / "compatibility/lifecycle-baseline.json").write_text(
                json.dumps({"schema_version": 1}))
            with self.assertRaisesRegex(ValueError, "incomplete"):
                module.baseline(root)

    def test_snapshot_excludes_only_declared_volatile_state(self):
        module = load()
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            volatile = home / ".local/state/agent-harness/manifest.json"
            volatile.parent.mkdir(parents=True)
            volatile.write_text("first")
            kept = home / "kept"
            kept.write_text("value")
            first = module.snapshot(home)
            volatile.write_text("second")
            self.assertEqual(first, module.snapshot(home))
            self.assertIn("kept", first)

    def test_snapshot_compares_effective_json_and_profile_content(self):
        module = load()
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            settings = home / "settings.json"
            profile = home / ".zprofile"
            settings.write_text('{"one": 1, "two": 2}\n')
            profile.write_text('\nexport PATH="x"\n')
            first = module.snapshot(home)
            settings.write_text('{\n  "two": 2,\n  "one": 1\n}\n')
            profile.write_text('\n\nexport PATH="x"\n')
            self.assertEqual(first, module.snapshot(home))

    def test_preservation_check_names_changed_user_state(self):
        module = load()
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            module.seed(home)
            (home / "user-note.txt").write_text("changed")
            with self.assertRaisesRegex(AssertionError, "user file"):
                module.assert_preserved(home)
