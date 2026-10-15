# brain

The CodeBuddy daemon. See `../SPEC.md` and `../AGENTS.md`.

```sh
uv run buddy ask src/x.py:12                 # line 12 holds a `#? …` or `#!teoria …` trigger
uv run buddy ask src/x.py:12 "why …"         # explicit question about line 12
uv run buddy ask src/x.py:12 --show-prompt   # print the prompt, call nothing (offline)
uv run buddy serve                           # WebSocket on 127.0.0.1:8790/ws (settings: config.toml)
uv run buddy latency --kind question --last 10   # first-token p50/p90/min/max
uv run buddy eval --repeat 3                 # score answers on ../evals/cases (see evals/README.md)
uv run pytest                                # offline tests (fake models)
```

Proactive hints: the plugin sends `idle` after 4 s without typing. The brain answers with one short
hint (`prompts/hint.md`) from the local engine it finds on `127.0.0.1:8080` (llama.cpp) or `:8000`
(MTPLX) via `/v1/models`, at most once every 3 minutes and only when the code changed. With no
local engine there is no hint. `BUDDY_PROACTIVE_CLOUD=1` is the only way a hint can use Claude.

Settings: `config.toml` in the user's config folder (`$BUDDY_CONFIG`; `src/buddy/settings.py`
documents every key), edited from PyCharm → Settings → Tools → CodeBuddy through the brain.
Answers come from Claude Code (default), OpenRouter or an OpenAI-compatible server; hint engines
are a list of addresses. Any address that is not this computer needs `network.allow_remote`, and
a broken file stops `buddy serve` with the reason. API keys: `keys.json` next to the token, or
`OPENROUTER_API_KEY` / `BUDDY_ANSWERS_API_KEY` / `BUDDY_HINTS_API_KEY`.

Latency: every finished answer (triggers, hints, `buddy ask`) appends one JSON line (id, kind,
model, first_token_ms, total_ms, input_tokens) to `$BUDDY_HOME/latency.jsonl`. `buddy latency`
reads it; percentiles interpolate linearly, so the p50 of 10 runs is the mean of the 5th and 6th.
