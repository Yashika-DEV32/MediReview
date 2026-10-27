from __future__ import annotations

from typing import Any

import requests


API_BASE_URL = "http://127.0.0.1:8000/api"


def create_review(
    text: str,
    *,
    patient_reference: str | None = None,
    report_reference: str | None = None,
    source_name: str | None = None,
) -> dict[str, Any]:
    """
    Send a new review to Django.

    Django will:
    1. validate the request
    2. run the NLP pipeline
    3. save the case
    4. return the saved database record
    """

    payload = {
        "text": text,
        "patient_reference": patient_reference or "",
        "report_reference": report_reference or "",
        "source_name": source_name or "",
    }

    try:
        response = requests.post(
            f"{API_BASE_URL}/reviews/",
            json=payload,
            timeout=60,
        )

    except requests.ConnectionError as exc:
        raise RuntimeError(
            "Cannot connect to Django API. "
            "Make sure Django is running on http://127.0.0.1:8000."
        ) from exc

    except requests.Timeout as exc:
        raise RuntimeError(
            "The Django API took too long to respond."
        ) from exc

    except requests.RequestException as exc:
        raise RuntimeError(
            f"API request failed: {exc}"
        ) from exc

    # --------------------------------------------------------
    # HANDLE API ERRORS
    # --------------------------------------------------------

    if not response.ok:

        try:
            error_data = response.json()
        except ValueError:
            error_data = response.text

        raise RuntimeError(
            f"API returned {response.status_code}: {error_data}"
        )

    # --------------------------------------------------------
    # JSON RESPONSE
    # --------------------------------------------------------

    try:
        data = response.json()

    except ValueError as exc:
        raise RuntimeError(
            "Django returned an invalid JSON response."
        ) from exc

    if not isinstance(data, dict):
        raise RuntimeError(
            "Django returned an unexpected response."
        )

    return data


def update_review_assessment(
    review_id: int,
    reviewer_classification: str,
    reviewer_notes: str,
) -> dict[str, Any]:
    """
    Save the human reviewer's assessment in Django.
    """

    payload = {
        "reviewer_classification": reviewer_classification,
        "reviewer_notes": reviewer_notes,
    }

    try:
        response = requests.patch(
            f"{API_BASE_URL}/reviews/{review_id}/",
            json=payload,
            timeout=30,
        )

    except requests.ConnectionError as exc:
        raise RuntimeError(
            "Cannot connect to Django API. "
            "Make sure Django is running."
        ) from exc

    except requests.Timeout as exc:
        raise RuntimeError(
            "Django API took too long to respond."
        ) from exc

    except requests.RequestException as exc:
        raise RuntimeError(
            f"API request failed: {exc}"
        ) from exc

    if not response.ok:

        try:
            error_data = response.json()

        except ValueError:
            error_data = response.text

        raise RuntimeError(
            f"Django API returned "
            f"{response.status_code}: "
            f"{error_data}"
        )

    try:
        data = response.json()

    except ValueError as exc:
        raise RuntimeError(
            "Django returned an invalid JSON response."
        ) from exc

    if not isinstance(
        data,
        dict,
    ):
        raise RuntimeError(
            "Django returned an unexpected response."
        )

    return data


def update_review_assessment(
    review_id: int,
    reviewer_classification: str,
    reviewer_notes: str,
) -> dict[str, Any]:
    """
    Update reviewer classification and notes
    for an existing saved review.
    """

    payload = {
        "reviewer_classification": reviewer_classification,
        "reviewer_notes": reviewer_notes,
    }

    try:
        response = requests.patch(
            f"{API_BASE_URL}/reviews/{review_id}/",
            json=payload,
            timeout=30,
        )

    except requests.ConnectionError as exc:
        raise RuntimeError(
            "Cannot connect to Django API. "
            "Make sure Django is running."
        ) from exc

    except requests.Timeout as exc:
        raise RuntimeError(
            "Django API took too long to respond."
        ) from exc

    except requests.RequestException as exc:
        raise RuntimeError(
            f"API request failed: {exc}"
        ) from exc

    if not response.ok:

        try:
            error_data = response.json()

        except ValueError:
            error_data = response.text

        raise RuntimeError(
            f"Django API returned "
            f"{response.status_code}: "
            f"{error_data}"
        )

    try:
        data = response.json()

    except ValueError as exc:
        raise RuntimeError(
            "Django returned an invalid JSON response."
        ) from exc

    if not isinstance(
        data,
        dict,
    ):
        raise RuntimeError(
            "Django returned an unexpected response."
        )

    return data


