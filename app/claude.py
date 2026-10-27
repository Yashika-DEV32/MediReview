from __future__ import annotations

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
FILTER_OPTIONS = ["All", *REVIEWER_OPTIONS[1:]]
VIEWS = ["New case", "Current case", "History"]
CLASS_COLORS = {
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
    for key in (
        "manual_review",
        "patient_reference_input",
        "report_reference_input",
        "uploaded_report",
        "input_method",
    ):
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
    except Exception as exc:
        st.session_state["history_error"] = f"Unable to open case: {exc}"


# ============================================================
# STYLE
# ============================================================

def apply_css() -> None:
    st.markdown(
        """
        <style>
        .stApp { background:#0b0f17; color:#f8fafc; }
        .block-container { max-width:1400px; padding:1.2rem 2rem 3rem; }
        header[data-testid="stHeader"] { background:transparent; }
        #MainMenu, footer { visibility:hidden; }
        h1,h2,h3,h4,h5 { color:#f8fafc !important; }
        p,label,.stCaption { color:#a4adbb !important; }
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background:#111722 !important; border:1px solid #2a3342 !important;
            border-radius:12px !important;
        }
        div[data-testid="stTextArea"] textarea,
        div[data-testid="stTextInput"] input {
            background:#171d29 !important; color:#f8fafc !important;
            border:1px solid #333d4f !important; border-radius:8px !important;
        }
        div[data-baseweb="select"] > div {
            background:#171d29 !important; border-color:#333d4f !important;
        }
        .stButton > button, .stFormSubmitButton > button, .stDownloadButton > button {
            border-radius:8px !important; min-height:40px !important; font-weight:600 !important;
        }
        .stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {
            background:#ff4b55 !important; color:#fff !important; border:none !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


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


def classification_label(value: Any) -> str:
    text = safe_text(value, "Not classified")
    return f":{CLASS_COLORS.get(text, 'gray')}[**{text}**]"


def get_entity_values(result: dict[str, Any], entity_type: str) -> list[str]:
    entities = result.get("entities")
    if not isinstance(entities, list):
        return []
    values = [
        str(e.get("value", "")).strip()
        for e in entities
        if isinstance(e, dict) and str(e.get("type", "")).strip().upper() == entity_type
    ]
    return unique_strings(values)


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
    return list(merged.values())


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
    return list(medicines.values())


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
    return [_new_med(m) for m in unique_strings(result.get("medicines", []))]


def medications_table(details: list[dict[str, Any]]) -> pd.DataFrame:
    rows = [
        {
            "Medicine": safe_text(m.get("medicine")),
            "Dosage": safe_text(m.get("dosage")),
            "Frequency": safe_text(m.get("frequency")),
            "Route": safe_text(m.get("route")),
        }
        for m in details
        if isinstance(m, dict)
    ]
    return pd.DataFrame(rows, columns=["Medicine", "Dosage", "Frequency", "Route"])


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


# ============================================================
# NEW CASE
# ============================================================

def show_new_case() -> None:
    st.subheader("New case")
    method = st.radio(
        "Input",
        ["Write narrative", "Upload document"],
        horizontal=True,
        key="input_method",
        label_visibility="collapsed",
    )

    with st.form("analysis_form"):
        c1, c2 = st.columns(2)
        patient_reference = c1.text_input("Patient reference", key="patient_reference_input")
        report_reference = c2.text_input("Report reference", key="report_reference_input")

        text, upload = "", None
        if method == "Write narrative":
            text = st.text_area(
                "Narrative",
                height=260,
                key="manual_review",
                placeholder="e.g. Patient took Metformin 500 mg twice daily and later reported nausea, denied rash.",
            )
        else:
            upload = st.file_uploader(
                "Report (TXT, PDF, DOCX)", type=["txt", "pdf", "docx"], key="uploaded_report"
            )
        submitted = st.form_submit_button("Analyze case", type="primary", use_container_width=True)

    if not submitted:
        return

    source_name = "Typed narrative"
    if method == "Upload document":
        if upload is None:
            st.warning("Upload a document first.")
            return
        try:
            text = extract_text_from_file(upload)
        except ValueError as exc:
            st.error(str(exc))
            return
        source_name = upload.name

    text = (text or "").strip()
    if len(text.split()) < 3:
        st.warning("Narrative is empty or too short to analyze.")
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


# ============================================================
# CURRENT CASE — EVIDENCE
# ============================================================

def show_case_header(result: dict[str, Any]) -> None:
    left, right = st.columns([3, 1.4])
    with left:
        st.subheader(f"Case #{safe_text(result.get('review_id'))}")
        st.markdown(
            f"Automated assessment: {classification_label(result.get('narrative_classification'))}"
            f" · Reviewer: {classification_label(st.session_state['reviewer_classification'])}"
        )
        st.caption(
            f"Patient: {safe_text(result.get('patient_reference'))} · "
            f"Report: {safe_text(result.get('report_reference'))} · "
            f"Source: {safe_text(st.session_state.get('source_name'))}"
        )
    with right:
        st.button("＋ New case", on_click=reset_current_case, use_container_width=True)
        show_export(result)


def show_evidence(result: dict[str, Any]) -> None:
    st.markdown("##### Medicines")
    meds = get_medication_details(result)
    if meds:
        st.dataframe(medications_table(meds), hide_index=True, use_container_width=True)
    else:
        st.caption("None identified.")

    reported = unique_strings(result.get("reported_symptoms", []))
    denied = unique_strings(result.get("negated_symptoms", []))
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("##### ⚠ Symptoms reported")
        for s in reported:
            st.write(f"• {s}")
        if not reported:
            st.caption("None identified.")
    with c2:
        st.markdown("##### ✓ Symptoms denied")
        for s in denied:
            st.write(f"• {s}")
        if not denied:
            st.caption("None identified.")

    dates = get_entity_values(result, "DATE")
    durations = get_entity_values(result, "DURATION")
    if dates or durations:
        st.markdown("##### Timeline")
        st.write(" · ".join([*dates, *durations]))

    links = medicine_symptom_links(result)
    if links:
        st.markdown("##### Medicine–symptom mentions")
        st.dataframe(pd.DataFrame(links), hide_index=True, use_container_width=True)
        st.caption("Co-mentions in the narrative only. Causation is not inferred.")


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


# ============================================================
# CURRENT CASE — REVIEW
# ============================================================

def show_reviewer_assessment() -> None:
    review_id = st.session_state.get("review_id")
    key = str(review_id)
    current = st.session_state["reviewer_classification"]
    index = REVIEWER_OPTIONS.index(current) if current in REVIEWER_OPTIONS else 0

    st.markdown("##### Assessment")
    classification = st.selectbox(
        "Classification", REVIEWER_OPTIONS, index=index, key=f"reviewer_classification_select_{key}"
    )
    notes = st.text_area(
        "Notes",
        value=st.session_state["reviewer_notes"],
        height=120,
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


def show_current_case() -> None:
    result = st.session_state.get("analysis_result")
    if not isinstance(result, dict):
        st.info("No case open. Create a new case or open one from History.")
        return

    show_case_header(result)
    evidence_tab, review_tab, narrative_tab = st.tabs(["Evidence", "Review", "Narrative"])
    with evidence_tab:
        show_evidence(result)
    with review_tab:
        show_reviewer_assessment()
    with narrative_tab:
        st.text_area(
            "Original narrative",
            value=st.session_state.get("submitted_text", ""),
            height=320,
            disabled=True,
            label_visibility="collapsed",
        )


# ============================================================
# HISTORY
# ============================================================

def show_history() -> None:
    st.subheader("History")
    if st.session_state.get("history_error"):
        st.error(st.session_state["history_error"])

    with st.form("history_filter_form"):
        c1, c2, c3 = st.columns(3)
        search = c1.text_input("Search", key="history_search")
        medicine = c2.text_input("Medicine", key="history_medicine")
        classification = c3.selectbox("Classification", FILTER_OPTIONS, key="history_classification")
        c4, c5, c6 = st.columns([1, 1, 1])
        patient_reference = c4.text_input("Patient reference", key="history_patient_reference")
        report_reference = c5.text_input("Report reference", key="history_report_reference")
        c6.write("")
        c6.write("")
        submitted = c6.form_submit_button("Search", type="primary", use_container_width=True)

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
    st.caption(f"{len(reviews)} case(s)")
    if not reviews:
        st.info("No cases match.")
        return

    header = st.columns([0.6, 1.2, 1.2, 1.5, 1.5, 1.4, 0.9])
    for col, label in zip(
        header, ["Case", "Patient", "Report", "Automated", "Reviewer", "Created", ""]
    ):
        col.caption(label)

    for review in reviews:
        review_id = review.get("id")
        row = st.columns([0.6, 1.2, 1.2, 1.5, 1.5, 1.4, 0.9])
        row[0].write(f"#{safe_text(review_id)}")
        row[1].write(safe_text(review.get("patient_reference")))
        row[2].write(safe_text(review.get("report_reference")))
        row[3].markdown(classification_label(review.get("narrative_classification")))
        row[4].markdown(classification_label(review.get("reviewer_classification") or "Needs Review"))
        row[5].write(safe_text(review.get("created_at")))
        try:
            row[6].button(
                "Open",
                key=f"open_case_{review_id}",
                on_click=open_saved_case,
                args=(int(review_id),),
                use_container_width=True,
            )
        except (TypeError, ValueError):
            row[6].caption("Invalid ID")


# ============================================================

def main() -> None:
    initialize_state()
    apply_css()

    # Apply a pending view change before the navigation widget is created.
    if st.session_state["goto"]:
        st.session_state["active_view"] = st.session_state["goto"]
        st.session_state["goto"] = None

    st.title("💊 MediReview")
    view = st.radio("View", VIEWS, horizontal=True, key="active_view", label_visibility="collapsed")
    st.divider()

    if view == "New case":
        show_new_case()
    elif view == "Current case":
        show_current_case()
    else:
        show_history()

    st.caption(
        "Reported associations do not establish causation and do not replace clinical assessment."
    )


if __name__ == "__main__":
    main()