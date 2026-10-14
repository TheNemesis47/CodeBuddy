from buddy.context import MAX_SCOPE_LINES, build_context, enclosing_scope

SOURCE = """\
import json


@cache
def load(path):
    #? perché non chiude il file?
    data = json.load(open(path))
    return data


class Store:
    def get(self, key):
        return self.items[key]

    def put(self, key, value):
        self.items[key] = value
"""


def test_window_is_centered_and_clamped() -> None:
    ctx = build_context(SOURCE, 6, radius=2)
    assert ctx.window_start == 4
    assert ctx.window_code.splitlines() == SOURCE.splitlines()[3:8]
    assert build_context(SOURCE, 1, radius=2).window_start == 1


def test_line_beyond_the_file_is_clamped() -> None:
    ctx = build_context(SOURCE, 999, radius=1)
    assert ctx.window_code.splitlines()[-1] == "        self.items[key] = value"


def test_empty_source() -> None:
    assert build_context("", 3).window_code == ""


def test_scope_is_the_function_with_its_decorator() -> None:
    scope = enclosing_scope(SOURCE, 6)
    assert scope is not None
    assert scope.splitlines()[0] == "@cache"
    assert scope.splitlines()[-1] == "    return data"


def test_scope_is_the_innermost_method() -> None:
    assert (
        enclosing_scope(SOURCE, 16)
        == "    def put(self, key, value):\n        self.items[key] = value"
    )


def test_top_level_line_has_no_scope() -> None:
    assert enclosing_scope(SOURCE, 1) is None


def test_broken_code_falls_back_to_indentation() -> None:
    broken = "def half(x:\n    y = x +\n    return y\n\nz = 1\n"
    assert enclosing_scope(broken, 2) == "def half(x:\n    y = x +\n    return y"
    assert enclosing_scope(broken, 5) is None


def test_huge_scope_is_dropped() -> None:
    body = "\n".join("    x = 1" for _ in range(MAX_SCOPE_LINES + 5))
    assert enclosing_scope(f"def big():\n{body}\n", 3) is None


def test_non_python_has_no_scope() -> None:
    assert build_context("fun main() {\n  println(1)\n}\n", 2, language="kotlin").scope is None
