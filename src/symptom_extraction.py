"""Rule-based symptom extraction with assertion and evidence spans."""

from __future__ import annotations

import re

from src.context_detection import detect_assertion_context, detect_negation
from src.schemas import ExtractedEntity
from src.text_utils import make_evidence_span, spans_overlap


SYMPTOM_NAMES = (
    "nausea", "vomiting", "diarrhea", "constipation", "stomach pain",
    "abdominal pain", "stomach ache", "bloating", "gas", "heartburn",
    "indigestion", "loss of appetite", "increased appetite", "stomach cramps",
    "abdominal cramps", "headache", "migraine", "dizziness", "lightheadedness",
    "vertigo", "tremor", "shaking", "tingling", "numbness", "confusion",
    "brain fog", "fatigue", "tiredness", "weakness", "drowsiness",
    "sleepiness", "insomnia", "difficulty sleeping", "trouble sleeping",
    "chest pain", "back pain", "muscle pain", "joint pain", "body ache",
    "body aches", "muscle ache", "muscle aches", "joint ache", "joint aches",
    "leg pain", "arm pain", "neck pain", "cramps", "rash", "itching",
    "itchiness", "redness", "swelling", "hives", "dry skin", "acne",
    "skin irritation", "shortness of breath", "difficulty breathing",
    "breathing difficulty", "wheezing", "cough", "sore throat", "runny nose",
    "stuffy nose", "nasal congestion", "palpitations", "heart palpitations",
    "rapid heartbeat", "fast heartbeat", "irregular heartbeat", "fever",
    "chills", "sweating", "night sweats", "dry mouth", "dehydration",
    "blurred vision", "blurry vision", "double vision", "vision problems",
    "anxiety", "irritability", "mood swings", "restlessness", "weight gain",
    "weight loss", "hair loss", "hair thinning",
)


def normalize_text(text: str) -> str:
    """Normalize whitespace/case for compatibility with previous callers."""

    if not isinstance(text, str):
        return ""
    return re.sub(r"\s+", " ", text.lower().replace("’", "'")).strip()


def is_negated(text: str, symptom_start: int) -> bool:
    """Backward-compatible negation helper."""

    return detect_negation(text, symptom_start)


def extract_symptom_entities(review: str) -> list[ExtractedEntity]:
    """Extract all non-overlapping symptom mentions with linguistic context."""

    if not isinstance(review, str) or not review.strip():
        return []

    candidates: list[tuple[int, int, str]] = []
    for symptom in sorted(SYMPTOM_NAMES, key=len, reverse=True):
        pattern = re.compile(r"(?<!\w)" + re.escape(symptom) + r"(?!\w)", re.IGNORECASE)
        candidates.extend((match.start(), match.end(), symptom) for match in pattern.finditer(review))

    candidates.sort(key=lambda item: (item[0], -(item[1] - item[0])))
    occupied: list[tuple[int, int]] = []
    entities: list[ExtractedEntity] = []

    for start, end, canonical in candidates:
        if spans_overlap(start, end, occupied):
            continue
        occupied.append((start, end))
        entities.append(
            {
                "id": f"symptom_{len(entities) + 1}",
                "type": "SYMPTOM",
                "value": review[start:end],
                "normalized": canonical,
                "span": make_evidence_span(review, start, end),
                "assertion": detect_assertion_context(review, start),
            }
        )

    return entities


def extract_symptoms(review: str) -> dict[str, list[str]]:
    """Return unique reported/negated symptom names for old UI callers."""

    reported: list[str] = []
    negated: list[str] = []

    for entity in extract_symptom_entities(review):
        target = negated if entity["assertion"]["negated"] else reported
        name = entity["normalized"]
        if name not in target:
            target.append(name)

    return {"reported": reported, "negated": negated}


def extract_reported_symptoms(review: str) -> list[str]:
    """Return only non-negated symptoms."""

    return extract_symptoms(review)["reported"]
