"""Evals: score the buddy's answers on the cases in `evals/cases/` (G10).

Each case is a snippet, a cursor line and a kind (`hint`, `#?`, `#!teoria`). `buddy eval` builds
the real prompt for it (the same `build_prompt` the server uses), asks the model, and scores the
answer with deterministic checks:

- concept:  names at least one expected concept (case regexes);
- shape:    hints ≤ 3 lines with no code block, `#?` answers ≤ 15 lines (the notch is small);
- no_leak:  none of the case's forbidden regexes, i.e. it doesn't name the fix;
- no_fix:   no answer line contains a corrected line (whitespace and backticks ignored);
- language: the prose is in the language the brain asked for.

A case scores the fraction of its checks that pass; the total is their mean times 100. An optional
LLM judge grades the rubric (1 to 5) and is reported apart: it's slower and noisier, so the
ratcheted number is the deterministic total. Idea from benchkit's graders: automatic checks
first, a judge or a human only for what can't be checked.
"""

import json
import re
import time
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from buddy.context import build_context
from buddy.models import Done, Model, ModelError, TextDelta
from buddy.prompting import Prompt, Request, RequestKind, build_prompt
from buddy.triggers import parse_trigger_line

HINT_MAX_LINES = 3
QUESTION_MAX_LINES = 15
KINDS: dict[str, RequestKind] = {"hint": "hint", "#?": "question", "#!teoria": "theory"}

# Short function words, counted outside code to tell Italian prose from English prose. ("a" is
# both, so it's in neither.)
# fmt: off
_ITALIAN = frozenset({
    "il", "lo", "la", "le", "gli", "un", "una", "che", "non", "per", "con", "del", "della", "dei",
    "delle", "nel", "nella", "è", "sono", "questo", "questa", "quando", "perché", "come", "se",
    "ma", "anche", "più", "già", "cosa", "qui", "dove", "ogni", "solo",
})
_ENGLISH = frozenset({
    "the", "an", "is", "are", "and", "of", "to", "this", "that", "it", "you", "when", "because",
    "what", "here", "where", "each", "only", "but", "with", "not",
})
# fmt: on
_CODE_BLOCK = re.compile(r"```.*?(```|$)", re.S)
_INLINE_CODE = re.compile(r"`[^`\n]*`")
_WORD = re.compile(r"[^\W\d_]+", re.U)


@dataclass(frozen=True)
class Case:
    id: str
    title: str
    kind: str  # "hint" | "#?" | "#!teoria"
    line: int
    code: str
    concepts: dict[str, list[str]]
    forbidden: list[str]
    fix_lines: list[str]
    rubric: str
    language: str = "italiano"

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Case:
        return cls(
            id=data["id"],
            title=data["title"],
            kind=data["kind"],
            line=data["line"],
            code=data["code"],
            concepts=data["concepts"],
            forbidden=data.get("forbidden", []),
            fix_lines=data.get("fix_lines", []),
            rubric=data["rubric"],
            language=data.get("language", "italiano"),
        )

    @property
    def is_trigger(self) -> bool:
        return self.kind != "hint"


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    detail: str = ""


def load_cases(directory: Path) -> list[Case]:
    return [Case.from_json(json.loads(p.read_text())) for p in sorted(directory.glob("*.json"))]


def request_for(case: Case) -> Request:
    """What the plugin would send for this case: the trigger at `line`, or an idle there."""
    kind = KINDS[case.kind]
    text = ""
    if case.is_trigger:
        trigger = parse_trigger_line(case.code.splitlines()[case.line - 1])
        if trigger is None:
            raise ValueError(f"{case.id}: line {case.line} holds no trigger")
        text = trigger.text
    context = build_context(case.code, case.line, "python")
    return Request(
        kind=kind,
        text=text,
        file=f"{case.id}.py",
        line=case.line,
        language="python",
        window_start=context.window_start,
        window_code=context.window_code,
        scope=context.scope,
    )


# ---------------------------------------------------------------- deterministic checks


def _prose(answer: str) -> str:
    return _INLINE_CODE.sub(" ", _CODE_BLOCK.sub(" ", answer))


def _nonblank_lines(answer: str) -> list[str]:
    return [line for line in answer.strip().splitlines() if line.strip()]


