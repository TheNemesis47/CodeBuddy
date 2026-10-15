# CodeBuddy on Windows

1. Install and log in to the Claude Code CLI (see INSTALL.md); check that `claude -p "ciao"` answers
   in PowerShell.
2. Unzip `CodeBuddy-windows-0.1.1.zip` anywhere, e.g. `%LOCALAPPDATA%\Programs\CodeBuddy`.
3. Double-click **`CodeBuddy.cmd`**. The builds are not signed: if SmartScreen says "Windows
   protected your PC", choose *More info → Run anyway*. A small black pill with a seed appears at the
   top centre of the screen: that's the panel. It started the brain too (no console window).
4. Install the plugin in PyCharm: Settings → Plugins → ⚙ → *Install Plugin from Disk…* →
   `codebuddy-pycharm-0.1.1.zip` → restart.
5. In a `.py` file write `#? cosa fa questa riga?` and press Enter.

Quit: right-click the panel → *Esci da CodeBuddy* (it stops the brain too). Start with Windows: put
a shortcut to `CodeBuddy.cmd` in `shell:startup`.

Troubleshooting: run `brain\buddy.exe serve` in a terminal to see the brain's log, and
`overlay\codebuddy-overlay.exe --demo` to check the panel alone. If the panel says `off`, the brain
isn't running or another program uses port 8790 (set `BUDDY_PORT` for both).
