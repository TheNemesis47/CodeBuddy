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

## Running the parts

The commands per module are in SPEC.md → Commands. Each one exists once its gap is closed (G2,
G3, G4).

## Driving it as an agent

- Brain: `uv run buddy ask file.py:LINE "question"` prints the answer. No UI or IDE needed.
- Notch: `swift run CodeBuddy --demo`, then `screencapture -x /tmp/notch.png` and look at the image.
- Plugin: `./gradlew runIde` opens a sandbox PyCharm. The full end-to-end check needs a human (G5).
