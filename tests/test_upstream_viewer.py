"""The optional adapter consumes only the upstream public process protocol."""
import hashlib
import json
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch
from test_harness import harness
from test_viewer_profile import fixture
from harness_core import integrations as api, upstream_viewer as adapter


class UpstreamAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.file = self.root / "profile.json"
        self.file.write_text(json.dumps(fixture()))
        self.payload = {"document": {"path": str(self.file), "sha256": hashlib.sha256(self.file.read_bytes()).hexdigest()},
                        "project_root": str(self.root)}
        self.request = {"contract_version": 1, "request_id": str(uuid.uuid4()), "implementation": "upstream",
                        "settings": {"viewer_executable": "/test/viewer", "state_root": str(self.root / "state")},
                        "operation": "validate", "input": self.payload}

    def test_validates_through_public_cli_and_keeps_mapping(self):
        with patch.object(adapter, "call", return_value={"status": "valid"}) as call:
            result = adapter.execute(self.request)
        self.assertEqual(call.call_args.args[:3], ("/test/viewer", "validate", "--file"))
        projection = result["result"]["projection"]
        self.assertTrue(Path(projection["path"]).is_file())
        self.assertTrue(Path(projection["mapping"]).is_file())
        self.assertEqual(result["status"], "ok")

    def test_digest_change_fails_before_invocation(self):
        self.file.write_text("{}")
        with patch.object(adapter, "call") as call, self.assertRaises(api.IntegrationError):
            adapter.execute(self.request)
        call.assert_not_called()

    def test_immutable_output_refuses_redirection(self):
        target = self.root / "snapshot"
        target.symlink_to(self.file)
        original = self.file.read_bytes()
        with self.assertRaises(api.IntegrationError):
            adapter.immutable(target, b"other")
        self.assertEqual(self.file.read_bytes(), original)

    def test_roots_are_explicit_and_companion_is_never_implicitly_launched(self):
        source = self.root / "src"
        source.mkdir()
        args = adapter.root_arguments(dict(self.payload, source_roots=[str(source)]), self.root)
        self.assertIn("--source-root", args)
        self.assertNotIn("--companion", args)
        with self.assertRaises(api.IntegrationError):
            adapter.root_arguments({"project_root": "relative"}, self.root)

    def test_profile_and_context_roots_cannot_escape_user_authority(self):
        project = self.root / "project"
        project.mkdir()
        self.payload["project_root"] = str(project)
        with patch.object(adapter, "call") as call, self.assertRaises(api.IntegrationError) as error:
            adapter.execute(self.request)
        self.assertEqual(error.exception.code, "path-denied")
        call.assert_not_called()

        link = project / "profile.json"
        link.symlink_to(self.file)
        self.payload["document"]["path"] = str(link)
        with self.assertRaises(api.IntegrationError) as error:
            adapter.execute(self.request)
        self.assertEqual(error.exception.code, "path-denied")

        shared = self.root / "shared"
        shared.mkdir()
        with self.assertRaises(api.IntegrationError) as error:
            adapter.root_arguments(dict(self.payload, source_roots=[str(shared)]), self.root)
        self.assertEqual(error.exception.code, "path-denied")

    def test_preconfigured_additional_root_authorizes_profile_and_source(self):
        project = self.root / "project"
        project.mkdir()
        self.payload["project_root"] = str(project)
        self.request["settings"]["allowed_roots"] = [str(self.root)]
        with patch.object(adapter, "call", return_value={"status": "valid"}):
            self.assertEqual(adapter.execute(self.request)["status"], "ok")
        args = adapter.root_arguments(dict(self.payload, source_roots=[str(self.root)]), self.root,
                                      self.request["settings"])
        self.assertIn(str(self.root.resolve()), args)

    def test_status_checks_session_epoch(self):
        directory = self.root / "state/runs/session"
        directory.mkdir(parents=True)
        self.request.update(operation="status", input={"session": {"directory": str(directory), "id": "s", "epoch": "old"}})
        with patch.object(adapter, "call", return_value={"session-id": "s", "epoch": "new"}) as call:
            with self.assertRaises(api.IntegrationError) as error:
                adapter.execute(self.request)
        self.assertEqual(error.exception.code, "session-lost")
        self.assertEqual(call.call_count, 1)

    def test_replacement_forwards_revision_and_digest_to_public_client(self):
        directory = self.root / "state/runs/session"
        directory.mkdir(parents=True)
        self.request.update(operation="replace-document")
        project = self.payload.pop("project_root")
        self.payload.update(session={"directory": str(directory), "id": "s", "epoch": "e",
                                     "project_root": project}, expected_revision=3)
        with patch.object(adapter, "call", return_value={"status": "applied", "revision": 4}) as call:
            result = adapter.execute(self.request)
        args = call.call_args.args
        self.assertEqual(args[:2], ("/test/viewer", "control"))
        command = json.loads(Path(args[args.index("--request-json") + 1]).read_text())
        self.assertEqual(command["expected-revision"], 3)
        self.assertEqual(command["sha256"], hashlib.sha256(Path(command["path"]).read_bytes()).hexdigest())
        self.assertEqual(result["result"]["revision"], 4)

    def test_close_retry_reaches_public_receipt_without_live_status_preflight(self):
        directory = self.root / "state/runs/session"
        directory.mkdir(parents=True)
        self.request.update(operation="close", input={"session": {"directory": str(directory), "id": "s", "epoch": "e"}})
        with patch.object(adapter, "call", return_value={"status": "closed", "epoch": "e"}) as call:
            self.assertEqual(adapter.execute(self.request)["status"], "ok")
        self.assertEqual(call.call_count, 1)
        self.assertEqual(call.call_args.args[1], "control")
        request_file = Path(call.call_args.args[-1])
        self.assertEqual(json.loads(request_file.read_text())["epoch"], "e")

    def test_upstream_rejection_is_never_reported_as_success(self):
        with patch.object(adapter, "call", return_value={"status": "rejected", "error": {"code": "invalid-document"}}):
            result = adapter.execute(self.request)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "invalid-document")

    def test_common_results_use_common_names(self):
        value = adapter.translated({"status": "applied", "document-id": "d", "epoch": "e",
                                    "regeneration": {"claim-id": "claim"}})
        self.assertEqual(value["result"]["document_id"], "d")
        self.assertEqual(value["result"]["regeneration"]["claim_id"], "claim")

    def test_unknown_upstream_outcomes_never_become_success(self):
        for value in ({}, {"status": []}, {"status": "failed"}, {"lifecycle": "unknown"}):
            with self.subTest(value=value), self.assertRaises(api.IntegrationError) as error:
                adapter.translated(value)
            self.assertEqual(error.exception.code, "invalid-response")
            self.assertTrue(error.exception.indeterminate)

    def test_same_projection_with_changed_optional_metadata_keeps_both_mappings(self):
        state = adapter.private(self.root / "state")
        first = adapter.snapshot(self.payload, state)
        value = fixture()
        value["nodes"][0]["source"]["line"] = 2
        self.file.write_text(json.dumps(value))
        self.payload["document"]["sha256"] = hashlib.sha256(self.file.read_bytes()).hexdigest()
        second = adapter.snapshot(self.payload, state)
        self.assertEqual(first["path"], second["path"])
        self.assertNotEqual(first["mapping"], second["mapping"])
        self.assertTrue(Path(first["mapping"]).is_file())

    def test_real_public_client_invalid_json_and_excess_output_reject(self):
        import os
        script = self.root / "fake-client"
        for body in ("print('invalid')", "print('x' * (1024 * 1024 + 1))"):
            script.write_text("#!/usr/bin/env python3\n" + body + "\n")
            os.chmod(script, 0o700)
            with self.assertRaises(api.IntegrationError):
                adapter.call(str(script), "describe")
