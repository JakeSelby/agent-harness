# SPDX-License-Identifier: MIT
"""Whether this host can start each qualification target it is asked about, answered before a round.

A target runs either here, when its platform is this host's, or in the Linux container the
qualification runbook builds, when it is a Linux target and this host is not Linux. What must
exist differs by case, and each missing piece otherwise surfaces part-way through a paid round:

- a target that runs here needs its client on `PATH`, and a credential the client can use — for
  Codex a ChatGPT session login in its configuration home or `OPENAI_API_KEY`, for Claude Code the
  answer `credentials.reachable` gives;
- a Linux target on a host that is not Linux needs `docker` on `PATH` and a daemon that answers;
  its client and login are checked by this same probe run inside the container;
- a macOS target cannot run anywhere but a Mac.

No value is read or printed. The Docker question is the only subprocess, bounded by a timeout, and
it is asked once however many targets need it. The provisioning contract these checks follow is
in docs/compatibility.md and the commands are in docs/qualification-runbook.md.
"""
import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from harness_core import credentials

RUNTIMES = {"claude-code-": ("claude-code", "claude"), "codex-": ("codex", "codex")}
PLATFORMS = {"Darwin": "macos", "Linux": "linux"}
CODEX_LOGIN = "auth.json"
DOCKER_TIMEOUT = 15


class Unready(Exception):
    """A target this host was asked to run cannot start here."""


def describe(target):
    """``(runtime, command, platform)`` for a target id such as ``codex-cli-linux``."""
    for prefix, (runtime, command) in RUNTIMES.items():
        if target.startswith(prefix):
            platform_name = target.rsplit("-", 1)[-1]
            if platform_name in PLATFORMS.values():
                return runtime, command, platform_name
    raise Unready("%s is not a target this probe knows how to check" % target)


def codex_login(env, home):
    """Raise `Unready` unless a Codex client launched from `env` has a login to use."""
    if env.get("OPENAI_API_KEY"):
        return
    folder = env.get("CODEX_HOME") or str(Path(home) / ".codex")
    if credentials.points_at_a_file(Path(folder) / CODEX_LOGIN):
        return
    raise Unready("no Codex login: neither a ChatGPT session login in the Codex home nor "
                  "OPENAI_API_KEY; run `codex login` before the round")


def docker_daemon(which=shutil.which, run=subprocess.run):
    """Raise `Unready` unless a Docker daemon answers within `DOCKER_TIMEOUT` seconds."""
    if not which("docker"):
        raise Unready("`docker` is not on PATH; a Linux target runs in a container on this host")
    try:
        result = run(["docker", "info", "--format", "{{.ServerVersion}}"],
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, timeout=DOCKER_TIMEOUT, check=False)
    except subprocess.TimeoutExpired:
        raise Unready("the Docker daemon did not answer within %ss" % DOCKER_TIMEOUT)
    except OSError:
        raise Unready("`docker info` could not be started")
    if result.returncode:
        raise Unready("the Docker daemon is not running; start it before the round")


def problems(targets, env, home, host, which=None, run=None):
    """Each target that cannot start on this host, with why, in the order asked."""
    which = which or shutil.which
    run = run or subprocess.run
    found = []
    daemon = None
    for target in targets:
        try:
            runtime, command, where = describe(target)
            if where != PLATFORMS.get(host):
                if where != "linux":
                    raise Unready("a %s target runs only on a %s host" % (where, where))
                if daemon is None:
                    try:
                        docker_daemon(which, run)
                        daemon = ""
                    except Unready as error:
                        daemon = str(error)
                if daemon:
                    raise Unready(daemon)
                continue
            if not which(command, path=env.get("PATH")):
                raise Unready("`%s` is not on PATH" % command)
            if runtime == "codex":
                codex_login(env, home)
            else:
                try:
                    credentials.reachable(env, home)
                except credentials.Unreachable as error:
                    raise Unready(str(error))
        except Unready as error:
            found.append((target, str(error)))
    return found


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--targets", required=True,
                        help="comma-separated target ids, for example codex-cli-linux")
    args = parser.parse_args(argv)
    targets = [name.strip() for name in args.targets.split(",") if name.strip()]
    if not targets:
        raise SystemExit("--targets names no target")
    found = problems(targets, dict(os.environ), os.path.expanduser("~"), platform.system())
    for target, reason in found:
        print("preconditions: %s: %s" % (target, reason), file=sys.stderr)
    if found:
        return 1
    print("preconditions: every target can start on this host")
    return 0


if __name__ == "__main__":
    sys.exit(main())
