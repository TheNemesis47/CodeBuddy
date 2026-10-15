# overlay

CodeBuddy's panel for Linux and Windows (the Mac uses `notch/`; why: `docs/decisions.md`). A
frameless, always-on-top Qt window at the top centre of the primary screen, with the notch's three
states (hidden pill → peek → expanded), Sprout, streamed markdown answers and the hint peek. It is a
`notch`-role client of the brain over protocol v0.

```sh
uv run codebuddy-overlay                         # connect to the brain (BUDDY_PORT, BUDDY_HOME)
uv run codebuddy-overlay --demo                  # every state with a fake answer, no brain
uv run codebuddy-overlay --demo --snapshots DIR  # save a PNG of each demo state and quit
uv run codebuddy-overlay --snapshots DIR         # brain mode; saves answer-<id>.png after each answer
uv run pytest                                    # logic + scenarios + offscreen window tests
```

Layout: `protocol.py`, `island.py` (state machine + clocks), `answers.py`, `markdown.py`
(preview), `model.py`, `demo.py` are pure logic, ports of `notch/Sources/CodeBuddyKit`, and replay
the shared `protocol/scenarios`. `client.py` (WebSocket thread, silent reconnect), `sprout.py`,
`window.py` and `app.py` are the Qt side.
