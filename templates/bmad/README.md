# BMad override templates

Files of your own in the [BMad Method](https://github.com/bmad-code-org/BMAD-METHOD)'s
override format (`_bmad/custom/<skill>.user.toml`), routing the framework's subagent spawns
through the harness's agent definitions so the `delegation` stance reaches them. Nothing here
is a copy of a framework file.

    bin/harness bmad check <repo>   # every key and layer id against the installed skills
    bin/harness bmad apply <repo>   # install what is missing; --force replaces a differing one

The `harness-session` hook runs `check` when a session starts. Installation is explicit:
run `citizen bmad apply` to add compatible templates while preserving differing overrides.
A template the installed skill no longer declares is skipped, never written. See
[BMad integration](../../docs/bmad.md) for the installation and compatibility procedures.
