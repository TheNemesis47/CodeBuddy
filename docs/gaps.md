# Where CodeBuddy falls short of the MVP

> **Last reviewed:** 2026-10-14 · **Last updated:** 2026-10-14 · **Change:** G4 closed (PyCharm plugin); G5 mostly done; G13 added

Every known shortfall, one entry each, ranked by impact. This is the work list agents pick from:
take the highest-ranked open entry, and when you close part of one, update its evidence and
estimate here. **Human** marks what an agent can't finish alone.

## Summary

| # | Gap | Kind | Impact | Estimate | Owner |
|---|---|---|---|---:|---|
| ~~G1~~ | ~~Protocol v0 schemas + examples + validator~~ (done 2026-10-14) | feature | — | — | agent |
| ~~G2~~ | ~~Brain: daemon, `buddy ask` CLI, Claude CLI provider, WebSocket with token~~ (done 2026-10-14) | feature | — | — | agent |
| ~~G3~~ | ~~Notch: extract panel from Coucou, Sprout placeholder, `--demo`~~ (done 2026-10-14) | feature | — | — | agent |
| ~~G4~~ | ~~PyCharm plugin: skeleton, trigger detection, context, send~~ (done 2026-10-14) | feature | — | — | agent |
| G5 | Latency p50 over 10 real runs (criterion 1); wiring is done. **Risk: first token 1.3–5.8 s** | perf | blocks next stage | 2 h | agent + **Human** (G13) |
| G6 | Proactive idle hint on the local engine + rate limit + no-cloud test (criterion 2) | feature | blocks next stage | 4 h | agent |
| G7 | Enforce module boundaries automatically | tooling | medium | 1 h | agent |
| G8 | Sprout final design | feature | medium | — | **Human** |
| G9 | CI on GitHub Actions | tooling | low | 1 h | **Human** (create remote) |
| G10 | Evals: snippet set + scorer for suggestion quality | tooling | high (after MVP) | 6 h | agent |
| G11 | Real-screen check of the notch (hover, click, Spaces, full screen) + 2 peek defects seen in snapshots | UX | medium | 1 h | **Human** + agent |
| G13 | Install the plugin in your real PyCharm and use `#?` / `#!teoria` on real code | feature | blocks next stage | 30 min | **Human** |
| G12 | Grant Screen Recording to the terminal so agents can `screencapture` the real screen (today: view snapshots only) | tooling | low | 5 min | **Human** |

## G1: Protocol v0 (closed 2026-10-14)

Done: 9 schemas + 11 examples in `protocol/`, validated by `brain/tests/test_protocol.py` (run by
`scripts/check`). The original entry is kept below for reference.

**Evidence (at the time).** `protocol/schemas/` and `protocol/examples/` are empty. SPEC.md → "Protocol v0"
describes the messages.
**Done when.** One JSON Schema per message type, one or more examples each, and `scripts/check`
validates every example (Python `jsonschema` inside `brain`'s test suite, which is the first
consumer).
**Approach.** Write the schemas from SPEC.md. Add a `hello` message carrying the local token
(see SECURITY.md).

## G2: Brain daemon (closed 2026-10-14)

Done: `buddy ask` and `buddy serve` work. 79 offline tests. Mutation-checked: removing the Origin
check, the token check or the hello timeout, or routing `idle` to the cloud, each fails a test. Real
run in `log/devlog.md`. The original entry is kept below.

**Evidence (at the time).** `brain/` doesn't exist.
**Done when.** `cd brain && uv run buddy ask some.py:12 "why …"` streams a Claude answer in the
terminal. `uv run buddy serve` accepts a WebSocket with a valid token and rejects a bad token or a
browser `Origin`. Tests run with a fake model, without network.
**Approach.** `uv init --package`, FastAPI + uvicorn. `CloudModel` interface, with
`ClaudeCliModel` wrapping the command in SPEC.md → "Cloud provider". Prompts in
`src/buddy/prompts/*.md`.

## G3: Notch app (closed 2026-10-14)

Done: `notch/` SwiftPM (`CodeBuddyKit` logic + `CodeBuddy` app), 36 tests. `--demo` and
`--demo --snapshots DIR` work. The real e2e run (brain + notch + plugin-like client) showed a Claude
answer in the notch (`docs/screenshots/notch/e2e-claude-answer.png`). Open follow-ups: G11, G12.

**Evidence (at the time).** `notch/` doesn't exist. Coucou source to extract: `IslandWindowController.swift`
(`IslandPanel`), `IslandStateMachine.swift`, `CoucouKit/IslandScreenGeometry.swift`,
`ChatMarkdownView.swift`. Xcode is installed but `xcode-select` points to the Command Line Tools.
**Done when.** `swift run CodeBuddy --demo` shows hidden → peek → expanded with a streamed answer
and a Sprout placeholder. State machine tests pass. `scripts/guard-assets` is green.
**Approach.** Human: `sudo xcode-select -s /Applications/Xcode.app`. Then a SwiftPM executable,
copying only those files, renamed, with the credit in `THIRD_PARTY.md`.

