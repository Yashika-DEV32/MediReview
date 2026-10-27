"""Create a complete, printable MediReview case report from saved NLP findings."""

from __future__ import annotations

import json
import re
import textwrap
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    LongTable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

TEAL = colors.HexColor("#087C88")
INK = colors.HexColor("#203744")
MUTED = colors.HexColor("#647A88")
BORDER = colors.HexColor("#DDE7EB")
LIGHT = colors.HexColor("#F2F8F9")
WHITE = colors.white
IST = timezone(timedelta(hours=5, minutes=30))


def _get_fonts() -> tuple[str, str]:
    """Use a widely available Unicode font when possible (including Windows)."""
    regular_paths = [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/calibri.ttf"),
        Path("C:/Windows/Fonts/segoeui.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    bold_paths = [
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("C:/Windows/Fonts/calibrib.ttf"),
        Path("C:/Windows/Fonts/segoeuib.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ]
    regular = next((p for p in regular_paths if p.is_file()), None)
    bold = next((p for p in bold_paths if p.is_file()), None)
    if regular is None:
        return "Helvetica", "Helvetica-Bold"
    if "MRReportRegular" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("MRReportRegular", str(regular)))
    if bold is None:
        return "MRReportRegular", "MRReportRegular"
    if "MRReportBold" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("MRReportBold", str(bold)))
    return "MRReportRegular", "MRReportBold"


def _as_text(value: Any, default: str = "Not provided") -> str:
    if value is None or value == "":
        return default
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, default=str)
    return str(value)


def _xml(value: Any) -> str:
    """Escape dynamic user text so it cannot break ReportLab Paragraph markup."""
    text = _as_text(value)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", text)
    return escape(text).replace("\n", "<br/>")


def _unique(values: Any) -> list[str]:
    if not isinstance(values, (list, tuple)):
        return []
    seen = set()
    result = []
    for value in values:
        text = _as_text(value, "").strip()
        if text and text.casefold() not in seen:
            result.append(text)
            seen.add(text.casefold())
    return result


