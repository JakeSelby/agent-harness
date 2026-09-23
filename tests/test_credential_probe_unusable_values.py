# SPDX-License-Identifier: MIT
"""A credential variable holding something that is not a path is answered, never raised over.

A pointer variable is routinely given the credential itself instead of a path to it — a service
account document pasted into `GOOGLE_APPLICATION_CREDENTIALS` is the common one. Asking the
filesystem about such a value raises, and the error carries the value into its own message and
out to whatever prints it. The probe treats an unusable value as a file that is not there and
names only the variable.
"""
import io
import os
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

from harness_core import credentials

# Not a credential: the shape is assembled here so the fixture is not itself a secret-shaped
# literal in source, as it is in test_rule_detectors.py.
MARKER = "-----BEGIN " + "PRIVATE KEY-----"
PASTED_DOCUMENT = '{"type": "service_account", "private_key": "%s"}' % MARKER
TOO_LONG_FOR_A_FILENAME = "x" * 5000


class UnusableValueTests(unittest.TestCase):
    def test_a_value_too_long_to_be_a_filename_is_absent_rather_than_an_error(self):
        self.assertFalse(credentials.points_at_a_file(TOO_LONG_FOR_A_FILENAME))

    def test_a_pasted_document_is_reported_by_variable_name_and_never_by_value(self):
        for name, value in (("GOOGLE_APPLICATION_CREDENTIALS", PASTED_DOCUMENT),
                            ("AWS_SHARED_CREDENTIALS_FILE", TOO_LONG_FOR_A_FILENAME)):
            with self.assertRaises(credentials.Unreachable) as caught:
                credentials.reachable({name: value}, Path(os.devnull).parent)
            message = str(caught.exception)
            self.assertIn(name, message)
            self.assertNotIn(value, message)
            self.assertNotIn(value[:40], message)

    def test_an_unusable_home_leaves_the_session_login_answer_empty(self):
        self.assertEqual(credentials.session_logins(TOO_LONG_FOR_A_FILENAME), [])

    def test_the_command_reports_the_reason_without_the_value(self):
        buffer = io.StringIO()
        with patch.dict(os.environ, {"GOOGLE_APPLICATION_CREDENTIALS": PASTED_DOCUMENT},
                        clear=True):
            with redirect_stderr(buffer):
                self.assertEqual(credentials.main(), 1)
        self.assertIn("GOOGLE_APPLICATION_CREDENTIALS", buffer.getvalue())
        self.assertNotIn(MARKER, buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