## G4: PyCharm plugin (closed 2026-10-14)

Done: `ide-pycharm/` (Gradle 9.8 wrapper, IntelliJ Platform Gradle Plugin 2.19, Kotlin 2.4.20)
built against the local PyCharm 2026.2.3 with `PythonCore`. 18 tests (trigger detection on PSI,
including strings, docstrings, trailing and normal comments; context; project map; Enter → trigger;
clear action; message shapes against `protocol/examples`; brain down). `buildPlugin` produces
`build/distributions/codebuddy-pycharm-0.1.0.zip`. The live e2e test (`-Pe2e`) took the plugin's
real code path to a running brain and notch. Not done: `idle` events (G6), testing in the real IDE
(G13).

**Evidence (at the time).** `ide-pycharm/` doesn't exist. Target: PyCharm 2026.2.3 (product `PY`, build 262).
JDK 21 is installed, Gradle is not (use the wrapper).
**Done when.** `./gradlew test buildPlugin` is green. Tests cover trigger detection (`#?`,
`#!teoria` fire; `# teoria`, triggers inside strings and docstrings don't). `runIde` sends a trigger
message to a brain stub.
**Approach.** IntelliJ Platform Gradle Plugin 2.x template. A document listener checks the line
on Enter. Context comes from PSI (enclosing function and class, ±60 lines). All I/O runs off the EDT
(golden rule 1).

## G5: End-to-end

**Progress (2026-10-14).** Wiring done and checked twice: a plugin-like Python client
(first token 1265 ms) and the plugin's own code via `LiveBrainE2ETest` (2278 ms), both shown in the
notch. Criterion 3: ~300–350 input tokens per trigger on small files, well under 8k (measured).
Criterion 4: covered by plugin tests. Left: criterion 1 as a p50 over 10 runs from the real IDE.

**Evidence.** `buddy ask` against Claude through the subscription (Sonnet 5.5, ~1.0k input
tokens): first token p50 2.9 s, range 1.6–5.8 s, over 15 runs on 2026-10-14: large run-to-run variance.
Criterion 1 (p50 ≤ 3 s) is **at risk**. Ideas to measure: `--model haiku` for `#?`, a warm process,
a shorter system prompt. `--effort low` made no clear difference (3 runs).
**Done when.** In the sandbox PyCharm, `#?` produces an answer in the notch. The brain logs
first-token latency and input tokens. Criteria 1, 3 and 4 are measured over 10 runs and written in
ROADMAP.md.

## G6: Proactive hint

**Done when.** An `idle` event produces a hint from llama.cpp :8080 or MTPLX :8000 in ≤ 8 s, at most
1 every 3 minutes, and only if the code changed. With no local engine it produces nothing. A test
proves that `idle` never reaches the cloud provider while `proactive_cloud = false`.

## G7: Boundaries

**Evidence.** The rule "plugin and notch talk only to brain, via protocol" lives only in prose
(AGENTS.md §2).
**Done when.** A script fails if `ide-pycharm` or `notch` contains model URLs (`:8080`, `:8000`,
`anthropic`, `claude -p`), or any port other than the brain's.

## G8: Sprout design (Human)

Concept: a seed → sprout → plant → tree that grows with the skill map. Needs an idea of the look
(sketch, or concepts made with Draw Things) before it is drawn in SwiftUI `Canvas`.

## G9: CI

The gate is local only (`scripts/check` + `pre-push`). Once there is a GitHub remote, add one
Actions job on macOS that runs `./scripts/check`.

## G11: Notch on the real screen (Human)

**Evidence.** Agents only see view snapshots (`--snapshots`). They don't see the menu bar around the
island, hover over it, or check it on a screen without a notch.
**Known defects** (from `docs/screenshots/notch/demo-5-peek-after.png`): in peek after an answer,
Sprout is drawn as a seed with no stem although its mood is happy, and the ✓ sits ~5 pt above
Sprout. An agent can fix these. Check whether they also show on the real screen.
**Done when.** You have run `swift run CodeBuddy --demo`, hovered and clicked it, and noted anything
off in the devlog.

## G13: Plugin in your real PyCharm (Human)

**Done when.** In PyCharm: Settings → Plugins → ⚙ → Install Plugin from Disk →
`ide-pycharm/build/distributions/codebuddy-pycharm-0.1.0.zip`, restart, start
`cd brain && uv run buddy serve` and `cd notch && swift run CodeBuddy`, then write
`#? …` and `#!teoria …` in a real project. Note in the devlog what felt slow, wrong or noisy,
whether typing ever stuttered (golden rule 1), and what the answers looked like.

## G12: Screen Recording for agents (Human)

`screencapture` fails with "could not create image from display": the terminal has no Screen
Recording permission (System Settings → Privacy & Security → Screen Recording).

## G10: Evals

After the MVP. 20–30 real snippets with expected concept tags and "good hint" rubrics. Reuse ideas
from `~/Work/testM5/benchkit`. Add the score to `quality/floors.json`.
