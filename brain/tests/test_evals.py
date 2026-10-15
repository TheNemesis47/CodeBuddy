"""Offline: the eval cases are valid, and the scorer works on canned answers (no model)."""

import json
import re
from datetime import date
from pathlib import Path

import jsonschema
import pytest
from conftest import REPO, FakeModel

from buddy import cli
from buddy.evals import (
    Case,
    EvalRun,
    check_concept,
    check_language,
    check_no_fix,
    check_no_leak,
    check_shape,
    detect_language,
    find_evals_dir,
    judge_prompt,
    load_cases,
    parse_judge,
    request_for,
    result_order,
    result_path,
    score_answer,
    summarize,
)
from buddy.prompting import build_prompt
from buddy.triggers import parse_trigger_line

EVALS = REPO / "evals"
SCHEMA = json.loads((EVALS / "schema" / "case.schema.json").read_text())
CASE_FILES = sorted((EVALS / "cases").glob("*.json"))


# ---------------------------------------------------------------- the cases themselves


def test_there_are_25_to_30_cases_of_every_kind() -> None:
    cases = load_cases(EVALS / "cases")
    assert 25 <= len(cases) <= 30
    assert {c.kind for c in cases} == {"hint", "#?", "#!teoria"}


@pytest.mark.parametrize("path", CASE_FILES, ids=lambda p: p.stem)
def test_every_case_is_valid(path: Path) -> None:
    data = json.loads(path.read_text())
    jsonschema.validate(data, SCHEMA)
    case = Case.from_json(data)
    assert case.id == path.stem
    lines = case.code.splitlines()
    assert 1 <= case.line <= len(lines)
    trigger = parse_trigger_line(lines[case.line - 1])
    if case.kind == "hint":
        assert trigger is None, "a hint case must not sit on a trigger line"
    else:
        expected = "question" if case.kind == "#?" else "theory"
        assert trigger is not None and trigger.kind == expected
    for pattern in [*case.forbidden, *(p for ps in case.concepts.values() for p in ps)]:
        re.compile(pattern)
    for fix in case.fix_lines:  # a fix already in the code would fail every answer that quotes it
        assert fix.strip() not in case.code
    prompt = build_prompt(request_for(case), case.language)  # the real prompt builds
    assert "→" in prompt.user


def test_the_schema_rejects_a_bad_case() -> None:
    bad = json.loads(CASE_FILES[0].read_text()) | {"kind": "#!alt"}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, SCHEMA)


# ---------------------------------------------------------------- one check at a time


def case(**changes: object) -> Case:
    base: dict = {
        "id": "c",
        "title": "File never closed",
        "kind": "hint",
        "line": 2,
        "code": "def load(path):\n    f = open(path)\n    return f.read()\n",
        "concepts": {"resource-leak": [r"chiu[sd]", r"\bclose"]},
        "forbidden": [r"\bwith\b"],
        "fix_lines": ["with open(path) as f:"],
        "rubric": "Names the open file, not the fix.",
    }
    return Case.from_json(base | changes)


GOOD_HINT = "Alla riga 2 il file viene aperto: chi lo chiude quando la funzione è finita?"


def test_concept_passes_when_one_pattern_matches() -> None:
    assert check_concept(case(), GOOD_HINT).passed


def test_concept_fails_when_nothing_matches() -> None:
    assert not check_concept(case(), "Guarda la riga 3, cosa restituisce?").passed


def test_shape_passes_for_a_short_hint() -> None:
    result = check_shape(case(), GOOD_HINT)
    assert result is not None and result.passed


def test_shape_fails_for_a_hint_with_four_lines() -> None:
    result = check_shape(case(), "uno\ndue\ntre\nquattro")
    assert result is not None and not result.passed


def test_shape_fails_for_a_hint_with_a_code_block() -> None:
    result = check_shape(case(), "Guarda qui:\n```python\nf.close()\n```")
    assert result is not None and not result.passed
    assert "code block" in result.detail


def test_shape_fails_for_an_empty_answer() -> None:
    result = check_shape(case(), "  \n")
    assert result is not None and not result.passed


def test_shape_limits_questions_and_skips_theory() -> None:
    question = case(kind="#?")
    assert check_shape(question, "riga\n" * 15).passed  # type: ignore[union-attr]
    assert not check_shape(question, "riga\n" * 16).passed  # type: ignore[union-attr]
    assert check_shape(case(kind="#!teoria"), "riga\n" * 40) is None


def test_no_leak_passes_without_forbidden_tokens() -> None:
    assert check_no_leak(case(), GOOD_HINT).passed


def test_no_leak_fails_when_the_hint_names_the_fix() -> None:
    result = check_no_leak(case(), "Usa `with` per aprire il file.")
    assert not result.passed
    assert "with" in result.detail


def test_no_fix_passes_without_the_corrected_line() -> None:
    assert check_no_fix(case(), GOOD_HINT).passed


@pytest.mark.parametrize(
    "answer",
    [
        "Scrivi `with open(path) as f:` alla riga 2.",
        "```python\n    with open( path ) as f:\n        ...\n```",
    ],
)
def test_no_fix_fails_when_a_corrected_line_is_written(answer: str) -> None:
    assert not check_no_fix(case(), answer).passed


@pytest.mark.parametrize(
    ("answer", "language"),
    [
        (GOOD_HINT, "italiano"),
        ("The file is opened at line 2: who closes it when the function returns?", "english"),
        ("`f.close()`", None),
        (
            "Il codice `the file is open and this is not` è sbagliato perché non lo chiudi.",
            "italiano",
        ),
    ],
)
def test_detect_language_reads_prose_not_code(answer: str, language: str | None) -> None:
    assert detect_language(answer) == language


