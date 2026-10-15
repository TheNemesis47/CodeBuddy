# Development

## One-time setup

| Step | Who | Command |
|---|---|---|
| Activate Xcode (needed by `notch`) | **Human** (sudo) | `sudo xcode-select -s /Applications/Xcode.app` |
| Enable the repo's git hooks | agent | `git config core.hooksPath .githooks` |
| Claude Code logged in with the subscription | **Human** | `claude` → `/login` (already done on this Mac) |
| Python toolchain | — | `uv` 0.12 and Python 3.14 are installed |
| Plugin toolchain | — | JDK 21 is installed; Gradle comes through the wrapper |

## Local models (for proactive hints)

The engines are managed by AIStatus (`~/Work/ai-menubar`) or by hand. The model choice is explained
in `~/Work/testM5/MODELS.md`.

- llama.cpp: `llama serve` on `:8080` (OpenAI API), model `Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf`
  from `~/Documents/AI/models/gguf/`.
- MTPLX: `mtplx serve` on `:8000` (OpenAI + Anthropic API).
- Check which one is up: `curl -s localhost:8080/v1/models; curl -s localhost:8000/v1/models`.
- Proactive hints use whichever is up (Qwen3-Coder-30B-A3B preferred). Without a local engine there
  are no hints; `BUDDY_PROACTIVE_CLOUD=1 uv run buddy serve` lets them use Claude instead.
- Live idle run through the plugin's code: `BUDDY_PORT=… BUDDY_HOME=… ./gradlew test --rerun -Pe2e
  --tests '*LiveBrainE2ETest.testIdleReachesTheBrain'` with the brain and notch running.

## Running the parts

The commands per module are in SPEC.md → Commands. Brain: see `brain/README.md`. Notch and
plugin exist once G3 and G4 are closed.

`uv run pytest -m live` with `BUDDY_LIVE=1` runs the one test that calls the real `claude` CLI.

## Driving it as an agent

- Brain: `uv run buddy ask file.py:LINE "question"` prints the answer. No UI or IDE needed.
- Notch: `swift run CodeBuddy --demo --snapshots /tmp/shots` saves a PNG of every state (no Screen
  Recording permission needed); look at them. `screencapture` needs that permission (G12).
- Plugin: `./gradlew test` (18 tests, IDE fixture with Python PSI), `./gradlew buildPlugin` →
  `build/distributions/codebuddy-pycharm-0.1.0.zip`, `./gradlew runIde` opens a sandbox PyCharm.
- End to end without a human: start `buddy serve` and `swift run CodeBuddy --snapshots /tmp/e2e`
  with the same `BUDDY_PORT`/`BUDDY_HOME`, then
  `cd ide-pycharm && ./gradlew test -Pe2e --tests '*LiveBrainE2ETest*'`. The notch log shows
  `answer_end …` and `/tmp/e2e/answer-<id>.png` is the result. Typing in the real IDE is G13.
