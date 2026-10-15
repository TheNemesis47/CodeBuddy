# Dev log

Newest first. Terse. Written at the end of every task so the next agent can pick up.

## 2026-10-15 12:30: G10 evals (branch feat/evals, from main)

- **Landed:** `evals/cases/` 29 cases (18 `hint`, 8 `#?`, 3 `#!teoria`) + `evals/schema/case.schema.json`;
  `brain/src/buddy/evals.py` + `buddy eval` (real `build_prompt` per case; checks concept, shape
  (hint ≤ 3 lines and no code block, `#?` ≤ 15 lines), no_leak (forbidden regexes), no_fix (no
  answer line contains a corrected line), language; optional `--judge local|claude`; `--repeat`,
  `--rescore`, `--only`); results in `evals/results/<date>[-N].json`. `scripts/ratchet`:
  `eval_score` = total of the latest committed complete result. `scripts/check`: "eval cases" step
  (offline: schema + scorer on canned answers). Ideas from benchkit's graders: automatic checks
  first, a judge or a human only for what they can't see; per-case fraction of checks passed.
- **Numbers:** brain tests 137 → 175 (`test_evals.py`: pass and fail for each check, every case
  valid, run/summary/rescore/repeat); floors `brain_tests` 175, `eval_score` **99.1**.
- **Engine and models:** hints: Qwen3-Coder-30B-A3B-Instruct-Q4_K_M on llama.cpp `llama-server`
  :8080 (`-ngl 999 -fa on -c 16384 --jinja`, temp 0.6/top_p 0.95 as in production); triggers:
  Claude Sonnet 5.5 via `claude -p`; judge: the same local Qwen.
- **Scores:**

  | Run | Prompts | Hints | Total (29 cases) | Leaks (no_leak fails) | Corrected lines written | Judge |
  |---|---|---:|---:|---|---|---|
  | `results/2026-10-15.json` (baseline) | `main` | ×1 | **94.5** | 3/29 | 5/29 (all `#?`) | 4.07 |
  | scratch | old `hint.md` | ×3 | hints 94.8 | 7/54 | 1/54 | — |
  | scratch | `hint.md` v1 (name the problem, not the fix) | ×3 | hints 95.9 | 4/54 (but 7 vague hints miss the concept) | 0 | — |
  | scratch | v2 (first sentence: the concrete problem) | ×3 | hints 96.3 | 9/54 ("why not use `X`?") | 1 | — |
  | scratch | **v3** (+ the question must not contain the answer, no "without `X`") | ×3 | hints **97.8**, again **98.5** | 6/54, 3/54 | 0 | — |
  | scratch | v4 (+ "don't say what is missing" + self-check) | ×3 | hints 95.9 | 7/54 + 3 too long | 0 | — (reverted) |
  | `results/2026-10-15-2.json` (improved) | v3 + `system.md` (never write the corrected line) | ×3 | **99.1** | 3/65 | **0/65** | 3.89 (hint 3.67, `#?` 5.0, teoria 5.0) |

  The baseline was re-scored once after two case fixes (`ombra` → `ombr`: «ombreggia» does name
  shadowing; `global` leak regex widened: «dichiarato come `global`» names the fix), via
  `--rescore`. The judge mean fell only because hints are now 54 of 65 judged answers; per kind it
  is flat (hint 3.72 → 3.67) or up (`#?` 4.5 → 5.0). The `system.md` example is not an eval case
  (kept out to avoid tuning to the test set).
- **Before / after:**
  1. `hint-missing-with` (the known leak). Before: «Apri il file con `with` per evitare problemi di
     chiusura del file…» (no_leak ✗, judge 3). After: «Il problema è che il file aperto non viene
     chiuso, causando un potenziale accumulo di risorse. Che cosa succede se la funzione viene
     chiamata più volte?» (all pass, judge 5).
  2. `q-while-misses-zero` (`#?`). Before: walks the loop, then «Usa `>=` invece di `>`:» and a
     code block `while n >= 0:` (no_fix ✗). After: same walk-through, then «devi cambiare
     l'operatore di confronto in modo che anche il valore 0 renda la condizione vera. Pensa a quale
     operatore significa "maggiore **o uguale**"», an example on other code (`while x < 5`), and
     «prova a fare una traccia a mano con `n = 2`» (all pass, judge 5).
  3. `hint-unbound-local`. Before: «…senza averlo dichiarato come `global` o `nonlocal`…»
     (no_leak ✗). After (final run, 3 of 3 pass): «La variabile `count` è usata prima di essere
     assegnata nella funzione `increment`, causando un errore `UnboundLocalError`. Perché il nome
     `count` non si riferisce alla variabile globale definita alla riga 1?» (one v3 scratch run
     still said `global`).
