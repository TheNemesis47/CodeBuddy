# Dev log

Newest first. Terse. Written at the end of every task so the next agent can pick up.

## 2026-10-16 12:30: deep theory and #!approfondisci (branch feat/brain-deeper-theory)

- **From the user:** a `#!` theory question ("dimmi la teoria che c'è dietro") came back like a
  `#?` answer; they wanted how it really works, some math, and something to dig further into.
- **Landed:** `prompts/theory.md` rewritten (7 bold parts, 25–45 lines, math only when real, "Per
  approfondire" with docs/PEPs, next concept, one exercise, a pointer to `#!approfondisci`);
  `prompts/deeper.md`; trigger kind `deeper` (brain `triggers.py`, plugin `Triggers.kt`, protocol
  `trigger.json` + `examples/trigger.deeper.json`); `Brain.last_theory` keeps the last finished
  theory; `ANSWER_MAX_TOKENS` 3000. Evals: theory's shape check is now a depth check (≥ 15 lines,
  a mechanism part, ≥ 2 pointers); 2 new cases (`t-recursion-math` written as a request,
  `t-dict-hashing`), 31 cases; rubrics updated; `buddy eval --triggers --only t-…` no longer needs
  a local engine.
- **Live, Claude Sonnet:** the 5 theory cases score **100.0** (5/5 on every check), result in the
  scratchpad (an `--only` run is incomplete, not committed). `t-recursion-math`: frames and the
  call stack, `T(n) = T(n-1) + T(n-2) + 1`, `O(φⁿ)` with φ explained, ~29.8 M calls for n = 35,
  memoization named in words only. `#!approfondisci` on it: bytecode (`dis`), 3.11 frames, Binet
  derived from `r² = r + 1`, edge cases, why no tail calls, autograd and the KV-cache. First token
  for theory was 7.8 s on one run (not in criterion 1, which is `#?`): watch it.
- **Tests:** brain 262 → **282**, plugin 58 → **60**; floors raised. Gate green. `eval_score` stays
  99.1 until a full run (needs the local engine for hints) is committed.
- **Still open:** a full `buddy eval --repeat 3 --triggers` with the new depth check, committed;
  hints now go to the settings model, so G16 (evals on the settings provider) matters more.

## 2026-10-16 12:05: the trigger line goes once sent (branch feat/plugin-erase-trigger-line)

