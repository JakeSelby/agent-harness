# SPDX-License-Identifier: MIT
"""OTLP export of ledger rows: the request, the credential rules, and what off means.

The ledger is the record and a backend is a copy of it, so every assertion here is about the
copy never costing the record anything: export off opens no socket at all, a dead or hanging
collector leaves the hook's exit status and its budget alone, and a header value never reaches
a printed line or an error record.

The collector is a stdlib `http.server` on an ephemeral port, so the shapes asserted are the
bytes a real endpoint would receive. Run: python3 -m unittest discover tests
"""
import calendar
import contextlib
import http.server
import io
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from test_usage import REPO, _load, harness

telemetry = _load("harness_telemetry", REPO / "claude" / "hooks" / "telemetry.py")
HOOK = REPO / "claude" / "hooks" / "usage-log.py"
VERSION = (REPO / "VERSION").read_text(encoding="utf-8").strip()

SESSION_ROW = {
    "kind": "session", "runtime": "claude-code", "session_id": "s-1", "repo": "a-repo",
    "branch": "topic", "models": ["model-a"], "harness_version": "0.12.0",
    "started": "2026-09-01T10:00:00.000Z", "ended": "2026-09-01T11:00:00.000Z",
    "input": 10, "output": 200, "cache_read": 800, "cache_write": None, "turns": 4,
    "rerouted": False, "days": {"2026-09-01": {"output": 200}},
    "rules": {"secrets": 0}, "counts": {"tool_calls": 7},
    "stances": {"commits": "conventional-attributed", "testing": "required"},
}
SUBAGENT_ROW = {
    "kind": "subagent", "runtime": "claude-code", "session_id": "s-1", "agent_id": "a-9",
    "agent_type": "worker-b", "model": "model-b", "output": 70, "spawn_depth": 1,
    "rerouted": True, "ended": "2026-09-01T10:30:00.000Z",
}
# The session row's `ended` in epoch nanoseconds: 2026-09-01T11:00:00Z is 1788260400 seconds,
# which `date -u -j -f "%Y-%m-%dT%H:%M:%S" "2026-09-01T11:00:00" +%s` prints.
SESSION_NANOS = "1788260400000000000"


def collector(status=200, delay=0.0):
    """A stub OTLP endpoint. Returns the server and the list its handler appends requests to."""
    seen = []

    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.0"

        def do_POST(self):
            if delay:
                time.sleep(delay)
            raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            try:
                body = json.loads(raw.decode("utf-8"))
            except ValueError:
                body = None
            seen.append({"path": self.path,
                         "content_type": self.headers.get("Content-Type"),
                         "header_names": sorted(k.lower() for k in self.headers.keys()),
                         "body": body})
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, seen


def closed_port():
    """A port nothing is listening on, taken and released so it cannot collide."""
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def records(request):
    return request["body"]["resourceLogs"][0]["scopeLogs"][0]["logRecords"]


def attrs(record):
    return {a["key"]: a["value"] for a in record["attributes"]}


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.errors = self.root / "usage.errors.jsonl"

    def config(self, **overrides):
        base = {"export": "otlp", "endpoint": "http://127.0.0.1:1", "headers_env": "",
                "headers_file": "", "labels": {}}
        base.update(overrides)
        return base

    def serve(self, **kwargs):
        server, seen = collector(**kwargs)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return "http://127.0.0.1:%d" % server.server_address[1], seen

    def error_lines(self):
        if not self.errors.exists():
            return []
        return [json.loads(l) for l in self.errors.read_text(encoding="utf-8").splitlines()]


