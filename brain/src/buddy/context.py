"""Build the code context around a line: a window of lines plus the enclosing function or class.

The PyCharm plugin computes the same thing from PSI and sends it in the message. This version is
for `buddy ask`, and is the reference for what "context" means.
"""

import ast
import re
from dataclasses import dataclass

WINDOW_RADIUS = 60
MAX_SCOPE_LINES = 300  # past this the scope costs more than it helps; the window is enough

_HEADER = re.compile(r"^(\s*)(async\s+def|def|class)\s")


@dataclass(frozen=True)
class CodeContext:
    window_start: int  # 1-based line number of window_code's first line
    window_code: str
    scope: str | None


def build_context(
    source: str, line: int, language: str = "python", radius: int = WINDOW_RADIUS
) -> CodeContext:
    lines = source.splitlines()
    if not lines:
        return CodeContext(1, "", None)
    line = min(max(line, 1), len(lines))
    start = max(1, line - radius)
    end = min(len(lines), line + radius)
    window = "\n".join(lines[start - 1 : end])
    scope = enclosing_scope(source, line) if language == "python" else None
    return CodeContext(start, window, scope)


def enclosing_scope(source: str, line: int) -> str | None:
    """Source of the innermost def/class containing `line`, decorators included."""
    lines = source.splitlines()
    try:
        span = _ast_scope_span(ast.parse(source), line)
    except SyntaxError:
        # The user is mid-edit more often than not: fall back to indentation.
        span = _indent_scope_span(lines, line)
    if span is None:
        return None
    first, last = span
    if last - first + 1 > MAX_SCOPE_LINES:
        return None
    return "\n".join(lines[first - 1 : last])


def _ast_scope_span(tree: ast.Module, line: int) -> tuple[int, int] | None:
    best: tuple[int, int] | None = None
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            continue
        first = min([node.lineno, *(d.lineno for d in node.decorator_list)])
        last = node.end_lineno or node.lineno
        if first <= line <= last and (best is None or first >= best[0]):
            best = (first, last)
    return best


def _indent_scope_span(lines: list[str], line: int) -> tuple[int, int] | None:
    cursor_indent = _indent_at(lines, line)
    for header in range(line, 0, -1):
        match = _HEADER.match(lines[header - 1])
        if match and (header == line or len(match.group(1)) < cursor_indent):
            header_indent = len(match.group(1))
            last = header
            for n in range(header + 1, len(lines) + 1):
                text = lines[n - 1]
                if text.strip() and len(text) - len(text.lstrip()) <= header_indent:
                    break
                if text.strip():
                    last = n
            return (header, last) if last >= line or header == line else None
    return None


def _indent_at(lines: list[str], line: int) -> int:
    """Indent of `line`, or of the nearest non-blank line above it when it is blank."""
    for n in range(line, 0, -1):
        text = lines[n - 1]
        if text.strip():
            return len(text) - len(text.lstrip())
    return 0
