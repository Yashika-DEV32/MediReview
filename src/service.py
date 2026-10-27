"""Main MediReview analysis service.

This module is the public orchestration layer.

Extraction, assertion detection, relation extraction and classification
logic remain inside focused ``src`` modules. Streamlit and Django should
call this service instead of implementing NLP logic themselves.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping

from src.entity_extraction import extract_entities
from src.input_handler import (
    NarrativeInput,
    load_batch_text_files,
    load_text_file,
)
from src.narrative_classification import classify_narrative
from src.predict import load_predictor, predict_reviews
from src.relation_extraction import (
    extract_medication_symptom_relations,
)


Predictor = tuple[Any, Any, dict[int, str]]


# ============================================================
# GENERAL HELPERS
# ============================================================

def _unique(items: Iterable[str]) -> list[str]:
    """
    Remove duplicate strings while preserving order.
    """

    return list(
        dict.fromkeys(items)
    )


# ============================================================
# MODEL LOADING
# ============================================================

@lru_cache(maxsize=1)
def get_predictor() -> Predictor:
    """
    Load the existing ML model and vectorizer once.
    """

    return load_predictor()


def _model_prediction(
    review: str,
    predictor: Predictor | None,
) -> str:
    """
    Run the legacy ML classifier.
    """

    active_predictor = (
        predictor
        if predictor is not None
        else get_predictor()
    )

    predictions = predict_reviews(
        [review],
        predictor=active_predictor,
    )

    if not predictions:
        raise ValueError(
            "The prediction model returned no result."
        )

    return str(
        predictions[0]
    ).strip()


# ============================================================
# MEDICATION DETAILS
# ============================================================

def _get_attribute_value(
    attributes: Mapping[str, Any],
    key: str,
) -> str | None:
    """
    Safely retrieve a value from a medication attribute.

    Supports structures such as:

    {
        "dosage": {
            "value": "500 mg",
            ...
        }
    }
    """

    attribute = attributes.get(
        key
    )

    if attribute is None:
        return None

    if isinstance(
        attribute,
        Mapping,
    ):
        value = attribute.get(
            "value"
        )

        if value is None:
            value = attribute.get(
                "normalized"
            )

    else:
        value = attribute

    if value is None:
        return None

    value = str(
        value
    ).strip()

    return value or None


def _build_medication_details(
    medications: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """
    Create compact medicine information for the UI/API.

    Repeated mentions of the same medicine are merged.
    Later non-empty medication attributes replace older ones.
    """

    merged: dict[
        str,
        dict[str, Any],
    ] = {}

    order: list[str] = []

    for entity in medications:

        medicine = str(
            entity.get(
                "normalized"
            )
            or entity.get(
                "value"
            )
            or ""
        ).strip()

        if not medicine:
            continue

        key = medicine.casefold()

        if key not in merged:

            merged[key] = {
                "medicine": medicine,
                "dosage": None,
                "frequency": None,
                "route": None,
            }

            order.append(
                key
            )

        attributes = (
            entity.get(
                "attributes"
            )
            or {}
        )

        if not isinstance(
            attributes,
            Mapping,
        ):
            attributes = {}

        dosage = (
            _get_attribute_value(
                attributes,
                "dosage",
            )
            or _get_attribute_value(
                attributes,
                "dose",
            )
            or _get_attribute_value(
                attributes,
                "strength",
            )
        )

        frequency = _get_attribute_value(
            attributes,
            "frequency",
        )

        route = _get_attribute_value(
            attributes,
            "route",
        )

        current = merged[
            key
        ]

        # Latest valid information wins.

        if dosage:
            current[
                "dosage"
            ] = dosage

        if frequency:
            current[
                "frequency"
            ] = frequency

        if route:
            current[
                "route"
            ] = route

    return [
        merged[key]
        for key in order
    ]


# ============================================================
# MAIN ANALYSIS
# ============================================================

def analyze_review(
    review: str,
    predictor: Predictor | None = None,
    *,
    patient_id: str | None = None,
    report_reference_id: str | None = None,
    metadata: Mapping[str, Any] | None = None,
    source_file: str | None = None,
    include_model_prediction: bool = True,
) -> dict[str, Any]:
    """
    Analyze one medicine-related narrative end to end.

    The assertion-driven ``narrative_classification`` is the
    primary narrative classification.

    The existing ML prediction is retained separately as
    ``model_prediction``.

    The returned dictionary is intentionally kept compact while
    preserving evidence entities and relations required by the UI
    and reviewer workflow.
    """

    # ========================================================
    # VALIDATION
    # ========================================================

    if (
        not isinstance(
            review,
            str,
        )
        or not review.strip()
    ):
        raise ValueError(
            "Review must be a non-empty string."
        )

    review = review.strip()

    # ========================================================
    # ENTITY EXTRACTION
    # ========================================================

    grouped = extract_entities(
        review
    )

    medications = grouped.get(
        "medications",
        [],
    )

    symptoms = grouped.get(
        "symptoms",
        [],
    )

    # ========================================================
    # RELATION EXTRACTION
    # ========================================================

    relations = (
        extract_medication_symptom_relations(
            review,
            medications,
            symptoms,
        )
    )

    # ========================================================
    # NARRATIVE CLASSIFICATION
    # ========================================================

    narrative_category = (
        classify_narrative(
            review,
            symptoms,
        )
    )

    # ========================================================
    # LEGACY ML MODEL
    # ========================================================

    model_prediction: str | None = None
    model_error: str | None = None

    if include_model_prediction:

        try:

            model_prediction = (
                _model_prediction(
                    review,
                    predictor,
                )
            )

        except Exception as exc:

            # Rule-based NLP result should still work if
            # the ML model cannot be loaded.
            model_error = str(
                exc
            )

    # ========================================================
    # REPORTED SYMPTOMS
    # ========================================================

    reported_symptoms = _unique(
        str(
            entity.get(
                "normalized"
            )
            or entity.get(
                "value"
            )
            or ""
        ).strip()

        for entity in symptoms

        if (
            not (
                entity.get(
                    "assertion"
                )
                or {}
            ).get(
                "negated",
                False,
            )
        )
    )

    reported_symptoms = [
        symptom
        for symptom in reported_symptoms
        if symptom
    ]

    # ========================================================
    # NEGATED SYMPTOMS
    # ========================================================

    negated_symptoms = _unique(
        str(
            entity.get(
                "normalized"
            )
            or entity.get(
                "value"
            )
            or ""
        ).strip()

        for entity in symptoms

        if (
            (
                entity.get(
                    "assertion"
                )
                or {}
            ).get(
                "negated",
                False,
            )
        )
    )

    negated_symptoms = [
        symptom
        for symptom in negated_symptoms
        if symptom
    ]

    # ========================================================
    # MEDICINE NAMES
    # ========================================================

    medicine_names = _unique(
        str(
            entity.get(
                "normalized"
            )
            or entity.get(
                "value"
            )
            or ""
        ).strip()

        for entity in medications
    )

    medicine_names = [
        medicine
        for medicine in medicine_names
        if medicine
    ]

    # ========================================================
    # COMPACT MEDICINE DETAILS
    # ========================================================

    medication_details = (
        _build_medication_details(
            medications
        )
    )

    # ========================================================
    # REFERENCES
    # ========================================================

    references = {
        "patient_id": patient_id,
        "report_reference_id": (
            report_reference_id
        ),
        "metadata": dict(
            metadata or {}
        ),
        "source_file": source_file,
    }

    # ========================================================
    # FINAL RESULT
    # ========================================================

    result: dict[str, Any] = {

        # Original narrative
        "source_text":
            review,

        # References
        "references":
            references,

        # Main classification
        "narrative_classification":
            narrative_category,

        # Legacy ML result
        "model_prediction":
            model_prediction,

        # Compact medicine output
        "medicines":
            medicine_names,

        "medication_details":
            medication_details,

        # Symptoms
        "reported_symptoms":
            reported_symptoms,

        "negated_symptoms":
            negated_symptoms,

        # Complete evidence entities.
        # This already includes medication, dosage,
        # frequency, route, symptoms, dates and durations.
        "entities":
            grouped.get(
                "all",
                [],
            ),

        # Medicine-symptom reported associations
        "relations":
            relations,
    }

    # ========================================================
    # OPTIONAL MODEL WARNING
    # ========================================================

    if model_error:

        result[
            "model_warning"
        ] = model_error

    return result


# ============================================================
# VALIDATED NARRATIVE INPUT
# ============================================================

def analyze_narrative_input(
    narrative: NarrativeInput,
    predictor: Predictor | None = None,
    *,
    include_model_prediction: bool = True,
) -> dict[str, Any]:
    """
    Analyze a validated NarrativeInput instance.
    """

    return analyze_review(
        narrative.text,
        predictor=predictor,
        patient_id=narrative.patient_id,
        report_reference_id=(
            narrative.report_reference_id
        ),
        metadata=narrative.metadata,
        source_file=narrative.source_file,
        include_model_prediction=(
            include_model_prediction
        ),
    )


# ============================================================
# SINGLE TEXT FILE
# ============================================================

def analyze_text_file(
    file_path: str | Path,
    *,
    patient_id: str | None = None,
    report_reference_id: str | None = None,
    metadata: Mapping[str, Any] | None = None,
    predictor: Predictor | None = None,
    include_model_prediction: bool = True,
) -> dict[str, Any]:
    """
    Read and analyze one plain-text narrative file.
    """

    narrative = load_text_file(
        file_path,
        patient_id=patient_id,
        report_reference_id=(
            report_reference_id
        ),
        metadata=metadata,
    )

    return analyze_narrative_input(
        narrative,
        predictor=predictor,
        include_model_prediction=(
            include_model_prediction
        ),
    )


# ============================================================
# BATCH FILES
# ============================================================

def analyze_batch_files(
    file_paths: Iterable[str | Path],
    *,
    metadata_by_file: (
        Mapping[
            str,
            Mapping[str, Any],
        ]
        | None
    ) = None,
    predictor: Predictor | None = None,
    include_model_prediction: bool = True,
    continue_on_error: bool = False,
) -> list[dict[str, Any]]:
    """
    Analyze multiple text files independently.
    """

    narratives = (
        load_batch_text_files(
            file_paths,
            metadata_by_file=(
                metadata_by_file
            ),
        )
    )

    results: list[
        dict[str, Any]
    ] = []

    active_predictor = predictor

    # ========================================================
    # LOAD MODEL ONCE FOR BATCH
    # ========================================================

    if (
        include_model_prediction
        and active_predictor is None
    ):

        try:

            active_predictor = (
                get_predictor()
            )

        except Exception:

            active_predictor = None

    # ========================================================
    # ANALYZE EACH NARRATIVE
    # ========================================================

    for narrative in narratives:

        try:

            result = (
                analyze_narrative_input(
                    narrative,
                    predictor=(
                        active_predictor
                    ),
                    include_model_prediction=(
                        include_model_prediction
                    ),
                )
            )

            results.append(
                result
            )

        except Exception as exc:

            if not continue_on_error:
                raise

            results.append(
                {
                    "source_file":
                        narrative.source_file,

                    "error":
                        str(exc),

                    "references": {
                        "patient_id":
                            narrative.patient_id,

                        "report_reference_id":
                            narrative.report_reference_id,

                        "metadata":
                            narrative.metadata,

                        "source_file":
                            narrative.source_file,
                    },
                }
            )

    return results