# Implementation decisions

Newest first. One entry per non-obvious decision.

## 2026-10-16: One model does everything; Ctrl+S asks for a review

**Decision.** The model picked in the settings (Claude Code, OpenRouter or the user's own
OpenAI-compatible server, local or not) answers every request: `#?`, `#!teoria`, the proactive
hint after `idle`, and the new `review` sent when the user presses Ctrl+S / Cmd+S in a Python
file. The `[hints]` section (hint engine list, `proactive_cloud`, `BUDDY_PROACTIVE_CLOUD`,
`BUDDY_HINTS_API_KEY`) is gone; an old file's `[hints]` table is ignored, and an old settings
page's `hints` / `hints_server` fields are accepted and dropped. Reviews have their own gate (only
a changed file, at most one every 30 s); a trigger pauses hints and reviews, a review pauses
hints. The plugin listens to the `SaveAll`/`SaveDocument` actions, not to document saves, so
PyCharm's autosave never asks for a review. A review peeks with a preview like a hint, it doesn't
open the panel.
**Why.** The user asked for it (2026-10-16: "il modello selezionato, che sia locale o che sia in
cloud, è quello che deve fare tutto"). Two models meant two setups and hints that silently did
nothing without llama.cpp running. Ctrl+S is the user's own gesture, so it may reach the cloud
model like a trigger. Peeking keeps a frequent Ctrl+S from covering the code.
**Supersedes** "Proactive suggestions stay local by default" (2026-10-14) and the routing part of
"How proactive hints are routed" (2026-10-14). With Claude picked, idle hints now send the code
around the cursor to Claude, at most once every 3 minutes (SECURITY.md).
**Alternatives.** A per-feature model setting: the user rejected two models. Opening the panel
on every review: too intrusive for a key pressed this often.
**Rollback.** `git revert` of the branch `feat/one-model-and-save-review`.

## 2026-10-15: The panel's monitor comes from the compositor, matched to Qt by connector name

**Decision.** `panel_placement` asks the compositor for its monitors (`hyprctl -j monitors`,
`swaymsg`), picks the focused one (or `BUDDY_MONITOR`), and the window follows the Qt screen with
the same name, looked up again on every placement. Qt's `primaryScreen()` is never used while the
compositor answers. On Hyprland the panel also asks to be pinned (`hl.dsp.window.pin`, retried on
a timer until `hyprctl clients` confirms it).
**Why.** XWayland publishes its own X11 layout, and it need not match the compositor's. On the
0.1.1 tester's two monitors (one rotated) XWayland called the vertical monitor primary and put it
at `0,0`, while Hyprland had the main one there: centring on Qt's primary asked for `x=500`, which
Hyprland read in its own space as `-580`, so the panel sat outside every screen — invisible, and
out of reach of the pointer. That layout can also change mid-session, because XWayland restarts
when its last client exits, which is why nothing reproduced it on demand. Connector names are the
one thing both sides agree on. Pinning is needed because Hyprland ties even a dock window to the
workspace it opened on, and ignores `_NET_WM_DESKTOP = 0xFFFFFFFF` and `_NET_WM_STATE_STICKY`
(both measured on 0.56.2).
**Alternatives.** Placing the window with `hyprctl dispatch movewindowpixel` after every resize:
compositor-specific, an IPC round trip per state change, and it fights the app's own geometry.
Matching monitors to screens by coordinates (0.1.1): that is exactly what the two layouts disagree
about. `_NET_WM_DESKTOP`/`STICKY` for the pin: ignored.
**Rollback.** `panel_placement` returning `Panel()` puts the panel back on Qt's primary; removing
the `keep_on_every_workspace` call leaves it on one workspace.

## 2026-10-15: Settings in PyCharm, written by the brain; remote engines need explicit consent

**Decision.** The settings live in one TOML file the brain owns (`config.toml` in the user's
config folder, `$BUDDY_CONFIG`). The PyCharm page (Settings → Tools → CodeBuddy) reads and saves it
through the brain with new protocol messages (`settings_get`, `settings_set`, `models_get`; v0, new
types only). Answers can come from Claude Code (default), OpenRouter, or any OpenAI-compatible
server; hint engines are a list of addresses. Precedence: flags > env vars > file > defaults.
**Why.** One settings page that works on macOS, Linux and Windows, written once in the plugin the
student already has open; the brain stays the only process that talks to models (boundaries), and
it checks every value before saving. A file keeps the settings readable and editable by hand.
**The posture change.** Until now nothing left the computer except explicit triggers to Claude. A
user's own server on another machine (their Mac over WireGuard) is legitimate, so it is allowed,
but only with `network.allow_remote`, and the brain refuses to start on a file that names a remote
address without it, rather than guess. Hints never go to OpenRouter, and still never to the answers
provider while `proactive_cloud` is off. Keys live in `keys.json` (mode 600) or env vars, never in
the file or in a message. What does not move: the brain's own server binds `127.0.0.1` only.
**Alternatives.** A settings window in the panel: two implementations (Swift and PySide6). Env vars
only: no UI, and they don't survive a desktop launcher. Writing the file from the plugin: the plugin
would have to know the brain's rules and paths, and the boundaries say it only talks to the brain.
**Known limit.** Smaller models follow "never write the fix" less well than Claude (a live run on
Qwen3-Coder rewrote the student's line); the page says so, and evals per provider are open (G16).

## 2026-10-15: Linux and Windows get a Python overlay; the Mac keeps the Swift notch

**Decision.** The Mac keeps `notch/` (Swift, AppKit: it sits in the real notch). Linux and Windows
get a new `overlay/` module in Python + PySide6: a frameless, always-on-top panel centred at the
top of the primary screen, with the same three states (hidden → peek → expanded), the same Sprout
moods, the same hint peek and the same timings. It talks to the brain with protocol v0 as a
`notch` client, so the protocol does not change. The behaviour both clients must share is written
once as JSON scenarios in `protocol/scenarios/`, replayed by the Swift tests and by the overlay
tests. The brain needs no fork: `BUDDY_HOME` comes from `platformdirs` (unchanged on macOS),
`claude` is found on `PATH` (`claude.exe`/`.cmd` on Windows). **Why.** Testers on Linux and
Windows can't run AppKit; Qt is the one toolkit with a frameless always-on-top window, a
WebSocket client and offscreen rendering (for CI snapshots) on both, and Python matches the brain.
**Alternatives.** Rewriting the notch in Qt for all three OSes (rejected: the Mac notch integration
is the product's best part on the Mac); Electron/Tauri (rejected: a second language and runtime);
a tray icon only (rejected: no place to stream an answer). **Limits.** On Wayland, clients can't
place their own windows: the panel may not sit exactly at the top centre (X11 and Windows are
fine). **Rollback.** Delete `overlay/`; nothing else depends on it.

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

## 2026-10-14: Proactive suggestions stay local by default (superseded 2026-10-16: one model)

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
