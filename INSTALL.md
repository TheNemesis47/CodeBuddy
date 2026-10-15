# Installing CodeBuddy (testers)

CodeBuddy has three parts: the **brain** (a local daemon that asks Claude or a local model), the
**panel** where answers appear (the notch on a Mac, a small overlay at the top of the screen on
Linux and Windows) and the **PyCharm plugin** that sends your `#?` questions.

| OS | Download | Guide |
|---|---|---|
| Windows 10/11 (x64) | `CodeBuddy-windows-0.1.0.zip` | [docs/install/windows.md](docs/install/windows.md) |
| Linux (x64, glibc ≥ 2.34: Ubuntu 22.04+, Fedora 36+) | `CodeBuddy-linux-0.1.0.tar.gz` | [docs/install/linux.md](docs/install/linux.md) |
| macOS 14+ | from source (Swift notch) | [docs/install/macos.md](docs/install/macos.md) |

Every OS needs:

1. **Claude Code CLI, logged in.** Install it (see https://claude.com/claude-code), run `claude`
   once and log in with your subscription. `claude -p "ciao"` in a terminal must answer. The brain
   finds `claude` on your `PATH` (`claude.exe` or `claude.cmd` on Windows).
2. **PyCharm 2026.2 or newer** with the plugin: Settings → Plugins → ⚙ → *Install Plugin from
   Disk…* → `codebuddy-pycharm-0.1.0.zip` (in the download) → restart PyCharm.
3. *Optional:* a local model for proactive hints, `llama-server` (llama.cpp) on port 8080, e.g.
   `llama-server -m Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf --port 8080 -ngl 999 -fa on -c 16384 --jinja`.
   Without it there are no proactive hints; `#?` and `#!teoria` still work.

Then, in a Python file: write `#? perché questo non funziona?` on its own line and press Enter. The
panel at the top of the screen opens and the answer streams in. Hover the panel to peek at it, click
to open it, right-click → *Esci da CodeBuddy* to quit (Linux/Windows).

Data: the brain keeps its token and `latency.jsonl` in `~/.local/share/CodeBuddy` (Linux),
`%LOCALAPPDATA%\CodeBuddy` (Windows) or `~/Library/Application Support/CodeBuddy` (macOS). It only
listens on 127.0.0.1; see SECURITY.md. The builds are **not code-signed** yet: Windows SmartScreen
and some Linux desktops will warn the first time.