- **Worse / still open:** v3's "be concrete" rule can make the local model guess with confidence:
  `hint-remove-while-iterating` once claimed an `UnboundLocalError` (concept ✗, judge 2).
  `hint-missing-await` still says «manca `await`» in 2 of 3 runs. `#?` answers are often 6+
  paragraphs (inside 15 lines, still long for the notch). The local judge is noisy and once
  rewarded giving the fix. All in **G14 (Human)**: judge the borderline answers, then harder cases.
- **Processes:** `llama-server` stopped after the runs (`pgrep llama-server` empty).
- **Still open:** G14 (Human: borderline answers), G13 (Human: real PyCharm), G11, G12, G8;
  agent: G5 is on `feat/brain-latency` (not merged), G7.

## 2026-10-14 21:50: G6 proactive hints (branch feat/proactive-hints, on top of feat/ide-pycharm)

- **Landed:** plugin `Idle.kt`: an `editorFactoryDocumentListener` (EDT: a `.py` check, an offset,
  a timer restart) → per-document `Debouncer` (4 s) → `IdleDispatcher` builds the context like a
  trigger's (±60 lines, scope, project hash) in a non-blocking read action and sends `idle`; the
  same window as the last idle from that document is not resent. Brain: `local.py` (`/v1/models`
  detection on 127.0.0.1:8080/:8000, prefers Qwen3-Coder-30B-A3B; `LocalModel` streams OpenAI SSE,
  max 160 tokens), `hints.py` (`HintGate`: 1 hint / 180 s, changed window only, slot given back
  when no engine answers, paused 180 s by an explicit trigger; `BUDDY_PROACTIVE_CLOUD`),
  `prompts/hint.md` (one nudge, ≤ 3 lines, no solution), no project map and a ~3k-token budget for
  hints. Notch: a hint peeks with its first ~70 characters (`Markdown.preview`), a click opens it;
  `--demo` plays a hint; brain-mode `--snapshots` also saves a hint after clicking it open.
  Also untracked `ide-pycharm/.intellijPlatform/` (1726 sandbox files, already in `.gitignore`).
- **Numbers:** tests brain 81 → 116 (1 live, skipped), notch 36 → 40, plugin 18 → 26; floors
  raised. Mutation checks: unconditional cloud fallback (4 tests fail), no gate (1), no undo (1),
  no unchanged-window check in the plugin (1), no debounce restart (2). The compiler caught
  `key in ConcurrentHashMap` (it checks values) in the debouncer before it shipped.
- **Live run** (`llama-server` with `Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf`, `-c 16384 -fa on`,
  :8080; brain and notch on 8796; `./gradlew test --rerun -Pe2e --tests
  '*LiveBrainE2ETest.testIdleReachesTheBrain'`, which types into `load.py` and waits for the real
  timer): idle fired **4049 ms** after the last keystroke; brain `idle load.py:6 → hint on
  Qwen3-Coder-30B-A3B ~225 tokens in`, `hint answer_end in 585 ms`; notch `first_token_ms=24
  total_ms=570` (first run, cold cache: 197 / 955 ms). Well inside 8 s. Hint: «Il file `f` non
  viene chiuso dopo l'apertura, il che può causare problemi di risorse. Considera l'uso di un
  `with` statement…». The first run's prompt gave three unrelated nudges; `hint.md` now asks for
  one. With the engine stopped, the same run logs `no local engine, no hint` and the notch shows
  nothing. The engine was stopped afterwards.
- **Screenshots** (all opened and checked): `docs/screenshots/notch/e2e-hint-peek.png` (Sprout, ✓,
  preview cut on a word) and `e2e-hint-opened.png` (SUGGERIMENTO, `load.py:6`, full hint,
  `Qwen3-Coder-30B-A3B · primo token 24 ms · totale 570 ms`); demo `demo-1…8` (the six old states
  unchanged; `7-hint-peek`, `8-hint-expanded` new). Two intermediate live shots showed the panel
  still open from the previous run's scripted click (a hint never shrinks an open panel, by
  design), so the run of record restarted the notch.
