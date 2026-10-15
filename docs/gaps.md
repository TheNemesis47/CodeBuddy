# Where CodeBuddy falls short of the MVP

> **Last reviewed:** 2026-10-15 · **Last updated:** 2026-10-15 · **Change:** G5 closed (first token p50 1572 ms over 10 runs); G10 closed (evals: 29 cases, `buddy eval`, eval score 94.5 → 99.1 in the ratchet); G14 added (human review of borderline eval answers)

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
| ~~G5~~ | ~~Latency p50 over 10 real runs (criterion 1)~~ (done 2026-10-15: p50 1572 ms) | perf | — | — | agent |
| ~~G6~~ | ~~Proactive idle hint on the local engine + rate limit + no-cloud test (criterion 2)~~ (done 2026-10-14) | feature | — | — | agent |
| G7 | Enforce module boundaries automatically | tooling | medium | 1 h | agent |
| G8 | Sprout final design | feature | medium | — | **Human** |
| G9 | CI on GitHub Actions | tooling | low | 1 h | **Human** (create remote) |
| ~~G10~~ | ~~Evals: snippet set + scorer for suggestion quality~~ (done 2026-10-15: score 99.1) | tooling | — | — | agent |
| G14 | Judge the borderline eval answers by hand; make the cases harder once the score saturates | quality | medium | 1 h | **Human** + agent |
| G11 | Real-screen check of the notch: hover, click, Spaces, full screen | UX | medium | 1 h | **Human** |
| G13 | Install the plugin in your real PyCharm and use `#?` / `#!teoria` and idle hints on real code | feature | blocks next stage | 45 min | **Human** |
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

## G5: End-to-end latency (closed 2026-10-15)

Done on branch `feat/brain-latency`. Every `answer_end` (triggers, hints, `buddy ask`) appends one
line (id, kind, model, first_token_ms, total_ms, input_tokens) to `$BUDDY_HOME/latency.jsonl`;
`buddy latency [--kind K] [--last N]` prints first-token p50/p90/min/max. `scripts/bench-latency
LABEL [serve options]` starts a brain, the notch and an answer recorder, sends 10 `#?` triggers on
10 different files of `brain/src/buddy/` through the plugin's own code (`LiveLatencyBenchTest`:
`TriggerDispatcher.prepare` on PSI, then `BrainConnection`), one at a time, and stops everything.
**Result, Claude Sonnet 5.5 through `claude -p`:** first token p50 **1572 ms** (p90 1896, range
1397–2097); repeat run p50 **1634 ms** (p90 1947, range 1492–2967). Criterion 1 is met, so none of
the fallbacks (Haiku for `#?`, a warm process, a shorter prompt, prompt caching) was needed.
Criterion 3: 1656–3167 input tokens per trigger as Claude counts them (the brain's estimate was
678–1636: the CLI adds its own overhead), under 8k. The number starts when the brain receives the
trigger (SPEC.md defines it so); the Enter → PSI → localhost send part isn't in it. Open: that part
in a real IDE (G13); answers run ~1000–1200 characters, so the panel scrolls and its first line
hides under the header (devlog 2026-10-15). The original entry:

**Evidence (at the time).** `buddy ask` against Claude through the subscription (Sonnet 5.5, ~1.0k input
tokens): first token p50 2.9 s, range 1.6–5.8 s, over 15 runs on 2026-10-14: large run-to-run variance.
**Done when.** In the sandbox PyCharm, `#?` produces an answer in the notch. The brain logs
first-token latency and input tokens. Criteria 1, 3 and 4 are measured over 10 runs and written in
ROADMAP.md.

## G6: Proactive hint (closed 2026-10-14)

