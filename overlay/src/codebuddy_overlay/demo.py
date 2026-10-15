"""`--demo`: every state with a fake streamed answer, no brain needed (as `DemoScript.swift`)."""

from dataclasses import dataclass

from codebuddy_overlay.protocol import AnswerDelta, AnswerEnd, AnswerKind, AnswerStart, BrainMessage

ANSWER_ID = "demo-1"
HINT_ID = "demo-hint"

HINT = (
    "Alla riga 6 il file resta aperto se `json.load` fallisce: "
    "quale costrutto di Python chiude le risorse anche in caso di errore?"
)

ANSWER = """Alla riga 6 `open(path)` crea un file che **nessuno chiude**: lo passi a `json.load`, \
che lo legge ma non lo chiude.

- In CPython si chiude "per caso" quando il garbage collector lo elimina.
- Se `json.load` fallisce, il file può restare aperto.

Usa un context manager:

```python
with open(path) as f:
    data = json.load(f)
```

Il file si chiude all'uscita dal blocco, anche in caso di errore."""


@dataclass(frozen=True)
class Hover:
    inside: bool


@dataclass(frozen=True)
class Click:
    pass


type Step = Hover | Click | BrainMessage


def chunks(text: str, size: int) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)]


def steps(chunk_size: int = 12) -> list[tuple[float, Step]]:
    """(seconds from start, step). The same timeline as the notch's demo."""
    out: list[tuple[float, Step]] = [
        (1.0, Hover(True)),
        (3.0, Hover(False)),
        (4.0, AnswerStart(ANSWER_ID, AnswerKind.QUESTION, "perché non chiude il file?")),
    ]
    t = 4.5
    for chunk in chunks(ANSWER, chunk_size):
        out.append((t, AnswerDelta(ANSWER_ID, chunk)))
        t += 0.06
    out.append((t + 0.2, AnswerEnd(ANSWER_ID, "demo", 500, int((t - 4.0) * 1000))))
    out.append((21.0, AnswerStart(HINT_ID, AnswerKind.HINT, "load.py:6")))
    t = 21.3
    for chunk in chunks(HINT, chunk_size):
        out.append((t, AnswerDelta(HINT_ID, chunk)))
        t += 0.03
    out.append((t + 0.1, AnswerEnd(HINT_ID, "demo-local", 300, int((t - 21.0) * 1000))))
    out += [(23.8, Hover(True)), (24.0, Click()), (24.2, Hover(False))]
    return out