- **MVP criteria:** 5/6 (criterion 2 now ✅). Open: 1 (latency p50, G5).
- **Still open:** Human: G13 now includes trying idle hints in the real PyCharm (too often? too
  rare? typing stutter?), G11 real screen. Agent: G5; G10 to turn hint quality into a number (the
  hint still names the fix, `with`, which is borderline for "a nudge, not a solution"). A hint
  arriving while the panel shows an explicit answer still replaces it after 3 minutes; fine for
  now, revisit with the priority queue.

## 2026-10-14 21:25: G4 PyCharm plugin (branch feat/ide-pycharm, on top of feat/notch-app)

- **Landed:** `ide-pycharm/`. Gradle 9.8 wrapper and IntelliJ Platform Gradle Plugin 2.19 (versions
  from JetBrains' template, 2026-10-10), Kotlin 2.4.20, built against `/Applications/PyCharm.app`
  2026.2.3 with `PythonCore`. Pieces: `TriggerParser` (mirrors the brain);
  `TriggerDetector` (PSI: the line's first character must be inside a `PsiComment`, so strings,
  docstrings and trailing comments never fire); `ContextBuilder` (±60 lines, enclosing
  `PyFunction`/`PyClass` with decorators, relative path); `ProjectMapBuilder` (content files minus
  excluded, top-level signatures, SHA-256 hash); `TriggerEnterHandler` (EDT: one text check
  only) → `TriggerDispatcher` (non-blocking read action on a pool thread) → `BrainConnection`
  (JDK WebSocket on its own thread, 2 s connect and 3 s send timeouts, silent with a 5 s retry
  pause; `MapTracker` resends `project_map` when it changes or on a new socket);
  `ClearTriggersAction` (the only document write, guarded by `scripts/guard-no-edits`).
- **Numbers:** plugin tests 0 → 18, floor raised. The gate runs all three modules, none skipped.
  Mutation check: parsing raw text instead of PSI fails 2 tests. A "comment must start at the
  line's first char" check turned out to be dead code (the PSI lookup already guarantees it) and was
  removed.
- **E2E with the plugin's own code** (`./gradlew test -Pe2e --tests '*LiveBrainE2ETest*'`, brain
  and notch on port 8797): brain `trigger question load.py:5 ~297 tokens in`; notch
  `answer_start → island expanded → answer_end first_token_ms=2278 total_ms=6128`. Screenshot:
  `docs/screenshots/notch/e2e-plugin-to-notch.png` (looked at). The JDK WebSocket sends no
  `Origin`, so the brain accepts it.
- **MVP criteria:** 3 (≤ 8k tokens: ~300 measured) ✅, 4 (trigger rules: plugin tests) ✅, 5 (demo) ✅,
  6 (gate) ✅. 1 (p50 ≤ 3 s, 10 runs from the IDE) and 2 (proactive, G6) are open.
- **Still open, for a human:** G13 install `ide-pycharm/build/distributions/codebuddy-pycharm-0.1.0.zip`
  in your PyCharm and try it on real code; G11 look at the notch on the real screen; G12 Screen
  Recording permission. Agent: G5 latency p50, G6 proactive hints on the local model.

## 2026-10-14 21:15: G3 notch app (branch feat/notch-app)

- **Landed:** `notch/` SwiftPM. `CodeBuddyKit` holds the logic: a 3-state island machine
  (adapted from Coucou) on an injectable clock, screen geometry, the markdown parser, protocol
  decoding, `AnswerStore`, `NotchModel`, `BrainClient` (reconnects with backoff, reads the token
  file) and the demo script. `CodeBuddy` is the app: panel over the notch, island shape, Sprout
  placeholder in Canvas (seed → sprout, moods), markdown view. Licence and file list in
  `THIRD_PARTY.md`.
- **Bug found by the e2e run:** the notch sent its hello as a *binary* frame and the brain only read
  text frames, so it dropped the connection. Fixed on both sides: the notch sends text, and the
  brain accepts UTF-8 JSON in binary frames (2 new tests).
- **Numbers:** notch tests 0 → 36 (state machine, geometry, markdown, protocol decoding against
  `protocol/examples`, answer store, model, a full demo replay on a manual clock). Brain 79 → 81.
  Floors raised.
