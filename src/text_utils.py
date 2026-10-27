"""Shared text/span helpers for rule-based NLP extraction."""

from __future__ import annotations

import re

from src.schemas import EvidenceSpan


TOKEN_PATTERN = re.compile(r"\S+")
SENTENCE_BREAK_PATTERN = re.compile(r"[.!?;\n]")


def make_evidence_span(text: str, start: int, end: int) -> EvidenceSpan:
    """Create exact character and token offsets for ``text[start:end]``."""

    if start < 0 or end < start or end > len(text):
        raise ValueError("Invalid evidence span offsets.")

    tokens = list(TOKEN_PATTERN.finditer(text))
    overlapping = [
        index
        for index, token in enumerate(tokens)
        if token.end() > start and token.start() < end
    ]

    if overlapping:
        token_start = overlapping[0]
        token_end = overlapping[-1] + 1
    else:
        token_start = sum(1 for token in tokens if token.end() <= start)
        token_end = token_start

    return {
        "text": text[start:end],
        "char_start": start,
        "char_end": end,
        "token_start": token_start,
        "token_end": token_end,
    }


def sentence_bounds(text: str, position: int) -> tuple[int, int]:
    """Return character bounds for the sentence containing ``position``."""

    if not text:
        return 0, 0

    position = min(max(position, 0), len(text))
    left = 0
    right = len(text)

    for match in SENTENCE_BREAK_PATTERN.finditer(text):
        if match.end() <= position:
            left = match.end()
            continue
        if match.start() >= position:
            right = match.start()
            break

    while left < right and text[left].isspace():
        left += 1
    while right > left and text[right - 1].isspace():
        right -= 1

    return left, right


def spans_overlap(start: int, end: int, occupied: list[tuple[int, int]]) -> bool:
    """Return True when a character span overlaps any occupied span."""

    return any(start < used_end and end > used_start for used_start, used_end in occupied)
