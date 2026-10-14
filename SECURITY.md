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

Implemented in `brain/` (G2): loopback bind, Origin refusal, token hello with a 5 s timeout,
600 token file, `--tools ""`. Each one has a test that fails when the protection is removed
(checked by mutation on 2026-10-14). Not done yet: the `proactive_cloud` setting itself (G6;
today `idle` is simply ignored), and rate limiting of hello attempts (low risk on loopback).
