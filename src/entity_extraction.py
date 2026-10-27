"""Orchestrates medication, symptom, attribute and temporal extraction."""

from __future__ import annotations

from src.medication_attributes import attach_attributes_to_medications, extract_attribute_entities
from src.medicine_extraction import extract_medicine_entities
from src.schemas import ExtractedEntity
from src.symptom_extraction import extract_symptom_entities
from src.temporal_extraction import extract_temporal_entities


def extract_entities(text: str) -> dict[str, list[ExtractedEntity]]:
    """Extract all required entity families while preserving source evidence."""

    if not isinstance(text, str) or not text.strip():
        raise ValueError("Narrative text must be a non-empty string.")

    medications = extract_medicine_entities(text)
    symptoms = extract_symptom_entities(text)
    medication_attributes = extract_attribute_entities(text)
    temporal_entities = extract_temporal_entities(text)

    attach_attributes_to_medications(text, medications, medication_attributes)

    dates = [entity for entity in temporal_entities if entity["type"] == "DATE"]
    durations = [entity for entity in temporal_entities if entity["type"] == "DURATION"]

    all_entities = medications + symptoms + medication_attributes + temporal_entities
    all_entities.sort(key=lambda entity: (entity["span"]["char_start"], entity["span"]["char_end"]))

    return {
        "all": all_entities,
        "medications": medications,
        "symptoms": symptoms,
        "attributes": medication_attributes,
        "dates": dates,
        "durations": durations,
    }
