# CodeBuddy on macOS

Needs macOS 14+ on Apple Silicon, and the Claude Code CLI logged in (see INSTALL.md).

1. Open `CodeBuddy-macos-0.2.0.dmg` and drag **CodeBuddy** onto **Applications**.
2. Start it from Applications (or Spotlight). The build is not signed by Apple, so the first time
   macOS says it can't check it: open **System Settings → Privacy & Security**, scroll to
   "CodeBuddy was blocked", click **Open Anyway** and confirm. (Or, in a terminal:
   `xattr -dr com.apple.quarantine /Applications/CodeBuddy.app`.) This happens once.
3. Sprout appears in the notch (on a Mac without a notch: a small bar at the top centre). The app
   started the brain too; it has no Dock icon. Its log: `~/Library/Logs/CodeBuddy/brain.log`.
4. Install the plugin in PyCharm: Settings → Plugins → ⚙ → *Install Plugin from Disk…* →
   `codebuddy-pycharm-0.2.0.zip` (it's in the dmg) → restart.
5. In a `.py` file write `#? cosa fa questa riga?` and press Enter.

Quit: right-click the island → *Esci da CodeBuddy* (it stops the brain too). Start at login: System
Settings → General → Login Items → **+** → CodeBuddy.

If the island says `off`: the brain didn't start or port 8790 is taken (look at the log). If answers
fail with "claude not installed": the app looks for `claude` on PATH and in `~/.local/bin`,
`~/.claude/local`, `/opt/homebrew/bin`, `/usr/local/bin`.

## From source (developers)

```sh
cd brain && uv run buddy serve            # terminal 1: the brain
cd notch && swift run CodeBuddy           # terminal 2: the notch
```

Plugin: `cd ide-pycharm && ./gradlew buildPlugin`. The dmg: `uv run --project overlay python
packaging/build.py --plugin ide-pycharm/build/distributions/codebuddy-pycharm-0.2.0.zip`. More in
`docs/development.md`.
