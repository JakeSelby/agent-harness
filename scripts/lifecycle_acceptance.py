#!/usr/bin/env python3
"""Exercise the harness filesystem lifecycle against the immutable release baseline."""
import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VOLATILE = {".local/state/agent-harness/manifest.json"}


def command(*args, cwd=ROOT, check=True, env=None, binary=False):
    result = subprocess.run(args, cwd=str(cwd), env=env, capture_output=True,
                            text=not binary, check=False)
    if check and result.returncode:
        output = result.stderr if binary else (result.stdout + result.stderr)
        raise RuntimeError("command failed (%s): %s" % (result.returncode, output.strip()))
    return result


def baseline(root=ROOT):
    data = json.loads((root / "compatibility" / "lifecycle-baseline.json").read_text())
    archive = data.get("archive", {})
    required = (data.get("schema_version") == 1, data.get("version"), data.get("tag"),
                data.get("commit"), archive.get("format") == "git-archive-tar",
                archive.get("prefix"), archive.get("sha256"))
    if not all(required):
        raise ValueError("lifecycle baseline metadata is incomplete")
    return data


def git(root, *args):
    return command("git", "-C", str(root), *args).stdout.strip()


def archive_baseline(root, destination, data):
    commit = git(root, "rev-parse", data["tag"] + "^{commit}")
    if commit != data["commit"]:
        raise ValueError("baseline tag does not resolve to its pinned commit")
    result = command("git", "-C", str(root), "archive", "--format=tar",
                     "--prefix=" + data["archive"]["prefix"], data["tag"], binary=True)
    digest = hashlib.sha256(result.stdout).hexdigest()
    if digest != data["archive"]["sha256"]:
        raise ValueError("baseline source archive digest does not match the pin")
    destination.write_bytes(result.stdout)


def harness(checkout, home, python, *args, expected=0):
    env = dict(os.environ)
    env.update({"HOME": str(home), "HARNESS_MANAGE_VSCODE": "false",
                "PYTHONDONTWRITEBYTECODE": "1"})
    result = command(python, str(checkout / "bin" / "harness"), *args,
                     cwd=checkout, check=False, env=env)
    if result.returncode != expected:
        raise AssertionError("harness %s returned %s, expected %s:\n%s" %
                             (" ".join(args), result.returncode, expected,
                              (result.stdout + result.stderr).strip()))
    return result.stdout + result.stderr


def seed(home):
    config = home / ".config" / "agent-harness" / "config.json"
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps({
        "identity": {"name": "Lifecycle Fixture", "role": "acceptance operator"},
        "vscode": {"manage": False},
    }, indent=2) + "\n")
    claude = home / ".claude" / "settings.json"
    claude.parent.mkdir(parents=True)
    claude.write_text(json.dumps({
        "theme": "fixture",
        "permissions": {"allow": ["WebFetch(domain:example.invalid)"]},
    }, indent=2) + "\n")
    codex = home / ".codex" / "config.toml"
    codex.parent.mkdir(parents=True)
    codex.write_text('model = "fixture-model"\n[unrelated]\ntheme = "dark"\n')
    hooks = home / ".codex" / "hooks.json"
    hooks.write_text(json.dumps({"hooks": {}, "unrelated": "keep"}, indent=2) + "\n")
    (home / "user-note.txt").write_text("preserve me\n")


def snapshot(home):
    values = {}
    for path in sorted(home.rglob("*")):
        name = str(path.relative_to(home))
        if name in VOLATILE or path.is_dir():
            continue
        if path.is_symlink():
            values[name] = {"kind": "link", "target": os.readlink(path)}
        else:
            content = path.read_bytes()
            if path.suffix == ".json":
                canonical = json.dumps(json.loads(content), sort_keys=True, separators=(",", ":"))
                content = canonical.encode()
            elif name == ".zprofile":
                content = ("\n".join(line for line in path.read_text().splitlines() if line.strip()) + "\n").encode()
            values[name] = {"kind": "file", "sha256": hashlib.sha256(content).hexdigest()}
    return values


