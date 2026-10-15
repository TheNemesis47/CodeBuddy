# Behaviour scenarios

What every brain → UI client must do, written once and replayed by the macOS notch
(`notch/Tests/CodeBuddyKitTests/ScenarioTests.swift`) and the Linux/Windows overlay
(`overlay/tests/test_scenarios.py`). A client that changes behaviour changes a scenario here, and
both test suites see it.

Each file: `delays` (seconds: expanded → peek, peek → hidden) and `steps`, run in order on a manual
clock:

| step | meaning |
|---|---|
| `{"message": {...}}` | a brain → client frame (protocol v0), decoded by the client's own parser |
| `{"connection": "connected" \| "connecting" \| "offline"}` | the WebSocket state |
| `{"pointer": "enter" \| "leave"}`, `{"click": true}`, `{"close": true}` | the user |
| `{"advance": 20}` | the clock moves 20 s |
| `{"expect": {...}}` | any of `state` (hidden/peek/expanded), `mood` (idle/thinking/happy/worried), `peek_status`, `preview` (a hint's one-line preview or null), `text` (the current answer's text or null) |
