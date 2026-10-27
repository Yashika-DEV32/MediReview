"""
Dataset-oriented NER enrichment for MediReview preprocessing notebooks.
This module intentionally reuses the same extraction service as the runtime
application. That keeps training/preprocessing outputs aligned with what the
UI and programmatic service return for the same source narrative.

"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pandas as pd

from src.service import analyze_review


NER_COLUMNS = (
    "ner_medication_names",
    "ner_symptom_names",
    "ner_reported_symptoms",
    "ner_negated_symptoms",
    "ner_date_values",
    "ner_duration_values",
    "narrative_classification",
    "ner_entities_json",
    "ner_relations_json",
    "ner_error",
)


def _json(value: Any) -> str:
    """Serialize NER output safely for CSV storage."""

    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def extract_ner_record(text: str) -> dict[str, str]:
    """Extract structured NER fields from one original narrative.

    The original, uncleaned text must be supplied so evidence character/token
    offsets remain valid against the source review.
    """

    result = analyze_review(text, include_model_prediction=False)

    symptom_entities = result.get("symptom_entities", []) or []

    return {
        "ner_medication_names": _json(result.get("medicines", [])),
        "ner_symptom_names": _json(
            list(dict.fromkeys(entity.get("normalized", "") for entity in symptom_entities if entity.get("normalized")))
        ),
        "ner_reported_symptoms": _json(result.get("reported_symptoms", [])),
        "ner_negated_symptoms": _json(result.get("negated_symptoms", [])),
        "ner_date_values": _json([entity.get("value", "") for entity in result.get("date_entities", [])]),
        "ner_duration_values": _json([entity.get("value", "") for entity in result.get("duration_entities", [])]),
        "narrative_classification": str(result.get("narrative_classification", "Insufficient Information")),
        "ner_entities_json": _json(result.get("entities", [])),
        "ner_relations_json": _json(result.get("relations", [])),
        "ner_error": "",
    }


def _empty_ner_record(error: str = "") -> dict[str, str]:
    return {
        "ner_medication_names": "[]",
        "ner_symptom_names": "[]",
        "ner_reported_symptoms": "[]",
        "ner_negated_symptoms": "[]",
        "ner_date_values": "[]",
        "ner_duration_values": "[]",
        "narrative_classification": "Insufficient Information",
        "ner_entities_json": "[]",
        "ner_relations_json": "[]",
        "ner_error": error,
    }


def enrich_dataframe_with_ner(
    dataframe: pd.DataFrame,
    *,
    source_column: str = "review",
    continue_on_error: bool = True,
    progress_every: int | None = 1000,
    progress_callback: Callable[[int, int], None] | None = None,
) -> pd.DataFrame:
    """Return a copy of ``dataframe`` enriched with structured NER columns.

    Parameters
    ----------
    dataframe:
        Source dataframe. It is never mutated in place.
    source_column:
        Column containing the original narrative. Do not point this at a
        cleaned/lowercased column if source evidence offsets are required.
    continue_on_error:
        When true, row-level failures are recorded in ``ner_error`` and other
        NER columns receive safe empty values. When false, the original error
        is raised.
    progress_every:
        Emit lightweight progress every N rows when no callback is provided.
        Set to ``None`` or ``0`` to disable console progress.
    progress_callback:
        Optional ``(processed_rows, total_rows)`` callback for notebook/UI use.
    """

    if source_column not in dataframe.columns:
        raise KeyError(f"Source text column not found: {source_column}")

    enriched = dataframe.copy()
    records: list[dict[str, str]] = []
    total = len(enriched)

    for position, raw_text in enumerate(enriched[source_column].tolist(), start=1):
        try:
            if pd.isna(raw_text) or not str(raw_text).strip():
                raise ValueError("Narrative text is empty.")
            record = extract_ner_record(str(raw_text))
        except Exception as exc:
            if not continue_on_error:
                raise
            record = _empty_ner_record(str(exc))

        records.append(record)

        if progress_callback is not None:
            progress_callback(position, total)
        elif progress_every and (position % progress_every == 0 or position == total):
            print(f"NER processed: {position:,}/{total:,}")

    ner_frame = pd.DataFrame.from_records(records, columns=NER_COLUMNS, index=enriched.index)

    for column in NER_COLUMNS:
        enriched[column] = ner_frame[column]

    return enriched