def get_reviews(
    *,
    classification: str | None = None,
    patient_reference: str | None = None,
    report_reference: str | None = None,
    medicine: str | None = None,
    search: str | None = None,
) -> list[dict[str, Any]]:
    """
    Fetch saved review history from Django.

    Optional filters:
    - classification
    - patient_reference
    - report_reference
    - medicine
    - search
    """

    params: dict[str, str] = {}

    if classification:
        params["classification"] = classification

    if patient_reference:
        params["patient_reference"] = patient_reference

    if report_reference:
        params["report_reference"] = report_reference

    if medicine:
        params["medicine"] = medicine

    if search:
        params["search"] = search

    try:
        response = requests.get(
            f"{API_BASE_URL}/reviews/",
            params=params,
            timeout=30,
        )

    except requests.ConnectionError as exc:
        raise RuntimeError(
            "Cannot connect to Django API. "
            "Make sure Django is running."
        ) from exc

    except requests.Timeout as exc:
        raise RuntimeError(
            "Django API took too long to respond."
        ) from exc

    except requests.RequestException as exc:
        raise RuntimeError(
            f"API request failed: {exc}"
        ) from exc

    if not response.ok:

        try:
            error_data = response.json()

        except ValueError:
            error_data = response.text

        raise RuntimeError(
            f"Django API returned "
            f"{response.status_code}: "
            f"{error_data}"
        )

    try:
        data = response.json()

    except ValueError as exc:
        raise RuntimeError(
            "Django returned an invalid JSON response."
        ) from exc

    if not isinstance(
        data,
        list,
    ):
        raise RuntimeError(
            "Django returned an unexpected response."
        )

    return data

def get_review_by_id(
    review_id: int,
) -> dict[str, Any]:
    """
    Fetch one saved review from Django.
    """

    try:
        response = requests.get(
            f"{API_BASE_URL}/reviews/{review_id}/",
            timeout=30,
        )

    except requests.ConnectionError as exc:
        raise RuntimeError(
            "Cannot connect to Django API. "
            "Make sure Django is running."
        ) from exc

    except requests.Timeout as exc:
        raise RuntimeError(
            "Django API took too long to respond."
        ) from exc

    except requests.RequestException as exc:
        raise RuntimeError(
            f"API request failed: {exc}"
        ) from exc

    # Check HTTP response
    if not response.ok:

        try:
            error_data = response.json()

        except ValueError:
            error_data = response.text

        raise RuntimeError(
            f"Django API returned "
            f"{response.status_code}: "
            f"{error_data}"
        )

    # Convert JSON
    try:
        data = response.json()

    except ValueError as exc:
        raise RuntimeError(
            "Django returned invalid JSON."
        ) from exc

    if not isinstance(
        data,
        dict,
    ):
        raise RuntimeError(
            "Django returned an unexpected response."
        )

    return data


# ============================================================
# RE-ANALYZE SAVED REVIEW
# ============================================================

def reanalyze_review(
    review_id: int,
) -> dict[str, Any]:
    """
    Re-run NLP analysis for an existing saved review.
    """

    try:
        response = requests.post(
            f"{API_BASE_URL}/reviews/{review_id}/reanalyze/",
            timeout=120,
        )

    except requests.ConnectionError as exc:
        raise RuntimeError(
            "Cannot connect to Django API. "
            "Make sure Django is running."
        ) from exc

    except requests.Timeout as exc:
        raise RuntimeError(
            "Review re-analysis took too long."
        ) from exc

    except requests.RequestException as exc:
        raise RuntimeError(
            f"API request failed: {exc}"
        ) from exc

    if not response.ok:
        try:
            error_data = response.json()
        except ValueError:
            error_data = response.text

        raise RuntimeError(
            f"Django API returned "
            f"{response.status_code}: {error_data}"
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError(
            "Django returned invalid JSON."
        ) from exc

    if not isinstance(data, dict):
        raise RuntimeError(
            "Unexpected response from Django."
        )

    return data


#DELETE

def delete_review(review_id: int) -> None:
    """Delete a saved case through the Django API."""

    review_id = int(review_id)

    if review_id <= 0:
        raise ValueError("Invalid case ID.")

    url = f"{API_BASE_URL.rstrip('/')}/reviews/{review_id}/"

    # Use JWT authentication when enabled.
    request_function = globals().get(
        "authenticated_request",
        requests.request,
    )

    try:
        response = request_function(
            "DELETE",
            url,
            timeout=30,
        )

    except requests.RequestException as exc:
        raise RuntimeError(
            f"Cannot complete delete request: {exc}"
        ) from exc

    if not response.ok:
        try:
            details = response.json()
        except ValueError:
            details = response.text

        raise RuntimeError(
            f"Django API returned {response.status_code}: {details}"
        )
