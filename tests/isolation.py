# SPDX-License-Identifier: MIT
"""Environment isolation shared by the tests that run `bin/harness`.

`claude_dir()` prefers `CLAUDE_CONFIG_DIR` over the home a test controls, which is the right
runtime precedence: it is how a profile other than `~/.claude` is synced. It also means a value
inherited from the caller's shell silently overrides a temporary `HOME`, so a sync test writes
the harness into a real profile instead of its own fixture. The suite therefore drops the
variable everywhere it builds an environment, and importing this module drops it from the test
process once, before any test runs.
"""
import os

CONFIG_DIR = "CLAUDE_CONFIG_DIR"


def drop_inherited_config_dir():
    """Remove an inherited config dir from this process. Returns the value that was dropped."""
    return os.environ.pop(CONFIG_DIR, None)


def without_config_dir(env=None):
    """A mutable copy of `env` (default `os.environ`) with an inherited config dir removed."""
    clean = dict(os.environ if env is None else env)
    clean.pop(CONFIG_DIR, None)
    return clean


def isolate_home(home, quiet=True):
    """Point `os.environ` at a temporary home: `HOME` set, `HARNESS_*` and the config dir gone.

    Callers save and restore `os.environ` themselves; this only applies the isolation.
    """
    os.environ["HOME"] = str(home)
    for key in list(os.environ):
        if key.startswith("HARNESS_"):
            del os.environ[key]
    drop_inherited_config_dir()
    if quiet:
        os.environ["HARNESS_QUIET"] = "1"


def without_harness_vars(env=None):
    """`without_config_dir`, with the `HARNESS_*` variables dropped as well.

    The base for a subprocess a test drives, so neither the config dir nor a stance set in the
    developer's shell reaches it. The caller adds the home and whatever else it means to set.
    """
    clean = without_config_dir(env)
    for key in [name for name in clean if name.startswith("HARNESS_")]:
        del clean[key]
    return clean


drop_inherited_config_dir()