class TheRequest(Fixture):
    def test_one_record_per_row_with_the_path_type_and_header_the_endpoint_expects(self):
        endpoint, seen = self.serve()
        stanced = dict(SESSION_ROW, session_id="s-2")
        config = self.config(endpoint=endpoint, headers_env="HARNESS_TEST_OTLP_HEADERS")
        sent, failed = telemetry.export_rows(
            [SESSION_ROW, SUBAGENT_ROW, stanced], config=config,
            env={"HARNESS_TEST_OTLP_HEADERS": "authorization=secret-value,x-scope=one"},
            version=VERSION, errors_path=self.errors)
        self.assertEqual((sent, failed), (3, 0))
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0]["path"], "/v1/logs")
        self.assertEqual(seen[0]["content_type"], "application/json")
        # By name: the value is a credential and this test never learns it from the wire.
        self.assertIn("authorization", seen[0]["header_names"])
        self.assertIn("x-scope", seen[0]["header_names"])
        resource = {a["key"]: a["value"]["stringValue"]
                    for a in seen[0]["body"]["resourceLogs"][0]["resource"]["attributes"]}
        self.assertEqual(resource["service.name"], "agent-harness")
        self.assertEqual(len(records(seen[0])), 3)

    def test_a_record_carries_the_rows_own_time_body_and_scalar_attributes(self):
        endpoint, seen = self.serve()
        telemetry.export_rows([SESSION_ROW], config=self.config(endpoint=endpoint),
                              env={}, version=VERSION, errors_path=self.errors)
        record = records(seen[0])[0]
        self.assertEqual(record["timeUnixNano"], SESSION_NANOS)
        self.assertGreater(int(record["observedTimeUnixNano"]), int(SESSION_NANOS))
        self.assertIsInstance(record["observedTimeUnixNano"], str)
        # Everything the ledger holds but the stance map, which travels as attributes alone.
        self.assertEqual(json.loads(record["body"]["stringValue"]),
                         dict((k, v) for k, v in SESSION_ROW.items() if k != "stances"))
        values = attrs(record)
        self.assertEqual(values["kind"], {"stringValue": "session"})
        # OTLP/JSON carries a 64-bit integer as a decimal string, never as a JSON number.
        self.assertEqual(values["output"], {"intValue": "200"})
        self.assertEqual(values["rerouted"], {"boolValue": False})
        self.assertEqual(values["harness.row_key"],
                         {"stringValue": "s-1|claude-code|session|"})
        self.assertEqual(values["harness.version"], {"stringValue": "0.12.0"})
        # A stance is a dimension a report groups by, so each one is its own attribute.
        self.assertEqual(values["harness.commits"], {"stringValue": "conventional-attributed"})
        self.assertEqual(values["harness.testing"], {"stringValue": "required"})
        # A null is absent, a nested map travels in the body only.
        self.assertNotIn("cache_write", values)
        for nested in ("days", "rules", "counts", "stances", "models"):
            self.assertNotIn(nested, values)

    def test_a_subagent_row_keys_on_its_agent_id_and_a_label_rides_along(self):
        endpoint, seen = self.serve()
        telemetry.export_rows([SUBAGENT_ROW], version=VERSION, env={},
                              config=self.config(endpoint=endpoint,
                                                 labels={"deployment.environment": "laptop"}),
                              errors_path=self.errors)
        values = attrs(records(seen[0])[0])
        self.assertEqual(values["harness.row_key"], {"stringValue": "s-1|claude-code|subagent|a-9"})
        self.assertEqual(values["deployment.environment"], {"stringValue": "laptop"})
        self.assertEqual(values["agent_type"], {"stringValue": "worker-b"})
        # The row carries no version of its own, so the running one is stamped instead.
        self.assertEqual(values["harness.version"], {"stringValue": VERSION})

    def test_a_replay_of_the_same_row_repeats_its_key_so_a_reader_can_deduplicate(self):
        endpoint, seen = self.serve()
        for _ in range(2):
            telemetry.export_rows([SESSION_ROW], config=self.config(endpoint=endpoint),
                                  env={}, version=VERSION, errors_path=self.errors)
        keys = [attrs(records(r)[0])["harness.row_key"] for r in seen]
        self.assertEqual(keys[0], keys[1])

    def test_rows_are_batched_by_count_and_by_size(self):
        endpoint, seen = self.serve()
        rows = [dict(SESSION_ROW, session_id="s-%d" % i) for i in range(250)]
        sent, failed = telemetry.export_rows(rows, config=self.config(endpoint=endpoint),
                                             env={}, version=VERSION, errors_path=self.errors)
        self.assertEqual((sent, failed), (250, 0))
        self.assertEqual(len(seen), 3)
        big = [dict(SESSION_ROW, session_id="s-%d" % i, counts={"pad": "x" * 200000})
               for i in range(10)]
        self.assertGreater(len(list(telemetry.batches(big))), 1)


