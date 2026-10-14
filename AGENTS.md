# AGENTS.md: guide for AI agents and contributors

CodeBuddy is a coding tutor that lives in the Mac notch. A PyCharm plugin streams what the user is
writing to a local Python daemon (`brain`). The brain asks a local model or Claude and pushes the
answers to a Swift notch app, where a character called **Sprout** shows them. It is a personal
learning tool: the user is growing from coding basics toward AI engineer, so the buddy **explains
and hints, it never writes the user's code**. Stack: Python (brain), Kotlin (PyCharm plugin), Swift
6 + SwiftUI/AppKit (notch, extracted from Coucou under MIT). **The goal is the MVP in
[SPEC.md](SPEC.md), measured by its 6 success criteria (0/6 today). After the MVP: the per-module
user stories as a checklist, plus an eval score of suggestion quality that only goes up.**
Read this file first, then the files below.

## 1. Orientation (5 minutes)

| Read | Why |
|---|---|
| `SPEC.md` | What the MVP is, protocol v0, commands, success criteria, boundaries |
| `CAPABILITY-MAP.md` | The modules, what depends on what, build order |
| `docs/development.md` | Setup (Xcode, local engines, Claude CLI), how to run each part |
| `ROADMAP.md` | Stage, headline numbers, what's next |
| `docs/gaps.md` | Every known shortfall, ranked: **the work list** |
| `docs/decisions.md` | Why things are the way they are |
| `log/devlog.md` | What the last sessions did and left open |
| `SECURITY.md` | Localhost surface, what goes to the cloud |

## 2. Map

```text
protocol/      JSON Schemas (v0) + example messages: the contract between all processes
brain/         Python daemon on 127.0.0.1:8790: context, model routing, streaming   (see brain/README.md)
notch/         Swift package: notch panel, states, Sprout, markdown answers         (G3, not created yet)
ide-pycharm/   Kotlin plugin: PSI context, #? / #!cmd triggers, idle detection      (G4, not created yet)
evals/         snippets + expected outcomes, scores suggestion quality               (G10, later)
quality/       floors.json: ratcheted numbers
scripts/       check (the gate), guards, ratchet
docs/ log/     tracking (see §8)
```

**Boundaries:** `ide-pycharm` and `notch` never talk to each other or to a model. They only talk to
`brain`, and only through messages defined in `protocol/`. The brain is the only process that
calls models. (manual: see gaps G7)

## 3. Golden rules

Ranked. A higher rule outranks a lower one and outranks feature work.

### 1. Never block or crash the IDE (outranks feature work)

The user is coding. A frozen PyCharm costs more than any hint is worth.
- No network or model work on the EDT. Every brain call is async and has a timeout.
- If the brain is down or slow, the plugin stays silent: no error dialogs, no retries in a loop.
- **Enforced by:** plugin tests in `cd ide-pycharm && ./gradlew test` (not yet working: see gaps G4).
- **Prove it:** every fix of a violation comes with a regression test that failed before.

### 2. Never edit the user's code

The buddy talks, the user writes. That is the whole teaching model.
- The plugin reads documents. The only write is the explicit "CodeBuddy: clear triggers" action
  (`ClearTriggersAction.kt`), which removes `#?` / `#!cmd` lines.
- **Enforced by:** `scripts/guard-no-edits` (fails on document-write APIs outside that action).

### 3. No Coucou name or assets

Coucou's code is MIT, but its name, the Mochi character, its icons and its sounds are © all rights
reserved.
- Code extracted from Coucou is renamed and credited in `THIRD_PARTY.md`. The character is Sprout.
- **Enforced by:** `scripts/guard-assets` (fails on "Mochi"/"Coucou" in source folders and on audio
  files under `notch/`).

### 4. Never lower the bar

- No skipped or deleted tests to get to green, no lint suppressions without a comment saying why.
- Floors in `quality/floors.json` only go up.
- **Enforced by:** `scripts/ratchet` (run by `scripts/check`).

Also binding (from SPEC.md → Boundaries): no API keys in the repo; proactive suggestions use the
local model only unless `proactive_cloud` is turned on (see `docs/decisions.md`); a protocol change
bumps `v` and updates `protocol/examples/`.

## 4. Picking work

Priorities: important infrastructure first, then low-hanging fruit toward the target, then the long
tail.

0. Read `ROADMAP.md`, then `docs/gaps.md`. Take the **highest-ranked open entry**.
1. The "Still open" bullets of the latest `log/devlog.md` entries.

When your work moves a number, update the gap entry and ROADMAP.md with the date. When a ratcheted
number rises, raise its floor in `quality/floors.json`. **Never lower a floor.**

## 5. Before you finish a task

```sh
./scripts/check
```

It runs: the guards, protocol example validation, then for each module that exists: format check,
lint (warnings as errors), typecheck and tests (brain: `ruff`, `pyright`, `pytest`; notch:
`swift build`, `swift test`; plugin: `./gradlew test buildPlugin`), then the ratchet. Modules that
don't exist yet are reported as `skip`, never as `ok`.
While iterating, run only the module you touch (e.g. `cd brain && uv run pytest -x`). The full gate
is the final word.

UI changes: run `cd notch && swift run CodeBuddy --demo`, take a screenshot
(`screencapture -x /tmp/notch.png`) and look at it. Put the path in the devlog entry.

Then append a terse entry to `log/devlog.md` (what landed, numbers, what's still open). Sessions can
end abruptly: the devlog plus a green tree is how the next agent picks up. **Keep the tree building
at every step.**

## 6. Git

- Local repo only (no remote yet). The `pre-push` hook runs `./scripts/check` once a remote exists.
  Enable hooks with `git config core.hooksPath .githooks`.
- One branch per slice: `feat/<module>-<topic>`, `fix/<module>-<topic>`, `docs/<topic>`.
- Commits: Conventional Commits in English (`feat(brain): stream claude answers`). The subject says
  what changed; the body says why and lists the tests.
- **The user merges into `main`** after reading the diff (they are learning from it). Agents never
  merge into `main` and never rewrite its history.
- Never commit secrets, `.env`, build output, or model files.
- Human only: merging, signing the notch app, real-world PyCharm tests, Sprout's final design.

## 7. Parallel agents

One agent at a time is the norm. If two ever run, each works in its own git worktree, on its own
module, and the brain port moves (`BUDDY_PORT=8791`).

## 8. Where things are tracked

- `ROADMAP.md`: stage and headline numbers. `docs/gaps.md`: ranked work list.
- `docs/decisions.md`: design decisions. `log/devlog.md`: session log (committed).
- `quality/floors.json`: ratcheted numbers. `scripts/check`: what the gate enforces.
