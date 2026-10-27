from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# ============================================================
# PROJECT ROOT
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# IMPORTS
# ============================================================

import streamlit as st

from app.api_client import (
    create_review,
    get_reviews,
    update_review_assessment,
)
# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="MediReview",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ============================================================
# CONSTANTS
# ============================================================

REVIEWER_OPTIONS = [
    "Needs Review",
    "Side Effect",
    "No Side Effect",
    "Mixed Evidence",
    "Insufficient Information",
]


# ============================================================
# SESSION STATE
# ============================================================

def initialize_state() -> None:
    defaults = {
        "analysis_result": None,
        "submitted_text": "",
        "source_name": None,
        "review_id": None,
        "reviewer_classification": "Needs Review",
        "reviewer_notes": "",
        "history_reviews": [],
        "history_loaded": False,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


# ============================================================
# CSS
# ============================================================

def apply_css() -> None:
    st.markdown(
        """
        <style>

        .stApp {
            background: #0b0f17;
            color: #f8fafc;
        }

        .block-container {
            max-width: 1460px;
            padding-top: 1.2rem;
            padding-left: 2rem;
            padding-right: 2rem;
            padding-bottom: 3rem;
        }

        header[data-testid="stHeader"] {
            background: transparent;
        }

        #MainMenu {
            visibility: hidden;
        }

        footer {
            visibility: hidden;
        }

        h1,
        h2,
        h3,
        h4,
        h5 {
            color: #f8fafc !important;
        }

        p,
        label,
        .stCaption {
            color: #a4adbb !important;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: #111722 !important;
            border: 1px solid #2a3342 !important;
            border-radius: 14px !important;
            box-shadow: none !important;
        }

        div[data-testid="stTextArea"] textarea,
        div[data-testid="stTextInput"] input {
            background: #171d29 !important;
            color: #f8fafc !important;
            border: 1px solid #333d4f !important;
            border-radius: 9px !important;
        }

        div[data-testid="stTextArea"] textarea:focus,
        div[data-testid="stTextInput"] input:focus {
            border-color: #ff4b55 !important;
            box-shadow: 0 0 0 1px #ff4b55 !important;
        }

        div[data-baseweb="select"] > div {
            background: #171d29 !important;
            color: #f8fafc !important;
            border-color: #333d4f !important;
        }

        [data-testid="stFileUploader"] {
            background: #111722;
            border-radius: 12px;
        }

        .stButton > button,
        .stFormSubmitButton > button,
        .stDownloadButton > button {
            border-radius: 10px !important;
            min-height: 42px !important;
            font-weight: 600 !important;
        }

        .stButton > button[kind="primary"],
        .stFormSubmitButton > button[kind="primary"] {
            background: #ff4b55 !important;
            color: #ffffff !important;
            border: none !important;
        }

        .stButton > button[kind="primary"]:hover,
        .stFormSubmitButton > button[kind="primary"]:hover {
            background: #eb404a !important;
        }

        [data-testid="stAlert"] {
            border-radius: 11px !important;
        }

        hr {
            border-color: #273142 !important;
        }

        [data-testid="stMetric"] {
            background: #111722;
            border: 1px solid #2a3342;
            border-radius: 12px;
            padding: 12px;
        }

        @media (max-width: 900px) {
            .block-container {
                padding-left: 1rem;
                padding-right: 1rem;
            }
        }

        </style>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# FILE READING
# ============================================================

def extract_text_from_file(uploaded_file: Any) -> str:
    """
    Extract text from TXT, PDF or DOCX.
    """

    if uploaded_file is None:
        return ""

    file_name = str(
        uploaded_file.name
    ).lower()

    # ========================================================
    # TXT
    # ========================================================

    if file_name.endswith(".txt"):

        try:
            return (
                uploaded_file
                .getvalue()
                .decode(
                    "utf-8",
                    errors="ignore",
                )
                .strip()
            )

        except Exception as exc:
            raise ValueError(
                f"Unable to read TXT file: {exc}"
            ) from exc

    # ========================================================
    # PDF
    # ========================================================

    if file_name.endswith(".pdf"):

        try:
            from pypdf import PdfReader

        except ImportError as exc:
            raise ValueError(
                "PDF support requires pypdf. "
                "Install it using: pip install pypdf"
            ) from exc

        try:
            reader = PdfReader(
                uploaded_file
            )

            pages: list[str] = []

            for page in reader.pages:

                text = (
                    page.extract_text()
                    or ""
                ).strip()

                if text:
                    pages.append(
                        text
                    )

            return "\n\n".join(
                pages
            ).strip()

        except Exception as exc:
            raise ValueError(
                f"Unable to read PDF file: {exc}"
            ) from exc

    # ========================================================
    # DOCX
    # ========================================================

    if file_name.endswith(".docx"):

        try:
            from docx import Document

        except ImportError as exc:
            raise ValueError(
                "DOCX support requires python-docx. "
                "Install it using: pip install python-docx"
            ) from exc

        try:
            document = Document(
                uploaded_file
            )

            paragraphs: list[str] = []

            for paragraph in document.paragraphs:

                text = (
                    paragraph.text
                    or ""
                ).strip()

                if text:
                    paragraphs.append(
                        text
                    )

            return "\n".join(
                paragraphs
            ).strip()

        except Exception as exc:
            raise ValueError(
                f"Unable to read DOCX file: {exc}"
            ) from exc

    raise ValueError(
        "Unsupported file format. "
        "Please upload TXT, PDF or DOCX."
    )


# ============================================================
# GENERAL HELPERS
# ============================================================

def safe_text(
    value: Any,
    fallback: str = "Not mentioned",
) -> str:

    if value is None:
        return fallback

    value = str(
        value
    ).strip()

    if not value:
        return fallback

    return value


def unique_strings(
    values: Any,
) -> list[str]:

    if not isinstance(
        values,
        (list, tuple),
    ):
        return []

    output: list[str] = []
    seen: set[str] = set()

    for value in values:

        if value is None:
            continue

        text = str(
            value
        ).strip()

        if not text:
            continue

        key = text.casefold()

        if key in seen:
            continue

        seen.add(
            key
        )

        output.append(
            text
        )

    return output


# ============================================================
# ENTITY HELPERS
# ============================================================

def get_span_start(
    entity: dict[str, Any],
) -> int:

    span = (
        entity.get(
            "span"
        )
        or {}
    )

    try:

        return int(
            span.get(
                "char_start",
                0,
            )
        )

    except (
        TypeError,
        ValueError,
    ):

        return 0


def get_entity_values(
    result: dict[str, Any],
    entity_type: str,
) -> list[str]:

    entities = (
        result.get(
            "entities"
        )
        or []
    )

    if not isinstance(
        entities,
        list,
    ):
        return []

    values: list[str] = []
    seen: set[str] = set()

    for entity in entities:

        if not isinstance(
            entity,
            dict,
        ):
            continue

        current_type = str(
            entity.get(
                "type",
                "",
            )
        ).strip().upper()

        if current_type != entity_type.upper():
            continue

        value = str(
            entity.get(
                "value",
                "",
            )
        ).strip()

        if not value:
            continue

        key = value.casefold()

        if key in seen:
            continue

        seen.add(
            key
        )

        values.append(
            value
        )

    return values


# ============================================================
# MEDICINE NORMALIZATION
# ============================================================

def normalize_medicine_name(
    name: str,
) -> str:

    return (
        str(
            name
        )
        .strip()
        .casefold()
    )


# ============================================================
# MERGE DUPLICATE MEDICINES
# ============================================================

def merge_duplicate_medications(
    medication_details: list[
        dict[str, Any]
    ],
) -> list[dict[str, Any]]:

    merged: dict[
        str,
        dict[str, Any],
    ] = {}

    order: list[str] = []

    for item in medication_details:

        if not isinstance(
            item,
            dict,
        ):
            continue

        medicine = (
            item.get(
                "medicine"
            )
            or item.get(
                "medication"
            )
            or item.get(
                "name"
            )
        )

        if not medicine:
            continue

        medicine = str(
            medicine
        ).strip()

        if not medicine:
            continue

        key = normalize_medicine_name(
            medicine
        )

        if key not in merged:

            merged[
                key
            ] = {
                "medicine": medicine,
                "dosage": None,
                "frequency": None,
                "route": None,
            }

            order.append(
                key
            )

        current = merged[
            key
        ]

        dosage = (
            item.get(
                "dosage"
            )
            or item.get(
                "dose"
            )
            or item.get(
                "strength"
            )
        )

        frequency = item.get(
            "frequency"
        )

        route = item.get(
            "route"
        )

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
        merged[
            key
        ]
        for key in order
    ]


# ============================================================
# ENTITY-BASED MEDICINE GROUPING
# ============================================================

def build_medication_details_from_entities(
    entities: list[
        dict[str, Any]
    ],
) -> list[dict[str, Any]]:

    if not isinstance(
        entities,
        list,
    ):
        return []

    ordered_entities = [
        entity
        for entity in entities
        if isinstance(
            entity,
            dict,
        )
    ]

    ordered_entities.sort(
        key=get_span_start
    )

    medicines: dict[
        str,
        dict[str, Any],
    ] = {}

    order: list[str] = []

    current_key: str | None = None

    for entity in ordered_entities:

        entity_type = str(
            entity.get(
                "type",
                "",
            )
        ).strip().upper()

        value = str(
            entity.get(
                "value",
                "",
            )
        ).strip()

        if not value:
            continue

        # ====================================================
        # MEDICATION
        # ====================================================

        if entity_type in {
            "MEDICATION",
            "MEDICINE",
            "DRUG",
        }:

            key = normalize_medicine_name(
                value
            )

            if key not in medicines:

                medicines[
                    key
                ] = {
                    "medicine": value,
                    "dosage": None,
                    "frequency": None,
                    "route": None,
                }

                order.append(
                    key
                )

            current_key = key

            continue

        if current_key is None:
            continue

        current = medicines.get(
            current_key
        )

        if current is None:
            continue

        # ====================================================
        # DOSAGE
        # ====================================================

        if entity_type in {
            "DOSAGE",
            "STRENGTH",
            "DOSE",
        }:

            current[
                "dosage"
            ] = value

        # ====================================================
        # FREQUENCY
        # ====================================================

        elif entity_type == "FREQUENCY":

            current[
                "frequency"
            ] = value

        # ====================================================
        # ROUTE
        # ====================================================

        elif entity_type == "ROUTE":

            current[
                "route"
            ] = value

    return [
        medicines[
            key
        ]
        for key in order
    ]


# ============================================================
# GET FINAL MEDICATION DETAILS
# ============================================================

def get_medication_details(
    result: dict[str, Any],
) -> list[dict[str, Any]]:

    backend_details = result.get(
        "medication_details"
    )

    if (
        isinstance(
            backend_details,
            list,
        )
        and backend_details
    ):

        merged = (
            merge_duplicate_medications(
                backend_details
            )
        )

        if merged:
            return merged

    entities = (
        result.get(
            "entities"
        )
        or []
    )

    if isinstance(
        entities,
        list,
    ):

        details = (
            build_medication_details_from_entities(
                entities
            )
        )

        if details:
            return details

    medicines = unique_strings(
        result.get(
            "medicines",
            [],
        )
    )

    return [
        {
            "medicine": medicine,
            "dosage": None,
            "frequency": None,
            "route": None,
        }
        for medicine in medicines
    ]


# ============================================================
# HEADER
# ============================================================

def show_header() -> None:

    title_col, status_col = (
        st.columns(
            [4, 1]
        )
    )

    with title_col:

        st.title(
            "💊 MediReview"
        )

        st.caption(
            "Medicine safety review workspace"
        )

    with status_col:

        st.write("")
        st.write("")

        st.caption(
            "Safety review • Structured evidence"
        )

    st.divider()


# ============================================================
# INPUT
# ============================================================

def show_input_panel() -> None:

    st.subheader(
        "Case input"
    )

    st.caption(
        "Enter a medicine-related narrative or upload a report."
    )

    input_method = st.radio(
        "Input method",
        [
            "Write narrative",
            "Upload document",
        ],
        horizontal=True,
        key="input_method",
    )

    with st.form(
        "analysis_form",
        clear_on_submit=False,
    ):

        ref1, ref2 = (
            st.columns(
                2
            )
        )

        with ref1:

            patient_reference = (
                st.text_input(
                    "Patient reference",
                    placeholder="Optional",
                )
            )

        with ref2:

            report_reference = (
                st.text_input(
                    "Report reference",
                    placeholder="Optional",
                )
            )

        review_text = ""

        uploaded_file = None

        # ====================================================
        # WRITE NARRATIVE
        # ====================================================

        if input_method == "Write narrative":

            review_text = (
                st.text_area(
                    "Medicine experience",
                    placeholder=(
                        "Example: Patient reports taking "
                        "Metformin 500 mg twice daily and "
                        "Losartan 50 mg every morning. "
                        "The patient later experienced nausea "
                        "but denies vomiting or rash."
                    ),
                    height=290,
                    key="manual_review",
                )
            )

        # ====================================================
        # UPLOAD DOCUMENT
        # ====================================================

        else:

            uploaded_file = (
                st.file_uploader(
                    "Upload patient report",
                    type=[
                        "txt",
                        "pdf",
                        "docx",
                    ],
                )
            )

            st.caption(
                "Supported formats: TXT, PDF and DOCX"
            )

        submitted = (
            st.form_submit_button(
                "Analyze case",
                type="primary",
                use_container_width=True,
            )
        )

    if not submitted:
        return

    # ========================================================
    # FILE EXTRACTION
    # ========================================================

    if input_method == "Upload document":

        if uploaded_file is None:

            st.warning(
                "Please upload a document."
            )

            return

        try:

            review_text = (
                extract_text_from_file(
                    uploaded_file
                )
            )

        except ValueError as exc:

            st.error(
                str(
                    exc
                )
            )

            return

        source_name = (
            uploaded_file.name
        )

    else:

        source_name = (
            "Typed narrative"
        )

    # ========================================================
    # NORMALIZE
    # ========================================================

    if not isinstance(
        review_text,
        str,
    ):

        review_text = str(
            review_text
            or ""
        )

    review_text = (
        review_text.strip()
    )

    # ========================================================
    # VALIDATION
    # ========================================================

    if not review_text:

        st.warning(
            "No readable narrative was provided."
        )

        return

    if len(
        review_text.split()
    ) < 3:

        st.warning(
            "Please provide more information before analysis."
        )

        return

    # ========================================================
    # DJANGO API ANALYSIS + SAVE
    # ========================================================

    try:

        with st.spinner(
            "Analyzing and saving case..."
        ):

            api_response = (
                create_review(
                    review_text,
                    patient_reference=(
                        patient_reference.strip()
                        or None
                    ),
                    report_reference=(
                        report_reference.strip()
                        or None
                    ),
                    source_name=source_name,
                )
            )

        # ====================================================
        # GET ANALYSIS RESULT
        # ====================================================

        result = (
            api_response.get(
                "analysis_result"
            )
        )

        if not isinstance(
            result,
            dict,
        ):

            raise ValueError(
                "Django response does not contain "
                "a valid analysis_result."
            )

        # ====================================================
        # DATABASE INFORMATION
        # ====================================================

        review_id = (
            api_response.get(
                "id"
            )
        )

        result[
            "review_id"
        ] = review_id

        result[
            "patient_reference"
        ] = (
            api_response.get(
                "patient_reference"
            )
        )

        result[
            "report_reference"
        ] = (
            api_response.get(
                "report_reference"
            )
        )

        # ====================================================
        # SESSION STATE
        # ====================================================

        st.session_state[
            "analysis_result"
        ] = result

        st.session_state[
            "submitted_text"
        ] = review_text

        st.session_state[
            "source_name"
        ] = source_name

        st.session_state[
            "review_id"
        ] = review_id

        st.success(
            "Case analyzed and saved successfully."
        )

    except Exception as exc:

        st.error(
            f"Unable to analyze and save case: {exc}"
        )


# ============================================================
# INPUT PREVIEW
# ============================================================

def show_submitted_text_preview() -> None:

    text = (
        st.session_state.get(
            "submitted_text",
            "",
        )
    )

    if not text:
        return

    with st.expander(
        "Preview submitted narrative",
        expanded=False,
    ):

        st.text_area(
            "Submitted text",
            value=text,
            height=200,
            disabled=True,
            key="submitted_text_preview",
        )


# ============================================================
# CASE SUMMARY
# ============================================================

def show_case_summary(
    result: dict[str, Any],
) -> None:

    classification = safe_text(
        result.get(
            "narrative_classification"
        ),
        "Insufficient Information",
    )

    st.subheader(
        "Case summary"
    )

    with st.container(
        border=True
    ):

        st.caption(
            "Automated narrative assessment"
        )

        st.markdown(
            f"### {classification}"
        )


# ============================================================
# CASE OVERVIEW
# ============================================================

def show_case_overview(
    result: dict[str, Any],
) -> None:

    patient_reference = safe_text(
        result.get(
            "patient_reference"
        ),
        "Not provided",
    )

    report_reference = safe_text(
        result.get(
            "report_reference"
        ),
        "Not provided",
    )

    review_id = safe_text(
        result.get(
            "review_id"
        ),
        "Not available",
    )

    source_name = safe_text(
        st.session_state.get(
            "source_name"
        ),
        "Not available",
    )

    medicines = (
        get_medication_details(
            result
        )
    )

    symptoms = unique_strings(
        result.get(
            "reported_symptoms",
            [],
        )
    )

    with st.container(
        border=True
    ):

        st.markdown(
            "#### Case overview"
        )

        metric1, metric2 = (
            st.columns(
                2
            )
        )

        with metric1:

            st.metric(
                "Medicines",
                len(
                    medicines
                ),
            )

        with metric2:

            st.metric(
                "Reported symptoms",
                len(
                    symptoms
                ),
            )

        st.divider()

        ref1, ref2 = (
            st.columns(
                2
            )
        )

        with ref1:

            st.caption(
                "Patient reference"
            )

            st.write(
                patient_reference
            )

        with ref2:

            st.caption(
                "Report reference"
            )

            st.write(
                report_reference
            )

        info1, info2 = (
            st.columns(
                2
            )
        )

        with info1:

            st.caption(
                "Case ID"
            )

            st.write(
                review_id
            )

        with info2:

            st.caption(
                "Source"
            )

            st.write(
                source_name
            )


# ============================================================
# MEDICINE INFORMATION
# ============================================================

def show_medicine_information(
    result: dict[str, Any],
) -> None:

    st.subheader(
        "💊 Medicine information"
    )

    st.caption(
        "Each medicine is shown once with the latest "
        "available dosage, frequency and route."
    )

    medication_details = (
        get_medication_details(
            result
        )
    )

    if not medication_details:

        st.info(
            "No medicine information was identified."
        )

        return

    for start_index in range(
        0,
        len(
            medication_details
        ),
        2,
    ):

        row_items = (
            medication_details[
                start_index:
                start_index + 2
            ]
        )

        columns = st.columns(
            len(
                row_items
            ),
            gap="large",
        )

        for column, medication in zip(
            columns,
            row_items,
        ):

            with column:

                medicine = safe_text(
                    medication.get(
                        "medicine"
                    ),
                    "Medicine",
                )

                dosage = safe_text(
                    medication.get(
                        "dosage"
                    )
                )

                frequency = safe_text(
                    medication.get(
                        "frequency"
                    )
                )

                route = safe_text(
                    medication.get(
                        "route"
                    )
                )

                with st.container(
                    border=True
                ):

                    st.markdown(
                        f"### 💊 {medicine}"
                    )

                    st.divider()

                    dose_col, freq_col = (
                        st.columns(
                            2
                        )
                    )

                    with dose_col:

                        st.caption(
                            "Dosage"
                        )

                        st.markdown(
                            f"**{dosage}**"
                        )

                    with freq_col:

                        st.caption(
                            "Frequency"
                        )

                        st.markdown(
                            f"**{frequency}**"
                        )

                    st.write("")

                    st.caption(
                        "Route"
                    )

                    st.markdown(
                        f"**{route}**"
                    )


# ============================================================
# TIMELINE
# ============================================================

def show_timeline(
    result: dict[str, Any],
) -> None:

    dates = get_entity_values(
        result,
        "DATE",
    )

    durations = get_entity_values(
        result,
        "DURATION",
    )

    st.subheader(
        "🗓 Timeline"
    )

    with st.container(
        border=True
    ):

        st.markdown(
            "#### Date references"
        )

        if dates:

            for value in dates:

                st.write(
                    f"📅 {value}"
                )

        else:

            st.caption(
                "No date references identified."
            )

        st.divider()

        st.markdown(
            "#### Duration / timing"
        )

        if durations:

            for value in durations:

                st.write(
                    f"⏱ {value}"
                )

        else:

            st.caption(
                "No duration identified."
            )


# ============================================================
# REPORTED EXPERIENCE
# ============================================================

def show_reported_experience(
    result: dict[str, Any],
) -> None:

    reported = unique_strings(
        result.get(
            "reported_symptoms",
            [],
        )
    )

    denied = unique_strings(
        result.get(
            "negated_symptoms",
            [],
        )
    )

    st.subheader(
        "Reported experience"
    )

    with st.container(
        border=True
    ):

        experienced_col, denied_col = (
            st.columns(
                2,
                gap="large",
            )
        )

        with experienced_col:

            st.markdown(
                "#### ⚠ Symptoms experienced"
            )

            if reported:

                for symptom in reported:

                    st.write(
                        f"• {symptom}"
                    )

            else:

                st.caption(
                    "No reported symptoms identified."
                )

        with denied_col:

            st.markdown(
                "#### ✓ Symptoms not experienced"
            )

            if denied:

                for symptom in denied:

                    st.write(
                        f"• {symptom}"
                    )

            else:

                st.caption(
                    "No denied symptoms identified."
                )


# ============================================================
# MEDICINE / SYMPTOM CONTEXT
# ============================================================

def show_medicine_symptom_context(
    result: dict[str, Any],
) -> None:

    st.subheader(
        "Medicine and symptom context"
    )

    st.caption(
        "Reported narrative associations only. "
        "Clinical causation is not inferred."
    )

    relations = (
        result.get(
            "relations"
        )
        or []
    )

    if not isinstance(
        relations,
        list,
    ):

        relations = []

    messages: list[str] = []

    seen: set[str] = set()

    for relation in relations:

        if not isinstance(
            relation,
            dict,
        ):

            continue

        medicine = (
            relation.get(
                "medication"
            )
            or relation.get(
                "medicine"
            )
        )

        symptom = (
            relation.get(
                "symptom"
            )
        )

        if not medicine or not symptom:
            continue

        assertion = (
            relation.get(
                "symptom_assertion"
            )
            or {}
        )

        if not isinstance(
            assertion,
            dict,
        ):

            assertion = {}

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

        if negated:

            message = (
                f"{symptom} was reported as not experienced "
                f"while {medicine} was being discussed."
            )

        elif uncertain:

            message = (
                f"{symptom} was mentioned with uncertainty "
                f"while {medicine} was being discussed."
            )

        else:

            message = (
                f"{symptom} was reported while "
                f"{medicine} was being discussed."
            )

        key = message.casefold()

        if key in seen:
            continue

        seen.add(
            key
        )

        messages.append(
            message
        )

    with st.container(
        border=True
    ):

        if messages:

            for message in messages:

                st.write(
                    f"• {message}"
                )

        else:

            st.caption(
                "No medicine–symptom context identified."
            )


# ============================================================
# REVIEWER ASSESSMENT
# ============================================================

def show_reviewer_assessment() -> None:

    st.subheader(
        "Reviewer assessment"
    )

    st.caption(
        "Manual reviewer decision and case notes."
    )

    # ========================================================
    # GET CURRENT SAVED REVIEW ID
    # ========================================================

    review_id = st.session_state.get(
        "review_id"
    )

    # ========================================================
    # CURRENT REVIEWER CLASSIFICATION
    # ========================================================

    current_value = st.session_state.get(
        "reviewer_classification",
        "Needs Review",
    )

    if current_value not in REVIEWER_OPTIONS:
        current_value = "Needs Review"

    selected_index = REVIEWER_OPTIONS.index(
        current_value
    )

    # ========================================================
    # REVIEWER CLASSIFICATION
    # ========================================================

    classification = st.selectbox(
        "Reviewer classification",
        REVIEWER_OPTIONS,
        index=selected_index,
        key="reviewer_classification_select",
    )

    # ========================================================
    # REVIEWER NOTES
    # ========================================================

    notes = st.text_area(
        "Reviewer notes",
        value=st.session_state.get(
            "reviewer_notes",
            "",
        ),
        placeholder=(
            "Record clarification and "
            "follow-up requirements or assessment notes..."
        ),
        height=135,
        key="reviewer_notes_field",
    )

    # ========================================================
    # SAVE ASSESSMENT
    # ========================================================

    if st.button(
        "Save assessment",
        use_container_width=True,
        key="save_assessment",
    ):

        # ----------------------------------------------------
        # REVIEW MUST ALREADY EXIST IN DATABASE
        # ----------------------------------------------------

        if review_id is None:

            st.error(
                "No saved review ID is available. "
                "Analyze and save a case first."
            )

            return

        try:

            with st.spinner(
                "Saving reviewer assessment..."
            ):

                response = (
                    update_review_assessment(
                        int(review_id),
                        classification,
                        notes.strip(),
                    )
                )

            # ------------------------------------------------
            # UPDATE STREAMLIT SESSION
            # ------------------------------------------------

            st.session_state[
                "reviewer_classification"
            ] = response.get(
                "reviewer_classification",
                classification,
            )

            st.session_state[
                "reviewer_notes"
            ] = response.get(
                "reviewer_notes",
                notes,
            )

            st.success(
                "Reviewer assessment saved successfully."
            )

        except Exception as exc:

            st.error(
                f"Unable to save assessment: {exc}"
            )
# ============================================================
# EXPORT
# ============================================================

def show_export(
    result: dict[str, Any],
) -> None:

    export_result = dict(
        result
    )

    export_result[
        "display_medication_details"
    ] = (
        get_medication_details(
            result
        )
    )

    export_result[
        "reviewer_classification"
    ] = (
        st.session_state.get(
            "reviewer_classification",
            "Needs Review",
        )
    )

    export_result[
        "reviewer_notes"
    ] = (
        st.session_state.get(
            "reviewer_notes",
            "",
        )
    )

    export_json = json.dumps(
        export_result,
        indent=2,
        ensure_ascii=False,
        default=str,
    )

    st.download_button(
        "Download case summary",
        data=export_json,
        file_name="medireview_case_summary.json",
        mime="application/json",
        use_container_width=True,
    )

# ============================================================
# REVIEW HISTORY
# ============================================================

def show_review_history() -> None:

    st.subheader(
        "📋 Review history"
    )

    st.caption(
        "Search and filter previously saved medicine review cases."
    )

    # ========================================================
    # FILTERS
    # ========================================================

    with st.container(
        border=True
    ):

        with st.form(
            "history_filter_form",
            clear_on_submit=False,
        ):

            row1_col1, row1_col2 = st.columns(
                2
            )

            with row1_col1:

                search = st.text_input(
                    "Search",
                    placeholder=(
                        "Narrative, patient reference, "
                        "report reference..."
                    ),
                    key="history_search",
                )

            with row1_col2:

                medicine = st.text_input(
                    "Medicine",
                    placeholder="Example: Metformin",
                    key="history_medicine",
                )

            row2_col1, row2_col2, row2_col3 = st.columns(
                3
            )

            with row2_col1:

                classification = st.selectbox(
                    "Classification",
                    [
                        "All",
                        "Side Effect",
                        "No Side Effect",
                        "Mixed Evidence",
                        "Insufficient Information",
                    ],
                    key="history_classification",
                )

            with row2_col2:

                patient_reference = st.text_input(
                    "Patient reference",
                    placeholder="PAT-001",
                    key="history_patient_reference",
                )

            with row2_col3:

                report_reference = st.text_input(
                    "Report reference",
                    placeholder="REP-001",
                    key="history_report_reference",
                )

            submitted = st.form_submit_button(
                "Search history",
                type="primary",
                use_container_width=True,
            )

    # ========================================================
    # LOAD HISTORY
    # ========================================================

    if submitted:

        try:

            with st.spinner(
                "Loading review history..."
            ):

                reviews = get_reviews(
                    classification=(
                        None
                        if classification == "All"
                        else classification
                    ),
                    patient_reference=(
                        patient_reference.strip()
                        or None
                    ),
                    report_reference=(
                        report_reference.strip()
                        or None
                    ),
                    medicine=(
                        medicine.strip()
                        or None
                    ),
                    search=(
                        search.strip()
                        or None
                    ),
                )

            st.session_state[
                "history_reviews"
            ] = reviews

            st.session_state[
                "history_loaded"
            ] = True

        except Exception as exc:

            st.error(
                f"Unable to load review history: {exc}"
            )

            return

    # ========================================================
    # INITIAL LOAD
    # ========================================================

    if not st.session_state.get(
        "history_loaded",
        False,
    ):

        try:

            reviews = get_reviews()

            st.session_state[
                "history_reviews"
            ] = reviews

            st.session_state[
                "history_loaded"
            ] = True

        except Exception as exc:

            st.error(
                f"Unable to load review history: {exc}"
            )

            return

    # ========================================================
    # RESULTS
    # ========================================================

    reviews = st.session_state.get(
        "history_reviews",
        [],
    )

    if not isinstance(
        reviews,
        list,
    ):
        reviews = []

    st.write("")

    st.caption(
        f"{len(reviews)} review(s) found"
    )

    if not reviews:

        st.info(
            "No saved reviews match the selected filters."
        )

        return

    # ========================================================
    # DISPLAY EACH REVIEW
    # ========================================================

    for review in reviews:

        if not isinstance(
            review,
            dict,
        ):
            continue

        review_id = review.get(
            "id",
            "N/A",
        )

        patient_reference = safe_text(
            review.get(
                "patient_reference"
            ),
            "Not provided",
        )

        report_reference = safe_text(
            review.get(
                "report_reference"
            ),
            "Not provided",
        )

        classification_value = safe_text(
            review.get(
                "narrative_classification"
            ),
            "Not classified",
        )

        reviewer_classification = safe_text(
            review.get(
                "reviewer_classification"
            ),
            "Needs Review",
        )

        review_text = safe_text(
            review.get(
                "text"
            ),
            "No narrative available",
        )

        source_name = safe_text(
            review.get(
                "source_name"
            ),
            "Not available",
        )

        created_at = safe_text(
            review.get(
                "created_at"
            ),
            "Not available",
        )

        # ====================================================
        # REVIEW CARD
        # ====================================================

        with st.container(
            border=True
        ):

            title_col, status_col = st.columns(
                [
                    1.4,
                    0.6,
                ]
            )

            with title_col:

                st.markdown(
                    f"### Case #{review_id}"
                )

            with status_col:

                st.markdown(
                    f"**{classification_value}**"
                )

            st.divider()

            info1, info2, info3 = st.columns(
                3
            )

            with info1:

                st.caption(
                    "Patient reference"
                )

                st.write(
                    patient_reference
                )

            with info2:

                st.caption(
                    "Report reference"
                )

                st.write(
                    report_reference
                )

            with info3:

                st.caption(
                    "Reviewer status"
                )

                st.write(
                    reviewer_classification
                )

            st.caption(
                "Narrative"
            )

            if len(
                review_text
            ) > 300:

                preview_text = (
                    review_text[:300]
                    + "..."
                )

            else:

                preview_text = review_text

            st.write(
                preview_text
            )

            footer1, footer2 = st.columns(
                2
            )

            with footer1:

                st.caption(
                    f"Source: {source_name}"
                )

            with footer2:

                st.caption(
                    f"Created: {created_at}"
                )
# ============================================================
# DISCLAIMER
# ============================================================

def show_disclaimer() -> None:

    st.write("")

    st.divider()

    show_review_history()

    st.caption(
        "MediReview structures information reported in medicine "
        "experience narratives. Reported associations do not establish "
        "that a medicine caused a symptom and should not replace "
        "clinical assessment."
    )





# ============================================================
# MAIN
# ============================================================

def main() -> None:

    initialize_state()

    apply_css()

    show_header()

    # ========================================================
    # TOP SECTION
    # ========================================================

    input_col, summary_col = (
        st.columns(
            [
                1.05,
                0.95,
            ],
            gap="large",
        )
    )

    # ========================================================
    # INPUT
    # ========================================================

    with input_col:

        with st.container(
            border=True
        ):

            show_input_panel()

        show_submitted_text_preview()

    # ========================================================
    # GET LATEST RESULT AFTER INPUT SUBMISSION
    # ========================================================

    result = (
        st.session_state.get(
            "analysis_result"
        )
    )

    # ========================================================
    # CASE SUMMARY
    # ========================================================

    with summary_col:

        if isinstance(
            result,
            dict,
        ):

            show_case_summary(
                result
            )

            show_case_overview(
                result
            )

        else:

            st.subheader(
                "Case summary"
            )

            with st.container(
                border=True
            ):

                st.info(
                    "Submit a medicine narrative or document "
                    "to begin the case analysis."
                )

    # ========================================================
    # NOTHING ANALYZED
    # ========================================================

    if not isinstance(
        result,
        dict,
    ):

        show_disclaimer()

        return

    # ========================================================
    # MEDICINES
    # ========================================================

    st.write("")

    st.divider()

    show_medicine_information(
        result
    )

    # ========================================================
    # TIMELINE + EXPERIENCE
    # ========================================================

    st.write("")

    st.divider()

    timeline_col, experience_col = (
        st.columns(
            [
                0.85,
                1.15,
            ],
            gap="large",
        )
    )

    with timeline_col:

        show_timeline(
            result
        )

    with experience_col:

        show_reported_experience(
            result
        )

    # ========================================================
    # CONTEXT + REVIEWER
    # ========================================================

    st.write("")

    st.divider()

    context_col, reviewer_col = (
        st.columns(
            [
                1.15,
                0.85,
            ],
            gap="large",
        )
    )

    with context_col:

        show_medicine_symptom_context(
            result
        )

    with reviewer_col:

        show_reviewer_assessment()

        st.write("")

        show_export(
            result
        )

        source_name = (
            st.session_state.get(
                "source_name"
            )
        )

        if source_name:

            st.caption(
                f"Source: {source_name}"
            )

    # ========================================================
    # FOOTER
    # ========================================================

    show_disclaimer()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()