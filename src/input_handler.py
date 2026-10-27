"""Input helpers for single narratives and batches of plain-text files."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping


@dataclass(slots=True)
class NarrativeInput:
    """Validated narrative plus optional source references."""

    text: str
    patient_id: str | None = None
    report_reference_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    source_file: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("Narrative text must be a non-empty string.")


def load_text_file(
    file_path: str | Path,
    *,
    patient_id: str | None = None,
    report_reference_id: str | None = None,
    metadata: Mapping[str, Any] | None = None,
    encoding: str = "utf-8",
) -> NarrativeInput:
    """Read one UTF-8 text narrative and retain optional references."""

    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Text file not found: {path}")
    if path.suffix.lower() != ".txt":
        raise ValueError(f"Only .txt files are supported for batch input: {path.name}")

    with path.open("r", encoding=encoding, newline="") as handle:
        text = handle.read()

    return NarrativeInput(
        text=text,
        patient_id=patient_id,
        report_reference_id=report_reference_id,
        metadata=dict(metadata or {}),
        source_file=str(path),
    )


def load_batch_text_files(
    file_paths: Iterable[str | Path],
    *,
    metadata_by_file: Mapping[str, Mapping[str, Any]] | None = None,
    encoding: str = "utf-8",
) -> list[NarrativeInput]:
    """Load multiple ``.txt`` files as independent narratives.

    ``metadata_by_file`` may use either the full path string or filename as a
    key. Supported reserved metadata keys are ``patient_id`` and
    ``report_reference_id``; all remaining keys are kept in ``metadata``.
    """

    inputs: list[NarrativeInput] = []
    metadata_map = metadata_by_file or {}

    for file_path in file_paths:
        path = Path(file_path)
        item_metadata = dict(
            metadata_map.get(str(path), metadata_map.get(path.name, {}))
        )
        patient_id = item_metadata.pop("patient_id", None)
        report_reference_id = item_metadata.pop("report_reference_id", None)
        inputs.append(
            load_text_file(
                path,
                patient_id=patient_id,
                report_reference_id=report_reference_id,
                metadata=item_metadata,
                encoding=encoding,
            )
        )

    return inputs
