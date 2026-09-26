# SPDX-License-Identifier: MIT
"""The `hook-composition` case ties both hooks to one write and survives odd transcript lines.

The user hook's log names a file, not the call that wrote it, while the harness notice is read by
call id, so a turn that wrote a patch file twice cannot show both hooks fired on the same write.
A transcript line that decodes to something other than an object must not end the read before a
later record carries the notice. No test here launches a client.
"""
import json
import unittest

from test_native_acceptance import MODULE
from test_native_acceptance_hook_composition import SESSION, harness_notice

ALPHA, BETA = MODULE.PATCH_FILES
WRITTEN = {ALPHA: True, BETA: True}


def heard(name):
    return {"session_id": SESSION, "event": "PostToolUse", "tool": "Write", "file": "/p/" + name}


class RepeatedWriteTests(unittest.TestCase):

    def test_one_write_per_file_is_read(self):
        calls = [{"id": "a", "tool": "Write", "file": "/p/" + ALPHA},
                 {"id": "b", "tool": "Write", "file": "/p/" + BETA}]
        self.assertEqual(MODULE.patch_verdict(MODULE.PATCH_FILES, WRITTEN, calls,
                                              [heard(ALPHA), heard(BETA)], SESSION),
                         [ALPHA, BETA])

    def test_a_second_write_to_the_flagged_file_is_unverified(self):
        calls = [{"id": "a", "tool": "Write", "file": "/p/" + ALPHA},
                 {"id": "b1", "tool": "Write", "file": "/p/" + BETA},
                 {"id": "b2", "tool": "Write", "file": "/p/" + BETA}]
        with self.assertRaises(MODULE.Unverified) as caught:
            MODULE.patch_verdict(MODULE.PATCH_FILES, WRITTEN, calls,
                                 [heard(ALPHA), heard(BETA)], SESSION)
        self.assertIn("at %s more than once" % BETA, str(caught.exception))

    def test_an_edit_after_the_write_is_a_repeat_too(self):
        calls = [{"id": "a", "tool": "Write", "file": "/p/" + ALPHA},
                 {"id": "b", "tool": "Write", "file": "/p/" + BETA},
                 {"id": "c", "tool": "Edit", "file": "/p/" + BETA}]
        with self.assertRaises(MODULE.Unverified):
            MODULE.patch_verdict(MODULE.PATCH_FILES, WRITTEN, calls,
                                 [heard(ALPHA), heard(BETA)], SESSION)


class NonObjectLineTests(unittest.TestCase):

    def test_a_line_that_is_not_an_object_is_skipped_not_fatal(self):
        text = "\n".join(["[1, 2]", '"text"', "42", "null", json.dumps(harness_notice("b"))])
        self.assertEqual(len(MODULE.write_hook_records(text, {"b"})), 1)
        self.assertTrue(MODULE.harness_post_notice(text, {"b"}).startswith(MODULE.HARNESS_NOTICE))


if __name__ == "__main__":
    unittest.main()
