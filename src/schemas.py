"""Typed schemas used by the MediReview NLP pipeline."""

from __future__ import annotations

from typing import Any, Literal, NotRequired, TypedDict


NarrativeCategory = Literal[
    "Side Effect",
    "No Side Effect",
    "Mixed Experience",
    "Neutral",
]

class EvidenceSpan(TypedDict):
    text: str
    char_start: int
    char_end: int
    token_start: int
    token_end: int


class AssertionContext(TypedDict):
    negated: bool
    uncertain: bool
    temporal: Literal["Current", "Historical"]
    subject: Literal["Patient", "Family Member", "Unknown"]


class ExtractedEntity(TypedDict):
    id: str
    type: str
    value: str
    normalized: str
    span: EvidenceSpan
    assertion: NotRequired[AssertionContext]
    attributes: NotRequired[dict[str, Any]]


class ExtractedRelation(TypedDict):
    id: str
    type: Literal["MEDICATION_SYMPTOM_REPORTED_ASSOCIATION"]
    medication_id: str
    symptom_id: str
    medication: str
    symptom: str
    evidence: EvidenceSpan
    association_basis: str
    clinical_causation_inferred: Literal[False]
    symptom_assertion: AssertionContext


class NarrativeReferences(TypedDict):
    patient_id: str | None
    report_reference_id: str | None
    metadata: dict[str, Any]
    source_file: str | None
