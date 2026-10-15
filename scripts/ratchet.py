"""Golden rule 4: measured numbers may never drop below quality/floors.json.

Raise a floor when a number goes up; never lower one. Modules that don't exist yet are skipped.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def count_brain_tests() -> int | None:
    if not (ROOT / "brain/pyproject.toml").exists():
        return None
    out = subprocess.run(
        ["uv", "run", "pytest", "--collect-only", "-q"],
        cwd=ROOT / "brain", capture_output=True, text=True, check=False,
    ).stdout
    match = re.search(r"(\d+) tests? collected", out)
    return int(match.group(1)) if match else 0


def count_notch_tests() -> int | None:
    if not (ROOT / "notch/Package.swift").exists():
        return None
    out = subprocess.run(
        ["swift", "test", "list"], cwd=ROOT / "notch", capture_output=True, text=True, check=False,
    ).stdout
    return sum(1 for line in out.splitlines() if "/" in line)


def count_plugin_tests() -> int | None:
    """Reads the JUnit reports that `./gradlew test` (run earlier by scripts/check) writes."""
    if not (ROOT / "ide-pycharm/gradlew").exists():
        return None
    import xml.etree.ElementTree as ET

    reports = (ROOT / "ide-pycharm/build/test-results/test").glob("TEST-*.xml")
    return sum(int(ET.parse(r).getroot().get("tests", 0)) for r in reports)


def eval_score() -> float | None:
    """The total of the latest *committed* complete eval result (evals/results/<date>[-N].json).
    Uncommitted runs don't count, and neither do partial ones (e.g. hints only)."""
    if not (ROOT / "evals/cases").is_dir():
        return None
    listed = subprocess.run(
        ["git", "ls-files", "evals/results/*.json"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    ).stdout.split()

    def order(path: str) -> tuple[str, int]:
        stem = Path(path).stem
        return stem[:10], int(stem[11:]) if stem[11:].isdigit() else 1

    for path in sorted(listed, key=order, reverse=True):
        result = json.loads((ROOT / path).read_text())
        if result.get("complete"):
            return float(result["total"])
    return 0.0


MEASURES = {
    "brain_tests": count_brain_tests,
    "notch_tests": count_notch_tests,
    "plugin_tests": count_plugin_tests,
    "eval_score": eval_score,
}


def main() -> int:
    floors = json.loads((ROOT / "quality/floors.json").read_text())
    failed = False
    for name, floor in floors.items():
        measure = MEASURES.get(name)
        if measure is None:
            print(f"skip: {name} (no measure yet, see docs/gaps.md)")
            continue
        value = measure()
        if value is None:
            print(f"skip: {name} (module not created yet)")
        elif value < floor:
            print(f"FAIL: {name} = {value} < floor {floor}")
            failed = True
        else:
            hint = "  -> raise the floor" if value > floor else ""
            print(f"ok: {name} = {value} (floor {floor}){hint}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
