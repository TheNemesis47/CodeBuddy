"""`buddy ask` (one answer in the terminal, no UI), `buddy serve` (the daemon) and `buddy latency`
(first-token percentiles from the latency log)."""

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

    latency = sub.add_parser("latency", help="first-token p50/p90/min/max from the latency log")
    latency.add_argument("--file", type=Path, help="default: $BUDDY_HOME/latency.jsonl")
    latency.add_argument("--kind", choices=["question", "theory", "hint"], help="only this kind")
    latency.add_argument("--last", type=int, metavar="N", help="only the last N answers")

    args = parser.parse_args(argv)
    if args.command == "ask":
        return _ask(args)
    if args.command == "latency":
        return _latency(args)
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
    from buddy.auth import buddy_home
    from buddy.claude_cli import ClaudeCliModel
    from buddy.latency import FILE_NAME, LatencyLog

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
    LatencyLog(buddy_home() / FILE_NAME).record(final, request.kind)
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


def _latency(args: argparse.Namespace) -> int:
    from buddy.auth import buddy_home
    from buddy.latency import FILE_NAME, read_records, summarize

    path: Path = args.file or buddy_home() / FILE_NAME
    records = read_records(path)
    if args.kind:
        records = [r for r in records if r.get("kind") == args.kind]
    if args.last:
        records = records[-args.last :]
    summary = summarize(records)
    if summary is None:
        print(f"buddy: no answers logged in {path}")
        return 1
    models = sorted({str(r.get("model")) for r in records})
    print(f"{summary.count} answers · {', '.join(models)} · {path}")
    print(
        f"first token: p50 {summary.p50:.0f} ms · p90 {summary.p90:.0f} ms · "
        f"min {summary.min} ms · max {summary.max} ms"
    )
    if summary.without_text:
        print(f"({summary.without_text} answers ended without text and are left out)")
    return 0


def _serve(args: argparse.Namespace) -> int:
    import logging

    import uvicorn

    from buddy.auth import buddy_home, load_or_create_token
    from buddy.claude_cli import ClaudeCliModel
    from buddy.hints import proactive_cloud_from_env
    from buddy.latency import FILE_NAME, LatencyLog
    from buddy.server import create_app

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    token_path = buddy_home() / "token"
    token = load_or_create_token(token_path)
    print(f"buddy: token in {token_path}", file=sys.stderr)
    proactive_cloud = proactive_cloud_from_env(os.environ)
    where = "local engine, else Claude" if proactive_cloud else "local engine only"
    print(f"buddy: proactive hints → {where}", file=sys.stderr)
    latency = LatencyLog(buddy_home() / FILE_NAME)
    print(f"buddy: latency log in {latency.path}", file=sys.stderr)
    app = create_app(
        ClaudeCliModel(args.model), token, proactive_cloud=proactive_cloud, latency=latency
    )
    # Loopback only, never configurable (SECURITY.md).
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="info")
    return 0