class WhenTheEndpointIsUnreachable(Fixture):
    def test_a_closed_port_costs_a_failure_line_and_no_exception(self):
        endpoint = "http://127.0.0.1:%d" % closed_port()
        started = time.time()
        sent, failed = telemetry.export_rows([SESSION_ROW], config=self.config(endpoint=endpoint),
                                             env={}, version=VERSION, errors_path=self.errors)
        self.assertEqual((sent, failed), (0, 1))
        self.assertLess(time.time() - started, telemetry.TIMEOUT + 2)
        line = self.error_lines()[0]
        self.assertEqual(line["action"], "otlp-export")
        self.assertEqual(line["rows"], 1)
        self.assertTrue(line["error"])

    def test_a_hanging_endpoint_is_abandoned_inside_the_timeout(self):
        endpoint, _ = self.serve(delay=telemetry.TIMEOUT + 3)
        started = time.time()
        sent, failed = telemetry.export_rows([SESSION_ROW], config=self.config(endpoint=endpoint),
                                             env={}, version=VERSION, errors_path=self.errors)
        elapsed = time.time() - started
        self.assertEqual((sent, failed), (0, 1))
        self.assertLess(elapsed, telemetry.TIMEOUT + 2)

    def test_a_rejected_request_is_a_failure_not_a_silent_success(self):
        endpoint, seen = self.serve(status=401)
        sent, failed = telemetry.export_rows([SESSION_ROW], config=self.config(endpoint=endpoint),
                                             env={}, version=VERSION, errors_path=self.errors)
        self.assertEqual((sent, failed), (0, 1))
        self.assertEqual(len(seen), 1)

    def test_an_error_record_names_the_host_and_never_a_header_value(self):
        endpoint = "http://127.0.0.1:%d/v1/logs?token=secret-value" % closed_port()
        telemetry.export_rows(
            [SESSION_ROW], config=self.config(endpoint=endpoint,
                                              headers_env="HARNESS_TEST_OTLP_HEADERS"),
            env={"HARNESS_TEST_OTLP_HEADERS": "authorization=secret-value"},
            version=VERSION, errors_path=self.errors)
        text = self.errors.read_text(encoding="utf-8")
        self.assertNotIn("secret-value", text)
        self.assertEqual(json.loads(text.splitlines()[0])["endpoint"],
                         endpoint.split("/v1/logs")[0])


class Credentials(Fixture):
    def test_a_header_value_in_the_config_is_refused_by_name(self):
        with self.assertRaises(ValueError) as caught:
            telemetry.settings({"telemetry": {"export": "otlp", "headers": {"authorization": "k"}}})
        self.assertIn("headers_env", str(caught.exception))
        with self.assertRaises(ValueError):
            telemetry.settings({"telemetry": {"export": "otlp", "headers_env": "authorization=k"}})

    def test_an_unset_environment_variable_is_named_and_nothing_is_sent(self):
        endpoint, seen = self.serve()
        sent, failed = telemetry.export_rows(
            [SESSION_ROW], config=self.config(endpoint=endpoint, headers_env="HARNESS_TEST_ABSENT"),
            env={}, version=VERSION, errors_path=self.errors)
        self.assertEqual((sent, failed), (0, 1))
        self.assertEqual(seen, [])

    def test_a_headers_file_is_read_only_when_it_is_private_and_outside_a_repository(self):
        path = self.root / "otlp-headers"
        path.write_text("authorization=secret-value\nx-scope=one\n", encoding="utf-8")
        os.chmod(str(path), 0o600)
        self.assertEqual(telemetry.headers_from_file(path),
                         {"authorization": "secret-value", "x-scope": "one"})
        os.chmod(str(path), 0o644)
        with self.assertRaises(ValueError) as caught:
            telemetry.headers_from_file(path)
        self.assertIn("readable by other users", str(caught.exception))
        self.assertNotIn("secret-value", str(caught.exception))

    def test_a_headers_file_inside_a_work_tree_is_refused(self):
        repo = self.root / "repo"
        (repo / ".git").mkdir(parents=True)
        path = repo / "otlp-headers"
        path.write_text("authorization=secret-value\n", encoding="utf-8")
        os.chmod(str(path), 0o600)
        with self.assertRaises(ValueError) as caught:
            telemetry.headers_from_file(path)
        self.assertIn("git work tree", str(caught.exception))

    def test_the_comma_separated_form_the_otel_variable_uses_is_accepted(self):
        self.assertEqual(telemetry.parse_headers("a=1, b=2"), {"a": "1", "b": "2"})
        self.assertEqual(telemetry.parse_headers("a=1\nb=2\n"), {"a": "1", "b": "2"})
        with self.assertRaises(ValueError):
            telemetry.parse_headers("not-a-header")