def check_concept(case: Case, answer: str) -> Check:
    for tag, patterns in case.concepts.items():
        for pattern in patterns:
            if re.search(pattern, answer, re.I):
                return Check("concept", True, f"{tag}: /{pattern}/")
    return Check("concept", False, f"none of {sorted(case.concepts)}")


def check_shape(case: Case, answer: str) -> Check | None:
    """None when the kind has no shape rule (theory is long by design)."""
    lines = len(_nonblank_lines(answer))
    if case.kind == "hint":
        if "```" in answer:
            return Check("shape", False, "code block in a hint")
        ok = 0 < lines <= HINT_MAX_LINES
        return Check("shape", ok, f"{lines} lines (max {HINT_MAX_LINES})")
    if case.kind == "#?":
        ok = 0 < lines <= QUESTION_MAX_LINES
        return Check("shape", ok, f"{lines} lines (max {QUESTION_MAX_LINES})")
    return None


def check_no_leak(case: Case, answer: str) -> Check:
    for pattern in case.forbidden:
        if match := re.search(pattern, answer, re.I):
            return Check("no_leak", False, f"/{pattern}/ matched {match.group(0)!r}")
    return Check("no_leak", True)


def _squash(text: str) -> str:
    return re.sub(r"[\s`]", "", text)


def check_no_fix(case: Case, answer: str) -> Check:
    lines = [_squash(line) for line in answer.splitlines()]
    for fix in case.fix_lines:
        target = _squash(fix)
        if any(target in line for line in lines):
            return Check("no_fix", False, f"wrote {fix!r}")
    return Check("no_fix", True)


def detect_language(answer: str) -> str | None:
    """'italiano', 'english', or None when the prose has too few function words to tell."""
    words = [w.lower() for w in _WORD.findall(_prose(answer))]
    italian = sum(w in _ITALIAN for w in words)
    english = sum(w in _ENGLISH for w in words)
    if italian == english:
        return None
    return "italiano" if italian > english else "english"


def check_language(case: Case, answer: str) -> Check:
    found = detect_language(answer)
    return Check("language", found == case.language, f"looks {found or 'undecided'}")


def score_answer(case: Case, answer: str) -> tuple[float, list[Check]]:
    checks = [
        check_concept(case, answer),
        check_shape(case, answer),
        check_no_leak(case, answer),
        check_no_fix(case, answer),
        check_language(case, answer),
    ]
    applied = [c for c in checks if c is not None]
    return sum(c.passed for c in applied) / len(applied), applied


# ---------------------------------------------------------------- judge

JUDGE_SYSTEM = """You grade answers of a programming tutor for a student who is still learning.
The tutor must teach, not do the work: it explains and hints, it never writes the fix.
Reply with one JSON object only: {"score": N, "reason": "one short sentence"}, where N is
1 (bad), 2, 3, 4 or 5 (excellent) for how well the answer meets the rubric."""


def judge_prompt(case: Case, answer: str) -> Prompt:
    user = (
        f"Kind: {case.kind}\nRubric: {case.rubric}\n\nStudent code (cursor at line {case.line}):\n"
        f"```python\n{case.code}```\n\nTutor answer:\n<<<\n{answer}\n>>>\n"
    )
    return Prompt(JUDGE_SYSTEM, user)


def parse_judge(text: str) -> tuple[int, str] | None:
    match = re.search(r'"score"\s*:\s*([1-5])', text)
    if not match:
        return None
    reason = re.search(r'"reason"\s*:\s*"([^"]*)"', text)
    return int(match.group(1)), reason.group(1) if reason else ""


# ---------------------------------------------------------------- running


async def collect(model: Model, prompt: Prompt) -> tuple[str, int | None, str]:
    """The whole answer, its first-token ms, and the model id the provider reported."""
    started = time.monotonic()
    parts: list[str] = []
    first: int | None = None
    model_id = model.name
    async for event in model.stream(prompt):
        if isinstance(event, TextDelta) and event.text:
            if first is None:
                first = round((time.monotonic() - started) * 1000)
            parts.append(event.text)
        elif isinstance(event, Done):
            model_id = event.model
    return "".join(parts), first, model_id


@dataclass
class CaseResult:
    id: str
    kind: str
    model: str
    score: float
    checks: list[Check]
    answer: str
    first_token_ms: int | None = None
    error: str | None = None
    judge: dict[str, Any] | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "model": self.model,
            "score": round(self.score, 3),
            "checks": [
                {"name": c.name, "passed": c.passed, "detail": c.detail} for c in self.checks
            ],
            "answer": self.answer,
            "first_token_ms": self.first_token_ms,
            "error": self.error,
            "judge": self.judge,
        }


