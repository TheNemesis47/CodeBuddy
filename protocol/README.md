# Protocol v0

JSON over WebSocket, one message per frame, on `ws://127.0.0.1:8790/ws`. Every message has
`"v": 0` and a `"type"`. Schemas live in `schemas/<type>.json`, examples in
`examples/<type>[.variant].json`. Every example must validate against the schema of its `type`.
`scripts/check` enforces this through `brain/tests/test_protocol.py`.

| type | direction | purpose |
|---|---|---|
| `hello` | client → brain | First frame: role (`ide`/`notch`) + local token. Anything else first closes the socket |
| `welcome` | brain → client | Hello accepted |
| `trigger` | ide → brain | `#? …` (question) or `#!teoria …` (theory) with code context |
| `idle` | ide → brain | User paused typing (local hint, G6) |
| `project_map` | ide → brain | File tree + signatures, sent when its hash changes |
| `answer_start` / `answer_delta` / `answer_end` | brain → notch | One streamed answer |
| `error` | brain → client | Failure; `id` is null when not tied to a request |

The connection is refused when the `Origin` header is present (browsers always send it, our clients
never do) or when the hello token is wrong. See SECURITY.md.

Changing a schema in a way that breaks old messages bumps `v` (ask first, AGENTS.md).