- **From the user:** after Enter the `#?` line should go; several tries left many lines behind.
- **Landed:** `TriggerEnterHandler` marks the line (`RangeMarker`), `TriggerDispatcher` sends with a
  delivery callback (new `BrainSender.send(map, message, delivered)`; `BrainConnection` reports
  whether the socket took it), then `TriggerEraser.erase` on the EDT removes the line as an
  undoable command, only if PSI still sees a trigger there. Brain down → the line stays. All
  document writes stay in `ClearTriggersAction.kt` (guard unchanged, comment updated). Golden
  rule 2 reworded in AGENTS.md (the user's request), decision in docs/decisions.md.
- **Tests:** plugin 53 → **58** (erased + caret on the new line + context still had the line,
  Ctrl+Z restores it, brain down keeps it, an edited line is kept, normal/trailing/string comments
  never erased). Floor raised. Gate green.
- **Still open:** try it in the real PyCharm (G13): the erase lands ~10–50 ms after Enter on
  localhost; check it doesn't fight fast typing.

## 2026-10-16 11:50: the panel opens at the first token (branch feat/ui-open-on-first-token)

- **From the user:** "quando premo invio mi si apre il pannello davanti anche se non ha generato
  ancora la risposta": the panel should open when the first tokens arrive.
- **Landed:** both state machines (`IslandStateMachine.swift`, `island.py`): any answer first
  peeks with Sprout thinking and "…"; an explicit one opens at `answerHasContent` (first non-empty
  delta, an error, or the end). A click or the close button while waiting cancels the pending
  open, so later tokens never reopen a panel the user closed; an already open panel stays open.
  Scenarios: `question-opens-streams-and-folds` now expects peek until the first token (an empty
  delta is not one); new `an-explicit-answer-that-fails-before-any-token-opens-to-show-why`.
- **Snapshots** (looked at): new `2b-thinking` moment in both demos, a peek with Sprout and "…"
  before the first token, then `3-expanded-streaming` with text. Overlay e2e (stub brain) OK.
- **Tests:** notch 42 → **44**, overlay 118 → **121**; floors raised. Gate green.
- **Still open:** how it feels on the real screen (G11) with a slow model.

## 2026-10-16 11:40: one model for everything, review on Ctrl+S (branch feat/one-model-and-save-review)

- **From the user (2026-10-16):** "il modello selezionato, che sia locale o che sia in cloud, è
  quello che deve fare tutto", and a check of the file on Ctrl+S that says what's off and "potresti
  fare questa cosa, oppure quest'altra".
- **One model:** `[hints]` (engine list, `proactive_cloud`, `BUDDY_PROACTIVE_CLOUD`, the hint key)
  removed from `settings.py`/`providers.py`/`keys.py`; `Brain` has one `model`. Old `[hints]`
  tables, `hints` in `settings_set` and the `hints_server` key are accepted and ignored. The
  PyCharm page lost its "Proactive hints" group. docs/decisions.md, SPEC.md (US3, routing,
  criterion 2 annotated), SECURITY.md, AGENTS.md, README/INSTALL updated.
- **Review on save:** new `review` message (protocol v0, additive: README explains), `answer_start`
  kind `review`. Plugin: `SaveReviewListener` (AnActionListener on `SaveAll`/`SaveDocument`, so
  autosave never fires it) + `ReviewDispatcher` (whole file, off the EDT; > 200k chars → the ±60
  window). Brain: `prompts/review.md`, its own `HintGate(30 s)` keyed on the file text; triggers
  pause hints and reviews, a review pauses hints. Notch + overlay: a review peeks with a preview
  like a hint (scenario `review-after-save-peeks-and-opens-on-click`).
- **Live, Claude Sonnet via `claude -p`, `protocol/examples/review.json`:** found the missing
  `return` (line 7) and `scale` ignoring `h` (line 10) with two directions each, suggested a
  `@property` with its trade-off, no corrected line.
- **Tests:** brain 262 (16 tests of the old local-only routing replaced by tests of the new
  routing, the review gate, prompt and protocol), plugin 48 → **53**, overlay 117 → **118**, notch
  42 (the new scenario runs inside the scenario test). Floors raised. `./scripts/check` green.
- **Still open:** `buddy eval` has no review cases yet; reviews and hints on Claude use quota
  (rate limits above); try Ctrl+S in the real PyCharm (G13).

## 2026-10-15 16:25: the panel's monitor, and the pin it needed (branch fix/overlay-hyprland)

- **From the tester's second report** (`~/Work/codebuddy-0.1.1-report.md`, Omarchy, two monitors,
  the second rotated), run against the CI package of this branch: bugs 1, 2, 3, 4 and 6 confirmed
  fixed on the real desktop, two left.
- **Bug 7 (new, it made the panel invisible):** XWayland publishes its own X11 layout. There it
  called the rotated monitor primary and put it at `0,0`, while Hyprland has the main one there.
  Centring on `primaryScreen()` asked for `x=500`; Hyprland read that in its own space as
  **`-580`**, so the panel sat outside every screen: nothing drawn, no pointer, `VIEWABLE` in X11.
  It also explains the panel that "disappeared after 15 minutes" in the first report, which nobody
  could reproduce: XWayland restarts when its last client exits, and the layouts drift apart.
  Now `panel_placement` picks the compositor's focused monitor (or `BUDDY_MONITOR`) and the window
  follows the **Qt screen with the same connector name**, looked up on every placement.
  Measured here: X11 `2320,30` → Hyprland `1240,30`, centred on DP-2 under the 30 px bar, and the
  log now prints the chosen screen and every screen Qt sees.