class WhenExportIsOff(Fixture):
    def test_nothing_opens_a_connection(self):
        def refuse(*args, **kwargs):
            raise AssertionError("export is off; no request may be built")

        with patch.object(telemetry.urllib.request, "urlopen", refuse):
            self.assertEqual(
                telemetry.export_rows([SESSION_ROW], config={"export": "off"}, env={},
                                      errors_path=self.errors),
                (0, 0))
            self.assertEqual(telemetry.settings({})["export"], "off")
            self.assertEqual(telemetry.settings({"telemetry": {"export": "off"}})["export"], "off")
        self.assertEqual(self.error_lines(), [])

    def test_the_shipped_configuration_exports_nothing(self):
        example = json.loads((REPO / "config.example.json").read_text(encoding="utf-8"))
        self.assertEqual(telemetry.settings(example)["export"], "off")

    def test_a_block_that_cannot_be_honoured_is_refused_with_a_reason(self):
        for block in ({"export": "yes"}, {"endpoint": "ftp://h", "export": "otlp"},
                      {"export": "otlp", "labels": {"a": {"b": 1}}}, {"export": "otlp", "nonsense": 1}):
            with self.assertRaises(ValueError):
                telemetry.settings({"telemetry": block})


class TheHook(Fixture):
    """The detached worker, run the way the hook runs it: a subprocess over a temp HOME."""

    def run_worker(self, home, transcript):
        started = time.time()
        out = subprocess.run([sys.executable, str(HOOK), "--worker", str(transcript), "s-1", ""],
                             capture_output=True, text=True,
                             env=dict(os.environ, HOME=str(home)), timeout=120)
        return out, time.time() - started

    def transcript(self, home):
        stamp = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(time.time() - 60))
        path = home / ".claude" / "projects" / "p" / "s-1.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(
            {"type": "assistant", "sessionId": "s-1", "cwd": "", "timestamp": stamp,
             "message": {"id": "m1", "model": "model-a", "content": [],
                         "usage": {"input_tokens": 1, "output_tokens": 2,
                                   "cache_read_input_tokens": 3,
                                   "cache_creation_input_tokens": 4}}}) + "\n", encoding="utf-8")
        return path

    def write_config(self, home, block):
        path = home / ".config" / "agent-harness" / "config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"telemetry": block}), encoding="utf-8")

    def test_a_dead_endpoint_leaves_the_exit_status_and_the_ledger_alone(self):
        home = self.root / "home"
        home.mkdir()
        transcript = self.transcript(home)
        self.write_config(home, {"export": "otlp",
                                 "endpoint": "http://127.0.0.1:%d" % closed_port()})
        out, elapsed = self.run_worker(home, transcript)
        self.assertEqual(out.returncode, 0, out.stderr)
        ledger = home / ".local/state/agent-harness/usage.jsonl"
        self.assertTrue(ledger.exists())
        # The row is on disk whatever the endpoint did; that is what makes replay the fix.
        self.assertTrue(any(json.loads(l)["session_id"] == "s-1"
                            for l in ledger.read_text(encoding="utf-8").splitlines()))
        failures = home / ".local/state/agent-harness/usage.errors.jsonl"
        self.assertTrue(failures.exists())
        self.assertIn("otlp-export", failures.read_text(encoding="utf-8"))

    def test_the_row_reaches_a_live_endpoint_from_the_worker(self):
        endpoint, seen = self.serve()
        home = self.root / "live"
        home.mkdir()
        transcript = self.transcript(home)
        self.write_config(home, {"export": "otlp", "endpoint": endpoint})
        out, _ = self.run_worker(home, transcript)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(len(seen), 1)
        keys = [attrs(r)["harness.row_key"]["stringValue"] for r in records(seen[0])]
        self.assertIn("s-1|claude-code|session|", keys)

    def test_the_default_configuration_writes_no_error_and_sends_nothing(self):
        home = self.root / "quiet"
        home.mkdir()
        out, _ = self.run_worker(home, self.transcript(home))
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertFalse((home / ".local/state/agent-harness/usage.errors.jsonl").exists())