def create_pdf_report(
    result: dict[str, Any],
    *,
    case_id: Any,
    patient_reference: Any,
    report_reference: Any,
    source_name: Any,
    original_narrative: str,
    medication_details: list[dict[str, Any]],
    reviewer_classification: str,
    reviewer_notes: str,
) -> bytes:
    """Generate PDF in memory: nothing is written to a server-side file."""
    if not isinstance(result, dict):
        raise ValueError("Missing NLP analysis to include in the PDF.")

    regular, bold = _get_fonts()
    styles = {
        "title": ParagraphStyle(
            "MRTitle", fontName=bold, fontSize=19, leading=24,
            textColor=INK, spaceAfter=3,
        ),
        "subtitle": ParagraphStyle(
            "MRSubtitle", fontName=regular, fontSize=9, leading=13,
            textColor=MUTED, spaceAfter=12,
        ),
        "section": ParagraphStyle(
            "MRSection", fontName=bold, fontSize=11, leading=15,
            textColor=TEAL, spaceBefore=14, spaceAfter=7,
            keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "MRBody", fontName=regular, fontSize=8.6, leading=13,
            textColor=INK, spaceAfter=5, splitLongWords=True,
        ),
        "small": ParagraphStyle(
            "MRSmall", fontName=regular, fontSize=7.5, leading=11,
            textColor=INK, spaceAfter=3, splitLongWords=True,
        ),
        "table_head": ParagraphStyle(
            "MRTableHead", fontName=bold, fontSize=7.8, leading=11,
            textColor=WHITE,
        ),
        "appendix": ParagraphStyle(
            "MRAppendix", fontName=regular, fontSize=7, leading=10.5,
            textColor=INK, leftIndent=7, spaceAfter=1, splitLongWords=True,
        ),
        "notice": ParagraphStyle(
            "MRNotice", fontName=regular, fontSize=7.5, leading=11,
            textColor=MUTED, spaceAfter=8,
        ),
    }

    output = BytesIO()
    document = SimpleDocTemplate(
        output, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=19 * mm, bottomMargin=19 * mm,
        title=f"MediReview Case {_as_text(case_id, 'Report')}",
        author="MediReview",
    )
    story: list[Any] = []

    def para(value: Any, style: str = "body") -> Paragraph:
        return Paragraph(_xml(value), styles[style])

    def section(title: str) -> None:
        story.append(Paragraph(_xml(title), styles["section"]))

    def matrix(headers: list[str], rows: list[list[Any]], widths: list[float] | None = None) -> None:
        if not rows:
            story.append(para("No information recorded."))
            return
        content: list[list[Any]] = [
            [Paragraph(_xml(h), styles["table_head"]) for h in headers]
        ]
        content.extend([[para(v, "small") for v in row] for row in rows])
        table = LongTable(
            content, colWidths=widths, repeatRows=1, hAlign="LEFT",
            splitByRow=1,
        )
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), TEAL),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, 0), (-1, 0), 0.5, TEAL),
            ("LINEBELOW", (0, 1), (-1, -1), 0.3, BORDER),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        story.append(table)
        story.append(Spacer(1, 3 * mm))

    story.append(Paragraph("MediReview", styles["title"]))
    story.append(Paragraph(
        "MEDICINE SAFETY REVIEW REPORT  |  NLP EVIDENCE &amp; REVIEWER ASSESSMENT",
        styles["subtitle"],
    ))
    story.append(HRFlowable(width="100%", color=BORDER, thickness=0.8))

    section("1. Case details")
    matrix(["Field", "Value"], [
        ["Case ID", _as_text(case_id)],
        ["Patient reference", _as_text(patient_reference)],
        ["Report reference", _as_text(report_reference)],
        ["Source", _as_text(source_name)],
        ["Report exported (IST)", datetime.now(IST).strftime("%d %b %Y, %I:%M %p")],
    ], [46 * mm, 128 * mm])

    section("2. Automated and reviewer assessments")
    matrix(["Assessment", "Result"], [
        ["NLP classification", _as_text(result.get("narrative_classification"), "Not classified")],
        ["Reviewer classification", _as_text(reviewer_classification, "Needs Review")],
    ], [46 * mm, 128 * mm])
    story.append(Paragraph("<b>Reviewer notes</b>", styles["body"]))
    note_lines = _as_text(reviewer_notes, "No notes recorded").splitlines()
    for note_line in note_lines or ["No notes recorded"]:
        for offset in range(0, len(note_line), 850):
            story.append(para(note_line[offset:offset + 850]))
        if not note_line.strip():
            story.append(Spacer(1, 2 * mm))

    section("3. Identified medicines")
    medications = [m for m in medication_details if isinstance(m, dict)]
    med_rows = []
    for med in medications:
        med_rows.append([
            med.get("medicine") or med.get("Medicine") or med.get("name"),
            med.get("dosage") or med.get("Dosage"),
            med.get("frequency") or med.get("Frequency"),
            med.get("route") or med.get("Route"),
        ])
    matrix(["Medicine", "Dosage", "Frequency", "Route"], med_rows,
           [51 * mm, 37 * mm, 47 * mm, 39 * mm])

    section("4. Reported and denied symptoms")
    reported = _unique(result.get("reported_symptoms"))
    denied = _unique(result.get("negated_symptoms"))
    uncertain = _unique(result.get("uncertain_symptoms"))
    matrix(["Symptom status", "Extracted symptoms"], [
        ["Reported", ", ".join(reported) if reported else "None identified"],
        ["Denied / negated", ", ".join(denied) if denied else "None identified"],
        ["Uncertain", ", ".join(uncertain) if uncertain else "None identified"],
    ], [46 * mm, 128 * mm])

    entities = result.get("entities")
    entities = entities if isinstance(entities, list) else []
    section("5. Timeline evidence")
    timeline = []
    for entity in entities:
        if isinstance(entity, dict) and str(entity.get("type", "")).upper() in {"DATE", "DURATION", "TIME"}:
            timeline.append([entity.get("type"), entity.get("value")])
    matrix(["Type", "Evidence text"], timeline, [46 * mm, 128 * mm])

    section("6. Medicine-symptom associations")
    relations = result.get("relations")
    relations = relations if isinstance(relations, list) else []
    rel_rows = []
    for relation in relations:
        if not isinstance(relation, dict):
            continue
        assertion = relation.get("symptom_assertion")
        assertion = assertion if isinstance(assertion, dict) else {}
        status = (
            "Denied" if assertion.get("negated")
            else "Uncertain" if assertion.get("uncertain")
            else "Reported"
        )
        rel_rows.append([
            relation.get("medication") or relation.get("medicine"),
            relation.get("symptom"), status,
        ])
    matrix(["Medicine", "Symptom", "Evidence status"], rel_rows,
           [67 * mm, 67 * mm, 40 * mm])
    story.append(para(
        "These links are text-based reported associations and do not establish causality.",
        "notice",
    ))

    section("7. Extracted entities and evidence spans")
    entity_rows = []
    for entity in entities:
        if not isinstance(entity, dict):
            continue
        span = entity.get("span")
        if isinstance(span, dict):
            start = span.get("char_start", span.get("start"))
            end = span.get("char_end", span.get("end"))
            location = f"{start}-{end}" if start is not None and end is not None else "-"
        else:
            location = "-"
        assertion = entity.get("assertion")
        if not isinstance(assertion, dict):
            assertion = {}
        flags = [
            name for name, match in (
                ("negated", assertion.get("negated", entity.get("negated"))),
                ("uncertain", assertion.get("uncertain", entity.get("uncertain"))),
                ("historical", assertion.get("historical", entity.get("historical"))),
            ) if match
        ]
        entity_rows.append([
            entity.get("type"), entity.get("value"),
            location, ", ".join(flags) if flags else "-",
        ])
    matrix(["Entity type", "Exact text", "Offsets", "Assertion"], entity_rows,
           [40 * mm, 78 * mm, 24 * mm, 32 * mm])

    section("8. Original patient narrative")
    raw_narrative = _as_text(original_narrative, "No original narrative available")
    # Split long narratives into printable paragraphs to avoid a giant unbreakable block.
    for original_line in raw_narrative.splitlines() or [raw_narrative]:
        if not original_line.strip():
            story.append(Spacer(1, 2 * mm))
            continue
        for offset in range(0, len(original_line), 850):
            story.append(para(original_line[offset:offset + 850]))

    section("9. Complete structured NLP evidence (audit appendix)")
    story.append(para(
        "The following preserves all fields returned in the saved NLP analysis result, "
        "including any additional extracted metadata not displayed in the summary tables.",
        "notice",
    ))
    payload = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    for line in payload.splitlines():
        if not line.strip():
            continue
        # Text chunks stay within the printable width; indentation is shown in text.
        depth = min((len(line) - len(line.lstrip(" "))) // 2, 9)
        shortened = line.strip()
        for part in textwrap.wrap(shortened, width=95, break_long_words=True,
                                  break_on_hyphens=False, replace_whitespace=False) or [""]:
            entry = ("  " * depth) + part
            story.append(para(entry, "appendix"))

    def decorate(canvas: Any, doc: Any) -> None:
        canvas.saveState()
        w, h = A4
        canvas.setStrokeColor(BORDER)
        canvas.setLineWidth(0.45)
        canvas.line(18 * mm, 14 * mm, w - 18 * mm, 14 * mm)
        canvas.setFont(regular, 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(18 * mm, 10 * mm, "MediReview  |  Medicine safety review evidence")
        canvas.drawRightString(w - 18 * mm, 10 * mm, f"Page {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=decorate, onLaterPages=decorate)
    return output.getvalue()