- **Bug 5 (not fixed by the dock after all):** a dock window on Hyprland belongs to the workspace
  it opened on (`hyprctl clients`: `workspace: 4`), and `_NET_WM_DESKTOP = 0xFFFFFFFF` and
  `_NET_WM_STATE_STICKY` set before the map are both ignored (measured on 0.56.2). The panel now
  asks Hyprland to pin it (`hl.dsp.window.pin`, `action = "on"`; the flat form is a toggle, so it
  is only the fallback), retried on a Qt timer until `hyprctl clients` confirms. Measured:
  `pinned: true`, and the panel is on every workspace.
- **Tests:** overlay 112 → **117** (floor raised). `hyprland_tops`/`sway_tops`/`top_for_screen`
  became `hyprland_monitors`/`sway_monitors`/`target_monitor` (name, bar, focus), `top_placement`
  became `panel_placement` (screen + offset), plus the pin commands and `_screen()` by name.
  `scripts/smoke_bundle_desktop.py` now checks the chosen screen is named in the log and that the
  pin was dispatched; its fake `hyprctl` answers `clients` so the retry stops on its own.
  `overlay/tests/conftest.py` no longer inherits a Wayland session's `QT_QPA_PLATFORM`
  (`wayland;xcb` made `./scripts/check` fail on the tester's machine only).
- **Verified on the machine that reported it** (packaged build, Hyprland 0.56.2, two monitors):
  log `top offset 30 px (from hyprland) on DP-2`, `X11 window type: dock`; hover opens the ears
  (80x24 → 232x24, still centred); panel visible on another workspace. Gate green (`./scripts/check`),
  package smoke test green.
- **Still open:** click, right-click → Esci and a real `#?` are the human's to try (no pointer-click
  tool on Hyprland here); the 15-minute endurance only means something now that the panel is on
  screen. `[overlay] monitor` is not in the settings file or the PyCharm page yet: `BUDDY_MONITOR`
  only, because the plugin's page would drop a key it doesn't know.

## 2026-10-15 17:00: v0.1.2 (main)

- **Landed:** `fix/overlay-hyprland` merged into `main` at the user's request (a9f420e), after the
  user tested it on Omarchy (clean reinstall, works). CI run 38751943599 green. It brings the 0.1.1
  report fixes plus the monitor-by-name placement and the Hyprland pin (c808339). Version 0.1.1 →
  **0.1.2** for a downloadable release; the user moves on to testing on Windows. Gate: brain 262,
  notch 42, plugin 48, overlay 117, eval 99.1.
- **Still open:** delete the merged branches (the agent's delete was refused by the permission
  check; the commands were given to the user). Human: Windows test, G17, G13, G11. G16.

## 2026-10-15 16:00: 0.1.1 tester report fixed (branch fix/overlay-hyprland)

