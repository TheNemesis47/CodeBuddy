# Spec: CodeBuddy MVP (the thin end-to-end path)

Status: **draft, waiting for approval** · 2026-10-14 · module map: [CAPABILITY-MAP.md](CAPABILITY-MAP.md)

## Objective

I know the basics of programming and I want to grow into an **AI engineer**. CodeBuddy helps in
two ways:

1. **Using it** teaches me to code: while I write in PyCharm, a buddy in the notch explains,
   suggests how to continue and answers questions about the code in front of me, without me
   leaving the editor.
2. **Building it** teaches me AI engineering: model routing (local vs cloud), context building,
   prompt caching, streaming, evals, latency and cost budgets.

It is **not** an autocomplete. It never edits my code. It talks; I write.

### MVP user stories

- **US1, question.** I type `#? why doesn't this close the file?` on its own line and press
  Enter. Within seconds Sprout peeks out of the notch and the answer streams in the expanded panel,
  about the code around that line.
- **US2, theory.** I type `#!teoria context manager`. I get an explanation of the concept tied to
  my code: what it is, why it exists, how it really works underneath, the math when there is some,
  a minimal example, and what to read next (made deep at the user's request, 2026-10-16).
  `#!approfondisci [focus]` goes one level further on the last theory.
- **US3, proactive.** I stop typing for a few seconds. Sprout, using the model in the settings
  (until 2026-10-16: the **local** model), peeks out with **one** short hint on how to continue. It shows at most one hint every N minutes, and only if
  the code changed since the last one.
- **US4, demo.** I can run the notch app with no IDE and no model and see every state (hidden,
  peek, expanded with a streamed answer). I use this to work on the UI.

Out of the MVP (next slices, already decided): `#!alt`, `#!review`, triggers on bug, function
completed and save, the priority queue, the study/work toggle, the `growth` module, RAG, VS Code.

## Architecture

```
PyCharm plugin ──ws──▶ brain (Python daemon, 127.0.0.1:8790) ──ws──▶ notch app (Swift)
                         ├── local:  llama.cpp :8080 / MTPLX :8000  (Qwen3-Coder-30B-A3B)
                         └── cloud:  Claude via `claude -p` CLI       (explicit requests, your subscription)
```

- The **brain** is the only process that talks to models and keeps state. The plugin and the notch
  are thin clients.
- The **plugin** sends text and structure from the IntelliJ PSI, **never screenshots**. It sends a
  window of the file around the cursor (±60 lines), the enclosing function and class, and the
  project's symbol map (file tree + top-level signatures), which is cached and only resent when it
  changes.
- **Routing** (changed by the user on 2026-10-16, docs/decisions.md): one model, the one in the
  settings (Claude Sonnet by default), answers `#?`, `#!teoria`, the proactive hint and the review
  on Ctrl+S. Until then the hint went only to a local engine.
- **Notch**: a **selective extraction** from Coucou, not a full fork. Coucou has about 55k lines of
  Swift (Stripe, Spotify, voice, phone…). We take only the panel and geometry
  (`IslandWindowController`/`IslandPanel`, `IslandScreenGeometry`, `IslandStateMachine`) and
  the markdown view (`ChatMarkdownView`). We credit the MIT licence in `THIRD_PARTY.md`. **Not**
  Mochi, the name, icons or sounds: those are © all rights reserved.

### Protocol v0 (JSON over WebSocket, one message per frame)

The source of truth is [`protocol/`](protocol/README.md) (JSON Schemas + examples). Summary:

```jsonc
// any client → brain (first frame), brain → client
{"v":0,"type":"hello","role":"ide|notch","token":"<local token>","client":"pycharm-plugin/0.1.0"}
{"v":0,"type":"welcome","brain":"0.1.0"}

// plugin → brain
{"v":0,"type":"trigger","id":"uuid","kind":"question|theory","text":"why ...",
 "file":"src/load.py","line":12,"language":"python",
 "window":{"start":1,"code":"..."},"scope":"def load(path): ...","project":"<hash of symbol map>"}
{"v":0,"type":"idle","id":"uuid","file":"...","line":40,"window":{...},"scope":"...","project":"..."}
{"v":0,"type":"project_map","hash":"...","tree":["src/load.py", "..."],"symbols":{"src/load.py":["def load(path)"]}}

// brain → notch
{"v":0,"type":"answer_start","id":"uuid","kind":"question|theory|hint","title":"..."}
{"v":0,"type":"answer_delta","id":"uuid","text":"..."}
{"v":0,"type":"answer_end","id":"uuid","model":"claude-sonnet-5-5","first_token_ms":1930,"total_ms":2590,"tokens":{"in":0,"out":0}}
{"v":0,"type":"error","id":"uuid|null","message":"..."}
```

## Tech stack

| Part | Choice | Notes |
|---|---|---|
| brain | Python 3.13+ (3.14 is installed), `uv`, FastAPI + uvicorn (WebSocket), `httpx` for the local engines, `pytest`, `ruff` | Claude is reached through the `claude` CLI (see "Cloud provider") |
| ide-pycharm | Kotlin, IntelliJ Platform Gradle Plugin 2.x, Gradle wrapper, JDK 21 (installed) | Targets the installed PyCharm |
| notch | Swift 6, SwiftUI + AppKit, Swift Package (`swift build`); XcodeGen only if signing or entitlements require it | Xcode is installed but **inactive**: run `sudo xcode-select -s /Applications/Xcode.app` |
| local models | llama.cpp `llama-server` :8080 or MTPLX :8000 (already set up in `~/Work`) | Qwen3-Coder-30B-A3B Q4_K_M for the hint |

### Cloud provider: Claude subscription via the `claude` CLI

The brain runs the user's own Claude Code CLI headless, logged in with their subscription. No API
key. Measured on 2026-10-14 (Sonnet 5.5, 3 runs): **first token 1.8–2.2 s, total 2.5–2.9 s**.

```
claude -p "<prompt>" --output-format stream-json --verbose --include-partial-messages \
  --system-prompt "<tutor prompt>" --tools "" --setting-sources "" --strict-mcp-config \
  --disable-slash-commands --no-session-persistence --model sonnet
```

- `--bare` **cannot** be used: it only accepts `ANTHROPIC_API_KEY`, never OAuth.
- No tools, no settings, no MCP, so the call is a plain tutor answer with no side effects.
- The provider is behind a `CloudModel` interface, so an API-key implementation can replace it
  without touching the routing.
- **Personal use only.** Anthropic does not allow third-party products to offer Claude.ai
  login or subscription limits to other users. If CodeBuddy is ever distributed, the cloud provider
  must switch to API keys.

## Commands (target: none of these exist yet, they will be created in slice S0)

```
./scripts/check                  # the single gate: runs everything below
cd brain && uv run pytest         # brain tests
cd brain && uv run ruff check .   # brain lint
cd brain && uv run buddy serve    # start the daemon on :8790
cd brain && uv run buddy ask src/x.py:12 "why ..."   # CLI, no UI: for debugging prompts
cd notch && swift build && swift test
cd notch && swift run CodeBuddy --demo               # every state, no IDE or model needed
cd ide-pycharm && ./gradlew test buildPlugin
cd ide-pycharm && ./gradlew runIde                    # sandbox PyCharm with the plugin
```

## Project structure

```
CodeBuddy/
├── AGENTS.md, CLAUDE.md→AGENTS.md, SPEC.md, CAPABILITY-MAP.md, THIRD_PARTY.md
├── protocol/        # JSON Schemas for v0 + example messages (shared fixtures for all tests)
├── brain/           # Python daemon (src/buddy/…, tests/)
├── notch/           # Swift package (Sources/CodeBuddy/…, Tests/)
├── ide-pycharm/     # Kotlin plugin
├── evals/           # snippets + expected outcomes (after the MVP)
├── docs/            # gaps.md, decisions.md, architecture.md
├── log/devlog.md
└── scripts/check
```

## Code style

Python, with types everywhere, small pure functions, and side effects at the edges:

```python
def build_question_prompt(trigger: Trigger, project: ProjectMap) -> list[Message]:
    """Pure: same input, same prompt. Tested with fixtures from protocol/examples."""
    ...
```

- Python: `ruff` (format + lint), `pyright` in basic mode. Swift: `swift-format` defaults. Kotlin:
  `ktlint`.
- Code and docs are in English. The buddy **answers in Italian** (configurable).
- Prompts live in `brain/src/buddy/prompts/*.md`, not inside code strings, so they can be read
  and diffed.

## Testing strategy

- **protocol**: every message in `protocol/examples/` validates against its schema in all three
  languages. This is the guard against drift between processes.
- **brain**: unit tests on the pure functions (trigger parsing, context building, routing, rate
  limit). Integration tests on the WebSocket with **fake** models (no network in CI). One live smoke
  test, marked `@pytest.mark.live`, is run by hand.
- **ide-pycharm**: tests of trigger detection on sample documents (`BasePlatformTestCase`).
- **notch**: tests on the state machine (hidden→peek→expanded, timeouts). A demo mode lets you look
  at the UI by hand, with screenshots in the devlog.
- **End to end** (manual for the MVP, automated later): write `#?` in the sandbox PyCharm and see
  the answer in the notch.

## Boundaries

- **Always:** run `./scripts/check` before saying something is done; keep the protocol schemas
  and fixtures in sync; record measured latency in the devlog.
- **Ask first:** new dependencies; changing the protocol (bump `v`); using a paid model in an
  automatic path; touching anything outside this folder.
- **Never:** commit API keys; send code anywhere the user didn't pick in the settings (since
  2026-10-16 the picked model gets proactive hints too); edit the user's code from the plugin (removing a trigger line once sent is not code, 2026-10-16); copy Coucou's Mochi, name, icons or sounds.