class Replay(Fixture):
    def ledger(self, home, rows):
        path = home / ".local" / "state" / "agent-harness" / "usage.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")

    def export(self, home, **kwargs):
        args = harness.argparse.Namespace(action="export", since=None, until=None,
                                          dry_run=False, days=30, by="day", rules=False,
                                          rescan=False)
        for key, value in kwargs.items():
            setattr(args, key, value)
        buf = io.StringIO()
        with patch.dict(os.environ, {"HOME": str(home), "HARNESS_HOME": str(home)}):
            with contextlib.redirect_stdout(buf):
                status = harness.cmd_usage(args)
        return status, buf.getvalue()

    def setUp(self):
        super().setUp()
        self.home = self.root / "home"
        (self.home / ".config" / "agent-harness").mkdir(parents=True)
        self.rows = [dict(SESSION_ROW, session_id="s-%d" % i,
                          ended="2026-09-0%dT11:00:00.000Z" % i) for i in (1, 2, 3)]
        self.ledger(self.home, self.rows)

    def configure(self, endpoint):
        (self.home / ".config" / "agent-harness" / "config.json").write_text(
            json.dumps({"telemetry": {"export": "otlp", "endpoint": endpoint}}), encoding="utf-8")

    def test_only_the_window_is_replayed(self):
        endpoint, seen = self.serve()
        self.configure(endpoint)
        status, output = self.export(self.home, since="2026-09-02", until="2026-09-02")
        self.assertEqual(status, 0)
        self.assertIn("sent 1 row(s)", output)
        self.assertEqual([attrs(r)["session_id"]["stringValue"] for r in records(seen[0])], ["s-2"])
        status, output = self.export(self.home, since="2026-09-02")
        self.assertEqual(status, 0)
        self.assertIn("sent 2 row(s)", output)

    def test_a_failed_batch_exits_non_zero_and_says_where_the_failures_are(self):
        endpoint, _ = self.serve(status=503)
        self.configure(endpoint)
        status, output = self.export(self.home, since="2026-09-01")
        self.assertEqual(status, 1)
        self.assertIn("3 row(s) failed", output)
        self.assertIn("harness.row_key", output)

    def test_a_dry_run_counts_the_window_and_opens_no_connection(self):
        self.configure("http://127.0.0.1:%d" % closed_port())

        def refuse(*args, **kwargs):
            raise AssertionError("a dry run sends nothing")

        with patch.object(telemetry.urllib.request, "urlopen", refuse):
            status, output = self.export(self.home, since="2026-09-01", dry_run=True)
        self.assertEqual(status, 0)
        self.assertIn("3 row(s)", output)
        self.assertIn("1 batch(es)", output)

    def test_a_replay_with_export_off_is_refused_and_a_dry_run_still_counts(self):
        (self.home / ".config" / "agent-harness" / "config.json").write_text(
            json.dumps({"telemetry": {"export": "off"}}), encoding="utf-8")
        with self.assertRaises(SystemExit) as caught:
            self.export(self.home, since="2026-09-01")
        self.assertIn("telemetry.export is off", str(caught.exception))
        status, output = self.export(self.home, since="2026-09-01", dry_run=True)
        self.assertEqual(status, 0)
        self.assertIn("export is off", output)

    def test_a_malformed_date_is_refused_before_anything_is_read(self):
        self.configure("http://127.0.0.1:1")
        with self.assertRaises(SystemExit):
            self.export(self.home, since="yesterday")
        with self.assertRaises(SystemExit):
            self.export(self.home)


