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
| `idle` | ide → brain | User paused typing: the brain may peek with one hint |
| `review` | ide → brain | User saved the file (Ctrl+S / Cmd+S): the brain may review the whole file |
| `project_map` | ide → brain | File tree + signatures, sent when its hash changes |
| `answer_start` / `answer_delta` / `answer_end` | brain → notch | One streamed answer (`kind`: question, theory, hint, review) |
| `error` | brain → client | Failure; `id` is null when not tied to a request |
| `settings_get` / `settings_set` | ide → brain | The PyCharm settings page reads / saves the settings (and sets API keys) |
| `settings` | brain → ide | The saved settings, which keys are set (never the keys), overrides |
| `models_get` / `models` | ide ↔ brain | The models a provider offers, for the settings page |

The connection is refused when the `Origin` header is present (browsers always send it, our clients
never do) or when the hello token is wrong. See SECURITY.md.

The settings messages and `review` were added in v0 without a bump: they are new types, and no
existing message changed, so older clients keep working (an older notch ignores an
`answer_start` whose `kind` it doesn't know, `review` included). The brain answers them on the same socket, with the
request's `id`.

Changing a schema in a way that breaks old messages bumps `v` (ask first, AGENTS.md).
