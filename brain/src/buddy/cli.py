"""`buddy ask` (one answer in the terminal, no UI), `buddy serve` (the daemon) and `buddy eval`
(score answers on evals/cases)."""

import argparse
import asyncio
import os
import sys
import uuid
from pathlib import Path

from buddy.answers import Message, run_answer
from buddy.context import build_context
from buddy.prompting import Request, build_prompt
from buddy.triggers import ParsedTrigger, parse_trigger_line

DEFAULT_PORT = 8790
LANGUAGES = {
    ".py": "python",
    ".kt": "kotlin",
    ".swift": "swift",
    ".js": "javascript",
    ".ts": "typescript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="buddy", description="CodeBuddy brain")
    sub = parser.add_subparsers(dest="command", required=True)

    ask = sub.add_parser("ask", help="answer one question about a line of code, in the terminal")
    ask.add_argument("target", help="FILE:LINE")
    ask.add_argument("question", nargs="*", help="omit it to use the trigger written at LINE")
    ask.add_argument("--theory", action="store_true", help="ask for theory instead of an answer")
    ask.add_argument("--model", default="sonnet", help="claude model alias (default: sonnet)")
    ask.add_argument("--show-prompt", action="store_true", help="print the prompt; call nothing")

    serve = sub.add_parser("serve", help="run the daemon on 127.0.0.1")
    serve.add_argument("--port", type=int, default=int(os.environ.get("BUDDY_PORT", DEFAULT_PORT)))
    serve.add_argument("--model", default="sonnet", help="claude model alias (default: sonnet)")

    ev = sub.add_parser("eval", help="score answers on evals/cases (hints on the local engine)")
    ev.add_argument("--cases", type=Path, help="default: evals/cases above the current folder")
    ev.add_argument("--only", action="append", metavar="ID", help="run only this case (repeatable)")
    ev.add_argument(
        "--triggers",
        action="store_true",
        help="also run #? / #!teoria cases on Claude (uses quota)",
    )
    ev.add_argument("--model", default="sonnet", help="claude model alias for triggers")
    ev.add_argument(
        "--judge", choices=["none", "local", "claude"], default="none", help="LLM judge on rubrics"
    )
    ev.add_argument("--label", default="", help="a note stored in the result")
    ev.add_argument("--out", type=Path, help="default: evals/results/<date>.json")
    ev.add_argument(
        "--rescore",
        type=Path,
        metavar="RESULT",
        help="re-check the answers saved in RESULT against the current cases; calls no model",
    )

    args = parser.parse_args(argv)
    if args.command == "ask":
        return _ask(args)
    if args.command == "eval":
        return asyncio.run(_eval(args))
    return _serve(args)


def build_request(path: Path, line: int, question: str, theory: bool) -> Request:
    """The `ask` equivalent of what the plugin sends: trigger + context from the file on disk."""
    source = path.read_text(encoding="utf-8")
    if question:
        trigger = ParsedTrigger("theory" if theory else "question", question)
    else:
        lines = source.splitlines()
        found = parse_trigger_line(lines[line - 1]) if 0 < line <= len(lines) else None
        if found is None:
            raise SystemExit(
                f"buddy: no `#?` or `#!teoria` trigger at {path}:{line}; "
                "pass a question after FILE:LINE"
            )
        trigger = found
    language = LANGUAGES.get(path.suffix, "text")
    context = build_context(source, line, language)
    return Request(
        kind=trigger.kind,
        text=trigger.text,
        file=str(path),
        line=line,
        language=language,
        window_start=context.window_start,
        window_code=context.window_code,
        scope=context.scope,
    )


def _parse_target(target: str) -> tuple[Path, int]:
    file, sep, line = target.rpartition(":")
    if not sep or not line.isdigit():
        raise SystemExit(f"buddy: expected FILE:LINE, got {target!r}")
    path = Path(file)
    if not path.is_file():
        raise SystemExit(f"buddy: no such file: {file}")
    return path, int(line)


def _ask(args: argparse.Namespace) -> int:
    from buddy.claude_cli import ClaudeCliModel

    path, line = _parse_target(args.target)
    request = build_request(path, line, " ".join(args.question).strip(), args.theory)
    prompt = build_prompt(request)
    if args.show_prompt:
        print(f"--- system ---\n{prompt.system}\n--- user ---\n{prompt.user}")
        print(f"~{prompt.estimated_tokens()} tokens", file=sys.stderr)
        return 0

    async def emit(message: Message) -> None:
        if message["type"] == "answer_delta":
            print(message["text"], end="", flush=True)

    final = asyncio.run(
        run_answer(
            ClaudeCliModel(args.model),
            prompt,
            id=str(uuid.uuid4()),
            kind=request.kind,
            title=request.text,
            emit=emit,
        )
    )
    print()
    if final["type"] == "error":
        print(f"buddy: {final['message']}", file=sys.stderr)
        return 1
    print(
        f"[{final['model']} · first token {final['first_token_ms']} ms · total "
        f"{final['total_ms']} ms · tokens in {final['tokens']['in']} out "
        f"{final['tokens']['out']}]",
        file=sys.stderr,
    )
    return 0


async def _eval(args: argparse.Namespace) -> int:
    import json

    from buddy.claude_cli import ClaudeCliModel
    from buddy.evals import (
        CaseResult,
        EvalRun,
        find_evals_dir,
        load_cases,
        rescore,
        result_path,
        summarize,
    )
    from buddy.local import LocalModel, detect_local_model

    evals_dir = find_evals_dir(Path.cwd())
    cases_dir = args.cases or (evals_dir / "cases" if evals_dir else None)
    if cases_dir is None or not cases_dir.is_dir():
        print("buddy: no evals/cases folder found; pass --cases", file=sys.stderr)
        return 2
    cases = load_cases(cases_dir)
    if args.only:
        cases = [c for c in cases if c.id in set(args.only)]
    if args.rescore:
        saved = json.loads(args.rescore.read_text(encoding="utf-8"))
        summary = summarize(
            rescore(saved, cases), cases, label=saved.get("label", ""), engines=saved["engines"]
        )
        summary["date"] = saved["date"]
        (args.out or args.rescore).write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"total {saved['total']} → {summary['total']} · {summary['checks']}")
        return 0
    local = await detect_local_model()
    if local is None:
        print("buddy: no local engine on :8080 or :8000 (hints need one)", file=sys.stderr)
        return 2
    trigger_model = ClaudeCliModel(args.model) if args.triggers else None
    judge = None
    if args.judge == "local":
        judge = LocalModel(local.base_url, local.name, max_tokens=200)
    elif args.judge == "claude":
        judge = ClaudeCliModel(args.model)

    async def progress(result: CaseResult) -> None:
        failed = [c.name for c in result.checks if not c.passed]
        note = result.error or (f"failed: {', '.join(failed)}" if failed else "all checks pass")
        judged = f" · judge {result.judge.get('score')}" if result.judge else ""
        print(f"{result.score:4.2f}  {result.id:<28} {note}{judged}", flush=True)

    run = EvalRun(local, trigger_model, judge, progress=progress)
    results = await run.run(cases)
    engines = {"hint": local.name, "hint_engine": local.base_url}
    if trigger_model:
        engines["trigger"] = trigger_model.name
    if judge:
        engines["judge"] = judge.name
    summary = summarize(results, cases, label=args.label, engines=engines)
    out = args.out or result_path((evals_dir or cases_dir.parent) / "results")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"total {summary['total']} over {summary['cases']} cases · {summary['checks']}")
    if summary["judge_mean"] is not None:
        print(f"judge mean {summary['judge_mean']} / 5")
    print(f"saved {out}" + ("" if summary["complete"] else " (incomplete: not for the ratchet)"))
    return 0


def _serve(args: argparse.Namespace) -> int:
    import logging

    import uvicorn

    from buddy.auth import buddy_home, load_or_create_token
    from buddy.claude_cli import ClaudeCliModel
    from buddy.hints import proactive_cloud_from_env
    from buddy.server import create_app

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    token_path = buddy_home() / "token"
    token = load_or_create_token(token_path)
    print(f"buddy: token in {token_path}", file=sys.stderr)
    proactive_cloud = proactive_cloud_from_env(os.environ)
    where = "local engine, else Claude" if proactive_cloud else "local engine only"
    print(f"buddy: proactive hints → {where}", file=sys.stderr)
    app = create_app(ClaudeCliModel(args.model), token, proactive_cloud=proactive_cloud)
    # Loopback only, never configurable (SECURITY.md).
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="info")
    return 0
