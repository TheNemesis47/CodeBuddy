"""The latency log: one JSON line per finished answer in $BUDDY_HOME/latency.jsonl, and the
percentiles `buddy latency` prints from it (MVP criterion 1: first token p50 ≤ 3 s)."""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from buddy.answers import Message

log = logging.getLogger("buddy.latency")

FILE_NAME = "latency.jsonl"


class LatencyLog:
    def __init__(self, path: Path) -> None:
        self.path = path

    def record(self, final: Message, kind: str) -> None:
        """Append one line for an answer_end; errors aren't answers and aren't logged. A log that
        can't be written is reported and skipped: it must never break the answer itself."""
        if final["type"] != "answer_end":
            return
        line = {
            "id": final["id"],
            "kind": kind,
            "model": final["model"],
            "first_token_ms": final["first_token_ms"],
            "total_ms": final["total_ms"],
            "input_tokens": final["tokens"]["in"],
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(line) + "\n")
        except OSError as error:
            log.warning("latency log not written to %s: %s", self.path, error)


def read_records(path: Path) -> list[dict[str, Any]]:
    """Every well-formed line, oldest first. A missing file has no records."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    records = []
    for line in text.splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            records.append(record)
    return records


def percentile(values: list[int], p: float) -> float:
    """Linear interpolation between closest ranks (numpy's default): p50 of 10 runs is the mean
    of the 5th and 6th."""
    ordered = sorted(values)
    rank = (len(ordered) - 1) * p / 100
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (rank - low)


@dataclass(frozen=True)
class Summary:
    count: int
    p50: float
    p90: float
    min: int
    max: int
    without_text: int  # answers that ended with no text, so no first token


def summarize(records: list[dict[str, Any]]) -> Summary | None:
    """First-token percentiles over the records that have one; None when none do."""
    values = [r["first_token_ms"] for r in records if isinstance(r.get("first_token_ms"), int)]
    if not values:
        return None
    return Summary(
        count=len(values),
        p50=percentile(values, 50),
        p90=percentile(values, 90),
        min=min(values),
        max=max(values),
        without_text=len(records) - len(values),
    )
