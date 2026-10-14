# Dev log

Newest first. Terse. Written at the end of every task so the next agent can pick up.

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
  redrawn flush with the screen top.
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
