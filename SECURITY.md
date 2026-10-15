# Security policy

CodeBuddy is a personal tool running on one Mac. It handles:

- **A local network service**: the brain listens on `127.0.0.1:8790` (WebSocket). Any process on
  the Mac can reach it, and so can **any web page open in the browser** (browsers allow WebSockets
  to localhost).
- **Source code**: excerpts of the open project are sent to the hint engine (local by default)
  and, on explicit triggers, to the answers provider the user picked: Claude through the `claude`
  CLI (default), OpenRouter, or their own OpenAI-compatible server.
- **Credentials**: API keys for OpenRouter or the user's own servers, only if they set one, in
  `keys.json` next to the token (mode 600) or in env vars. Claude auth belongs to Claude Code's
  own login.

## Required protections (part of G1/G2)

- Bind to `127.0.0.1` only, never `0.0.0.0`.
- Every client sends a `hello` with a random token, created on first run in
  `~/Library/Application Support/CodeBuddy/token` (mode 600). Connections without it are closed.
- Reject any WebSocket whose `Origin` header is set, because real clients (plugin, notch) send
  none and browsers always do.
- The `claude` call runs with `--tools ""`: code and questions are text in, text out, with no tool
  execution.
- Proactive events never go to the cloud while `proactive_cloud = false` (`BUDDY_PROACTIVE_CLOUD`,
  default off). By default the hint engine is only looked for on `127.0.0.1:8080` and `:8000`.
- **Settings (2026-10-15).** The settings file (`config.toml`) can point answers and hints at
  other machines. Any address that is not this computer needs `network.allow_remote = true`; the
  brain refuses to start, and the settings page refuses to save, otherwise. Hints never go to
  OpenRouter. The startup log says where the code may go, and the panel's footer shows the host
  of a remote engine. HTTP clients ignore proxy env vars (`trust_env=False`).
- API keys never go in the config file, in a message, or in a log: the settings page only learns
  whether a key is set. The settings messages travel on the same authenticated loopback socket.

## Reporting

Personal project: open a note in `docs/gaps.md` with the tag `security`.

## Current limitations

Implemented in `brain/` (G2): loopback bind, Origin refusal, token hello with a 5 s timeout,
600 token file, `--tools ""`. Each one has a test that fails when the protection is removed
(checked by mutation on 2026-10-14). `proactive_cloud` (G6): `idle` goes to the local engine or
nowhere; `brain/tests/test_server.py` proves the cloud model never sees it while the setting is
off (engine up, down or failing), and an unconditional cloud fallback fails 4 tests (mutation,
2026-10-14). Settings (2026-10-15): `brain/tests/test_settings.py`, `test_providers.py` and the
settings tests in `test_server.py`; mutations caught: no network check (4 fail), hints falling
back to the answers provider (5), a key echoed in the settings reply (2). The brain's own server
still binds `127.0.0.1` only, never configurable. Not done yet: rate limiting of hello attempts
(low risk on loopback); TLS to a remote engine is up to the user (WireGuard, or an https URL).
