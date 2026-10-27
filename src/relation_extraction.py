"""Medication-symptom relation extraction.

Relations represent narrative co-associations only. They never assert clinical
causation.
"""

from __future__ import annotations

from src.schemas import ExtractedEntity, ExtractedRelation
from src.text_utils import make_evidence_span, sentence_bounds


MAX_FALLBACK_DISTANCE = 180


def _distance(left: ExtractedEntity, right: ExtractedEntity) -> int:
    left_span = left["span"]
    right_span = right["span"]
    if left_span["char_end"] <= right_span["char_start"]:
        return right_span["char_start"] - left_span["char_end"]
    if right_span["char_end"] <= left_span["char_start"]:
        return left_span["char_start"] - right_span["char_end"]
    return 0


def extract_medication_symptom_relations(
    text: str,
    medications: list[ExtractedEntity],
    symptoms: list[ExtractedEntity],
) -> list[ExtractedRelation]:
    """Link symptoms to medications mentioned in the same/nearby context.

    If several medicines occur in the same sentence as a symptom, all are
    retained as reported co-associations. When no medicine occurs in the same
    sentence, only the nearest medicine within a conservative distance is used.
    """

    relations: list[ExtractedRelation] = []

    for symptom in symptoms:
        symptom_start = symptom["span"]["char_start"]
        sentence_start, sentence_end = sentence_bounds(text, symptom_start)

        same_sentence = sorted(
            [
                medication
                for medication in medications
                if medication["span"]["char_start"] >= sentence_start
                and medication["span"]["char_end"] <= sentence_end
            ],
            key=lambda item: _distance(item, symptom),
        )

        if same_sentence:
            candidates = [(medication, "same sentence") for medication in same_sentence]
        elif medications:
            nearest = min(medications, key=lambda item: _distance(item, symptom))
            candidates = (
                [(nearest, "nearby narrative context")]
                if _distance(nearest, symptom) <= MAX_FALLBACK_DISTANCE
                else []
            )
        else:
            candidates = []

        assertion = symptom.get(
            "assertion",
            {"negated": False, "uncertain": False, "temporal": "Current", "subject": "Unknown"},
        )

        for medication, basis in candidates:
            relation_start = min(
                medication["span"]["char_start"],
                symptom["span"]["char_start"],
            )
            relation_end = max(
                medication["span"]["char_end"],
                symptom["span"]["char_end"],
            )

            relations.append(
                {
                    "id": f"relation_{len(relations) + 1}",
                    "type": "MEDICATION_SYMPTOM_REPORTED_ASSOCIATION",
                    "medication_id": medication["id"],
                    "symptom_id": symptom["id"],
                    "medication": medication["value"],
                    "symptom": symptom["value"],
                    "evidence": make_evidence_span(text, relation_start, relation_end),
                    "association_basis": basis,
                    "clinical_causation_inferred": False,
                    "symptom_assertion": assertion,
                }
            )

    return relations
