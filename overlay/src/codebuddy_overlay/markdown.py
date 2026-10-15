"""Markdown helpers. The panel renders answers with Qt's own markdown support; what has to match
the notch exactly is the one-line hint preview (`Markdown.preview` in Swift)."""

import unicodedata

_DROPPED_TOKENS = {"-", "*", "•", ">", "#", "##", "###"}


def _strip_punctuation_and_spaces(text: str) -> str:
    def edge(ch: str) -> bool:
        return ch.isspace() or unicodedata.category(ch).startswith("P")

    start, end = 0, len(text)
    while start < end and edge(text[start]):
        start += 1
    while end > start and edge(text[end - 1]):
        end -= 1
    return text[start:end]


def preview(markdown: str, max_chars: int) -> str | None:
    """One plain line: markup dropped, whitespace collapsed, cut on a word boundary with "…".
    None when there is no text yet."""
    plain = markdown.replace("```", " ").replace("**", "").replace("`", "")
    words = [w for w in plain.split() if w not in _DROPPED_TOKENS]
    text = " ".join(words)
    if not text:
        return None
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    space = cut.rfind(" ")
    word = cut[:space] if space >= 0 else cut
    return _strip_punctuation_and_spaces(word) + "…"
