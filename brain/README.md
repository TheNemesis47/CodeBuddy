# brain

The CodeBuddy daemon. See `../SPEC.md` and `../AGENTS.md`.

```sh
uv run buddy ask src/x.py:12                 # line 12 holds a `#? …` or `#!teoria …` trigger
uv run buddy ask src/x.py:12 "why …"         # explicit question about line 12
uv run buddy ask src/x.py:12 --show-prompt   # print the prompt, call nothing (offline)
uv run buddy serve                           # WebSocket on 127.0.0.1:8790/ws
uv run buddy eval --repeat 3                 # score answers on ../evals/cases (see evals/README.md)
uv run pytest                                # offline tests (fake models)
```

Proactive hints: the plugin sends `idle` after 4 s without typing. The brain answers with one short
hint (`prompts/hint.md`) from the local engine it finds on `127.0.0.1:8080` (llama.cpp) or `:8000`
(MTPLX) via `/v1/models`, at most once every 3 minutes and only when the code changed. With no
local engine there is no hint. `BUDDY_PROACTIVE_CLOUD=1` is the only way a hint can use Claude.
