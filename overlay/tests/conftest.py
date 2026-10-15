import os
from pathlib import Path

# Headless by default (macOS/Windows dev and CI); Linux CI runs under Xvfb with QT_QPA_PLATFORM=xcb.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

REPO = Path(__file__).resolve().parents[2]
SCENARIOS = REPO / "protocol" / "scenarios"
EXAMPLES = REPO / "protocol" / "examples"
