# SPDX-License-Identifier: MIT
"""Whether a client launched under a prepared environment could authenticate at all.

A native probe launches its client under a disposable `HOME`, so only credentials named in the
environment travel with it. A machine or container whose only login is an interactive session —
`claude login` writing `.claude/.credentials.json`, `codex login` writing `.codex/auth.json`,
both under the operator's real home — hands the client nothing, and the client waits on a login
it will never be given until the turn timeout fires. The recorded cost of that is a 300-second
hang reported as a timeout rather than as the authentication failure it is.

`reachable` answers the same question in stat calls: no subprocess, no network, no value read or
logged. It is one check of the deterministic smoke tier, which is additive — it writes nothing
under `compatibility/evidence/`, appears in no catalog record, and a green run is never native
client qualification.
"""
import os
import sys
from pathlib import Path

# A key or token the client reads directly. Presence is the whole test; the value is never read.
API_KEY_VARS = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "OPENAI_API_KEY")
# Pointers to a credential file. Each must name a path that exists, or the lookup behind it hangs.
FILE_POINTER_VARS = ("AWS_SHARED_CREDENTIALS_FILE", "AWS_CONFIG_FILE",
                     "GOOGLE_APPLICATION_CREDENTIALS")
# An interactive login, which stays in the home that performed it and never reaches a disposable one.
SESSION_LOGIN_FILES = (Path(".claude") / ".credentials.json", Path(".codex") / "auth.json")


class Unreachable(Exception):
    """No credential the client could use is reachable from the prepared environment."""


def session_logins(home):
    """The interactive-login files present in `home`, which a substituted `HOME` leaves behind."""
    return [str(name) for name in SESSION_LOGIN_FILES if (Path(home) / name).exists()]


def reachable(env, home=None):
    """Name the credential a client launched under `env` would use, or raise `Unreachable`.

    `home` is the real home the environment was built from, used only to say why nothing travelled.
    """
    for name in FILE_POINTER_VARS:
        value = env.get(name)
        if value and not Path(value).exists():
            raise Unreachable("%s names a file that does not exist; unset it or point it at a "
                              "real credential file" % name)
    for name in API_KEY_VARS:
        if env.get(name):
            return name
    if env.get("AWS_PROFILE"):
        if any(env.get(name) for name in ("AWS_SHARED_CREDENTIALS_FILE", "AWS_CONFIG_FILE")):
            return "AWS_PROFILE"
        raise Unreachable("AWS_PROFILE is set but neither AWS_SHARED_CREDENTIALS_FILE nor "
                          "AWS_CONFIG_FILE points into the home the profile lives in")
    if env.get("GOOGLE_APPLICATION_CREDENTIALS"):
        return "GOOGLE_APPLICATION_CREDENTIALS"
    held = session_logins(home if home is not None else os.path.expanduser("~"))
    if held:
        raise Unreachable("this home holds only an interactive session login (%s), which does not "
                          "travel into the disposable home the probe launches under; export an API "
                          "key or a cloud profile instead" % ", ".join(held))
    raise Unreachable("no API key, cloud profile or session login is reachable; the client would "
                      "wait on a login prompt until the turn timeout")


def main():
    """Report the credential a probe run would use. Exit 1 with the reason when there is none."""
    try:
        print("credentials: %s" % reachable(dict(os.environ)))
    except Unreachable as error:
        print("credentials: unreachable: %s" % error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
