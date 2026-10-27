"""Four-way narrative classification based on extracted assertion evidence."""

from __future__ import annotations

import re

from src.schemas import ExtractedEntity, NarrativeCategory


# ============================================================
# EXPLICIT ABSENCE OF SIDE EFFECTS
# ============================================================

EXPLICIT_ABSENCE_PATTERNS = (
    re.compile(
        r"\bno\s+(?:side|adverse)\s+effects?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bno\s+adverse\s+reactions?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bwithout\s+(?:any\s+)?"
        r"(?:side|adverse)\s+effects?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:did not|didn't|never)\s+experience\s+"
        r"(?:any\s+)?(?:side|adverse)\s+effects?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bden(?:y|ies|ied)\s+(?:any\s+)?"
        r"(?:side|adverse)\s+effects?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\btolerat(?:e|ed|ing)\s+(?:the\s+)?"
        r"(?:medication|medicine|drug)\s+well\b",
        re.IGNORECASE,
    ),
)


# ============================================================
# EXPLICIT REPORTED SIDE EFFECT
# ============================================================

REPORTED_EVENT_PATTERNS = (
    re.compile(
        r"\bexperience(?:d|s|ing)?\s+"
        r"(?:a\s+|an\s+|some\s+)?"
        r"(?:side|adverse)\s+effects?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bdevelop(?:ed|s|ing)?\s+"
        r"(?:a\s+|an\s+|some\s+)?"
        r"adverse\s+reactions?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:side|adverse)\s+effects?\s+"
        r"(?:started|occurred|appeared|developed)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bsuffer(?:ed|s|ing)?\s+"
        r"(?:from\s+)?(?:side|adverse)\s+effects?\b",
        re.IGNORECASE,
    ),
)


# ============================================================
# SPECIAL PHRASES
# ============================================================

NO_OTHER_EFFECT_PATTERNS = (
    re.compile(
        r"\bno\s+other\s+(?:side|adverse)\s+effects?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bno\s+additional\s+(?:side|adverse)\s+effects?\b",
        re.IGNORECASE,
    ),
)


# ============================================================
# HELPERS
# ============================================================

def _symptom_name(
    symptom: ExtractedEntity,
) -> str:
    """
    Return normalized symptom text.
    """

    value = (
        symptom.get("normalized")
        or symptom.get("value")
        or symptom.get("text")
        or symptom.get("entity")
        or ""
    )

    return str(
        value
    ).strip().casefold()


def _get_assertion(
    symptom: ExtractedEntity,
) -> dict:
    """
    Safely return symptom assertion information.
    """

    assertion = symptom.get(
        "assertion",
        {},
    )

    if not isinstance(
        assertion,
        dict,
    ):
        return {}

    return assertion


def _is_family_member(
    symptom: ExtractedEntity,
) -> bool:
    """
    Return True if symptom belongs to someone
    other than the patient.
    """

    assertion = _get_assertion(
        symptom
    )

    subject = str(
        assertion.get(
            "subject",
            "Patient",
        )
    ).strip().casefold()

    return subject in {
        "family member",
        "family",
        "mother",
        "father",
        "sister",
        "brother",
        "spouse",
        "wife",
        "husband",
        "child",
    }


def _is_historical(
    symptom: ExtractedEntity,
) -> bool:
    """
    Return True for historical symptom mentions.
    """

    assertion = _get_assertion(
        symptom
    )

    temporal = str(
        assertion.get(
            "temporal",
            "Current",
        )
    ).strip().casefold()

    return temporal in {
        "historical",
        "history",
        "past",
        "previous",
        "previously",
    }


# ============================================================
# CLASSIFICATION
# ============================================================

