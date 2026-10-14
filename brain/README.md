# brain

The CodeBuddy daemon. See `../SPEC.md` and `../AGENTS.md`.

```sh
uv run buddy ask src/x.py:12                 # line 12 holds a `#? …` or `#!teoria …` trigger
uv run buddy ask src/x.py:12 "why …"         # explicit question about line 12
uv run buddy ask src/x.py:12 --show-prompt   # print the prompt, call nothing (offline)
uv run buddy serve                           # WebSocket on 127.0.0.1:8790/ws
uv run pytest                                # offline tests (fake models)
```
