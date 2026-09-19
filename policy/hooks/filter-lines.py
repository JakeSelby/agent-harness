#!/usr/bin/env python3
"""Reads a test, build or log run on stdin and prints only the lines that carry
information: failures, tracebacks and what follows them, summary lines, and the
tail of the run.

Invoked by `filter-output.py`, which rewrites a matching Bash command to pipe
through it. Always exits 0, so the `pipefail` pipeline reports the status of the
command being filtered.
"""
import re
import sys

KEEP = re.compile(
    r"FAILED|FAIL:|ERROR|error\[|error:|panicked|Traceback|AssertionError|assert |✗|✘|not ok|warning: unused"
)
CONTEXT_AFTER = re.compile(r"Traceback|panicked")
SUMMARY = [
    re.compile(r"^=+ .* =+$"),
    re.compile(r"^Ran \d+ tests"),
    re.compile(r"^test result:"),
    re.compile(r"^Tests:"),
    re.compile(r"^ok\b|^FAILED\b"),
]
COUNTED = re.compile(r"passed|failed")
DIGIT = re.compile(r"\d")

CONTEXT_LINES = 3
TAIL_LINES = 20
MIN_KEPT = 5
CAP = 200


def is_summary(line):
    if any(p.search(line) for p in SUMMARY):
        return True
    return bool(COUNTED.search(line) and DIGIT.search(line))


def select(lines):
    keep = set()
    for i, line in enumerate(lines):
        if KEEP.search(line) or is_summary(line):
            keep.add(i)
        if CONTEXT_AFTER.search(line):
            keep.update(range(i + 1, min(i + 1 + CONTEXT_LINES, len(lines))))
    keep.update(range(max(0, len(lines) - TAIL_LINES), len(lines)))
    return [lines[i] for i in sorted(keep)]


def filter_text(text):
    lines = text.splitlines()
    kept = select(lines)
    if len(kept) < MIN_KEPT:
        kept = lines
    if len(kept) > CAP:
        half = CAP // 2
        kept = kept[:half] + ["[filter-lines: %d lines omitted]" % (len(kept) - CAP)] + kept[-half:]
    return "\n".join(kept)


def main():
    try:
        try:
            sys.stdin.reconfigure(errors="replace")
        except Exception:
            pass
        out = filter_text(sys.stdin.read())
        if out:
            sys.stdout.write(out + "\n")
    except Exception:
        return


if __name__ == "__main__":
    main()