- **From** `~/Downloads/codebuddy-0.1.1-report.md` (Omarchy, Hyprland 0.56.2, packaged 0.1.1).
  Six bugs, all fixed:
  1. `QT_QPA_PLATFORM=wayland;xcb` (a distro's fallback chain) kept the panel on Wayland. Now only
     a single platform counts as a choice.
  2. The bundle's `LD_LIBRARY_PATH` broke the system `hyprctl` (offset 0). `desktop.child_env`
     gives back PyInstaller's `*_ORIG` to the probes and the brain, and a failing probe now logs
     its stderr.
  3. `app.placement` never passed the config's `top_offset`. `configured` is now required, and a
     test goes through `app.placement`.
  4. and 5. Hyprland gives an override-redirect XWayland window no pointer events and keeps it on
     one workspace. On Hyprland the panel is now a `_NET_WM_WINDOW_TYPE_DOCK` window
     (`overlay/.../x11.py`, libX11 via ctypes, set before the first map); everywhere else it stays
     override-redirect. Sway would tile a dock and centre a floating window, so it can't be dock
     everywhere. `BUDDY_X11_WINDOW=dock|override` overrides.
  6. `#! teoria` with a space works in the brain and the plugin; an unknown `#!word` gets an
     editor hint (`EditorHints` service). Shebangs are excluded.
- **Why CI missed them:** the e2e ran from source and on Sway, and nothing touched the panel with
  a pointer. New: `scripts/smoke_bundle_desktop.py` runs the packaged overlay with a fake
  `hyprctl` (package job, Linux), and `e2e_wayland.py` now moves a virtual pointer (`wlrctl` +
  `swaymsg seat - cursor`): hover → ears, click → open; it also uses `QT_QPA_PLATFORM=wayland;xcb`.
  (wlrctl destroys its device at once, so `scripts/wl_pointer.py` keeps a
  zwlr_virtual_pointer_v1 alive; the demo is sampled from when the pill shows, as XWayland can
  take 5 s to start.) CI run 38746072727 green on every job; screenshots
  `docs/screenshots/overlay/ci-sway-pointer-{peek,expanded}.png` (opened: cursor on the pill,
  panel under swaybar). The package smoke test passed in the real PyInstaller build (offset 30
  from the fake hyprctl, clean LD_LIBRARY_PATH, dock set, config 64 used).
- **Numbers:** brain 262, plugin 48, overlay 112 (floors raised); notch 42; eval 99.1.
- **Still open:** Hyprland itself is not in CI. G17 human check with the next build (hover,
  click, workspaces, the "panel no longer drawn after 15 min" observation). G16.

## 2026-10-15 14:10: v0.1.1 (main)

- **Landed:** `feat/settings` (with `fix/overlay-wayland`) merged into `main` at the user's request
  (9385c04). Version 0.1.0 → **0.1.1** (patch: the user asked for a small step) in the brain,
  overlay, plugin, notch client id, packaging and install guides; CI no longer hardcodes the
  version (globs). Gate green: 257 / 42 / 45 / 93, eval 99.1.
- **Still open:** G16; Human: G17, G15, G13, G11.

## 2026-10-15 13:40: Wayland/top-bar fix + settings page (branches fix/overlay-wayland, feat/settings)

- **From a tester's report** (Omarchy/Hyprland 0.56.2, `~/Downloads/codebuddy-wayland-report.md`):
  on native Wayland the panel never resized; under XWayland it opened under the layer-shell bar
  (unclickable); the tiling WM tiled it. Fixed in the overlay for any compositor, no user config:
  Wayland + XWayland → Qt on `xcb`; on xcb the window is override-redirect (never tiled, moved or
  decorated); top offset = `BUDDY_TOP_OFFSET` > `[overlay] top_offset` > compositor
  (`hyprctl -j monitors` reserved top, `swaymsg` workspace rect) > Qt work area (GNOME/KDE/X11).
  `install-desktop-entry.sh` keeps an edited entry as `.bak`. New CI job **e2e-wayland**: Sway
  headless + swaybar, real geometry via `xwininfo`, screenshots via `grim`. Run 38724146815 green
  on all jobs; panel at y = 23 (bar height), centred, 80x24 → 232x24 → 520x380, log "top offset
  23 px (from sway)". Screenshots downloaded and opened: `docs/screenshots/overlay/ci-sway-{hidden,
  peek,expanded}.png`.
- **Settings** (decision 2026-10-15): `config.toml` owned by the brain (`buddy/settings.py`,
  `keys.py`, `providers.py`), PyCharm page Settings → Tools → CodeBuddy (`CodeBuddyConfigurable`,
  `BrainRequests` on its own socket, never on the EDT). Answers: Claude Code (default) /
  OpenRouter (key) / OpenAI-compatible server; hint engines: list + model + key; `allow_remote`
  for any non-loopback address (brain refuses to start otherwise); hints never to OpenRouter.
  Protocol v0 + `settings_get/settings_set/settings/models_get/models` (new types, no bump).
  `LocalModel` → `OpenAIModel` (auth header, optional sampling, "model @ host" for remote).
- **Live runs:** the page against a real brain (`LiveSettingsTest`, -Pe2e): loads, the brain
  refuses a remote URL without `allow_remote`, saves with it; PNG opened and fixed twice (key fields
  collapsed, path too wide, Claude model kept after switching provider):
  `docs/screenshots/plugin/settings-page.png`. Brain with a remote-style engine (Qwen3-Coder-30B-A3B
  on llama.cpp, reached as `http://localtest.me:8080`, a hostname the brain treats as another
  machine; my sandbox can't reach the Mac's own LAN IP): refused to start without `allow_remote`
  (exit 2, clear message); with it, `#?` first token 267 ms, total 1697 ms, footer
  "Qwen3-Coder-30B-A3B @ localtest.me:8080"; hint 244 / 764 ms. Engine and brain stopped.
