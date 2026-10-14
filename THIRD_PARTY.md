# Third-party code

## Coucou (Louis-CFM/coucou), MIT

Parts of `notch/` are adapted from https://github.com/Louis-CFM/coucou (MIT licence, © Louis Raillé).
Only code is used. The Coucou name, the Mochi character, icons, sounds and media are © Louis Raillé,
all rights reserved (`LICENSE-ASSETS.md` in that repo), and are **not** used here.

Source: commit `3290a410f891002959f40411b03e0854b3200b54` (2026-10-14). Files adapted:

| CodeBuddy file | Coucou source | What changed |
|---|---|---|
| `notch/Sources/CodeBuddyKit/IslandStateMachine.swift` | `NotchBuddy/Sources/App/IslandStateMachine.swift` | 5 states → 3 (hidden/peek/expanded); greeting and voice removed; timers through an injectable `Scheduler`; answers drive the island |
| `notch/Sources/CodeBuddyKit/IslandGeometry.swift` (`IslandScreenGeometry`) | `NotchBuddy/Sources/CoucouKit/IslandScreenGeometry.swift` | public API; the resting layout is replaced by `IslandLayout` |
| `notch/Sources/CodeBuddyKit/Markdown.swift` | `NotchBuddy/Sources/App/ChatMarkdown.swift` | renamed; tracks unclosed code fences while streaming; no regex |
| `notch/Sources/CodeBuddy/MarkdownView.swift` | `NotchBuddy/Sources/App/ChatMarkdownView.swift` | own palette; URL check inlined (http/https only) |
| `notch/Sources/CodeBuddy/IslandShape.swift` | `IslandShape` in `NotchBuddy/Sources/App/IslandRootView.swift` | the concave-ear variant is redrawn flush with the screen top |
| `notch/Sources/CodeBuddy/IslandWindowController.swift` (`IslandPanel`, panel setup, pointer polling) | `NotchBuddy/Sources/App/IslandWindowController.swift` | only the panel, level, collection behaviour, click-through and screen geometry; everything else dropped |

The MIT licence text is in `notch/LICENSES/MIT-louis-raille.txt`.

Not used, and never to be used: the Coucou name, the Mochi character and its drawings, icons,
sounds and any other media (all rights reserved, `LICENSE-ASSETS.md` upstream). Sprout
(`SproutView.swift`) is original.
