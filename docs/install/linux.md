# CodeBuddy on Linux

Needs x86-64 and glibc 2.34+ (Ubuntu 22.04+, Debian 12+, Fedora 36+, Arch). Works on X11 and on
Wayland (GNOME, KDE, Hyprland, Sway and other wlroots compositors); see "Wayland and top bars"
below.

1. Install and log in to the Claude Code CLI (see INSTALL.md); `claude -p "ciao"` must answer.
2. Unpack and add it to your applications menu:

   ```sh
   mkdir -p ~/.local/opt && tar -xzf CodeBuddy-linux-0.1.1.tar.gz -C ~/.local/opt
   ~/.local/opt/CodeBuddy-linux-0.1.1/install-desktop-entry.sh
   ```

3. Start **CodeBuddy** from the menu, or run `~/.local/opt/CodeBuddy-linux-0.1.1/codebuddy.sh`. A
   small black pill with a seed appears at the top centre of the screen; the brain starts with it.
4. Install the plugin in PyCharm: Settings → Plugins → ⚙ → *Install Plugin from Disk…* →
   `codebuddy-pycharm-0.1.1.zip` → restart.
5. In a `.py` file write `#? cosa fa questa riga?` and press Enter.

Quit: right-click the panel → *Esci da CodeBuddy*. If Qt complains about the `xcb` platform plugin,
install `libxcb-cursor0` (Debian/Ubuntu), `xcb-util-cursor` (Fedora, Arch). Logs: run
`codebuddy.sh` from a terminal; the panel alone: `overlay/codebuddy-overlay --demo`.

## Wayland and top bars

The panel handles these by itself; nothing to configure on most desktops:

- **Wayland:** a Wayland app can't place or (on wlroots compositors) resize its own window, so the
  panel runs through XWayland (`QT_QPA_PLATFORM=xcb`), where it can. It needs XWayland, which every
  mainstream desktop has. To force something else, set `QT_QPA_PLATFORM` yourself.
- **Tiling window managers** (Hyprland, Sway, i3…): the panel is an unmanaged X11 window
  (override-redirect), so it is never tiled, moved, dimmed or given borders, and needs no window
  rules. It shows on every workspace.
- **A bar at the top** (Waybar, Omarchy's bar, swaybar, Hyprpanel…): on wlroots compositors
  XWayland is not told about the bar, so the panel asks the compositor how much space it reserves:
  `hyprctl -j monitors` on Hyprland, `swaymsg` on Sway. GNOME and KDE tell Qt directly. The log
  says where the offset came from (`top offset 30 px (from hyprland)`).

On any other compositor with a top bar (river, niri, labwc…), if the panel opens under the bar and
can't be clicked, set the bar's height by hand: in PyCharm → Settings → Tools → CodeBuddy → "Space
above it" (saved as `top_offset` under `[overlay]` in the settings file), or for one run
`BUDDY_TOP_OFFSET=32 ./codebuddy.sh`. The env var wins over the file, and both win over the
automatic value. Restart CodeBuddy after changing it.

`install-desktop-entry.sh` keeps a menu entry you edited as `codebuddy.desktop.bak` before
writing the new one.
