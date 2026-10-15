"""One log line on stderr, the format the brain uses too: `[12:00:00] overlay: …`."""

import sys
from datetime import datetime


def log(message: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] overlay: {message}", file=sys.stderr, flush=True)
