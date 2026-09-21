"""The default keychain of a home other than the operator's, on macOS.

macOS resolves the default keychain under `HOME`. A native client launched in a home without one
raises a system dialog — "A keychain cannot be found" — whose default button resets the operator's
keychain settings. Every place that launches a client under a substituted `HOME` goes through this
module: `provision` before a launch it intends, `missing` before one it can skip.
"""
import os
import platform
import subprocess
from pathlib import Path


def default_path(home):
    return Path(home) / "Library" / "Keychains" / "login.keychain-db"


def missing(home=None, host=None):
    """Whether a client launched under `home` would find no default keychain. False off macOS."""
    if (host or platform.system()) != "Darwin":
        return False
    return not default_path(home or os.environ.get("HOME") or Path.home()).exists()


def provision(home, host=None):
    """Give `home` its own throwaway default keychain; a no-op off macOS or when one exists.

    The keychain has an empty password and no lock timeout, so a store succeeds silently and never
    touches the operator's login keychain. Raises `OSError` when it cannot be created.
    """
    if not missing(home, host):
        return None
    path = default_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, HOME=str(home))
    created = subprocess.run(["security", "create-keychain", "-p", "", str(path)],
                             capture_output=True, text=True, env=env)
    if created.returncode:
        raise OSError("no keychain for the substituted home, so a client launch would raise a "
                      "system dialog: " + (created.stderr or "").strip()[-200:])
    subprocess.run(["security", "set-keychain-settings", str(path)],
                   capture_output=True, text=True, env=env)
    return path