def assert_preserved(home):
    if (home / "user-note.txt").read_text() != "preserve me\n":
        raise AssertionError("unrelated user file changed")
    claude = json.loads((home / ".claude" / "settings.json").read_text())
    allowed = claude.get("permissions", {}).get("allow", [])
    if claude.get("theme") != "fixture" or "WebFetch(domain:example.invalid)" not in allowed:
        raise AssertionError("unrelated Claude configuration changed")
    codex = (home / ".codex" / "config.toml").read_text()
    if 'model = "fixture-model"' not in codex or 'theme = "dark"' not in codex:
        raise AssertionError("unrelated Codex configuration changed")
    hooks = json.loads((home / ".codex" / "hooks.json").read_text())
    if hooks.get("unrelated") != "keep":
        raise AssertionError("unrelated Codex hooks configuration changed")


def clean_install(checkout, python, home):
    seed(home)
    harness(checkout, home, python, "sync")
    harness(checkout, home, python, "diff", "--quiet")
    first = snapshot(home)
    harness(checkout, home, python, "sync")
    if first != snapshot(home):
        raise AssertionError("second sync changed effective installed state")
    harness(checkout, home, python, "uninstall")
    assert_preserved(home)


def upgrade_and_rollback(baseline_checkout, candidate, python, home):
    seed(home)
    harness(baseline_checkout, home, python, "sync")
    baseline_state = snapshot(home)
    harness(candidate, home, python, "sync")
    harness(candidate, home, python, "sync")
    harness(candidate, home, python, "diff", "--quiet")
    harness(candidate, home, python, "uninstall")
    harness(baseline_checkout, home, python, "sync")
    if baseline_state != snapshot(home):
        raise AssertionError("rollback did not restore the baseline effective state")
    harness(baseline_checkout, home, python, "uninstall")
    assert_preserved(home)


def conflict_preservation(checkout, python, home):
    seed(home)
    harness(checkout, home, python, "sync")
    target = home / ".codex" / "AGENTS.md"
    target.write_text("user edit\n")
    output = harness(checkout, home, python, "sync", expected=2)
    if str(target) not in output or "generated content changed" not in output:
        raise AssertionError("conflict diagnostic did not identify its path and source")
    output = harness(checkout, home, python, "uninstall", expected=2)
    if str(target) not in output or target.read_text() != "user edit\n":
        raise AssertionError("uninstall did not preserve and report the user conflict")
    assert_preserved(home)


def run(root=ROOT, python=sys.executable):
    if git(root, "status", "--porcelain"):
        raise ValueError("candidate checkout must be clean")
    candidate_commit = git(root, "rev-parse", "HEAD")
    data = baseline(root)
    with tempfile.TemporaryDirectory() as temp:
        work = Path(temp)
        archive = work / "baseline.tar"
        archive_baseline(root, archive, data)
        with tarfile.open(archive) as stream:
            # This archive was produced locally from the pinned Git object and verified above.
            stream.extractall(work / "baseline")
        prior = work / "baseline" / data["archive"]["prefix"].rstrip("/")
        cases = []
        operations = (
            ("clean-install-idempotent-uninstall", lambda home: clean_install(root, python, home)),
            ("upgrade-rollback-uninstall",
             lambda home: upgrade_and_rollback(prior, root, python, home)),
            ("conflict-preservation", lambda home: conflict_preservation(root, python, home)),
        )
        for name, operation in operations:
            home = work / ("home-" + name)
            home.mkdir()
            operation(home)
            cases.append({"name": name, "status": "passed"})
    return {
        "schema_version": 1,
        "candidate_commit": candidate_commit,
        "baseline": {"version": data["version"], "commit": data["commit"],
                     "archive_sha256": data["archive"]["sha256"]},
        "environment": {"platform": platform.system().lower(),
                        "machine": platform.machine().lower(),
                        "python": platform.python_version()},
        "cases": cases,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rendered = json.dumps(run(), indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered)
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
