# Capability Map: CodeBuddy

A coding companion that lives in the Mac notch, watches what you write in the IDE and teaches you
while you code. The character is **Sprout**, a seed that grows as your skill map grows.

| Module id | Responsibility | Depends on |
|---|---|---|
| `protocol` | JSON message schemas shared by every process (events, requests, responses), versioned | — |
| `brain` | Python daemon: receives IDE events, builds context, routes to the local model or Claude, streams answers, priority queue + rate limit | `protocol` |
| `ide-pycharm` | PyCharm plugin (Kotlin): reads the open file, cursor, PSI symbols and project tree; detects `#?` / `#!cmd` triggers and proactive moments; sends events | `protocol` |
| `notch` | macOS app (Swift, extracted from Coucou, MIT): notch panel, hidden/peek/expanded states, Sprout, markdown rendering of answers, study/work toggle | `protocol` |
| `growth` | Skill map, targeted exercises, AI-engineer curriculum, weekly diary (SQLite inside `brain`) | `brain` |
| `codebase-rag` | Semantic index of the project with local embeddings; replaces the v1 symbol map only if evals prove it helps | `brain`, `ide-pycharm` |
| `evals` | Fixed set of code snippets + expected outcomes; scores suggestions and answers (reuses ideas from `~/Work/testM5/benchkit`) | `brain` |

Build order: `protocol` → `brain` → `notch`, `ide-pycharm` (in parallel) → `evals` → `growth` → `codebase-rag`

The MVP (see [SPEC.md](SPEC.md)) touches only `protocol`, `brain`, `notch` and `ide-pycharm`, with
a thin slice of each.
