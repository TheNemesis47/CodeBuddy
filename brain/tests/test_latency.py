import json
from pathlib import Path
from typing import Any

import pytest

from buddy import cli
from buddy.latency import LatencyLog, Summary, percentile, read_records, summarize

END = {
    "v": 0,
    "type": "answer_end",
    "id": "a1",
    "model": "claude-haiku-5-5",
    "first_token_ms": 1200,
    "total_ms": 3400,
    "tokens": {"in": 350, "out": 120},
}


def _write(path: Path, first_tokens: list[int | None], kind: str = "question") -> None:
    log = LatencyLog(path)
    for n, first in enumerate(first_tokens):
        log.record({**END, "id": f"a{n}", "first_token_ms": first}, kind)


def test_one_answer_appends_one_json_line(tmp_path: Path) -> None:
    path = tmp_path / "home" / "latency.jsonl"  # the folder is created on first write
    LatencyLog(path).record(END, "question")
    lines = path.read_text().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == {
        "id": "a1",
        "kind": "question",
        "model": "claude-haiku-5-5",
        "first_token_ms": 1200,
        "total_ms": 3400,
        "input_tokens": 350,
    }


def test_lines_are_appended_not_overwritten(tmp_path: Path) -> None:
    path = tmp_path / "latency.jsonl"
    _write(path, [100, 200, 300])
    assert [r["first_token_ms"] for r in read_records(path)] == [100, 200, 300]


def test_errors_are_not_logged(tmp_path: Path) -> None:
    path = tmp_path / "latency.jsonl"
    LatencyLog(path).record({"v": 0, "type": "error", "id": "a1", "message": "x"}, "question")
    assert not path.exists()


def test_a_log_that_cannot_be_written_never_breaks_an_answer(tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("")
    LatencyLog(blocker / "latency.jsonl").record(END, "question")  # parent is a file: no raise


def test_missing_and_empty_files_have_no_records(tmp_path: Path) -> None:
    assert read_records(tmp_path / "nope.jsonl") == []
    empty = tmp_path / "latency.jsonl"
    empty.write_text("")
    assert read_records(empty) == []
    assert summarize([]) is None


def test_broken_lines_are_skipped(tmp_path: Path) -> None:
    path = tmp_path / "latency.jsonl"
    _write(path, [100])
    with path.open("a") as file:
        file.write("not json\n[1, 2]\n\n")
    _write(path, [300])
    assert [r["first_token_ms"] for r in read_records(path)] == [100, 300]


@pytest.mark.parametrize(
    ("values", "p", "expected"),
    [
        ([5], 50, 5),
        ([5], 90, 5),
        ([1, 2], 50, 1.5),
        ([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 50, 5.5),
        ([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 90, 9.1),
        ([10, 1, 7, 3], 0, 1),
        ([10, 1, 7, 3], 100, 10),
    ],
)
def test_percentile_interpolates_linearly(values: list[int], p: float, expected: float) -> None:
    assert percentile(values, p) == pytest.approx(expected)


def test_one_line_summary() -> None:
    summary = summarize([{"first_token_ms": 1500, "total_ms": 4000}])
    assert summary == Summary(count=1, p50=1500, p90=1500, min=1500, max=1500, without_text=0)


def test_summary_of_ten_runs_and_answers_without_text() -> None:
    firsts = (900, 2500, 1800, 3100, 2200, 1300, 5800, 2000, 2900, 1600, None)
    records: list[dict[str, Any]] = [{"first_token_ms": ms} for ms in firsts]
    summary = summarize(records)
    assert summary is not None
    assert (summary.count, summary.min, summary.max, summary.without_text) == (10, 900, 5800, 1)
    assert summary.p50 == pytest.approx(2100)
    assert summary.p90 == pytest.approx(3370)


def test_buddy_latency_with_no_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["latency", "--file", str(tmp_path / "latency.jsonl")]) == 1
    assert "no answers logged" in capsys.readouterr().out


def test_buddy_latency_with_one_line(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "latency.jsonl"
    _write(path, [1234])
    assert cli.main(["latency", "--file", str(path)]) == 0
    out = capsys.readouterr().out
    assert "1 answers" in out
    assert "p50 1234 ms" in out
    assert "p90 1234 ms" in out
    assert "min 1234 ms" in out
    assert "max 1234 ms" in out


def test_buddy_latency_percentiles_kind_and_last(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "latency.jsonl"
    _write(path, [9000, 9000], kind="theory")
    _write(path, [9000, *range(1000, 11000, 1000)])  # an old slow run, then 1000…10000
    assert cli.main(["latency", "--file", str(path), "--kind", "question", "--last", "10"]) == 0
    out = capsys.readouterr().out
    assert "10 answers" in out
    assert "p50 5500 ms" in out
    assert "p90 9100 ms" in out
    assert "min 1000 ms" in out
    assert "max 10000 ms" in out


def test_buddy_latency_reads_buddy_home_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("BUDDY_HOME", str(tmp_path))
    _write(tmp_path / "latency.jsonl", [700])
    assert cli.main(["latency"]) == 0
    assert "p50 700 ms" in capsys.readouterr().out