@dataclass
class EvalRun:
    hint_model: Model
    trigger_model: Model | None = None  # None: triggers are skipped (they cost Claude quota)
    judge_model: Model | None = None
    language: str = "italiano"
    progress: Callable[[CaseResult], Awaitable[None]] | None = None
    results: list[CaseResult] = field(default_factory=list)

    async def run(self, cases: Iterable[Case]) -> list[CaseResult]:
        for case in cases:
            model = self.trigger_model if case.is_trigger else self.hint_model
            if model is None:
                continue
            result = await self._run_case(case, model)
            self.results.append(result)
            if self.progress:
                await self.progress(result)
        return self.results

    async def _run_case(self, case: Case, model: Model) -> CaseResult:
        prompt = build_prompt(request_for(case), case.language)
        try:
            answer, first, model_id = await collect(model, prompt)
        except ModelError as error:
            return CaseResult(case.id, case.kind, model.name, 0.0, [], "", error=str(error))
        score, checks = score_answer(case, answer)
        result = CaseResult(case.id, case.kind, model_id, score, checks, answer, first)
        if self.judge_model is not None:
            result.judge = await self._judge(case, answer)
        return result

    async def _judge(self, case: Case, answer: str) -> dict[str, Any]:
        assert self.judge_model is not None
        try:
            text, _, model_id = await collect(self.judge_model, judge_prompt(case, answer))
        except ModelError as error:
            return {"error": str(error)}
        parsed = parse_judge(text)
        if parsed is None:
            return {"model": model_id, "error": f"unparsable: {text[:120]!r}"}
        return {"model": model_id, "score": parsed[0], "reason": parsed[1]}


def rescore(saved: dict[str, Any], cases: list[Case]) -> list[CaseResult]:
    """Re-run the deterministic checks on the answers stored in a result file, against the cases
    as they are now (when a case regex is fixed, old runs stay comparable).
    Judge grades are kept."""
    by_id = {c.id: c for c in cases}
    results = []
    for old in saved["results"]:
        case = by_id.get(old["id"])
        if case is None:
            continue
        if old.get("error"):
            score, checks = 0.0, []
        else:
            score, checks = score_answer(case, old["answer"])
        results.append(
            CaseResult(
                old["id"],
                old["kind"],
                old["model"],
                score,
                checks,
                old["answer"],
                old.get("first_token_ms"),
                old.get("error"),
                old.get("judge"),
            )
        )
    return results


def summarize(
    results: list[CaseResult], cases: list[Case], *, label: str = "", engines: dict[str, str]
) -> dict[str, Any]:
    run_ids = {r.id for r in results}
    totals: dict[str, list[int]] = {}
    for result in results:
        for check in result.checks:
            totals.setdefault(check.name, [0, 0])
            totals[check.name][0] += check.passed
            totals[check.name][1] += 1
    judged = [r.judge["score"] for r in results if r.judge and "score" in r.judge]
    total = 100 * sum(r.score for r in results) / len(results) if results else 0.0
    return {
        "date": date.today().isoformat(),
        "label": label,
        "total": round(total, 1),
        "complete": run_ids == {c.id for c in cases},
        "cases": len(results),
        "skipped": sorted({c.id for c in cases} - run_ids),
        "engines": engines,
        "checks": {name: f"{ok}/{n}" for name, (ok, n) in sorted(totals.items())},
        "judge_mean": round(sum(judged) / len(judged), 2) if judged else None,
        "results": [r.to_json() for r in results],
    }


def result_path(directory: Path, today: date | None = None) -> Path:
    """evals/results/<date>.json, then <date>-2.json, <date>-3.json … on the same day."""
    stem = (today or date.today()).isoformat()
    path = directory / f"{stem}.json"
    n = 2
    while path.exists():
        path = directory / f"{stem}-{n}.json"
        n += 1
    return path


def result_order(path: Path) -> tuple[str, int]:
    """Sort key: date, then the same-day counter (a bare <date>.json is the first)."""
    day, counter = path.stem[:10], path.stem[11:]
    return day, int(counter) if counter.isdigit() else 1


def find_evals_dir(start: Path) -> Path | None:
    for folder in (start, *start.parents):
        if (folder / "evals" / "cases").is_dir():
            return folder / "evals"
    return None
