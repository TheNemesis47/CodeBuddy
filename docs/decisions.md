# Implementation decisions

Newest first. One entry per non-obvious decision.

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