- **Screenshots** (view snapshots via `--snapshots`, looked at; the desktop isn't included):
  `docs/screenshots/notch/demo-{1-hidden,2-peek,3-expanded-streaming,4-expanded-done,5-peek-after,6-hidden-after}.png`
  and `docs/screenshots/notch/e2e-claude-answer.png`. The first round showed a transparent strip
  at the top of the island (Coucou's ear path leaves the top edge at y = radius). The shape was
  redrawn flush with the screen top. A later full review (the 5th and 6th shots had been skipped at
  first) found two defects in peek-after: Sprout drawn as a seed with no stem although happy
  (`growth` was `@State` set in `onAppear`, so a fresh view drew the stale value), and the bare
  seed sitting low so the ✓ looked misaligned. Both fixed in `fix(notch): draw Sprout's stage…`;
  all six shots regenerated and each one opened and checked: hidden (notch-sized), peek (seed
  centred), expanded streaming (half-grown sprout, partial text), expanded done (full sprout,
  footer metrics), peek after (sprout with leaves, ✓ aligned), hidden after.
- **E2E** (`BUDDY_PORT=8798 buddy serve` + `swift run CodeBuddy --snapshots …` + a Python client
  sending `hello(ide)`, `project_map` and `trigger` exactly as the plugin will): notch log
  `brain connected → answer_start → island expanded → answer_end first_token_ms=1265
  total_ms=5481 → island peek (20 s) → hidden (8 s)`. ~343 input tokens.
- **Still open:** G11 (Human: try it on the real screen), G12 (Human: Screen Recording permission for
  real screenshots). `pkill -f .build/debug/CodeBuddy` misses the binary under
  `.build/out/Products/Debug/`: use `pkill -f "Debug/CodeBuddy|debug/CodeBuddy"`.

## 2026-10-14 21:30: G1 protocol v0 + G2 brain daemon (branches feat/protocol-v0, feat/brain-daemon)

- **Landed:** `protocol/` with 9 JSON Schemas (hello, welcome, trigger, idle, project_map,
  answer_start/delta/end, error) and 11 examples. `brain/` (uv, Python 3.14, FastAPI): `buddy ask`
  and `buddy serve`, `ClaudeCliModel` (subscription via `claude -p`, prompt on stdin, no
  tools/settings/MCP), token + Origin + hello-timeout handshake, prompts in
  `src/buddy/prompts/*.md`, an 8k-token budget that drops the project map, then trims the window.
- **Numbers:** brain tests 0 → 79 (78 offline + 1 live, skipped unless `BUDDY_LIVE=1`). Floor raised
  to 79. The gate is green; brain and protocol are no longer `skip`. Mutation check: removing the
  Origin check, the token check or the hello timeout, or sending `idle` to the cloud, each fails a
  test (the first version of the server tests hung on failure instead; fixed with context-managed
  sessions and a bounded handshake test).
- **Real run** (`cd demo && uv run --project brain buddy ask load.py:5`, file with
  `#? perché non chiude il file?` above `data = json.load(open(path))`):
  > Alla riga 6 `open(path)` crea un file object, ma non lo salvi in nessuna variabile e nessuno
  > chiama `.close()`. […] **Il modo giusto è il context manager (`with`):** […]
  `[claude-sonnet-5-5 · first token 3616 ms · total 7247 ms · tokens in 1034 out 703]`.
  `#!teoria context manager` at line 11 answered in the 4-part shape (first token 3872 ms).
- **Latency, 15 runs of the same ~1k-token prompt:** first token p50 **2.9 s**, range 1.6–5.8 s.
  The variance is per call, not per setup: a new vs reused model and `--effort low` show no clear
  difference. Criterion 1 is at risk (see G5).
- **Still open:** G3 notch (Human: `sudo xcode-select -s /Applications/Xcode.app` first), G4
  plugin, G5 with a 10-run p50 and maybe Haiku for `#?`. Answers run ~650–850 output tokens, which
  is long for a notch panel: tighten the system prompt when the notch shows real answers.
  `buddy ask` shows the path as given (absolute paths make the prompt noisier).

## 2026-10-14 20:05: project set up (agent-ready-project)

- **Landed:** SPEC.md, CAPABILITY-MAP.md, AGENTS.md (+ CLAUDE.md symlink), ROADMAP.md,
  docs/{gaps,decisions,development}.md, SECURITY.md, THIRD_PARTY.md, scripts/check + guards +
  ratchet, quality/floors.json, .githooks/pre-push, git init.
- **Numbers:** MVP criteria 0/6. Claude CLI first token 1.8–2.2 s (3 runs). Tests 0/0/0.
- **Still open:** G1 protocol v0 is next. Human: `sudo xcode-select -s /Applications/Xcode.app`
  before G3. Plugin test count has no measure in `scripts/ratchet.py` yet (add it with G4).