- **Numbers:** tests brain 207 → 257, plugin 30 → 45, overlay 58 → 93, notch 42; floors raised.
  Mutations caught: no network check (4), hint fallback to the cloud (5), key echoed (2), placement
  ignoring the bar (2), no override-redirect (1).
- **Still open:** G16 (Qwen as answers provider rewrote the student's line: evals per provider).
  Human: G17 (settings page in real PyCharm, OpenRouter key, WireGuard to the Mac, Hyprland check),
  G15, G13, G11. Scratch folder `~/Library/Caches/codebuddy-live` (test token/config) left in place.

## 2026-10-15 13:50: v0.1.0 released (main)

- **Landed:** `feat/cross-platform` merged into `main` at the user's request (0d81117); tag `v0.1.0`;
  CI run 38714216496 green (gate ×3, e2e, package ×2, draft release). Release published as a
  **pre-release** with install notes per OS:
  https://github.com/TheNemesis47/CodeBuddy/releases/tag/v0.1.0. Assets: Linux tar.gz 100 MB,
  Windows zip 68 MB, plugin zip 59 kB.
- **Still open:** G15 (real Linux/Windows machines, signing), G13, G11 (Human). No LICENSE yet.

## 2026-10-15 11:30: Linux and Windows (branch feat/cross-platform, from main)

- **Decision:** `docs/decisions.md` 2026-10-15: the Mac keeps the Swift notch; Linux and Windows get
  `overlay/` (Python + PySide6-Essentials), a `notch`-role client on protocol v0 (no protocol change).
- **Landed:**
  - `overlay/`: frameless, always-on-top, no-focus Qt window at the top centre of the primary
    screen; hidden pill → peek → expanded with the notch's sizes and timings; Sprout (QPainter
    port) in every state; streamed markdown (code in a real monospace font); hint peek with the
    70-char preview, click to open; silent reconnect with 1→15 s backoff on a thread
    (`websockets`); right-click → *Esci*; `--demo`, `--demo --snapshots DIR`, brain-mode
    `--snapshots`; `--start-brain CMD` for the launchers.
  - `protocol/scenarios/`: 12 behaviour scenarios replayed by **both** `notch` (`ScenarioTests.swift`)
    and `overlay` (`test_scenarios.py`). Mutation check: a broken expectation fails Swift; dropping
    messages fails 5 Python scenarios.
  - Brain: `BUDDY_HOME` from platformdirs (same path on macOS), `claude` via `shutil.which`
    (`claude.exe`/`.cmd`), POSIX mode bits only on POSIX, explicit UTF-8 everywhere (Windows
    defaults to cp1252), schemas found inside a frozen build, `buddy serve --stub TEXT`.
  - Plugin: `BrainConfig` used the macOS folder on every OS (it would never have found the token
    on Linux/Windows); now platformdirs-equivalent. Downloads PyCharm 2026.2.3 when there is no
    local install.
  - `scripts/check` OS-aware (notch macOS only, overlay everywhere); ratchet counts
    `overlay_tests` and skips notch off macOS. `scripts/e2e_overlay.py` (`--bundle` for packages).
  - `packaging/build.py` (PyInstaller onedir brain + overlay, launchers `CodeBuddy.cmd` /
    `codebuddy.sh` + `.desktop` + Sprout icon, plugin zip, INSTALL docs; smoke-tests the bundle);
    `INSTALL.md`, `docs/install/{windows,linux,macos}.md`.
  - `.github/workflows/ci.yml` (closes G9), `.gitattributes` (LF for scripts).
