# CodeBuddy on Linux

Needs x86-64 and glibc 2.34+ (Ubuntu 22.04+, Debian 12+, Fedora 36+). Works best on X11; on
Wayland the panel opens but the compositor may not place it exactly at the top centre.

1. Install and log in to the Claude Code CLI (see INSTALL.md); `claude -p "ciao"` must answer.
2. Unpack and add it to your applications menu:

   ```sh
   mkdir -p ~/.local/opt && tar -xzf CodeBuddy-linux-0.1.0.tar.gz -C ~/.local/opt
   ~/.local/opt/CodeBuddy-linux-0.1.0/install-desktop-entry.sh
   ```

3. Start **CodeBuddy** from the menu, or run `~/.local/opt/CodeBuddy-linux-0.1.0/codebuddy.sh`. A
   small black pill with a seed appears at the top centre of the screen; the brain starts with it.
4. Install the plugin in PyCharm: Settings → Plugins → ⚙ → *Install Plugin from Disk…* →
   `codebuddy-pycharm-0.1.0.zip` → restart.
5. In a `.py` file write `#? cosa fa questa riga?` and press Enter.

Quit: right-click the panel → *Esci da CodeBuddy*. If Qt complains about the `xcb` platform plugin,
install `libxcb-cursor0` (Debian/Ubuntu) or `xcb-util-cursor` (Fedora). Logs: run `codebuddy.sh`
from a terminal; the panel alone: `overlay/codebuddy-overlay --demo`.