Done on branch `feat/proactive-hints`. Plugin: `Idle.kt` sends `idle` 4 s after the last change
to a `.py` file (per-document `Debouncer`; PSI and I/O off the EDT; same window as last time → not
sent). Brain: `local.py` finds llama.cpp :8080 or MTPLX :8000 via `/v1/models` and streams from it
(`LocalModel`, `prompts/hint.md`); `hints.py` allows 1 hint every 180 s, only for a changed window,
and none for 180 s after an explicit trigger; `BUDDY_PROACTIVE_CLOUD=1` is the only path to Claude.
Notch: a hint peeks with its first ~70 characters, a click opens it. Live run (Qwen3-Coder-30B-A3B
on llama.cpp): idle 4.05 s after the last keystroke, hint done 585 ms later (devlog). Open: real
PyCharm use (G13) and hint quality as a number (G10). The original entry:

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
Two snapshot defects (Sprout without its stem in peek-after, the seed sitting low) were fixed on
2026-10-14. Check that they don't show on the real screen either.
**Done when.** You have run `swift run CodeBuddy --demo`, hovered and clicked it, and noted anything
off in the devlog.

## G13: Plugin in your real PyCharm (Human)

**Done when.** In PyCharm: Settings → Plugins → ⚙ → Install Plugin from Disk →
`ide-pycharm/build/distributions/codebuddy-pycharm-0.1.0.zip`, restart, start
`cd brain && uv run buddy serve` and `cd notch && swift run CodeBuddy`, then write
`#? …` and `#!teoria …` in a real project. For hints, also start a local engine
(`llama-server -m ~/Documents/AI/models/gguf/Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf --alias
Qwen3-Coder-30B-A3B --port 8080 -ngl 999 -fa on -c 16384 --jinja`) and pause while typing. Note in
the devlog what felt slow, wrong or noisy, whether typing ever stuttered (golden rule 1), whether
hints came too often or too rarely, and what the answers looked like. After a few `#?`, run
`cd brain && uv run buddy latency --kind question` and note whether the wait from Enter felt
longer than its p50 (the brain's clock starts when the trigger arrives).

## G12: Screen Recording for agents (Human)

`screencapture` fails with "could not create image from display": the terminal has no Screen
Recording permission (System Settings → Privacy & Security → Screen Recording).

## G10: Evals (closed 2026-10-15)

Done on branch `feat/evals`. `evals/cases/`: 29 snippets (18 `hint`, 8 `#?`, 3 `#!teoria`:
missing `with`, off-by-one, mutable defaults, scope, `is` vs `==`, typing, async, generators…),
validated against `evals/schema/case.schema.json` by `scripts/check`. `buddy eval` builds the real
prompt for each case and scores 5 deterministic checks (concept, shape, no_leak, no_fix,
language); `--triggers` runs `#?`/`#!teoria` on Claude, `--judge local|claude` adds a rubric grade
(reported, not ratcheted), `--repeat N` samples hints N times, `--rescore` re-checks saved answers.
`scripts/ratchet` reads the latest committed complete result. **Baseline 94.5 → 99.1** after
`hint.md` (name the problem, never the fix; one concrete sentence, at most one question that
doesn't contain the answer) and `system.md` (never write the corrected line). Hints:
Qwen3-Coder-30B-A3B on llama.cpp; triggers: Sonnet 5.5. Details and examples in the devlog.
Open: G14 (borderline answers, harder cases). The original entry:

After the MVP. 20–30 real snippets with expected concept tags and "good hint" rubrics. Reuse ideas
from `~/Work/testM5/benchkit`. Add the score to `quality/floors.json`.

## G14: Borderline eval answers (Human)

**Evidence.** The deterministic checks miss some things, and the local judge is noisy (it once
graded a hint 2 for *not* giving the `None` fix, and 5 for `#?` answers that wrote the corrected
line). Examples to look at in `evals/results/2026-10-15-2.json`: `hint-remove-while-iterating`
(a confident but wrong `UnboundLocalError` diagnosis, judge 2: the "be concrete" rule can make the
local model guess), `hint-missing-await` («manca `await`» still leaks in 2 of 3 runs), and
`#?` answers that are 6+ paragraphs (pass the 15-line shape check, still long for the notch).
**Done when.** You've read those answers and marked each as fine / too revealing / wrong in the
devlog; an agent turns the verdicts into tighter regexes or new cases. Once the score sits at
≥ 99 for two runs, add harder cases (the score should have room to rise).