- **Numbers:** tests brain 202 → 203, notch 42 (40 + 2 scenario tests), plugin 26 → 30, overlay
  **58** (new floor `overlay_tests`). Packages: Linux 100 MB `.tar.gz`, Windows 68 MB `.zip`.
- **CI runs:** 38707988352: Linux and macOS green, Windows red (`JsonTest` compared a path with
  `/`). 38709298204: all green, but the Windows snapshots drew every glyph as a box (Qt
  `offscreen` has no fonts on Windows). **38710592165: all green** with native rendering on Windows
  and xcb under Xvfb on Linux: gate ×3, Linux e2e, package ×2 each with an e2e on the packaged build.
  Bugs only the runs found: the overlay's missing `--start-brain` argument (bundle e2e), the
  Windows path test, the tofu snapshots.
- **Snapshots (downloaded from run 38710592165 and opened):**
  `docs/screenshots/overlay/ci-linux-demo-states.png` and `ci-windows-demo-states.png` (8 states
  each, stacked: pill, peek, streaming, done with footer, peek ✓, pill, hint peek with preview,
  hint open; Sprout seed → half → full; DejaVu/Segoe UI text, monospace code),
  `ci-linux-e2e-answer.png` (e2e from source) and `ci-windows-bundle-e2e-answer.png` (e2e on the
  packaged Windows build: «Alla riga 6 il file **non viene chiuso**…», footer `stub · primo token
  33 ms · totale 207 ms`). Artifacts: `overlay-snapshots-{Linux,Windows,macOS}`, `e2e-linux`,
  `bundle-check-{Linux,Windows}`, `codebuddy-{Linux,Windows}`.
- **E2E on the Linux runner:** `overlay: answer_end id=e2e-1792055258 model=stub
  first_token_ms=20 total_ms=163` and its snapshot; passes.
- **Still open:** **G15 (Human):** run the packages on real Windows/Linux desktops with PyCharm and
  `claude`, decide on code signing (SmartScreen warns), push `v0.1.0` and publish the draft
  release CI makes. Small: the close button's `⌃` is tiny on Linux; code *blocks* aren't shaded on
  Windows (inline code is); on Wayland the panel position is up to the compositor (decisions.md).
  G13, G14, G11, G12, G8 unchanged.

## 2026-10-15 13:00: first push to GitHub (main)

- **Landed:** public remote https://github.com/TheNemesis47/CodeBuddy, `main` pushed (174 files),
  `core.hooksPath .githooks` set, so `pre-push` runs `./scripts/check` (it ran: OK).
- **History rewritten, with the user's explicit OK:** commit `2cc77ed` had added the IDE sandbox
  `ide-pycharm/.intellijPlatform/` (~1.7k files, 345 of 348 MB of history: caches and logs).
  `git filter-repo --invert-paths --path ide-pycharm/.intellijPlatform/` on all refs; pack
  36 MB -> 1.4 MB; the tree of `main` is unchanged (same tree hash), commit hashes changed.
  Backup of the old history: `~/Documents/CodeBuddy-backups/codebuddy-2026-10-15-before-filter.bundle`.
