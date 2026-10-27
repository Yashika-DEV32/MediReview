"""Rule-based date and duration extraction with evidence spans."""

from __future__ import annotations

import re

from src.schemas import ExtractedEntity
from src.text_utils import make_evidence_span, spans_overlap


# ============================================================
# MONTHS
# ============================================================

MONTHS = (
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
    "jan",
    "feb",
    "mar",
    "apr",
    "jun",
    "jul",
    "aug",
    "sep",
    "sept",
    "oct",
    "nov",
    "dec",
)

MONTH_PATTERN = "|".join(MONTHS)


# ============================================================
# DATE PATTERNS
# ============================================================

DATE_PATTERNS = (

    # 2026-10-03
    re.compile(
        r"\b\d{4}-\d{1,2}-\d{1,2}\b",
        re.IGNORECASE,
    ),

    # 03/10/2026 or 03-10-2026
    re.compile(
        r"\b\d{1,2}[/-]\d{1,2}[/-](?:\d{2}|\d{4})\b",
        re.IGNORECASE,
    ),

    # October 3, 2026
    re.compile(
        rf"\b(?:{MONTH_PATTERN})\s+"
        r"\d{1,2}(?:st|nd|rd|th)?"
        r"(?:,?\s+\d{4})?\b",
        re.IGNORECASE,
    ),

    # 3 October 2026
    re.compile(
        rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+"
        rf"(?:{MONTH_PATTERN})"
        r"(?:\s+\d{4})?\b",
        re.IGNORECASE,
    ),

    # 01-03 October 2026
    re.compile(
        rf"\b\d{{1,2}}\s*[-–]\s*\d{{1,2}}\s+"
        rf"(?:{MONTH_PATTERN})"
        r"(?:\s+\d{4})?\b",
        re.IGNORECASE,
    ),

    # today, yesterday etc.
    re.compile(
        r"\b(?:today|yesterday|tomorrow|tonight|"
        r"this morning|this afternoon|this evening|"
        r"last night)\b",
        re.IGNORECASE,
    ),
)


# ============================================================
# NUMBER WORDS
# ============================================================

NUMBER_WORDS = (
    "one|two|three|four|five|six|seven|eight|nine|ten|"
    "eleven|twelve|few|several|couple"
)


# ============================================================
# DURATION
# ============================================================

DURATION_PATTERN = re.compile(
    rf"\b"
    rf"(?:(?:for|over|about|around|approximately|nearly|almost)\s+)?"
    rf"(?:\d+(?:\.\d+)?|{NUMBER_WORDS})\s+"
    rf"(?:minutes?|hours?|days?|weeks?|months?|years?)"
    rf"\b(?:\s+ago)?",
    re.IGNORECASE,
)


# ============================================================
# AGE PATTERNS
# Used only to prevent age from becoming duration.
# ============================================================

AGE_PATTERNS = (

    # Age: 34 years
    # Age / sex: 34 years / Female
    re.compile(
        r"\bage(?:\s*/\s*sex)?\s*[:\-]?\s*"
        r"\d{1,3}\s*(?:years?|yrs?)\b",
        re.IGNORECASE,
    ),

    # 34 years old
    re.compile(
        r"\b\d{1,3}\s*(?:years?|yrs?)\s+old\b",
        re.IGNORECASE,
    ),

    # 34-year-old
    re.compile(
        r"\b\d{1,3}[-\s]year[-\s]old\b",
        re.IGNORECASE,
    ),

    # aged 34
    re.compile(
        r"\baged?\s+\d{1,3}\b",
        re.IGNORECASE,
    ),
)


# ============================================================
# AGE SPANS
# ============================================================

def get_age_spans(text: str) -> list[tuple[int, int]]:
    """Return character spans containing patient age."""

    age_spans: list[tuple[int, int]] = []

    for pattern in AGE_PATTERNS:

        for match in pattern.finditer(text):

            age_spans.append(
                (
                    match.start(),
                    match.end(),
                )
            )

    return age_spans


# ============================================================
# CHECK WHETHER DURATION MATCH IS ACTUALLY AGE
# ============================================================

def is_age_duration(
    start: int,
    end: int,
    age_spans: list[tuple[int, int]],
) -> bool:
    """Check whether a duration-looking value belongs to age."""

    for age_start, age_end in age_spans:

        if start >= age_start and end <= age_end:
            return True

        if not (
            end <= age_start
            or start >= age_end
        ):
            return True

    return False


# ============================================================
# TEMPORAL EXTRACTION
# ============================================================

def extract_temporal_entities(
    text: str,
) -> list[ExtractedEntity]:
    """
    Extract DATE and DURATION entities.

    Patient age values such as "34 years" are excluded
    from duration extraction.
    """

    entities: list[ExtractedEntity] = []

    occupied: list[tuple[int, int]] = []

    raw_matches: list[
        tuple[int, int, str]
    ] = []

    # --------------------------------------------------------
    # DATE
    # --------------------------------------------------------

    for pattern in DATE_PATTERNS:

        for match in pattern.finditer(text):

            raw_matches.append(
                (
                    match.start(),
                    match.end(),
                    "DATE",
                )
            )

    # --------------------------------------------------------
    # AGE SPANS
    # --------------------------------------------------------

    age_spans = get_age_spans(text)

    # --------------------------------------------------------
    # DURATION
    # --------------------------------------------------------

    for match in DURATION_PATTERN.finditer(text):

        start = match.start()
        end = match.end()

        # Skip values belonging to patient age.
        if is_age_duration(
            start,
            end,
            age_spans,
        ):
            continue

        raw_matches.append(
            (
                start,
                end,
                "DURATION",
            )
        )

    # --------------------------------------------------------
    # SORT
    # --------------------------------------------------------

    raw_matches.sort(
        key=lambda item: (
            item[0],
            -(item[1] - item[0]),
        )
    )

    # --------------------------------------------------------
    # BUILD ENTITIES
    # --------------------------------------------------------

    counters = {
        "DATE": 0,
        "DURATION": 0,
    }

    for start, end, entity_type in raw_matches:

        if spans_overlap(
            start,
            end,
            occupied,
        ):
            continue

        occupied.append(
            (
                start,
                end,
            )
        )

        counters[entity_type] += 1

        value = text[start:end]

        entities.append(
            {
                "id": (
                    f"{entity_type.lower()}_"
                    f"{counters[entity_type]}"
                ),
                "type": entity_type,
                "value": value,
                "normalized": value.lower().strip(),
                "span": make_evidence_span(
                    text,
                    start,
                    end,
                ),
            }
        )

    return entities