## Success criteria (MVP)

1. US1: from pressing Enter on `#?` to the **first answer token in the notch: ≤ 3 s** (p50 over 10
   runs, Claude, measured by the brain and written in `answer_end.first_token_ms`).
2. US3: proactive hint with the local model **≤ 8 s**, at most **1 every 3 minutes**, never sent
   to the cloud. A test proves that no cloud request leaves the brain for `idle` events. (Met on
   2026-10-14. Since 2026-10-16 the hint uses the settings model, at the user's request; the rate
   limit and the "only changed code" rule still hold and are tested.)
3. Context sent per trigger is **≤ 8k input tokens** on this repo (the brain logs it).
4. `#?` / `#!teoria` lines inside strings or normal comments (`# teoria …`) do **not** fire: the
   plugin has tests for this.
5. `swift run CodeBuddy --demo` shows hidden → peek → expanded with a streamed answer, and
   Sprout is visible in every state.
6. `./scripts/check` is green, and the pre-push hook runs it.

## Open questions

1. ~~Claude API key?~~ Resolved: use the subscription through the `claude` CLI (see "Cloud provider").
2. ~~Do trigger lines stay?~~ Resolved: they stay. An IDE action ("CodeBuddy: clear triggers")
   removes them all.
3. ~~Which PyCharm version?~~ Resolved: unified PyCharm 2026.2.3 (product code `PY`, build 262),
   which is the plugin's target platform.
4. ~~Git remote?~~ Resolved: local only for now. CI runs as a local gate (`./scripts/check` plus
   a git pre-push hook); GitHub Actions comes later.