class TheExportStamp(Fixture):
    """`harness.exported_at` is the only thing that tells a record from its replay.

    The OTLP observed time does not survive ingest into the ClickHouse `otel_logs` table the
    doc's de-duplication example reads, and `Timestamp` is the row's own `ended`, identical
    across replays. So the stamp travels as an attribute, fixed width so that a backend holding
    attributes as strings still orders two records for one key correctly.
    """

    def test_the_stamp_is_a_fixed_width_rfc_3339_utc_string(self):
        endpoint, seen = self.serve()
        telemetry.export_rows([SESSION_ROW], config=self.config(endpoint=endpoint),
                              env={}, version=VERSION, errors_path=self.errors)
        stamp = attrs(records(seen[0])[0])["harness.exported_at"]["stringValue"]
        self.assertRegex(stamp, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$")
        self.assertEqual(len(stamp), 27)
        # UTC, and the moment of the export rather than the row's own time.
        parsed = calendar.timegm(time.strptime(stamp.split(".")[0], "%Y-%m-%dT%H:%M:%S"))
        self.assertLess(abs(parsed - time.time()), 120)
        self.assertGreater(parsed * 1000000000, int(SESSION_NANOS))

    def test_a_fixed_width_stamp_sorts_as_a_string_the_way_it_sorts_as_a_time(self):
        # A backend keeps OTLP attributes in a string map, so the ordering that matters is
        # lexical: a narrower second, a rolled-over minute and a new year must all compare right.
        seconds = [1788260400.0, 1788260400.000009, 1788260400.5, 1788260459.9,
                   1788260460.0, 1798000000.25]
        stamps = [telemetry.exported_at(s) for s in seconds]
        self.assertEqual(stamps, sorted(stamps))
        self.assertEqual(stamps[0], "2026-09-01T11:00:00.000000Z")
        self.assertEqual(stamps[1], "2026-09-01T11:00:00.000009Z")
        self.assertEqual(stamps[4], "2026-09-01T11:01:00.000000Z")

    def test_two_exports_of_one_row_differ_in_the_stamp_and_the_observed_time_alone(self):
        endpoint, seen = self.serve()
        for _ in range(2):
            telemetry.export_rows([SESSION_ROW], config=self.config(endpoint=endpoint),
                                  env={}, version=VERSION, errors_path=self.errors)
        first, second = records(seen[0])[0], records(seen[1])[0]
        self.assertEqual(dict((k, v) for k, v in first.items()
                              if k not in ("observedTimeUnixNano", "attributes")),
                         dict((k, v) for k, v in second.items()
                              if k not in ("observedTimeUnixNano", "attributes")))
        before, after = attrs(first), attrs(second)
        self.assertEqual(dict((k, v) for k, v in before.items() if k != "harness.exported_at"),
                         dict((k, v) for k, v in after.items() if k != "harness.exported_at"))
        self.assertLessEqual(before["harness.exported_at"]["stringValue"],
                             after["harness.exported_at"]["stringValue"])

    def test_the_stamp_is_the_instant_the_record_says_it_was_observed_at(self):
        record = telemetry.log_record(SESSION_ROW, now=1788260400.125)
        self.assertEqual(attrs(record)["harness.exported_at"],
                         {"stringValue": "2026-09-01T11:00:00.125000Z"})
        # The same instant the record reports as observed, to the microsecond the string keeps.
        self.assertAlmostEqual(int(record["observedTimeUnixNano"]) / 1000000000.0,
                               1788260400.125, places=6)

    def test_a_row_exported_without_a_stamp_still_gets_one(self):
        # `attributes` is reachable on its own; no record may leave without the key a reader
        # de-duplicates with.
        values = dict((a["key"], a["value"]) for a in telemetry.attributes(SUBAGENT_ROW))
        self.assertRegex(values["harness.exported_at"]["stringValue"],
                         r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$")


# The `otel_logs` columns of the OpenTelemetry ClickHouse exporter, read off a running backend.
# There is no `ObservedTimestamp`: the observed time is dropped on ingest, which is the defect
# the guard below exists to stop coming back.
OTEL_LOGS_COLUMNS = frozenset((
    "Timestamp", "TraceId", "SpanId", "TraceFlags", "SeverityText", "SeverityNumber",
    "ServiceName", "Body", "ResourceSchemaUrl", "ResourceAttributes", "ScopeSchemaUrl",
    "ScopeName", "ScopeVersion", "ScopeAttributes", "LogAttributes", "EventName"))
SQL_WORDS = frozenset((
    "select", "from", "where", "and", "or", "not", "as", "group", "by", "order", "having",
    "limit", "interval", "second", "minute", "hour", "day", "week", "month", "year", "null",
    "is", "in", "on", "join", "left", "asc", "desc", "distinct", "case", "when", "then",
    "else", "end", "otel_logs"))


def doc_sql(heading):
    """The fenced `sql` blocks under one `##` heading of docs/telemetry.md."""
    text = (REPO / "docs" / "telemetry.md").read_text(encoding="utf-8")
    section = text.split("\n## " + heading + "\n", 1)[1].split("\n## ", 1)[0]
    return re.findall(r"```sql\n(.*?)```", section, re.S)


def unknown_columns(sql, columns=OTEL_LOGS_COLUMNS):
    """Bare identifiers in `sql` that are neither a column, a keyword, an alias nor a function.

    Deliberately crude — this is a spelling check against a schema, not a parser. String
    literals are blanked first, a name followed by `(` is a function, and a name introduced by
    `AS` is an alias of the query's own making.
    """
    text = re.sub(r"'[^']*'", "''", sql)
    aliases = set(m.lower() for m in re.findall(r"\bAS\s+([A-Za-z_]\w*)", text))
    found = []
    for name in re.findall(r"\b([A-Za-z_]\w*)\b(?!\s*\()", text):
        if name in columns or name.lower() in SQL_WORDS or name.lower() in aliases:
            continue
        found.append(name)
    return sorted(set(found))


class TheDeduplicationExample(unittest.TestCase):
    """The documented query has to run as written against the standard `otel_logs` table."""

    heading = "De-duplicating an at-least-once stream"

    def test_the_example_names_no_column_the_otel_logs_table_does_not_have(self):
        blocks = doc_sql(self.heading)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(unknown_columns(blocks[0]), [])

    def test_the_guard_bites_on_the_column_that_was_wrong(self):
        # Prove the check can fail: the query as it read before, and a misspelt real column.
        self.assertEqual(unknown_columns(
            "SELECT argMax(Body, ObservedTimestamp) AS row FROM otel_logs"),
            ["ObservedTimestamp"])
        self.assertEqual(unknown_columns("SELECT body FROM otel_logs"), ["body"])

    def test_the_example_orders_on_the_export_stamp_and_reads_dollars_as_a_number(self):
        sql = doc_sql(self.heading)[0]
        self.assertNotIn("ObservedTimestamp", sql)
        self.assertEqual(sql.count("argMax("), 2)
        self.assertIn("LogAttributes['harness.exported_at']", sql)
        # `LogAttributes` is a Map(String, String), so the dollars are text until they are cast.
        self.assertIn("toFloat64OrNull(LogAttributes['harness.usd'])", sql)
        # A session's dollars already hold its Claude Code subagents': never sum both.
        self.assertIn("LogAttributes['kind'] = 'subagent'", sql)
        self.assertIn("LogAttributes['runtime'] != 'codex'", sql)


if __name__ == "__main__":
    unittest.main()
