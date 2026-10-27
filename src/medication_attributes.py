"""Extract dosage, route and frequency and associate them with medicines."""

from __future__ import annotations

import re
from typing import Iterable

from src.schemas import ExtractedEntity
from src.text_utils import make_evidence_span, sentence_bounds, spans_overlap


DOSAGE_PATTERN = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:mcg|µg|mg|g|kg|ml|mL|l|units?|iu|%)\b",
    re.IGNORECASE,
)

ROUTE_PATTERNS = (
    (re.compile(r"\b(?:by mouth|orally|oral|po)\b", re.IGNORECASE), "oral"),
    (re.compile(r"\b(?:intravenous|iv)\b", re.IGNORECASE), "intravenous"),
    (re.compile(r"\b(?:intramuscular|im)\b", re.IGNORECASE), "intramuscular"),
    (re.compile(r"\b(?:subcutaneous|subcutaneously|sc)\b", re.IGNORECASE), "subcutaneous"),
    (re.compile(r"\b(?:topical|topically|on the skin)\b", re.IGNORECASE), "topical"),
    (re.compile(r"\b(?:inhaled|inhalation|via inhaler)\b", re.IGNORECASE), "inhaled"),
    (re.compile(r"\b(?:nasal|intranasal)\b", re.IGNORECASE), "nasal"),
    (re.compile(r"\b(?:rectal|rectally)\b", re.IGNORECASE), "rectal"),
    (re.compile(r"\b(?:injected|injection)\b", re.IGNORECASE), "injection"),
)

FREQUENCY_PATTERNS = (
    re.compile(r"\b(?:once|twice|three times|four times)\s+(?:a\s+|per\s+)?(?:day|daily|week|weekly)\b", re.IGNORECASE),
    re.compile(r"\b(?:daily|nightly|weekly|monthly)\b", re.IGNORECASE),
    re.compile(r"\bevery\s+\d+\s+(?:hours?|days?|weeks?)\b", re.IGNORECASE),
    re.compile(r"\b(?:bid|tid|qid|qhs|qd|od|prn)\b", re.IGNORECASE),
    re.compile(r"\b(?:as needed|when needed|at bedtime|in the morning|at night)\b", re.IGNORECASE),
)


def extract_attribute_entities(text: str) -> list[ExtractedEntity]:
    """Extract standalone DOSAGE, ROUTE and FREQUENCY evidence entities."""

    candidates: list[tuple[int, int, str, str]] = []

    candidates.extend((m.start(), m.end(), "DOSAGE", m.group(0).lower()) for m in DOSAGE_PATTERN.finditer(text))

    for pattern, normalized in ROUTE_PATTERNS:
        candidates.extend((m.start(), m.end(), "ROUTE", normalized) for m in pattern.finditer(text))

    for pattern in FREQUENCY_PATTERNS:
        candidates.extend((m.start(), m.end(), "FREQUENCY", m.group(0).lower()) for m in pattern.finditer(text))

    candidates.sort(key=lambda item: (item[0], -(item[1] - item[0])))
    occupied: list[tuple[int, int]] = []
    counters = {"DOSAGE": 0, "ROUTE": 0, "FREQUENCY": 0}
    entities: list[ExtractedEntity] = []

    for start, end, entity_type, normalized in candidates:
        if spans_overlap(start, end, occupied):
            continue
        occupied.append((start, end))
        counters[entity_type] += 1
        entities.append(
            {
                "id": f"{entity_type.lower()}_{counters[entity_type]}",
                "type": entity_type,
                "value": text[start:end],
                "normalized": normalized,
                "span": make_evidence_span(text, start, end),
            }
        )

    return entities


def attach_attributes_to_medications(
    text: str,
    medications: list[ExtractedEntity],
    attributes: Iterable[ExtractedEntity],
) -> None:
    """Attach nearest same-sentence dosage/route/frequency to each medication."""

    attribute_list = list(attributes)

    for medication in medications:
        med_span = medication["span"]
        sentence_start, sentence_end = sentence_bounds(text, med_span["char_start"])
        med_center = (med_span["char_start"] + med_span["char_end"]) / 2
        selected: dict[str, ExtractedEntity] = {}

        for entity_type in ("DOSAGE", "ROUTE", "FREQUENCY"):
            candidates = [
                item
                for item in attribute_list
                if item["type"] == entity_type
                and item["span"]["char_start"] >= sentence_start
                and item["span"]["char_end"] <= sentence_end
            ]
            if not candidates:
                continue

            nearest = min(
                candidates,
                key=lambda item: abs(
                    ((item["span"]["char_start"] + item["span"]["char_end"]) / 2) - med_center
                ),
            )
            selected[entity_type.lower()] = nearest

        medication["attributes"] = {
            name: {
                "value": entity["value"],
                "normalized": entity["normalized"],
                "span": entity["span"],
            }
            for name, entity in selected.items()
        }
