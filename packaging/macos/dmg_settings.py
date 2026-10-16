# dmgbuild settings for CodeBuddy-macos-<version>.dmg (packaging/build.py passes the -D values).
# dmgbuild writes the window layout itself, so no Finder/AppleScript is needed (works on CI).
import os.path

app = defines["app"]  # noqa: F821  (dmgbuild injects `defines`)
plugin = defines["plugin"]  # noqa: F821
files = [app] + ([plugin] if plugin else [])
symlinks = {"Applications": "/Applications"}
background = defines["background"]  # noqa: F821  (its @2x twin is picked up for Retina)
window_rect = ((200, 120), (660, 440))
icon_size = 96
text_size = 13
show_status_bar = False
show_tab_view = False
show_toolbar = False
show_pathbar = False
show_sidebar = False
icon_locations = {"CodeBuddy.app": (165, 195), "Applications": (495, 195)}
if plugin:
    icon_locations[os.path.basename(plugin)] = (330, 345)
format = "UDZO"
