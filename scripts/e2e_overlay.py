"""End to end without Claude or an IDE: a fake trigger client → `buddy serve --stub` → the overlay.

Passes when the overlay logs the answer_end for the trigger's id and saves its snapshot, and that
answer is the stub's text. Starts and stops everything itself; runs on Linux (CI, under Xvfb),
Windows and macOS.
Usage: uv run --project brain python scripts/e2e_overlay.py OUTDIR [--port 8799]
       … OUTDIR --bundle dist/CodeBuddy-linux-0.1.0   (the packaged brain and overlay instead)
"""

import argparse
import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import websockets

ROOT = Path(__file__).resolve().parent.parent
STUB = "Alla riga 6 il file **non viene chiuso**: `open(path)` resta aperto. (risposta di prova)"


def start(cmd: list[str], env: dict[str, str], log: Path) -> subprocess.Popen[bytes]:
    return subprocess.Popen(cmd, env=env, stdout=log.open("wb"), stderr=subprocess.STDOUT)


def wait_for(predicate, timeout_s: float, what: str) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.2)
    raise SystemExit(f"e2e: timed out waiting for {what}")


async def send_trigger(port: int, token: str) -> str:
    trigger = json.loads((ROOT / "protocol/examples/trigger.question.json").read_text("utf-8"))
    trigger["id"] = f"e2e-{int(time.time())}"
    async with websockets.connect(f"ws://127.0.0.1:{port}/ws") as ws:
        hello = {"v": 0, "type": "hello", "role": "ide", "token": token, "client": "e2e/0"}
        await ws.send(json.dumps(hello))
        welcome = json.loads(await ws.recv())
        assert welcome["type"] == "welcome", welcome
        await ws.send(json.dumps(trigger))
        await asyncio.sleep(0.5)
    return trigger["id"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("out", type=Path)
    parser.add_argument("--port", type=int, default=8799)
    parser.add_argument("--bundle", type=Path, help="a packaged build (packaging/build.py)")
    args = parser.parse_args()
    out: Path = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    home = Path(tempfile.mkdtemp(prefix="codebuddy-e2e-"))
    env = {**os.environ, "BUDDY_HOME": str(home), "BUDDY_PORT": str(args.port)}
    uv = os.environ.get("UV", "uv")
    exe = ".exe" if sys.platform == "win32" else ""
    if args.bundle:
        brain_cmd = [str(args.bundle.resolve() / "brain" / f"buddy{exe}")]
        overlay_cmd = [str(args.bundle.resolve() / "overlay" / f"codebuddy-overlay{exe}")]
    else:
        brain_cmd = [uv, "run", "--project", str(ROOT / "brain"), "buddy"]
        overlay_cmd = [uv, "run", "--project", str(ROOT / "overlay"), "codebuddy-overlay"]
    procs: list[subprocess.Popen[bytes]] = []
    try:
        brain_log, overlay_log = out / "brain.log", out / "overlay.log"
        procs.append(
            start(
                [*brain_cmd, "serve", "--port", str(args.port), "--stub", STUB],
                env, brain_log,
            )
        )  # fmt: skip
        wait_for(lambda: (home / "token").exists() and "Uvicorn running" in brain_log.read_text(
            errors="replace"), 60, "the brain")
        procs.append(
            start(
                [*overlay_cmd, "--snapshots", str(out)],
                env, overlay_log,
            )
        )  # fmt: skip
        wait_for(lambda: "brain connected" in overlay_log.read_text(errors="replace"), 60,
                 "the overlay to connect")  # fmt: skip
        token = (home / "token").read_text(encoding="utf-8").strip()
        answer_id = asyncio.run(send_trigger(args.port, token))
        shot = out / f"answer-{answer_id}.png"
        wait_for(lambda: shot.exists() and shot.stat().st_size > 0, 30, f"{shot.name}")
        log = overlay_log.read_text(errors="replace")
        assert f"answer_end id={answer_id} model=stub" in log, log
        print(f"e2e: OK — overlay showed {answer_id} from the stub model; snapshot {shot}")
        return 0
    finally:
        for proc in reversed(procs):
            proc.terminate()
        for proc in procs:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    sys.exit(main())
