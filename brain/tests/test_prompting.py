from dataclasses import replace

from buddy.prompting import MAX_USER_CHARS, ProjectMap, Request, build_prompt

REQUEST = Request(
    kind="question",
    text="perché non chiude il file?",
    file="src/load.py",
    line=4,
    language="python",
    window_start=3,
    window_code=(
        "def load(path):\n    #? perché non chiude il file?\n    data = json.load(open(path))"
    ),
    scope=None,
)


def test_question_prompt_has_question_location_and_marked_line() -> None:
    prompt = build_prompt(REQUEST)
    assert "perché non chiude il file?" in prompt.user
    assert "`src/load.py` at line 4" in prompt.user
    assert "→    4 |     #? perché non chiude il file?" in prompt.user
    assert "     3 | def load(path):" in prompt.user


def test_system_prompt_sets_the_answer_language() -> None:
    assert "Answer in italiano." in build_prompt(REQUEST).system
    assert "Answer in English." in build_prompt(REQUEST, answer_language="English").system


def test_theory_prompt_uses_the_topic_or_the_line() -> None:
    theory = replace(REQUEST, kind="theory", text="context manager")
    assert "theory of: **context manager**" in build_prompt(theory).user
    assert "the concept used at line 4" in build_prompt(replace(theory, text="")).user


def test_scope_is_added_only_when_not_already_visible() -> None:
    inside = replace(REQUEST, scope="def load(path):")
    assert "Enclosing function/class" not in build_prompt(inside).user
    outside = replace(REQUEST, scope="class Loader:\n    pass")
    assert "Enclosing function/class" in build_prompt(outside).user


def test_project_map_lists_files_and_current_symbols() -> None:
    project = ProjectMap(["src/load.py", "src/main.py"], {"src/load.py": ["def load(path)"]})
    user = build_prompt(replace(REQUEST, project=project)).user
    assert "- src/main.py" in user
    assert "- `def load(path)`" in user


def test_over_budget_drops_map_then_trims_window_but_keeps_the_marked_line() -> None:
    lines = [f"x{n} = {'a' * 300}" for n in range(1, 201)]
    big = replace(
        REQUEST,
        line=100,
        window_start=1,
        window_code="\n".join(lines),
        project=ProjectMap([f"f{n}.py" for n in range(500)]),
    )
    user = build_prompt(big).user
    assert len(user) <= MAX_USER_CHARS
    assert "Project files" not in user
    assert "→  100 | x100 = " in user


def test_very_long_lines_are_cut() -> None:
    minified = replace(REQUEST, line=3, window_code="x = '" + "a" * 100_000 + "'")
    assert len(build_prompt(minified).user) < 2_000