def test_language_passes_in_italian_and_fails_in_english() -> None:
    assert check_language(case(), GOOD_HINT).passed
    assert not check_language(case(), "Who closes the file when the function is done?").passed


# ---------------------------------------------------------------- scoring and results


def test_a_good_hint_passes_every_check() -> None:
    score, checks = score_answer(case(), GOOD_HINT)
    assert score == 1.0
    assert [c.name for c in checks] == ["concept", "shape", "no_leak", "no_fix", "language"]


def test_a_leaking_hint_loses_the_checks_it_fails() -> None:
    score, checks = score_answer(case(), "Il file non viene chiuso: usa `with open(path) as f:`.")
    failed = {c.name for c in checks if not c.passed}
    assert failed == {"no_leak", "no_fix"}
    assert score == pytest.approx(3 / 5)


def test_theory_is_scored_on_four_checks() -> None:
    _, checks = score_answer(case(kind="#!teoria", forbidden=[]), "Il file va chiuso.")
    assert len(checks) == 4


def test_judge_reply_is_parsed() -> None:
    assert parse_judge('ok {"score": 4, "reason": "buono"}') == (4, "buono")
    assert parse_judge('{"score": 9}') is None
    assert parse_judge("nessun json") is None
    assert "Names the open file" in judge_prompt(case(), GOOD_HINT).user


@pytest.mark.anyio
async def test_run_scores_hints_and_skips_triggers_without_a_trigger_model() -> None:
    cases = [case(), case(id="q", kind="#?", code="#? perché?\nx = open('a')\n", line=1)]
    hint_model = FakeModel((GOOD_HINT,), is_local=True)
    judge = FakeModel(('{"score": 5, "reason": "ok"}',), is_local=True)
    results = await EvalRun(hint_model, None, judge).run(cases)
    assert [r.id for r in results] == ["c"]
    assert results[0].score == 1.0
    assert results[0].judge == {"model": "fake-1", "score": 5, "reason": "ok"}
    assert "nudge" in hint_model.prompts[0].system  # the real hint prompt, not a test one
    summary = summarize(results, cases, engines={"hint": "fake"})
    assert summary["total"] == 100.0
    assert summary["complete"] is False
    assert summary["skipped"] == ["q"]
    assert summary["judge_mean"] == 5
    assert summary["checks"]["no_leak"] == "1/1"


@pytest.mark.anyio
async def test_a_model_error_scores_zero() -> None:
    results = await EvalRun(FakeModel(fail="engine down", is_local=True)).run([case()])
    assert results[0].score == 0.0
    assert results[0].error == "engine down"


def test_result_files_are_numbered_per_day(tmp_path: Path) -> None:
    day = date(2026, 10, 15)
    first = result_path(tmp_path, day)
    assert first.name == "2026-10-15.json"
    first.write_text("{}")
    second = result_path(tmp_path, day)
    assert second.name == "2026-10-15-2.json"
    names = ["2026-10-15-2.json", "2026-10-16.json", "2026-10-15.json", "2026-10-15-10.json"]
    ordered = sorted((tmp_path / n for n in names), key=result_order)
    assert [p.name for p in ordered] == [
        "2026-10-15.json",
        "2026-10-15-2.json",
        "2026-10-15-10.json",
        "2026-10-16.json",
    ]


def test_evals_dir_is_found_from_a_subfolder() -> None:
    assert find_evals_dir(REPO / "brain" / "src") == EVALS


def test_buddy_eval_without_cases_fails_cleanly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    assert cli.main(["eval"]) == 2
    assert "no evals/cases" in capsys.readouterr().err


def test_rescore_rechecks_saved_answers_against_current_cases(tmp_path: Path) -> None:
    cases_dir = tmp_path / "cases"
    cases_dir.mkdir()
    data = json.loads(CASE_FILES[0].read_text())
    (cases_dir / CASE_FILES[0].name).write_text(json.dumps(data))
    saved = {
        "date": "2026-10-01",
        "label": "old",
        "total": 0.0,
        "engines": {"hint": "x"},
        "results": [
            {"id": data["id"], "kind": data["kind"], "model": "m", "answer": "", "judge": None},
            {"id": "gone", "kind": "hint", "model": "m", "answer": "x"},
        ],
    }
    path = tmp_path / "result.json"
    path.write_text(json.dumps(saved))
    assert cli.main(["eval", "--cases", str(cases_dir), "--rescore", str(path)]) == 0
    rescored = json.loads(path.read_text())
    assert rescored["date"] == "2026-10-01"
    assert [r["id"] for r in rescored["results"]] == [data["id"]]  # removed cases drop out
    assert rescored["results"][0]["score"] < 1  # an empty answer fails the checks


@pytest.mark.anyio
async def test_repeated_hints_average_and_every_case_weighs_the_same() -> None:
    answers = iter([GOOD_HINT, "Usa `with`, il file non viene chiuso.", GOOD_HINT, GOOD_HINT])

    class Alternating(FakeModel):
        async def stream(self, prompt):  # type: ignore[override]
            self.chunks = (next(answers),)
            async for event in super().stream(prompt):
                yield event

    cases = [case(), case(id="d")]
    results = await EvalRun(Alternating(is_local=True), hint_repeat=2).run(cases)
    assert [r.id for r in results] == ["c", "c", "d", "d"]
    summary = summarize(results, cases, engines={})
    assert (summary["cases"], summary["runs"]) == (2, 4)
    # c: (1.0 + 0.8) / 2 = 0.9; d: 1.0 → (0.9 + 1.0) / 2
    assert summary["total"] == 95.0
