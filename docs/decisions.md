# Implementation decisions

Newest first. One entry per non-obvious decision.

## 2026-10-14: How proactive hints are routed and limited (G6)

**Decision.** (1) The brain looks for a local engine on every `idle` that passes the gate (a
`/v1/models` probe on loopback, 0.5 s timeout), not once at startup, so starting or stopping
llama.cpp/MTPLX needs no brain restart. (2) With `proactive_cloud` on, the local engine is still
preferred; Claude is used only when none is up. (3) The 3-minute gate counts only hints actually
started: when no engine answers, the slot is given back. (4) An explicit trigger also starts the
3-minute quiet period, because the plugin sends `idle` 4 s after the `#?` line and the hint would
replace the answer in the notch. (5) Hints get their own system prompt, no project map and a ~3k
token budget: on the local engine prefill is the latency. (6) The plugin skips an `idle` whose
window equals the last one from that document; the brain separately skips a window equal to the
last hinted one. (7) `httpx2`, already used by the tests, becomes a runtime dependency for the
local engine client. **Why.** Hints must stay rare, cheap and never in the way of an explicit answer.
**Rollback.** Each is a line in `brain/src/buddy/server.py` or `hints.py`, or `Idle.kt`.

## 2026-10-14: Brain details chosen while building G2

**Decision.** (1) The JSON Schemas in `protocol/` are the source of truth, and the brain validates
every incoming message against them at runtime (tests validate every outgoing one). There are no
hand-written pydantic copies. (2) `answer_end` reports `first_token_ms` and `total_ms` (instead of a single
`latency_ms`), because criterion 1 is about the first token. (3) `claude -p` runs from an empty temp
directory with the prompt on stdin. (4) `httpx2` instead of `httpx` for tests (Starlette deprecates
`httpx`). **Why.** One schema avoids drift between three languages; stdin keeps code out of `ps`
and ARG_MAX; an empty directory means no CLAUDE.md is loaded. **Rollback.** Each one is local to
`brain/`.

## 2026-10-14: Proactive suggestions stay local by default

**Decision.** `idle`, bug, function-completed and save events go only to the local engine. A
`proactive_cloud` setting (default `false`) can send them to Claude. With no local engine running,
there is no proactive hint at all: no silent fallback to the cloud. **Why.** It keeps the
subscription quota for explicit questions, and code only leaves the machine when the user asks.
**Alternatives.** Making it a golden rule. The user didn't pick it as one, so it stays a setting.
**Rollback.** Flip the default.

## 2026-10-14: Claude through the user's subscription via the `claude` CLI

**Decision.** The brain runs `claude -p … --output-format stream-json` with no tools, no settings
and no MCP. **Why.** The user wants to use their subscription, not pay for an API key. Measured
latency is fine: first token 1.8–2.2 s, total 2.5–2.9 s (Sonnet 5.5, 3 runs, 2026-10-14). **Alternatives.**
`--bare` (rejected: it only reads `ANTHROPIC_API_KEY`); the Anthropic SDK with an API key (kept as a
drop-in behind `CloudModel`). **Limits.** Personal use only. If CodeBuddy is distributed, switch to
API keys. **Rollback.** Implement `ApiKeyClaudeModel` and switch the config.

## 2026-10-14: Brain as a separate Python daemon

**Decision.** All AI logic lives in `brain/` (Python). The plugin and the notch are thin clients
over WebSocket. **Why.** The user is learning AI engineering, which is mostly Python. It can be
tested without UI and reused for VS Code. **Alternatives.** Logic inside the Swift app (rejected:
harder to test, and the AI part would be written in Swift). **Rollback.** Not cheap. The protocol
boundary is what keeps it possible.

## 2026-10-14: Selective extraction from Coucou, not a full fork

**Decision.** Copy only the notch panel, geometry, state machine and markdown view from
Louis-CFM/coucou (MIT). **Why.** Coucou is about 55k lines of Swift, mostly features we don't want.
Its name, Mochi, icons and sounds are all rights reserved. **Alternatives.** A full fork (rejected:
far too much to strip); writing it from scratch (slower). **Rollback.** n/a.

## 2026-10-14: Triggers as `#?` and `#!<command>`

**Decision.** `#? <question>`, `#!teoria <topic>`, `#!alt`, `#!review`, detected on Enter. Trigger
lines stay in the file. The "clear triggers" action removes them. **Why.** The sigil avoids firing
on normal comments such as `# teoria …`. **Rollback.** Change the parser in the plugin.
