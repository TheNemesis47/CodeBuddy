# Security policy

CodeBuddy is a personal tool running on one Mac. It handles:

- **A local network service**: the brain listens on `127.0.0.1:8790` (WebSocket). Any process on
  the Mac can reach it, and so can **any web page open in the browser** (browsers allow WebSockets
  to localhost).
- **Source code**: excerpts of the open project are sent to the local model and, on explicit
  triggers, to Claude through the `claude` CLI.
- **Credentials**: none stored by CodeBuddy. Claude auth belongs to Claude Code's own login.

## Required protections (part of G1/G2)

- Bind to `127.0.0.1` only, never `0.0.0.0`.
- Every client sends a `hello` with a random token, created on first run in
  `~/Library/Application Support/CodeBuddy/token` (mode 600). Connections without it are closed.
- Reject any WebSocket whose `Origin` header is set, because real clients (plugin, notch) send
  none and browsers always do.
- The `claude` call runs with `--tools ""`: code and questions are text in, text out, with no tool
  execution.
- Proactive events never go to the cloud while `proactive_cloud = false` (test in G6).

## Reporting

Personal project: open a note in `docs/gaps.md` with the tag `security`.

## Current limitations

Nothing above is implemented yet: `brain/` doesn't exist (G2). Until it does, there is no exposed
surface.
