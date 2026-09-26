# SPDX-License-Identifier: MIT
"""A pipeline after a literal `cd` is governed in that `cd`'s directory.

A pipeline binds tighter than `&&`, `||` and `;`, so `cd <dir> && git push 2>&1 | tail -1` pushes
from `<dir>`. Only a `cd` inside a pipeline element, a subshell or a background job is confined,
and the walk then leaves the directory unknown rather than trusting the literal.

Run: python3 -m unittest discover tests
"""
import unittest

from test_governance_binding import Home, grader, make_repo


class PipelineAfterCd(Home):

    def setUp(self):
        super().setUp()
        self.configure("local")
        self.other = make_repo(self.home / "other")
        self.user_policy({"defaults": {"coding.git_push": 2},
                          "pairs": {"repo:alpha": {"coding.git_push": 3},
                                    "repo:other": {"coding.git_push": 3}}})

    def pushes(self, command):
        return [entry[2] for entry in grader.governed_text(command, str(self.repo))
                if entry[0] == "coding.git_push"]

    def test_regression_a_piped_push_after_a_literal_cd_resolves_to_that_repository(self):
        for command in ("cd %s && git push origin HEAD 2>&1 | tail -1",
                        "cd %s; git push origin HEAD |& cat",
                        "cd %s\ngit push | tail -1",
                        'cd %s && git commit -m "a | b" && git push | cat'):
            command = command % self.other
            self.assertEqual(self.pushes(command), [str(self.other)], command)
            self.assertEqual(self.bash(command, mode="auto"), (None, ""), command)

    def test_every_element_of_the_pipeline_starts_in_that_directory(self):
        found = grader.governed_text("cd %s && git push 2>&1 | tail -1" % self.other,
                                     str(self.repo))
        self.assertEqual([entry[2] for entry in found], [str(self.other)] * 2)

    def test_a_cd_inside_a_pipeline_element_does_not_carry_over(self):
        for command in ("cd %s | cat && git push", "cd %s |& cat; git push",
                        "cat | cd %s && git push", "{ cd %s; } | cat; git push"):
            command = command % self.other
            self.assertEqual(self.pushes(command), [None], command)
            answer, reason = self.bash(command)
            self.assertEqual(answer, "ask", command)
            self.assertIn("repo:unknown/local", reason, command)

    def test_a_cd_in_a_subshell_or_background_job_does_not_carry_over(self):
        for command in ("(cd %s) && git push", "(cd %s && true) | cat; git push",
                        "cd %s & git push", "cd %s & git push | cat"):
            self.assertEqual(self.pushes(command % self.other), [None], command)

    def test_a_pipeline_after_an_unknown_directory_stays_unknown(self):
        for command in ("cd - && git push | tail -1", 'cd "$D" && git push | tail -1',
                        "popd && git push | tail -1", "cd $(pwd) && git push | cat",
                        "cd %s && env -C %s git push | cat" % (self.other, self.other),
                        "cd %s && git --git-dir=x/.git push | cat" % self.other):
            self.assertEqual(self.pushes(command), [None], command)

    def test_a_literal_pushd_before_a_pipeline_resolves(self):
        self.assertEqual(self.pushes("pushd %s && git push | cat" % self.other),
                         [str(self.other)])

    def test_a_substitution_after_a_cd_in_a_pipeline_takes_its_segment_directory(self):
        command = 'cd %s && echo "$(git push)" | cat' % self.other
        self.assertEqual(self.pushes(command), [str(self.other)])

    def test_a_cd_in_a_compound_keeps_the_line_wide_rule(self):
        self.assertEqual(self.pushes("if true; then cd %s; fi && git push | cat" % self.other),
                         [None])
        self.assertEqual(self.pushes("{ cd %s; }; git push" % self.other), [str(self.other)])

    def test_a_quoted_operator_is_not_read_as_structure(self):
        self.assertEqual(self.pushes('cd %s "&&" | cat; git push' % self.other), [None])
        self.assertEqual(self.pushes('echo "|"; cd %s && git push | cat' % self.other),
                         [str(self.other)])


if __name__ == "__main__":
    unittest.main()
