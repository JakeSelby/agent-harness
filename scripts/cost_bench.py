#!/usr/bin/env python3
"""Measure what the harness adds to every Claude Code session, without calling a model.

A bare session loads none of the files counted here, so the total is the harness's standing
overhead against no harness. Tokens are an estimate from characters (`CHARS_PER_TOKEN`), good for
a trend between versions and not for billing; dollars come from `policy/prices.json`. Codex is not
counted: its instructions are rendered at sync time. Reading and limits: docs/benchmarks.md.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHARS_PER_TOKEN = 4.0
GROWTH_LIMIT = 0.05
STATIC = Path("benchmarks") / "static.json"
ALLOW = Path("benchmarks") / "allow.json"


def _description(path):
    """The frontmatter `description`, folded lines included; the part a session lists unasked."""
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    out, taking = [], False
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if line.startswith("description:"):
            out.append(line.split(":", 1)[1].strip())
            taking = True
        elif taking and line[:1] in (" ", "\t"):
            out.append(line.strip())
        else:
            taking = False
    return " ".join(part for part in out if part not in (">", "|", ">-", "|-"))


def _group(root, paths, text=None):
    rows = []
    for path in paths:
        body = text(path) if text else path.read_text(encoding="utf-8")
        rows.append({"path": path.relative_to(root).as_posix(), "lines": body.count("\n") + bool(body),
                     "chars": len(body)})
    return rows


def _sum(rows):
    chars = sum(row["chars"] for row in rows)
    return {"files": len(rows), "lines": sum(row["lines"] for row in rows), "chars": chars,
            "est_tokens": int(round(chars / CHARS_PER_TOKEN))}


def _variants(root, selected):
    """One file per stance dimension: the selected variant, or the longest when none is named."""
    out = []
    stances = root / "claude" / "stances"
    for folder in sorted(p for p in stances.iterdir() if p.is_dir()) if stances.is_dir() else []:
        options = sorted(folder.glob("*.md"))
        if not options:
            continue
        named = folder / (str((selected or {}).get(folder.name)) + ".md")
        out.append(named if selected is not None and named in options
                   else max(options, key=lambda p: (len(p.read_text(encoding="utf-8")), p.name)))
    return out


def measure(root=ROOT):
    """The static figure for one checkout: default selection, worst case, listings and dollars."""
    claude = root / "claude"
    example = root / "config.example.json"
    selected = json.loads(example.read_text(encoding="utf-8")).get("stances", {}) if example.is_file() else {}
    fixed = [p for p in [claude / "CLAUDE.md"] if p.is_file()]
    fixed += sorted((claude / "rules").glob("*.md")) + sorted((claude / "output-styles").glob("*.md"))
    always = _group(root, fixed + _variants(root, selected))
    worst = _group(root, fixed + _variants(root, None))
    listed = sorted((claude / "agents").glob("*.md")) + sorted((claude / "skills").glob("*/SKILL.md"))
    listed += sorted((claude / "commands").glob("*.md"))
    listings = _group(root, listed, _description)
    total = _sum(always + listings)
    version = root / "VERSION"
    return {
        "schema_version": 1,
        "harness_version": version.read_text(encoding="utf-8").strip() if version.is_file() else "",
        "chars_per_token": CHARS_PER_TOKEN,
        "always_loaded": _sum(always),
        "listings": _sum(listings),
        "total": total,
        "worst_case_est_tokens": _sum(worst + listings)["est_tokens"],
        "largest": sorted(always + listings, key=lambda r: (-r["chars"], r["path"]))[:5],
        "usd": price(root, total["est_tokens"]),
    }


def price(root, tokens):
    """USD the counted layer costs per model: written to the cache once, then read every turn."""
    table = root / "policy" / "prices.json"
    models = json.loads(table.read_text(encoding="utf-8")).get("models", {}) if table.is_file() else {}
    out = {}
    for name, row in sorted(models.items()):
        if name.startswith("claude-") and "cache_write" in row and "cache_read" in row:
            out[name] = {"session_start": round(tokens * row["cache_write"] / 1e6, 6),
                         "later_turn": round(tokens * row["cache_read"] / 1e6, 6)}
    return out


def check(root=ROOT):
    """Errors when the estimate has grown past the limit over the committed figure, unexplained."""
    committed = root / STATIC
    if not committed.is_file():
        return ["%s is missing; run `scripts/cost_bench.py static --write`" % STATIC.as_posix()]
    before = json.loads(committed.read_text(encoding="utf-8"))["total"]["est_tokens"]
    now = measure(root)
    after = now["total"]["est_tokens"]
    if after <= before * (1 + GROWTH_LIMIT):
        return []
    allow = root / ALLOW
    entries = json.loads(allow.read_text(encoding="utf-8")) if allow.is_file() else []
    if any(e.get("harness_version") == now["harness_version"] and e.get("est_tokens") == after
           and str(e.get("reason", "")).strip() for e in entries):
        return []
    return ["static context grew from %d to %d estimated tokens (+%.1f%%, limit %.0f%%); trim it, or "
            "record harness_version, est_tokens and a reason in %s"
            % (before, after, (after / before - 1) * 100 if before else 100.0, GROWTH_LIMIT * 100,
               ALLOW.as_posix())]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    static = sub.add_parser("static", help="count the always-loaded layer and the session listings")
    mode = static.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="refresh %s" % STATIC.as_posix())
    mode.add_argument("--check", action="store_true", help="fail on unexplained growth")
    args = parser.parse_args(argv)
    if args.check:
        errors = check(ROOT)
        for error in errors:
            print("cost-bench: " + error, file=sys.stderr)
        return 1 if errors else 0
    text = json.dumps(measure(ROOT), indent=2) + "\n"
    if args.write:
        (ROOT / STATIC).parent.mkdir(exist_ok=True)
        (ROOT / STATIC).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
