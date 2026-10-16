import json
import os
import sys
from pathlib import Path

import pytest
from conftest import FIXTURES

from buddy.claude_cli import ClaudeCliModel, build_command, find_claude, parse_line
from buddy.models import Done, ModelError, TextDelta
from buddy.prompting import Prompt

PROMPT = Prompt(system="Sei un tutor.", user="SECRET-CODE domanda")


def test_command_disables_every_side_effect_and_keeps_code_out_of_argv() -> None:
    cmd = build_command(PROMPT, "sonnet")
    assert cmd[:2] == ["claude", "-p"]
    assert cmd[cmd.index("--tools") + 1] == ""
    assert cmd[cmd.index("--setting-sources") + 1] == ""
    for flag in ("--strict-mcp-config", "--disable-slash-commands", "--no-session-persistence"):
        assert flag in cmd
    assert "--bare" not in cmd  # would ignore the subscription login
    assert not any("SECRET-CODE" in part for part in cmd)


def test_parse_fixture_stream() -> None:
    events = [
        e
        for line in (FIXTURES / "claude_stream.jsonl").read_text(encoding="utf-8").splitlines()
        if (e := parse_line(line)) is not None
    ]
    assert events == [
        TextDelta("`open(path)` "),
        TextDelta("non viene chiuso."),
        Done("claude-sonnet-5-5", 2 + 617 + 100, 8),
    ]


def test_parse_ignores_garbage() -> None:
    assert parse_line("not json") is None
    assert parse_line("[1, 2]") is None


def test_error_result_raises() -> None:
    with pytest.raises(ModelError, match="rate limited"):
        parse_line(json.dumps({"type": "result", "is_error": True, "result": "rate limited"}))


def _fake_claude(tmp_path: Path, body: str) -> list[str]:
    """A stand-in `claude`: records stdin and argv, then runs `body`. Run as `python script`, not
    through a shebang, so it works the same on Windows."""
    script = tmp_path / "fake_claude.py"
    script.write_text(
        "import sys, pathlib\n"
        f"pathlib.Path({str(tmp_path / 'stdin.txt')!r}).write_text(sys.stdin.read())\n"
        f"pathlib.Path({str(tmp_path / 'argv.txt')!r}).write_text('\\n'.join(sys.argv))\n" + body
    )
    return [sys.executable, str(script)]


async def _collect(model: ClaudeCliModel) -> list:
    return [event async for event in model.stream(PROMPT)]


@pytest.mark.anyio
async def test_model_streams_from_the_subprocess_with_prompt_on_stdin(tmp_path: Path) -> None:
    fixture = FIXTURES / "claude_stream.jsonl"
    exe = _fake_claude(tmp_path, f"sys.stdout.write(open({str(fixture)!r}).read())\n")
    events = await _collect(ClaudeCliModel("sonnet", executable=exe))
    assert events[-1] == Done("claude-sonnet-5-5", 719, 8)
    assert (tmp_path / "stdin.txt").read_text(encoding="utf-8") == PROMPT.user
    assert "SECRET-CODE" not in (tmp_path / "argv.txt").read_text(encoding="utf-8")


@pytest.mark.anyio
async def test_model_reports_a_crash(tmp_path: Path) -> None:
    exe = _fake_claude(tmp_path, "sys.stderr.write('not logged in'); sys.exit(1)\n")
    with pytest.raises(ModelError, match="not logged in"):
        await _collect(ClaudeCliModel("sonnet", executable=exe))


@pytest.mark.anyio
async def test_missing_executable() -> None:
    with pytest.raises(ModelError, match="not installed"):
        await _collect(ClaudeCliModel("sonnet", executable=["/nonexistent/claude"]))


@pytest.mark.live
@pytest.mark.anyio
@pytest.mark.skipif(os.environ.get("BUDDY_LIVE") != "1", reason="set BUDDY_LIVE=1 to call Claude")
async def test_live_claude() -> None:
    events = await _collect(ClaudeCliModel("sonnet"))
    assert isinstance(events[-1], Done)


def test_claude_is_looked_up_on_path(monkeypatch: pytest.MonkeyPatch) -> None:
    found = str(Path("bin") / "claude.exe")
    monkeypatch.setattr("shutil.which", lambda name, path=None: found if path is None else None)
    assert find_claude() == [found]
    assert build_command(PROMPT, "sonnet", find_claude())[0] == found
    monkeypatch.setattr("shutil.which", lambda name, path=None: None)
    assert find_claude() == ["claude"]  # unresolved: the spawn fails with "not installed"


def test_claude_is_found_where_the_installer_puts_it_when_path_is_short(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CodeBuddy.app started from the Dock has PATH=/usr/bin:/bin:/usr/sbin:/sbin."""
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    claude = bin_dir / ("claude.exe" if os.name == "nt" else "claude")
    claude.write_text("#!/bin/sh\n", encoding="utf-8")
    claude.chmod(0o755)
    found = find_claude(home=tmp_path, env={})
    assert Path(found[0]).parent == bin_dir
