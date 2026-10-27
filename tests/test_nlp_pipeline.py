from __future__ import annotations

import json
import tempfile
import unittest

import pandas as pd
from pathlib import Path

from src.dataset_ner import enrich_dataframe_with_ner, extract_ner_record
from src.medicine_extraction import extract_medicine_names
from src.service import analyze_batch_files, analyze_review, analyze_text_file


class NLPipelineTests(unittest.TestCase):
    def test_mixed_evidence_and_spans(self):
        text = (
            "Patient started Metformin 500 mg by mouth twice daily on October 1, 2026. "
            "After three days, I developed possible nausea and dizziness, but I denied headache."
        )
        result = analyze_review(
            text,
            patient_id="P-100",
            report_reference_id="R-200",
            include_model_prediction=False,
        )

        self.assertEqual(result["narrative_classification"], "Mixed Evidence")
        self.assertEqual(result["references"]["patient_id"], "P-100")
        self.assertEqual(result["references"]["report_reference_id"], "R-200")
        self.assertIn("nausea", result["reported_symptoms"])
        self.assertIn("headache", result["negated_symptoms"])

        metformin = result["medication_entities"][0]
        self.assertEqual(metformin["attributes"]["dosage"]["value"], "500 mg")
        self.assertEqual(metformin["attributes"]["route"]["normalized"], "oral")
        self.assertEqual(metformin["attributes"]["frequency"]["value"], "twice daily")

        nausea = next(entity for entity in result["symptom_entities"] if entity["normalized"] == "nausea")
        headache = next(entity for entity in result["symptom_entities"] if entity["normalized"] == "headache")
        self.assertTrue(nausea["assertion"]["uncertain"])
        self.assertFalse(nausea["assertion"]["negated"])
        self.assertTrue(headache["assertion"]["negated"])
        self.assertFalse(headache["assertion"]["uncertain"])

        for entity in result["entities"]:
            span = entity["span"]
            self.assertEqual(text[span["char_start"]:span["char_end"]], span["text"])

        self.assertTrue(result["relations"])
        self.assertTrue(all(not relation["clinical_causation_inferred"] for relation in result["relations"]))

    def test_explicit_absence_without_named_symptom(self):
        result = analyze_review(
            "I took the medicine as prescribed and had no side effects.",
            include_model_prediction=False,
        )
        self.assertEqual(result["narrative_classification"], "Explicit Absence of Events")

    def test_family_member_does_not_become_patient_event(self):
        result = analyze_review(
            "My mother had a rash last year while taking Aspirin.",
            include_model_prediction=False,
        )
        self.assertEqual(result["narrative_classification"], "Insufficient Information")
        symptom = result["symptom_entities"][0]
        self.assertEqual(symptom["assertion"]["subject"], "Family Member")
        self.assertEqual(symptom["assertion"]["temporal"], "Historical")

    def test_original_text_offsets_are_not_trimmed(self):
        text = "  Metformin caused nausea.  \n"
        result = analyze_review(text, include_model_prediction=False)
        self.assertEqual(result["source_text"], text)
        medication = result["medication_entities"][0]
        self.assertEqual(medication["span"]["char_start"], 2)
        self.assertEqual(
            text[medication["span"]["char_start"]:medication["span"]["char_end"]],
            "Metformin",
        )

    def test_subject_scope_resets_after_contrast(self):
        result = analyze_review(
            "My mother had nausea last year, but I developed rash today.",
            include_model_prediction=False,
        )
        nausea = next(entity for entity in result["symptom_entities"] if entity["normalized"] == "nausea")
        rash = next(entity for entity in result["symptom_entities"] if entity["normalized"] == "rash")
        self.assertEqual(nausea["assertion"]["subject"], "Family Member")
        self.assertEqual(nausea["assertion"]["temporal"], "Historical")
        self.assertEqual(rash["assertion"]["subject"], "Patient")
        self.assertEqual(rash["assertion"]["temporal"], "Current")

    def test_single_text_file_and_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "first.txt"
            second = Path(tmp) / "second.txt"
            first.write_bytes(b"Metformin caused nausea after two days.\r\nSecond line.")
            second.write_text("I had no nausea after taking Aspirin.", encoding="utf-8")

            single = analyze_text_file(
                first,
                patient_id="P1",
                report_reference_id="R1",
                include_model_prediction=False,
            )
            self.assertEqual(single["references"]["patient_id"], "P1")
            self.assertTrue(single["references"]["source_file"].endswith("first.txt"))
            self.assertIn("\r\n", single["source_text"])

            batch = analyze_batch_files(
                [first, second],
                metadata_by_file={
                    "first.txt": {"patient_id": "P1", "report_reference_id": "R1"},
                    "second.txt": {"patient_id": "P2", "report_reference_id": "R2", "site": "A"},
                },
                include_model_prediction=False,
            )
            self.assertEqual(len(batch), 2)
            self.assertEqual(batch[1]["references"]["patient_id"], "P2")
            self.assertEqual(batch[1]["references"]["metadata"]["site"], "A")

    def test_dataset_ner_enrichment_uses_original_text(self):
        source = "  Metformin 500 mg caused nausea after two days.  "
        frame = pd.DataFrame({"review": [source], "label": [2]})

        enriched = enrich_dataframe_with_ner(
            frame,
            source_column="review",
            progress_every=None,
        )

        self.assertEqual(enriched.loc[0, "review"], source)
        self.assertEqual(enriched.loc[0, "ner_error"], "")
        self.assertEqual(json.loads(enriched.loc[0, "ner_medication_names"]), ["Metformin"])
        self.assertIn("nausea", json.loads(enriched.loc[0, "ner_symptom_names"]))

        entities = json.loads(enriched.loc[0, "ner_entities_json"])
        medication = next(entity for entity in entities if entity["type"] == "MEDICATION")
        span = medication["span"]
        self.assertEqual(source[span["char_start"]:span["char_end"]], "Metformin")

    def test_extract_ner_record_has_structured_fields(self):
        record = extract_ner_record(
            "Aspirin 81 mg daily caused possible rash yesterday, but no nausea."
        )
        self.assertEqual(record["ner_error"], "")
        self.assertTrue(any(name.startswith("Aspirin") for name in json.loads(record["ner_medication_names"])))
        self.assertIn("rash", json.loads(record["ner_reported_symptoms"]))
        self.assertIn("nausea", json.loads(record["ner_negated_symptoms"]))
        self.assertEqual(record["narrative_classification"], "Mixed Evidence")

    def test_large_medicine_gazetteer_matcher_preserves_names(self):
        names = extract_medicine_names(
            "I used Zyrtec-D and Metformin, but not an unrelated word like metadata."
        )
        self.assertIn("ZYRTEC-D", names)
        self.assertIn("Metformin", names)



if __name__ == "__main__":
    unittest.main()
