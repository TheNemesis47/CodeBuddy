import os
from pathlib import Path

# Headless by default (macOS/Windows dev and CI); Linux CI runs under Xvfb with QT_QPA_PLATFORM=xcb.
# A Wayland session, or the fallback chain a distro sets for it ("wayland;xcb"), is not a choice
# of platform for the tests, and on Wayland the compositor owns the window's geometry: these tests
# need one where the app sets its own, so fall back to offscreen (see desktop.qt_platform_for).
_chosen = os.environ.get("QT_QPA_PLATFORM", "").strip()
if not _chosen or ";" in _chosen or _chosen == "wayland":
    os.environ["QT_QPA_PLATFORM"] = "offscreen"

REPO = Path(__file__).resolve().parents[2]
SCENARIOS = REPO / "protocol" / "scenarios"
EXAMPLES = REPO / "protocol" / "examples"
