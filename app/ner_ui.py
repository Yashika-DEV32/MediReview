from __future__ import annotations


import re


import json

import sys

from pathlib import Path

from typing import Any



import pandas as pd

import streamlit as st



PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:

    sys.path.insert(0, str(PROJECT_ROOT))



from app.api_client import (  # noqa: E402

    create_review,

    get_review_by_id,


    get_reviews,


    update_review_assessment,

)



st.set_page_config(page_title="MediReview", page_icon="💊", layout="wide")



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

FILTER_OPTIONS = ["All", *REVIEWER_OPTIONS[1:]]

VIEWS = ["New case", "Current case", "History"]

BADGE_COLORS = {

    "Side Effect": "red",

    "Mixed Evidence": "orange",

    "No Side Effect": "green",

    "Insufficient Information": "gray",

    "Needs Review": "blue",

}


# ============================================================

# STATE

# ============================================================



def initialize_state() -> None:

    defaults = {

        "active_view": "New case",

        "goto": None,

        "analysis_result": None,

        "submitted_text": "",

        "source_name": None,

        "review_id": None,

        "reviewer_classification": "Needs Review",

        "reviewer_notes": "",

        "history_reviews": [],

        "history_loaded": False,

        "history_error": None,


    }

    for key, value in defaults.items():

        st.session_state.setdefault(key, value)


def reset_current_case() -> None:

    """Start a new case. Saved data is never deleted."""

    for key in ("manual_review", "patient_reference_input", "report_reference_input", "uploaded_report"):

        st.session_state.pop(key, None)

    st.session_state.update(

        analysis_result=None,

        submitted_text="",

        source_name=None,

        review_id=None,

        reviewer_classification="Needs Review",

        reviewer_notes="",

        active_view="New case",

    )


def open_saved_case(review_id: int) -> None:

    """Callback: load a saved case into the workspace."""

    try:

        review = get_review_by_id(review_id)

        result = review.get("analysis_result")

        if not isinstance(result, dict):

            raise ValueError("Saved review has no valid analysis result.")

        result = dict(result)

        result["review_id"] = review.get("id")

        result["patient_reference"] = review.get("patient_reference")

        result["report_reference"] = review.get("report_reference")



        classification = review.get("reviewer_classification") or "Needs Review"

        if classification not in REVIEWER_OPTIONS:

            classification = "Needs Review"



        st.session_state.update(

            analysis_result=result,

            review_id=review.get("id"),

            submitted_text=review.get("text") or "",

            source_name=review.get("source_name") or "Saved review",

            reviewer_classification=classification,

            reviewer_notes=review.get("reviewer_notes") or "",

            active_view="Current case",

            history_error=None,

        )

        st.session_state.pop(f"reviewer_classification_select_{review_id}", None)
        st.session_state.pop(f"reviewer_notes_field_{review_id}", None)

    except Exception as exc:

        st.session_state["history_error"] = f"Unable to open case: {exc}"


# ============================================================

# HELPERS

# ============================================================



def safe_text(value: Any, fallback: str = "—") -> str:

    text = "" if value is None else str(value).strip()

    return text or fallback


def unique_strings(values: Any) -> list[str]:

    if not isinstance(values, (list, tuple)):

        return []

    seen: set[str] = set()

    out: list[str] = []

    for value in values:

        text = str(value).strip() if value is not None else ""

        if text and text.casefold() not in seen:

            seen.add(text.casefold())

            out.append(text)

    return out


def show_badge(value: Any) -> None:

    text = safe_text(value, "Not classified")

    color = BADGE_COLORS.get(text, "gray")

    if hasattr(st, "badge"):

        st.badge(text, color=color)

    else:

        st.markdown(f":{color}[**{text}**]")


def get_entity_values(result: dict[str, Any], entity_type: str) -> list[str]:

    entities = result.get("entities")

    if not isinstance(entities, list):

        return []

    return unique_strings([

        e.get("value")

        for e in entities

        if isinstance(e, dict) and str(e.get("type", "")).strip().upper() == entity_type

    ])


def _span_start(entity: dict[str, Any]) -> int:

    try:

        return int((entity.get("span") or {}).get("char_start", 0))

    except (TypeError, ValueError):

        return 0


def _new_med(name: str) -> dict[str, Any]:

    return {"medicine": name, "dosage": None, "frequency": None, "route": None}