- **Numbers:** unchanged: tests 196/40/26, eval score 99.1, MVP 6/6.
- **Still open:** G9 CI can start now (the remote exists). No LICENSE file yet: the repo is public
  but "all rights reserved" until the user picks one (Human). Human: G13, G11.

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
  agent: G7 (G5 merged into main together with this branch on 2026-10-15).
## 2026-10-15 10:10: G5 latency (branch feat/brain-latency)

- **Landed:** brain `latency.py`: every `answer_end` (triggers, hints, `buddy ask`) appends
  `{id, kind, model, first_token_ms, total_ms, input_tokens}` to `$BUDDY_HOME/latency.jsonl`
  (errors aren't logged; an unwritable log only warns). `buddy latency [--file] [--kind] [--last N]`
  prints first-token p50/p90/min/max (linear interpolation). The server also logs each answer's
  latency. Bench: `ide-pycharm/.../LiveLatencyBenchTest.kt` (excluded from the gate like every
  `Live*Test`) puts a `#?` above an anchor line in 10 different `brain/src/buddy/*.py` files, runs
  `TriggerDispatcher.prepare` on PSI and sends through `BrainConnection`, then waits for the
  brain's latency line before the next one. `scripts/bench-latency LABEL [serve options]` starts
  brain (8797), notch and `scripts/bench_answers.py` (records answer texts), runs it, prints
  `buddy latency`, stops all three. Output in `bench/LABEL/` (git-ignored).
- **Numbers:** brain tests 116 → 137 (19 in `test_latency.py`, 2 in `test_server.py`); floor
  raised. Notch 40, plugin 26 unchanged (the bench is a live test, not counted).
- **Runs** (10 `#?` each, Claude Sonnet 5.5 through `claude -p`, first token as measured by the
  brain in `answer_end.first_token_ms`):

  | Run | Setup | p50 | p90 | min | max | input tokens |
  |---|---|---:|---:|---:|---:|---|
  | `sonnet-baseline` | `buddy serve --model sonnet` (unchanged) | **1572 ms** | 1896 ms | 1397 ms | 2097 ms | 1656–3167 |
  | `sonnet-repeat` | same, run again right after | **1634 ms** | 1947 ms | 1492 ms | 2967 ms | similar |

  p50 ≤ 3 s in both, so none of the fallbacks (Haiku for `#?`, a warm process, a shorter prompt
  or map, prompt caching) was tried: nothing changed, so there are no before/after answers to
  compare. **Chosen setup: Sonnet for `#?` and `#!teoria`, one `claude -p` per trigger, as before.**
  Yesterday's 1.6–5.8 s spread (15 `buddy ask` runs) didn't show up today; total time per answer is
  5.7–6.7 s. Criterion 1 met (and 3: under 8k as Claude counts tokens; the brain's own estimate
  was 678–1636, about half, because the CLI adds overhead). MVP criteria **6/6**.
- **Notch:** 10 snapshots per run, all 10 answers recorded in full. Looked at
  `docs/screenshots/notch/bench-latency-answer.png` (from `bench/sonnet-baseline/shots/`): the
  `O_EXCL` answer, footer `claude-sonnet-5-5 · primo token 2097 ms · totale 6717 ms`, correct and
  in Italian, refers to "riga 19/20". **Defect:** answers are ~1000–1200 characters, the panel
  scrolls to the end, and the first line sits half-hidden under the header. Not fixed here (notch
  UI, not latency): shorter answers (system prompt) or scrolling to the top on `answer_end`.
- **What the number doesn't cover:** the brain's clock starts when the trigger arrives; Enter →
  PSI → localhost send in a real, busy IDE isn't in it (G13). The fixture project is small, so the
  project map is smaller than in a real project.
- **Processes:** every brain, notch and recorder the script started was stopped (`pgrep` empty);
  Gradle daemon stopped with `./gradlew --stop`.
- **Still open:** Human: G13 (try `#?` in your PyCharm, then `buddy latency --kind question`),
  G11, G12, G8. Agent: notch first-line clipping above, G7 boundaries, G10 evals.

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
