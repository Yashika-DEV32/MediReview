"""Assertion, temporal and subject context detection for symptom mentions."""

from __future__ import annotations

import re

from src.schemas import AssertionContext
from src.text_utils import sentence_bounds


NEGATION_CUES = (
    "no",
    "not",
    "never",
    "without",
    "denies",
    "denied",
    "deny",
    "did not",
    "didn't",
    "does not",
    "doesn't",
    "do not",
    "don't",
    "has no",
    "have no",
    "had no",
    "negative for",
    "free of",
)

NEGATION_BREAKERS = (
    "but",
    "however",
    "although",
    "though",
    "yet",
    "except",
    "nevertheless",
    "nonetheless",
)

UNCERTAINTY_CUES = (
    "possible",
    "possibly",
    "maybe",
    "perhaps",
    "might",
    "may",
    "could",
    "suspect",
    "suspected",
    "seems",
    "appears",
    "likely",
    "uncertain",
    "if",
)

HISTORICAL_CUES = (
    "history of",
    "historical",
    "previously",
    "in the past",
    "prior episode",
    "prior history",
    "used to",
    "years ago",
    "months ago",
    "last year",
    "before starting",
    "before taking",
)

FAMILY_TERMS = (
    "mother",
    "father",
    "mom",
    "mum",
    "dad",
    "sister",
    "brother",
    "wife",
    "husband",
    "daughter",
    "son",
    "child",
    "grandmother",
    "grandfather",
    "aunt",
    "uncle",
    "family member",
)


def _contains_phrase(text: str, phrases: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", lowered) for phrase in phrases)


def _pre_context(text: str, mention_start: int, max_chars: int = 120) -> str:
    sentence_start, _ = sentence_bounds(text, mention_start)
    start = max(sentence_start, mention_start - max_chars)
    context = text[start:mention_start]

    breaker_pattern = r"\b(?:" + "|".join(re.escape(word) for word in NEGATION_BREAKERS) + r")\b"
    pieces = re.split(breaker_pattern, context, flags=re.IGNORECASE)
    return pieces[-1] if pieces else context


def _mention_clause(text: str, mention_start: int) -> str:
    """Return the contrast-bounded clause containing a mention."""

    start, end = sentence_bounds(text, mention_start)
    sentence = text[start:end]
    relative = mention_start - start
    breaker_pattern = r"\b(?:" + "|".join(re.escape(word) for word in NEGATION_BREAKERS) + r")\b"

    segment_start = 0
    segment_end = len(sentence)
    for match in re.finditer(breaker_pattern, sentence, flags=re.IGNORECASE):
        if match.end() <= relative:
            segment_start = match.end()
        elif match.start() >= relative:
            segment_end = match.start()
            break

    return sentence[segment_start:segment_end]


def detect_negation(text: str, mention_start: int) -> bool:
    """Detect explicit negation in the local pre-mention scope."""

    context = _pre_context(text, mention_start)
    words = context.split()
    recent = " ".join(words[-10:])
    return _contains_phrase(recent, NEGATION_CUES)


def detect_uncertainty(text: str, mention_start: int) -> bool:
    """Detect uncertainty/speculation within the mention's clause."""

    return _contains_phrase(_mention_clause(text, mention_start), UNCERTAINTY_CUES)


def detect_temporal_context(text: str, mention_start: int) -> str:
    """Classify a mention as historical or current from local cues."""

    clause = _mention_clause(text, mention_start)
    return "Historical" if _contains_phrase(clause, HISTORICAL_CUES) else "Current"


def detect_subject(text: str, mention_start: int) -> str:
    """Attribute the symptom to the patient, a family member, or unknown."""

    clause = _mention_clause(text, mention_start)
    lowered = clause.lower()

    if any(re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", lowered) for term in FAMILY_TERMS):
        return "Family Member"

    if re.search(r"\b(?:i|me|my|patient)\b", lowered):
        return "Patient"

    # Medicine reviews are ordinarily written about the patient; use a
    # conservative patient default unless a family subject is explicit.
    return "Patient"


def detect_assertion_context(text: str, mention_start: int) -> AssertionContext:
    """Return all linguistic context flags for one symptom occurrence."""

    return {
        "negated": detect_negation(text, mention_start),
        "uncertain": detect_uncertainty(text, mention_start),
        "temporal": detect_temporal_context(text, mention_start),
        "subject": detect_subject(text, mention_start),
    }