def merge_duplicate_medications(details: list[Any]) -> list[dict[str, Any]]:

    merged: dict[str, dict[str, Any]] = {}

    for item in details:

        if not isinstance(item, dict):

            continue

        name = str(item.get("medicine") or item.get("medication") or item.get("name") or "").strip()

        if not name:

            continue

        current = merged.setdefault(name.casefold(), _new_med(name))

        for field, value in (

            ("dosage", item.get("dosage") or item.get("dose") or item.get("strength")),

            ("frequency", item.get("frequency")),

            ("route", item.get("route")),

        ):

            if value:

                current[field] = value

    return [
        item for item in merged.values()
        if item["medicine"].casefold() not in {"none", "null"}
    ]


def build_medications_from_entities(entities: list[Any]) -> list[dict[str, Any]]:

    medicines: dict[str, dict[str, Any]] = {}

    current: dict[str, Any] | None = None

    field_map = {

        "DOSAGE": "dosage", "STRENGTH": "dosage", "DOSE": "dosage",

        "FREQUENCY": "frequency", "ROUTE": "route",

    }

    for entity in sorted((e for e in entities if isinstance(e, dict)), key=_span_start):

        etype = str(entity.get("type", "")).strip().upper()

        value = str(entity.get("value", "")).strip()

        if not value:

            continue

        if etype in {"MEDICATION", "MEDICINE", "DRUG"}:

            current = medicines.setdefault(value.casefold(), _new_med(value))

        elif current is not None and etype in field_map:

            current[field_map[etype]] = value

    return [
        med for med in medicines.values()
        if med["medicine"].casefold() not in {"none", "null"}
    ]


def get_medication_details(result: dict[str, Any]) -> list[dict[str, Any]]:

    backend = result.get("medication_details")

    if isinstance(backend, list) and backend:

        merged = merge_duplicate_medications(backend)

        if merged:

            return merged

    entities = result.get("entities")

    if isinstance(entities, list):

        details = build_medications_from_entities(entities)

        if details:

            return details

    return [
        _new_med(m) for m in unique_strings(result.get("medicines", []))
        if m.casefold() not in {"none", "null"}
    ]


def medications_table(details: list[dict[str, Any]]) -> pd.DataFrame:
    rows = [
        {
            "Medicine": safe_text(item.get("medicine")),
            "Dosage": safe_text(item.get("dosage")),
            "Frequency": safe_text(item.get("frequency")),
            "Route": safe_text(item.get("route")),
        }
        for item in details
        if isinstance(item, dict)
        and str(item.get("medicine") or "").strip()
        and str(item.get("medicine")).strip().casefold() not in {"none", "null"}
    ]
    return pd.DataFrame(rows, columns=["Medicine", "Dosage", "Frequency", "Route"])

def medicine_symptom_links(result: dict[str, Any]) -> list[dict[str, str]]:

    relations = result.get("relations")

    if not isinstance(relations, list):

        return []

    rows, seen = [], set()

    for rel in relations:

        if not isinstance(rel, dict):

            continue

        medicine = rel.get("medication") or rel.get("medicine")

        symptom = rel.get("symptom")

        if not medicine or not symptom:

            continue

        assertion = rel.get("symptom_assertion")

        assertion = assertion if isinstance(assertion, dict) else {}

        status = (

            "Denied" if assertion.get("negated")

            else "Uncertain" if assertion.get("uncertain")

            else "Reported"

        )

        key = (str(medicine).casefold(), str(symptom).casefold(), status)

        if key in seen:

            continue

        seen.add(key)

        rows.append({"Medicine": str(medicine), "Symptom": str(symptom), "Status": status})

    return rows


def extract_text_from_file(uploaded_file: Any) -> str:

    name = str(uploaded_file.name).lower()

    try:

        if name.endswith(".txt"):

            return uploaded_file.getvalue().decode("utf-8", errors="ignore").strip()

        if name.endswith(".pdf"):

            from pypdf import PdfReader



            pages = [(p.extract_text() or "").strip() for p in PdfReader(uploaded_file).pages]

            return "\n\n".join(p for p in pages if p).strip()

        if name.endswith(".docx"):

            from docx import Document



            paras = [(p.text or "").strip() for p in Document(uploaded_file).paragraphs]

            return "\n".join(p for p in paras if p).strip()

    except ImportError as exc:

        raise ValueError(f"Missing library for this file type: {exc.name}") from exc

    except Exception as exc:

        raise ValueError(f"Unable to read file: {exc}") from exc

    raise ValueError("Unsupported format. Use TXT, PDF or DOCX.")


