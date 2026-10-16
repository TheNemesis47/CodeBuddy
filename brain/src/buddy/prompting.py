"""Turn a request (kind, text, code context) into a system + user prompt. Pure functions only.

Templates live in `prompts/*.md` so they can be read and diffed like code.
"""

from dataclasses import dataclass, field, replace
from functools import cache
from importlib.resources import files
from string import Template
from typing import Literal

from buddy.triggers import TriggerKind

type RequestKind = TriggerKind | Literal["hint", "review"]

# ~8k input tokens at ~4 chars/token (SPEC.md, criterion 3). Over budget, the project map goes
# first, then the window shrinks around the marked line.
MAX_USER_CHARS = 28_000
# Hints run on the local engine, where prefill is the latency: ~3k tokens, and no project map.
MAX_HINT_USER_CHARS = 12_000
MAX_MAP_FILES = 200
MAX_LINE_CHARS = 400  # minified code: one line could blow the budget alone


@dataclass(frozen=True)
class ProjectMap:
    tree: list[str]
    symbols: dict[str, list[str]] = field(default_factory=dict)


@dataclass(frozen=True)
class Request:
    kind: RequestKind
    text: str
    file: str
    line: int
    language: str
    window_start: int
    window_code: str
    scope: str | None = None
    project: ProjectMap | None = None


@dataclass(frozen=True)
class Prompt:
    system: str
    user: str

    def estimated_tokens(self) -> int:
        return (len(self.system) + len(self.user)) // 4


@cache
def _template(name: str) -> Template:
    return Template(files("buddy").joinpath("prompts", f"{name}.md").read_text(encoding="utf-8"))


def build_prompt(request: Request, answer_language: str = "italiano") -> Prompt:
    hint = request.kind == "hint"
    template = {"hint": "hint", "review": "review"}.get(request.kind, "system")
    system = _template(template).substitute(language=answer_language)
    budget = MAX_HINT_USER_CHARS if hint else MAX_USER_CHARS
    user = _render_user(request, with_map=not hint)
    if len(user) > budget:
        user = _render_user(request, with_map=False)
    while len(user) > budget and request.window_code.count("\n") > 0:
        request = _drop_farthest_line(request)
        user = _render_user(request, with_map=False)
    return Prompt(system, user)


def _render_user(request: Request, *, with_map: bool) -> str:
    if request.kind == "hint":
        head = (
            f"The student stopped typing in `{request.file}` at line {request.line}, marked `→`. "
            "Give one nudge."
        )
    elif request.kind == "review":
        head = (
            f"The student saved `{request.file}`; the cursor is at line {request.line}, marked "
            "`→`. Review the file."
        )
    elif request.kind == "question":
        head = _template("question").substitute(
            file=request.file, line=request.line, text=request.text
        )
    else:
        topic = request.text or f"the concept used at line {request.line}"
        head = _template("theory").substitute(file=request.file, line=request.line, topic=topic)

    parts = [head.strip(), _render_code(request)]
    if request.scope and request.scope not in request.window_code:
        parts.append(f"Enclosing function/class:\n```{request.language}\n{request.scope}\n```")
    if with_map and request.project:
        parts.append(_render_map(request.project, request.file))
    return "\n\n".join(parts) + "\n"


def _render_code(request: Request) -> str:
    rows = []
    for offset, text in enumerate(request.window_code.splitlines()):
        number = request.window_start + offset
        marker = "→" if number == request.line else " "
        if len(text) > MAX_LINE_CHARS:
            text = text[:MAX_LINE_CHARS] + " …"
        rows.append(f"{marker}{number:>5} | {text}")
    return f"`{request.file}`:\n```{request.language}\n" + "\n".join(rows) + "\n```"


def _render_map(project: ProjectMap, current_file: str) -> str:
    tree = project.tree[:MAX_MAP_FILES]
    more = len(project.tree) - len(tree)
    lines = ["Project files:", *(f"- {path}" for path in tree)]
    if more > 0:
        lines.append(f"- … and {more} more")
    if symbols := project.symbols.get(current_file):
        lines += [f"Top-level symbols in `{current_file}`:", *(f"- `{s}`" for s in symbols)]
    return "\n".join(lines)


def _drop_farthest_line(request: Request) -> Request:
    """Remove the window line farthest from the marked line; the scope goes too (it's in budget
    trouble already, and the window still shows the code around the line)."""
    lines = request.window_code.splitlines()
    start = request.window_start
    end = start + len(lines) - 1
    if request.line - start >= end - request.line:
        lines.pop(0)
        start += 1
    else:
        lines.pop()
    return replace(request, window_start=start, window_code="\n".join(lines), scope=None)
