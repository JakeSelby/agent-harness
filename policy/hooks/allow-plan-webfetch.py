#!/usr/bin/env python3
"""PreToolUse hook: approve WebFetch while in plan mode, so gathering context for a
plan does not prompt for every documentation or reference URL.

Scope is deliberately narrow: only when `permission_mode` is `plan`, and only for
`http`/`https` URLs. Every other mode keeps its normal permission flow, so this
changes nothing outside planning. This hook never denies.

Why this is safe enough to allow: plan mode already blocks edits, so the fetch
cannot change anything, and the `neutralize-tool-output` hook still scans the
fetched text for instruction-shaped content before it reaches the model. It does
not make fetched pages trusted; it removes the prompt for read-only research.

Test: echo '{"tool_name":"WebFetch","permission_mode":"plan","tool_input":{"url":"https://example.com"}}' | python3 allow-plan-webfetch.py
"""
import json
import sys


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    if payload.get("tool_name") != "WebFetch":
        return
    if payload.get("permission_mode") != "plan":
        return
    url = (payload.get("tool_input") or {}).get("url")
    if not isinstance(url, str):
        return
    if not (url.startswith("https://") or url.startswith("http://")):
        return
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": "plan-mode web research (allow-plan-webfetch hook)",
        }
    }))


if __name__ == "__main__":
    main()
