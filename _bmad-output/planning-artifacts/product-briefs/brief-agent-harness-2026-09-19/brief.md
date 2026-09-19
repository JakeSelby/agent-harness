---
title: Agent Harness product brief
status: final
created: 2026-09-19
updated: 2026-09-19
sources:
  - ../../source-ledger.md
---

# Agent Harness

## Product idea

Developers increasingly use more than one coding agent, but each runtime expects a different mix of
instructions, skills, hooks, roles and settings. Agent Harness lets a developer define working
preferences once, then projects that shared authority into Claude Code and Codex without pretending
the runtimes have identical capabilities.

The product is a local, inspectable tool—not an API gateway, hosted agent or model provider. Native
runtimes keep control of model access, permissions and client behavior.

## Who it serves

The initial user already customizes Claude Code, Codex or both. They care about repeatable behavior,
want useful defaults they can replace, and will inspect a dry run before allowing a tool to manage
their configuration. Contributors need the same policies and evidence to remain understandable
without access to the maintainer's private planning context.

## Value

- One shared primitive catalog instead of parallel runtime-specific working agreements.
- Switchable stances for autonomy, delegation, testing, cost, communication and maintenance.
- Safe preview, ownership, conflict and uninstall behavior for user-controlled configuration.
- Honest compatibility claims tied to native evidence rather than generated files alone.
- Public product reasoning linked to the GitHub delivery record.

## Product principles

1. **Useful defaults, replaceable choices.** Preferences are explicit switches; truth, secret
   protection, authorization and native restrictions are invariants.
2. **Preview before ownership.** The tool shows what it will manage and preserves unrelated data.
3. **One authority, thin adapters.** Runtime projections translate shared meaning rather than fork it.
4. **Evidence before support claims.** Unknown or failed native behavior stays visible.
5. **Public reasoning without surveillance.** Decisions and plans are public; raw conversations and
   private machine data are not.

## Current position

The 0.9 release series is experimental. Codex CLI has recorded macOS and Linux evidence;
the intended v1 floor also requires Claude Code CLI on both platforms. VS Code and Codex desktop are
preview surfaces and do not block v1. Cursor, Grok, hosted agents, native memory merging and the UML
viewer remain outside the stable floor.

## Success

Release success means a new developer can understand the value, run a safe preview, reproduce the
supported installation lifecycle and distinguish stable from preview surfaces. Adoption success is
measured by usable attempts, repeat use and actionable friction reports—not stars or clone counts
alone.
