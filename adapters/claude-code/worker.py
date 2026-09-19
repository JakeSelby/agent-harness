"""Claude worker tools are read-only; safe mode preserves native authentication."""
import json
from pathlib import Path


def prepare(executable, work, root, workspace, read_roots, instructions, bindings, original, env):
    # Preserve login/keychain discovery, while safe/restricted modes suppress user customization.
    env["HOME"] = original.get("HOME", str(Path.home()))
    # Native macOS keychain lookup includes the user identity, independently of HOME.
    if "USER" in original:
        env["USER"] = original["USER"]
    if "CLAUDE_CONFIG_DIR" in original:
        env["CLAUDE_CONFIG_DIR"] = original["CLAUDE_CONFIG_DIR"]
    (work / "instructions.md").write_text(instructions)
    command = [executable, "-p", "--safe-mode", "--restricted", "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
               "--setting-sources", "", "--tools", "Read,Grep,Glob", "--permission-mode", "dontAsk",
               "--permission-prompts", "none", "--disable-slash-commands", "--no-chrome", "--no-session-persistence",
               "--add-dir", str(workspace), "--add-dir", str(root), "--output-format", "json",
               "--append-system-prompt-file", str(work / "instructions.md"), "--model", bindings["model"]]
    if bindings.get("effort"):
        command += ["--effort", bindings["effort"]]
    for path in read_roots:
        command += ["--add-dir", str(path)]
    return command


def result(work, run_dir):
    path = run_dir / "stdout.log"
    if path.stat().st_size > 1024 * 1024:
        raise ValueError("native result exceeds 1 MiB")
    result = json.loads(path.read_text())
    if not isinstance(result, dict) or result.get("type") != "result" or result.get("subtype") != "success" or result.get("is_error") is not False:
        raise ValueError("Claude worker did not return a successful result envelope")
    return result.get("result")
