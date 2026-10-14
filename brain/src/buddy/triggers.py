"""Parse explicit trigger lines: `#? question` and `#!<command> text`.

Only whole-line comments count. `x = 1  #? why` and `# teoria …` never fire, so normal comments
can't trigger the buddy by accident. Detecting triggers inside strings is the plugin's job (PSI);
here a line is just text.
"""

from dataclasses import dataclass
from typing import Literal

type TriggerKind = Literal["question", "theory"]

# `#!<command>` → kind. Italian and English spellings. `alt` and `review` come after the MVP.
COMMANDS: dict[str, TriggerKind] = {"teoria": "theory", "theory": "theory"}


@dataclass(frozen=True)
class ParsedTrigger:
    kind: TriggerKind
    text: str


def parse_trigger_line(line: str) -> ParsedTrigger | None:
    stripped = line.strip()
    if stripped.startswith("#?"):
        text = stripped[2:].strip()
        return ParsedTrigger("question", text) if text else None
    if stripped.startswith("#!"):
        command, _, rest = stripped[2:].partition(" ")
        kind = COMMANDS.get(command.lower())
        # `#!teoria` with no topic is allowed: it asks for the theory behind the code at that line.
        return ParsedTrigger(kind, rest.strip()) if kind else None
    return None
