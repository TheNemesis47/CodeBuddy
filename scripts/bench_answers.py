"""Record every answer the brain broadcasts, for the latency bench (scripts/bench-latency).

Connects as a second notch client and appends one JSON line per finished answer (id, kind, title,
text, answer_end) to OUT, so answer quality can be compared between setups. Runs until killed.
Usage: uv run --project brain python scripts/bench_answers.py OUT
"""

import asyncio
import json
import os
import sys
from pathlib import Path

import websockets


async def main(out: Path) -> None:
    home = Path(os.environ["BUDDY_HOME"])
    port = os.environ.get("BUDDY_PORT", "8790")
    token = (home / "token").read_text().strip()
    async with websockets.connect(f"ws://127.0.0.1:{port}/ws") as ws:
        hello = {"v": 0, "type": "hello", "role": "notch", "token": token, "client": "bench/0"}
        await ws.send(json.dumps(hello))
        answers: dict[str, dict] = {}
        async for raw in ws:
            message = json.loads(raw)
            kind = message.get("type")
            if kind == "answer_start":
                answers[message["id"]] = {**message, "text": ""}
            elif kind == "answer_delta" and message["id"] in answers:
                answers[message["id"]]["text"] += message["text"]
            elif kind in ("answer_end", "error") and message.get("id") in answers:
                answer = answers.pop(message["id"])
                record = {k: answer[k] for k in ("id", "kind", "title", "text")}
                with out.open("a", encoding="utf-8") as file:
                    file.write(json.dumps({**record, "end": message}, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    asyncio.run(main(Path(sys.argv[1])))
