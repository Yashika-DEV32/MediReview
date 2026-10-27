from __future__ import annotations

import json
from typing import Any, Sequence

import joblib

from src.paths import ARTIFACTS, MODELS
from src.preprocessing import clean_review


Predictor = tuple[Any, Any, dict[int, str]]


def load_predictor() -> Predictor:
    paths = [
        MODELS / "best_model.joblib",
        ARTIFACTS / "tfidf.joblib",
        ARTIFACTS / "label_mapping.json",
    ]
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError("Run notebooks 02–04 first. Missing: " + ", ".join(missing))

    model = joblib.load(paths[0])
    vectorizer = joblib.load(paths[1])
    mapping = json.loads(paths[2].read_text(encoding="utf-8"))
    labels = {int(value): str(key) for key, value in mapping.items()}
    return model, vectorizer, labels


def predict_reviews(
    reviews: Sequence[str],
    predictor: Predictor | None = None,
) -> list[str]:
    cleaned = [clean_review(review) for review in reviews]
    if not cleaned or any(not text for text in cleaned):
        raise ValueError("Enter at least one non-empty review.")

    model, vectorizer, labels = predictor if predictor is not None else load_predictor()
    predictions = model.predict(vectorizer.transform(cleaned))
    return [labels[int(prediction)] for prediction in predictions]
