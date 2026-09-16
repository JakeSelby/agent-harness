# Secret hygiene

**Never put tokens, passwords, API keys, or secrets in any file that is committed to source
control.** That includes agent rule files, documentation, source, config, comments, docstrings,
commit messages, story files and planning artifacts. Editor rule directories are the case this
rule exists for: they feel private and are not.

## Read from the environment, never inline

```bash
# Correct
curl -H "Authorization: token $SERVICE_TOKEN" ...

# Wrong — never do this
curl -H "Authorization: token abc123def456" ...
```

Cloud CLIs resolve credentials from a profile or a secret store; use `--profile` or an
environment variable, never a pasted key.

## If you discover a secret in source control

1. **Stop.** Do not commit anything on top of it.
2. **Tell the user immediately.** The credential must be rotated before anything else happens;
   removing it from the file does not un-leak it, and history keeps it.
3. Remove it from the file, then the user rotates the credential, then history is rewritten if
   the repo's exposure warrants it.

## .gitignore before the file

If you need a new secret-bearing file, add it to `.gitignore` **before** creating it. A file
that is already tracked stays tracked when its directory is later ignored; check with
`git ls-files` before assuming an ignore rule protects it. Never `git add` a file that contains
credentials.