def format_timestamp(value: Any) -> str:

    text = safe_text(value)

    return text[:16].replace("T", " ") if text != "—" else text


# ============================================================

# SIDEBAR

# ============================================================



def apply_layout() -> None:
    """Keep spacing and colours consistent across Streamlit versions."""
    st.markdown(
        """
        <style>
        :root {
            --mr-primary: #0e6f8f;
            --mr-teal: #087e85;
            --mr-border: #e1e9ee;
            --mr-muted: #64748b;
            --mr-soft: #f3f8fa;
        }
        .block-container {
            max-width: 1230px;
            padding-top: 2.25rem;
            padding-bottom: 3rem;
            padding-left: 2.5rem;
            padding-right: 2.5rem;
        }
        [data-testid="stMain"] [data-testid="stVerticalBlock"] {
            gap: 0.95rem;
        }
        [data-testid="stHorizontalBlock"] { gap: 1.3rem; }
        h1, h2, h3 {
            color: #173445;
            letter-spacing: -0.025em;
            margin: 0 !important;
            padding: 0 !important;
        }
        h2 { font-size: 1.85rem !important; font-weight: 700 !important; }
        h3 { font-size: 1.24rem !important; font-weight: 650 !important; }
        [data-testid="stCaptionContainer"] {
            color: var(--mr-muted);
            line-height: 1.5;
        }
        [data-testid="stMarkdownContainer"] p { margin-bottom: 0; }
        [data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 15px;
            background: #fff;
        }
        [data-testid="stForm"] {
            border-color: var(--mr-border);
            border-radius: 15px;
            padding: 1.35rem 1.45rem 1.2rem;
        }
        [data-testid="stMetric"] {
            min-height: 100px;
            padding: 14px 16px;
            border: 1px solid var(--mr-border);
            border-radius: 12px;
            background: var(--mr-soft);
        }
        [data-testid="stMetricLabel"] { color: var(--mr-muted); }
        [data-testid="stMetricValue"] { color: #173445; }
        div[data-baseweb="input"] > div,
        div[data-baseweb="textarea"] > div,
        div[data-baseweb="select"] > div {
            border-radius: 9px;
        }
        [data-testid="stFileUploader"] section {
            border-radius: 12px;
            border-color: #cadde6;
            background: #f9fcfd;
        }
        [data-testid="stDataFrame"], [data-testid="stDataEditor"] {
            border-radius: 10px;
            overflow: hidden;
        }
        button[data-baseweb="tab"] {
            padding: 11px 18px;
            font-weight: 600;
        }
        button[data-baseweb="tab"][aria-selected="true"] {
            color: var(--mr-primary);
        }
        [data-baseweb="tab-panel"] { padding-top: 1rem; }
        .stButton > button, .stDownloadButton > button,
        [data-testid="stFormSubmitButton"] > button {
            border-radius: 10px;
            min-height: 41px;
            font-weight: 600;
        }
        hr {
            border-color: var(--mr-border) !important;
            margin: 0.85rem 0 !important;
        }
        [data-testid="stSidebar"] {
            background: #f3f6f9;
            border-right: 1px solid var(--mr-border);
        }
        [data-testid="stSidebarUserContent"] { padding-top: 2rem; }
        [data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: 0.8rem; }
        [data-testid="stSidebar"] [role="radiogroup"] { gap: 0.45rem; }
        [data-testid="stSidebar"] [role="radiogroup"] label {
            border-radius: 9px;
            padding: 9px 10px;
        }
        [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
            background: #e5f2f5;
        }
        .mr-brand {
            font-size: 1.42rem;
            font-weight: 750;
            color: #0e6f8f;
        }
        .mr-brand-sub {
            color: #64748b;
            font-size: 0.88rem;
            margin-top: 3px;
        }
        .mr-section-label {
            color: var(--mr-teal);
            font-size: 0.76rem;
            font-weight: 700;
            letter-spacing: 0.09em;
            text-transform: uppercase;
        }
        @media (max-width: 900px) {
            .block-container { padding: 1.6rem 1.15rem 2.5rem; }
            [data-testid="stHorizontalBlock"] { gap: 0.7rem; }
            [data-testid="stForm"] { padding: 1rem; }
            [data-testid="stMetric"] {
                padding: 11px;
                min-height: 88px;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

def show_sidebar() -> str:
    with st.sidebar:
        st.markdown(
            "<div class='mr-brand'>✚ MediReview</div>"
            "<div class='mr-brand-sub'>Medicine safety review</div>",
            unsafe_allow_html=True,
        )
        st.markdown("<div class='mr-section-label'>Workspace</div>", unsafe_allow_html=True)
        view = st.radio("Navigate", VIEWS, key="active_view", label_visibility="collapsed")
        review_id = st.session_state.get("review_id")
        if review_id is not None:
            st.divider()
            st.caption("Current case")
            st.markdown(f"**Case {review_id}**")
            show_badge(st.session_state["reviewer_classification"])
            st.button("Close case", on_click=reset_current_case, use_container_width=True)
        st.divider()
        st.caption(
            "Medicine–symptom links are reported associations, "
            "not proof of causation."
        )
    return view

def show_new_case() -> None:
    st.header("New case", anchor=False)
    st.caption("Enter a medicine experience narrative or upload a document for review.")
    with st.form("analysis_form"):
        st.markdown("**Case references**")
        c1, c2 = st.columns(2)
        patient_reference = c1.text_input(
            "Patient reference", key="patient_reference_input", placeholder="Optional patient ID"
        )
        report_reference = c2.text_input(
            "Report reference", key="report_reference_input", placeholder="Optional report ID"
        )
        st.markdown("**Review content**")
        write_tab, upload_tab = st.tabs(["Write narrative", "Upload document"])
        with write_tab:
            narrative = st.text_area(
                "Medicine experience",
                height=220,
                key="manual_review",
                placeholder=(
                    "Patient took Metformin 500 mg twice daily and later reported "
                    "nausea, but denied rash."
                ),
            )
        with upload_tab:
            upload = st.file_uploader(
                "Upload report (TXT, PDF or DOCX)",
                type=["txt", "pdf", "docx"],
                key="uploaded_report",
            )
        _, button_col = st.columns([3, 1])
        with button_col:
            submitted = st.form_submit_button(
                "Analyze case", type="primary", use_container_width=True
            )
    if not submitted:
        return
    text, source_name = (narrative or "").strip(), "Typed narrative"
    if not text and upload is not None:
        try:
            text = extract_text_from_file(upload)
        except ValueError as exc:
            st.error(str(exc))
            return
        source_name = upload.name
    # Validate input before NLP processing
    text = text.strip()

    if not text:
        st.error("Please enter a medicine review.")
        return

    # Extract actual alphabetic words, excluding number fragments
    words = re.findall(
        r"(?<!\w)[A-Za-z]+(?:'[A-Za-z]+)?(?!\w)",
        text
    )

    # Reject inputs containing too few real words
    if len(words) < 3:
        st.error(
            "Invalid review. Please enter at least "
            "3 meaningful words."
        )
        return

    # Reject long repeated character sequences
    if re.search(r"([A-Za-z0-9])\1{5,}", text):
        st.error(
            "Invalid review. Excessive repeated "
            "characters are not allowed."
        )
        return

    # Basic medical relevance check
    
    medical_keywords = {

        # Medicine and treatment terminology
        "medicine", "medicines", "medication", "medications",
        "drug", "drugs", "tablet", "tablets", "capsule", "capsules",
        "pill", "pills", "syrup", "injection", "injections",
        "cream", "ointment", "drops", "inhaler", "supplement",
        "supplements", "antibiotic", "antibiotics",
        "painkiller", "painkillers", "prescription",
        "prescribed", "treatment", "therapy", "therapeutic",
        "pharmaceutical", "vitamin", "vaccination", "vaccine",

        # Medicine names
        "metformin", "paracetamol", "acetaminophen",
        "ibuprofen", "aspirin", "amoxicillin",
        "azithromycin", "doxycycline", "ciprofloxacin",
        "cefixime", "cephalexin", "penicillin",
        "metronidazole", "omeprazole", "pantoprazole",
        "esomeprazole", "ranitidine", "famotidine",
        "cetirizine", "levocetirizine", "loratadine",
        "fexofenadine", "montelukast", "prednisone",
        "prednisolone", "dexamethasone", "salbutamol",
        "albuterol", "atorvastatin", "rosuvastatin",
        "simvastatin", "amlodipine", "losartan",
        "telmisartan", "lisinopril", "metoprolol",
        "atenolol", "propranolol", "insulin",
        "glimepiride", "sitagliptin", "empagliflozin",
        "levothyroxine", "sertraline", "fluoxetine",
        "escitalopram", "alprazolam", "gabapentin",
        "pregabalin", "tramadol", "diclofenac",
        "naproxen", "warfarin", "apixaban",
        "clopidogrel", "ondansetron", "loperamide",

        # Common symptoms
        "nausea", "nauseous", "vomiting", "vomit",
        "headache", "headaches", "migraine",
        "dizziness", "dizzy", "vertigo",
        "fever", "chills", "fatigue", "tiredness",
        "weakness", "weak", "drowsiness", "drowsy",
        "sleepiness", "insomnia", "sleeplessness",
        "rash", "rashes", "itching", "itchy",
        "hives", "redness", "swelling", "inflamed",
        "inflammation", "pain", "painful",
        "cramps", "cramping", "bloating",
        "diarrhea", "diarrhoea", "constipation",
        "indigestion", "heartburn", "acidity",
        "stomachache", "abdominal", "gastric",
        "gastritis", "cough", "coughing",
        "sneezing", "congestion", "runny",
        "breathlessness", "breathing",
        "wheezing", "palpitations", "tachycardia",
        "sweating", "tremors", "shaking",
        "numbness", "tingling", "blurred",
        "vision", "dryness", "dehydration",
        "anxiety", "restlessness", "irritability",
        "confusion", "fainting", "seizure",
        "bleeding", "bruising", "burning",
        "infection", "allergy", "allergic",
        "anaphylaxis", "reaction", "reactions",

        # Medical conditions and measurements
        "diabetes", "diabetic", "hypertension",
        "hypotension", "cholesterol", "asthma",
        "arthritis", "depression", "thyroid",
        "hypothyroidism", "hyperthyroidism",
        "anemia", "anaemia", "glucose",
        "pressure", "heartbeat", "pulse",
        "oxygen", "temperature", "sugar",

        # Dosage, route and frequency
        "dose", "doses", "dosage", "strength",
        "mg", "mcg", "ml", "gram", "grams",
        "oral", "orally", "topical", "topically",
        "intravenous", "intramuscular",
        "subcutaneous", "sublingual",
        "daily", "weekly", "monthly",
        "once", "twice", "thrice",
        "morning", "nightly", "bedtime",
        "hourly", "frequency", "administered",
        "administration",

        # Side effects and treatment outcomes
        "side", "effect", "effects", "adverse",
        "symptom", "symptoms", "discomfort",
        "intolerance", "tolerated", "tolerance",
        "relief", "relieved", "improved",
        "improvement", "worsened", "worsening",
        "recovered", "recovery", "resolved",
        "persistent", "persisted",
        "ineffective", "effective",

        # Patient experiences
        "took", "taken", "taking", "started",
        "stopped", "discontinued", "experienced",
        "prescribing", "prescriber",
    }


    has_medical_keyword = bool(
        set(word.lower() for word in words) & medical_keywords
    )

    has_dosage = bool(
        re.search(
            r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml)\b",
            text,
            re.IGNORECASE
        )
    )

    if not has_medical_keyword and not has_dosage:
        st.error(
            "Invalid review. Please enter a medicine-related "
            "experience containing treatment or symptom information."
        )
        return
    try:
        with st.spinner("Analyzing and saving..."):
            response = create_review(
                text,
                patient_reference=patient_reference.strip() or None,
                report_reference=report_reference.strip() or None,
                source_name=source_name,
            )
        result = response.get("analysis_result")
        if not isinstance(result, dict):
            raise ValueError("Response has no valid analysis result.")
        result["review_id"] = response.get("id")
        result["patient_reference"] = response.get("patient_reference")
        result["report_reference"] = response.get("report_reference")
    except Exception as exc:
        st.error(f"Unable to analyze case: {exc}")
        return
    st.session_state.update(
        analysis_result=result,
        submitted_text=text,
        source_name=source_name,
        review_id=response.get("id"),
        reviewer_classification="Needs Review",
        reviewer_notes="",
        history_loaded=False,
        goto="Current case",
    )
    st.rerun()

def show_export(result: dict[str, Any]) -> None:

    export = dict(result)

    export["display_medication_details"] = get_medication_details(result)

    export["reviewer_classification"] = st.session_state["reviewer_classification"]

    export["reviewer_notes"] = st.session_state["reviewer_notes"]

    st.download_button(

        "Download JSON",

        data=json.dumps(export, indent=2, ensure_ascii=False, default=str),

        file_name=f"medireview_case_{safe_text(result.get('review_id'), 'new')}.json",

        mime="application/json",

        use_container_width=True,

    )


def show_case_header(result: dict[str, Any]) -> None:
    title_col, export_col = st.columns([4, 1], vertical_alignment="center")
    with title_col:
        st.header(f"Case {safe_text(result.get('review_id'))}", anchor=False)
    with export_col:
        show_export(result)
    st.caption(
        f"Patient {safe_text(result.get('patient_reference'))}  ·  "
        f"Report {safe_text(result.get('report_reference'))}  ·  "
        f"{safe_text(st.session_state.get('source_name'))}"
    )
    with st.container(border=True):
        status_left, status_right = st.columns(2)
        with status_left:
            st.caption("Automated assessment")
            show_badge(result.get("narrative_classification"))
        with status_right:
            st.caption("Reviewer assessment")
            show_badge(st.session_state["reviewer_classification"])
    med_col, reported_col, denied_col = st.columns(3)
    med_col.metric("NLP medicines", len(get_medication_details(result)))
    reported_col.metric("NLP symptoms reported", len(unique_strings(result.get("reported_symptoms", []))))
    denied_col.metric("NLP symptoms denied", len(unique_strings(result.get("negated_symptoms", []))))

def _bullets(items: list[str], empty: str) -> None:

    if items:

        st.markdown("\n".join(f"- {item}" for item in items))

    else:

        st.caption(empty)


def show_evidence(result: dict[str, Any]) -> None:
    # Display the original NLP findings.
    meds = get_medication_details(result)
    with st.container(border=True):
        st.markdown("**Original NLP medicine information**")
        if meds:
            st.dataframe(medications_table(meds), hide_index=True, use_container_width=True)
        else:
            st.caption("No medicines identified.")
    reported = unique_strings(result.get("reported_symptoms", []))
    denied = unique_strings(result.get("negated_symptoms", []))
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            st.markdown("**Symptoms reported**")
            _bullets(reported, "None identified.")
    with right:
        with st.container(border=True):
            st.markdown("**Symptoms denied**")
            _bullets(denied, "None identified.")
    timing = [*get_entity_values(result, "DATE"), *get_entity_values(result, "DURATION")]
    if timing:
        with st.container(border=True):
            st.markdown("**Timeline**")
            st.write(" · ".join(timing))
    links = medicine_symptom_links(result)
    if links:
        with st.container(border=True):
            st.markdown("**Medicine–symptom mentions**")
            st.dataframe(pd.DataFrame(links), hide_index=True, use_container_width=True)
            st.caption("Reported associations only; causation is not inferred.")

def show_reviewer_assessment() -> None:

    review_id = st.session_state.get("review_id")

    key = str(review_id)

    current = st.session_state["reviewer_classification"]

    index = REVIEWER_OPTIONS.index(current) if current in REVIEWER_OPTIONS else 0



    with st.container(border=True):

        st.markdown("**Assessment**")

        classification = st.selectbox(

            "Classification", REVIEWER_OPTIONS, index=index, key=f"reviewer_classification_select_{key}"

        )

        notes = st.text_area(

            "Notes",

            value=st.session_state["reviewer_notes"],

            height=160,

            key=f"reviewer_notes_field_{key}",

        )

        if st.button("Save assessment", type="primary", use_container_width=True, key=f"save_assessment_{key}"):

            try:

                with st.spinner("Saving..."):

                    response = update_review_assessment(int(review_id), classification, notes.strip())

                st.session_state["reviewer_classification"] = response.get(

                    "reviewer_classification", classification

                )

                st.session_state["reviewer_notes"] = response.get("reviewer_notes", notes)

                st.success("Assessment saved.")

            except Exception as exc:

                st.error(f"Unable to save: {exc}")


def show_current_case() -> None:
    result = st.session_state.get("analysis_result")
    if not isinstance(result, dict):
        st.header("Current case", anchor=False)
        st.info("No case is open. Create a new case or open one from History.")
        return
    show_case_header(result)
    evidence_tab, review_tab, narrative_tab = st.tabs(
        ["Evidence", "Reviewer workspace", "Narrative"]
    )
    with evidence_tab:
        show_evidence(result)
    with review_tab:
        show_reviewer_assessment()
    with narrative_tab:
        with st.container(border=True):
            st.markdown("**Original narrative**")
            st.write(st.session_state.get("submitted_text", "") or "—")

def show_history() -> None:
    st.header("History", anchor=False)
    st.caption("Search saved reviews and open a case to inspect its evidence.")
    if st.session_state.get("history_error"):
        st.error(st.session_state["history_error"])
    with st.form("history_filter_form"):
        st.markdown("**Filter cases**")
        c1, c2, c3 = st.columns(3)
        search = c1.text_input("Search", key="history_search", placeholder="Review text or case ID")
        medicine = c2.text_input("Medicine", key="history_medicine", placeholder="Medicine name")
        classification = c3.selectbox("Classification", FILTER_OPTIONS, key="history_classification")
        c4, c5 = st.columns(2)
        patient_reference = c4.text_input("Patient reference", key="history_patient_reference")
        report_reference = c5.text_input("Report reference", key="history_report_reference")
        _, search_col = st.columns([4, 1])
        with search_col:
            submitted = st.form_submit_button("Search cases", type="primary", use_container_width=True)
    if submitted or not st.session_state["history_loaded"]:
        try:
            with st.spinner("Loading..."):
                if submitted:
                    reviews = get_reviews(
                        classification=None if classification == "All" else classification,
                        patient_reference=patient_reference.strip() or None,
                        report_reference=report_reference.strip() or None,
                        medicine=medicine.strip() or None,
                        search=search.strip() or None,
                    )
                else:
                    reviews = get_reviews()
            st.session_state["history_reviews"] = reviews if isinstance(reviews, list) else []
            st.session_state["history_loaded"] = True
        except Exception as exc:
            st.error(f"Unable to load history: {exc}")
            return
    reviews = [r for r in st.session_state["history_reviews"] if isinstance(r, dict)]
    if not reviews:
        st.info("No cases match.")
        return

    # Selection is from the previous run so the action can sit above the table.
    state = st.session_state.get("history_table") or {}
    rows = (state.get("selection") or {}).get("rows") or []
    selected_id = None
    if rows and rows[0] < len(reviews):
        try:
            selected_id = int(reviews[rows[0]].get("id"))
        except (TypeError, ValueError):
            selected_id = None
    count_col, open_col = st.columns([4, 1], vertical_alignment="center")
    count_col.caption(f"{len(reviews)} case(s) · select a row to open it")
    open_col.button(
        "Open case", type="primary", disabled=selected_id is None,
        on_click=open_saved_case, args=(selected_id,), use_container_width=True,
    )
    table = pd.DataFrame([
        {
            "Case": r.get("id"),
            "Patient": safe_text(r.get("patient_reference")),
            "Report": safe_text(r.get("report_reference")),
            "Automated": safe_text(r.get("narrative_classification"), "Not classified"),
            "Reviewer": safe_text(r.get("reviewer_classification"), "Needs Review"),
            "Created": format_timestamp(r.get("created_at")),
        }
        for r in reviews
    ])
    st.dataframe(
        table, hide_index=True, on_select="rerun", selection_mode="single-row",
        key="history_table", use_container_width=True,
    )

def main() -> None:

    initialize_state()

    apply_layout()



    # Apply a pending view change before the navigation widget is created.

    if st.session_state["goto"]:

        st.session_state["active_view"] = st.session_state["goto"]

        st.session_state["goto"] = None



    view = show_sidebar()



    if view == "New case":

        show_new_case()

    elif view == "Current case":

        show_current_case()

    else:

        show_history()


if __name__ == "__main__":

    main()