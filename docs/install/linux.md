# CodeBuddy on Linux

Needs x86-64 and glibc 2.34+ (Ubuntu 22.04+, Debian 12+, Fedora 36+, Arch). Works on X11 and on
Wayland (GNOME, KDE, Hyprland, Sway and other wlroots compositors); see "Wayland and top bars"
below.

1. Install and log in to the Claude Code CLI (see INSTALL.md); `claude -p "ciao"` must answer.
2. Make the AppImage executable and start it:

   ```sh
   chmod +x CodeBuddy-0.2.0-x86_64.AppImage && ./CodeBuddy-0.2.0-x86_64.AppImage
   ```

   (or right-click → Properties → "Allow executing as program", then double-click). Without FUSE
   2 on the system it still runs: `./CodeBuddy-0.2.0-x86_64.AppImage --appimage-extract-and-run`.
   For a menu entry, use your AppImage manager (Gear Lever, AppImageLauncher) or the tarball
   below.
3. A small black pill with a seed appears at the top centre of the screen; the brain starts with it.
4. Install the plugin in PyCharm: Settings → Plugins → ⚙ → *Install Plugin from Disk…* →
   `codebuddy-pycharm-0.2.0.zip` → restart.
5. In a `.py` file write `#? cosa fa questa riga?` and press Enter.

Tarball instead, with a menu entry:

```sh
mkdir -p ~/.local/opt && tar -xzf CodeBuddy-linux-0.2.0.tar.gz -C ~/.local/opt
~/.local/opt/CodeBuddy-linux-0.2.0/install-desktop-entry.sh
```

Quit: right-click the panel → *Esci da CodeBuddy*. If Qt complains about the `xcb` platform plugin,
install `libxcb-cursor0` (Debian/Ubuntu), `xcb-util-cursor` (Fedora, Arch). Logs: run
`codebuddy.sh` from a terminal; the panel alone: `overlay/codebuddy-overlay --demo`.

## Wayland and top bars

The panel handles these by itself; nothing to configure on most desktops:

- **Wayland:** a Wayland app can't place or (on wlroots compositors) resize its own window, so the
  panel runs through XWayland (`QT_QPA_PLATFORM=xcb`), where it can. It needs XWayland, which every
  mainstream desktop has. A fallback list your distro sets for the whole session, like
  `wayland;xcb` (Omarchy), doesn't stop it; to force one platform, set `QT_QPA_PLATFORM` to just
  that one (`wayland`, `xcb`…).
- **Tiling window managers** (Hyprland, Sway, i3…): the panel is never tiled, moved, dimmed or
  given borders, needs no window rules, and shows on every workspace. On Hyprland it is a dock
  window (`_NET_WM_WINDOW_TYPE_DOCK`), because Hyprland gives no mouse events to unmanaged X11
  windows, and it asks Hyprland to pin it, because a dock there belongs to the workspace it opened
  on; everywhere else it is an unmanaged (override-redirect) window. If the panel can't be
  hovered or clicked on your desktop, try the other one: `BUDDY_X11_WINDOW=dock ./codebuddy.sh` or
  `BUDDY_X11_WINDOW=override ./codebuddy.sh`, and tell us which works.
- **More than one monitor:** the panel opens on the monitor the compositor says is focused. Qt is
  no help here — XWayland publishes an X11 layout of its own, where "primary" can be any monitor
  and the origins can be shifted, which is how the panel ended up off every screen in 0.1.1 — so
  the compositor's monitor and Qt's screen are matched by connector name (`DP-2`, `eDP-1`). To
  pick another one for a run: `BUDDY_MONITOR=DP-2 ./codebuddy.sh`. The log line says which screen
  it chose and lists what Qt sees.
- **A bar at the top** (Waybar, Omarchy's bar, swaybar, Hyprpanel…): on wlroots compositors
  XWayland is not told about the bar, so the panel asks the compositor how much space it reserves:
  `hyprctl -j monitors` on Hyprland, `swaymsg` on Sway. GNOME and KDE tell Qt directly. The log
  says where the offset came from (`top offset 30 px (from hyprland)`), and if `hyprctl` or
  `swaymsg` failed, why.

On any other compositor with a top bar (river, niri, labwc…), if the panel opens under the bar and
can't be clicked, set the bar's height by hand: in PyCharm → Settings → Tools → CodeBuddy → "Space
above it" (saved as `top_offset` under `[overlay]` in the settings file), or for one run
`BUDDY_TOP_OFFSET=32 ./codebuddy.sh`. The env var wins over the file, and both win over the
automatic value. Restart CodeBuddy after changing it.

`install-desktop-entry.sh` keeps a menu entry you edited as `codebuddy.desktop.bak` before
writing the new one.
