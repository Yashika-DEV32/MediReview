"""Shared text preprocessing used by training notebooks and runtime prediction."""

from __future__ import annotations

import html
import re
# emoji map is used to replace emojis with words to preserve sentiment information

EMOJI_MAP: dict[str, str] = {
    "🤮": "vomit",
    "👎": "thumbsdown",
    "😡": "angry",
    "😞": "sad",
    "👍": "thumbsup",
    "💊": "pill",
    "😊": "happy",
}


def expand_negative_contractions(text: str) -> str:
    """Expand common negative contractions while preserving negation cues."""

    normalized = str(text).replace("’", "'")

    special_cases = {
        r"\bwon't\b": "will not",
        r"\bcan't\b": "can not",
        r"\bshan't\b": "shall not",
    }

    for pattern, replacement in special_cases.items():
        normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)

    return re.sub(
        r"\b(\w+)n't\b",
        r"\1 not",
        normalized,
        flags=re.IGNORECASE,
    )


def clean_review(text: object) -> str:
    """Clean a review for TF-IDF without removing important NLP context.

    This function deliberately keeps punctuation and negation/context words.
    Structured NER must still run on the original source text because cleaning
    changes character offsets.
    """

    normalized = html.unescape(str(text))
    normalized = re.sub(r"<[^>]+>", " ", normalized)

    for emoji, word in EMOJI_MAP.items():
        normalized = normalized.replace(emoji, f" {word} ")

    normalized = expand_negative_contractions(normalized)
    normalized = normalized.lower()
    return re.sub(r"\s+", " ", normalized).strip()
