# CodeBuddy on Windows

1. Install and log in to the Claude Code CLI (see INSTALL.md); check that `claude -p "ciao"` answers
   in PowerShell.
2. Run **`CodeBuddy-Setup-0.2.0.exe`**. It's not signed: if SmartScreen says "Windows protected
   your PC", choose *More info → Run anyway*. It installs for your user only (no admin rights) in
   `%LOCALAPPDATA%\Programs\CodeBuddy`, adds CodeBuddy to the Start menu, and can start it when
   you sign in (a checkbox, on by default) and put an icon on the desktop.
3. At the end it starts CodeBuddy: a small black pill with a seed at the top centre of the screen
   is the panel. It started the brain too (no console window).
4. Install the plugin in PyCharm: Settings → Plugins → ⚙ → *Install Plugin from Disk…* →
   `codebuddy-pycharm-0.2.0.zip` in the CodeBuddy folder (the setup can open it for you) → restart.
5. In a `.py` file write `#? cosa fa questa riga?` and press Enter.

Quit: right-click the panel → *Esci da CodeBuddy* (it stops the brain too). Uninstall: Settings →
Apps → CodeBuddy.

Portable instead: unzip `CodeBuddy-windows-0.2.0.zip` anywhere and double-click `CodeBuddy.cmd`.

Troubleshooting: run `brain\buddy.exe serve` in a terminal to see the brain's log, and
`overlay\codebuddy-overlay.exe --demo` to check the panel alone. If the panel says `off`, the brain
isn't running or another program uses port 8790 (set `BUDDY_PORT` for both).