def classify_narrative(
    text: str,
    symptoms: list[ExtractedEntity],
) -> NarrativeCategory:
    """
    Classify narrative into:

    - Side Effect
    - No Side Effect
    - Mixed Evidence
    - Insufficient Information
    """

    text = (
        text
        if isinstance(
            text,
            str,
        )
        else str(
            text
            or ""
        )
    )

    # ========================================================
    # EVIDENCE GROUPS
    # ========================================================

    reported_symptoms: set[str] = set()

    negated_symptoms: set[str] = set()

    uncertain_symptoms: set[str] = set()

    historical_symptoms: set[str] = set()

    # ========================================================
    # PROCESS EXTRACTED SYMPTOMS
    # ========================================================

    for symptom in symptoms:

        if not isinstance(
            symptom,
            dict,
        ):
            continue

        # ----------------------------------------------------
        # Ignore symptoms experienced by family members
        # ----------------------------------------------------

        if _is_family_member(
            symptom
        ):
            continue

        name = _symptom_name(
            symptom
        )

        if not name:
            continue

        assertion = _get_assertion(
            symptom
        )

        negated = bool(
            assertion.get(
                "negated",
                False,
            )
        )

        uncertain = bool(
            assertion.get(
                "uncertain",
                False,
            )
        )

        historical = _is_historical(
            symptom
        )

        # ----------------------------------------------------
        # Historical symptoms should not automatically make
        # the current narrative a side-effect case.
        # ----------------------------------------------------

        if historical:

            historical_symptoms.add(
                name
            )

            continue

        # ----------------------------------------------------
        # Negated symptom
        # ----------------------------------------------------

        if negated:

            negated_symptoms.add(
                name
            )

            continue

        # ----------------------------------------------------
        # Uncertain symptom
        # ----------------------------------------------------

        if uncertain:

            uncertain_symptoms.add(
                name
            )

            continue

        # ----------------------------------------------------
        # Current reported symptom
        # ----------------------------------------------------

        reported_symptoms.add(
            name
        )

    # ========================================================
    # EXPLICIT TEXT EVIDENCE
    # ========================================================

    explicit_absence = any(
        pattern.search(
            text
        )
        for pattern in EXPLICIT_ABSENCE_PATTERNS
    )

    explicit_reported = any(
        pattern.search(
            text
        )
        for pattern in REPORTED_EVENT_PATTERNS
    )

    no_other_effects = any(
        pattern.search(
            text
        )
        for pattern in NO_OTHER_EFFECT_PATTERNS
    )

    # ========================================================
    # SAME SYMPTOM BOTH REPORTED AND DENIED
    # ========================================================

    conflicting_symptoms = (
        reported_symptoms
        &
        negated_symptoms
    )

    if conflicting_symptoms:

        return "Mixed Evidence"

    # ========================================================
    # REPORTED EVENT + GENERAL ABSENCE STATEMENT
    # ========================================================
    #
    # Example:
    #
    # "Patient developed nausea but later stated
    #  that there were no side effects."
    #
    # This is contradictory.
    #
    # But:
    #
    # "Patient developed nausea with no other side effects."
    #
    # is NOT contradictory.
    # ========================================================

    if (
        reported_symptoms
        and explicit_absence
        and not no_other_effects
    ):

        return "Mixed Evidence"

    if (
        explicit_reported
        and explicit_absence
        and not no_other_effects
    ):

        return "Mixed Evidence"

    # ========================================================
    # CURRENT REPORTED SIDE EFFECT
    # ========================================================

    if reported_symptoms:

        return "Side Effect"

    if explicit_reported:

        return "Side Effect"

    # ========================================================
    # UNCERTAIN CURRENT SYMPTOM
    # ========================================================
    #
    # Example:
    # "Patient may have experienced nausea."
    #
    # This contains possible event evidence, but there is not
    # enough certainty to classify it as a confirmed report.
    # ========================================================

    if uncertain_symptoms:

        return "Insufficient Information"

    # ========================================================
    # EXPLICIT ABSENCE / ONLY NEGATED SYMPTOMS
    # ========================================================

    if negated_symptoms:

        return "No Side Effect"

    if explicit_absence:

        return "No Side Effect"

    # ========================================================
    # HISTORICAL INFORMATION ONLY
    # ========================================================

    if historical_symptoms:

        return "Insufficient Information"

    # ========================================================
    # NO RELEVANT SIDE-EFFECT INFORMATION
    # ========================================================

    return "Insufficient Information"