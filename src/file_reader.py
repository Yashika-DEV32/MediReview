from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import BinaryIO


SUPPORTED_EXTENSIONS = {".txt", ".pdf", ".docx"}
MAX_FILE_SIZE_MB = 8


def extract_text_from_file(uploaded_file: BinaryIO) -> str:
    """Extract readable text from a Streamlit uploaded TXT, PDF, or DOCX file."""

    if uploaded_file is None:
        return ""

    file_name = str(getattr(uploaded_file, "name", "")).strip()
    extension = Path(file_name).suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError("Please upload a TXT, PDF, or DOCX file.")

    data = uploaded_file.getvalue()
    if not data:
        raise ValueError("The uploaded file is empty.")

    max_bytes = MAX_FILE_SIZE_MB * 1024 * 1024
    if len(data) > max_bytes:
        raise ValueError(f"Please upload a file smaller than {MAX_FILE_SIZE_MB} MB.")

    if extension == ".txt":
        text = data.decode("utf-8", errors="ignore").strip()

    elif extension == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ValueError(
                "PDF support is not installed. Run: pip install pypdf"
            ) from exc

        try:
            reader = PdfReader(BytesIO(data))
            pages = []
            for page in reader.pages:
                page_text = (page.extract_text() or "").strip()
                if page_text:
                    pages.append(page_text)
            text = "\n\n".join(pages).strip()
        except Exception as exc:
            raise ValueError("The PDF could not be read.") from exc

        if not text:
            raise ValueError(
                "No readable text was found in this PDF. If it is a scanned PDF, "
                "OCR would be required before analysis."
            )

    else:  # .docx
        try:
            from docx import Document
        except ImportError as exc:
            raise ValueError(
                "DOCX support is not installed. Run: pip install python-docx"
            ) from exc

        try:
            document = Document(BytesIO(data))
            paragraphs = [
                paragraph.text.strip()
                for paragraph in document.paragraphs
                if paragraph.text.strip()
            ]
            text = "\n".join(paragraphs).strip()
        except Exception as exc:
            raise ValueError("The DOCX file could not be read.") from exc

    if not text:
        raise ValueError("No readable text was found in the uploaded file.")

    return text
