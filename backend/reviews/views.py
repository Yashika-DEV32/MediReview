from __future__ import annotations


from django.db.models import Count, Q

from django.shortcuts import get_object_or_404


from rest_framework import status

from rest_framework.decorators import api_view

from rest_framework.response import Response


from src.service import analyze_review


from .models import Review

from .serializers import (

    ReviewAnalysisSerializer,

    ReviewCreateSerializer,

    ReviewerUpdateSerializer,

    ReviewSerializer,

)


# ============================================================

# HEALTH CHECK

# ============================================================


@api_view(["GET"])

def api_health(request):

    """

    Check whether the Django REST API is running.

    """


    return Response(

        {

            "status": "ok",

            "api": "running",

        },

        status=status.HTTP_200_OK,

    )


# ============================================================

# ANALYZE REVIEW

# ============================================================


@api_view(["POST"])

def analyze_review_api(request):

    """

    Analyze one medicine-related narrative.


    This endpoint performs NLP analysis only.

    It does not save the review in the database.

    """


    serializer = ReviewAnalysisSerializer(

        data=request.data

    )


    serializer.is_valid(

        raise_exception=True

    )


    data = serializer.validated_data


    text = data["text"]


    patient_reference = (

        data.get("patient_reference")

        or None

    )


    report_reference = (

        data.get("report_reference")

        or None

    )


    try:


        result = analyze_review(

            text,

            patient_id=patient_reference,

            report_reference_id=report_reference,

        )


        if not isinstance(

            result,

            dict,

        ):

            return Response(

                {

                    "error": (

                        "Analysis service returned "

                        "an invalid response."

                    )

                },

                status=status.HTTP_500_INTERNAL_SERVER_ERROR,

            )


        return Response(

            result,

            status=status.HTTP_200_OK,

        )


    except Exception as exc:


        return Response(

            {

                "error": "Review analysis failed.",

                "detail": str(exc),

            },

            status=status.HTTP_500_INTERNAL_SERVER_ERROR,

        )


# ============================================================

# REVIEW HISTORY + CREATE REVIEW

# ============================================================


@api_view(["GET", "POST"])

def review_list_create(request):

    """

    GET:

        Return review history with optional filters.


    POST:

        Analyze and save a new medicine review.

    """


    # ========================================================

    # GET - REVIEW HISTORY

    # ========================================================


    if request.method == "GET":


        reviews = Review.objects.all()


        # ----------------------------------------------------

        # QUERY PARAMETERS

        # ----------------------------------------------------


        classification = request.query_params.get(

            "classification"

        )


        patient_reference = request.query_params.get(

            "patient_reference"

        )


        report_reference = request.query_params.get(

            "report_reference"

        )


        medicine = request.query_params.get(

            "medicine"

        )


        search = request.query_params.get(

            "search"

        )


        # ----------------------------------------------------

        # CLASSIFICATION FILTER

        # ----------------------------------------------------


        if classification:


            reviews = reviews.filter(

                narrative_classification__iexact=(

                    classification.strip()

                )

            )


        # ----------------------------------------------------

        # PATIENT REFERENCE FILTER

        # ----------------------------------------------------


        if patient_reference:


            reviews = reviews.filter(

                patient_reference__iexact=(

                    patient_reference.strip()

                )

            )


        # ----------------------------------------------------

        # REPORT REFERENCE FILTER

        # ----------------------------------------------------


        if report_reference:


            reviews = reviews.filter(

                report_reference__iexact=(

                    report_reference.strip()

                )

            )


        # ----------------------------------------------------

        # GENERAL SEARCH

        # ----------------------------------------------------


        if search:


            search_value = search.strip()


            reviews = reviews.filter(

                Q(

                    patient_reference__icontains=search_value

                )

                |

                Q(

                    report_reference__icontains=search_value

                )

                |

                Q(

                    source_name__icontains=search_value

                )

                |

                Q(

                    text__icontains=search_value

                )

                |

                Q(

                    narrative_classification__icontains=search_value

                )

            )


        # ----------------------------------------------------

        # MEDICINE FILTER

        # ----------------------------------------------------

        #

        # Medicines are stored inside analysis_result.

        # Python-side filtering keeps this simple and

        # compatible with SQLite.

        # ----------------------------------------------------


        if medicine:


            medicine_query = (

                medicine

                .strip()

                .casefold()

            )


            filtered_reviews = []


            for review in reviews:


                analysis_result = (

                    review.analysis_result

                    or {}

                )


                medicines = analysis_result.get(

                    "medicines",

                    [],

                )


                if not isinstance(

                    medicines,

                    list,

                ):

                    continue


                matched = any(

                    medicine_query

                    in str(item).casefold()

                    for item in medicines

                )


                if matched:

                    filtered_reviews.append(

                        review

                    )


            reviews = filtered_reviews


        # ----------------------------------------------------

        # RESPONSE

        # ----------------------------------------------------


        serializer = ReviewSerializer(

            reviews,

            many=True,

        )


        return Response(

            serializer.data,

            status=status.HTTP_200_OK,

        )


    # ========================================================

    # POST - CREATE + ANALYZE + SAVE REVIEW

    # ========================================================


    serializer = ReviewCreateSerializer(

        data=request.data

    )


    serializer.is_valid(

        raise_exception=True

    )


    data = serializer.validated_data


    text = data["text"]


    patient_reference = (

        data.get("patient_reference")

        or None

    )


    report_reference = (

        data.get("report_reference")

        or None

    )


    source_name = (

        data.get("source_name")

        or None

    )


    try:


        # ----------------------------------------------------

        # NLP ANALYSIS

        # ----------------------------------------------------


        result = analyze_review(

            text,

            patient_id=patient_reference,

            report_reference_id=report_reference,

            source_file=source_name,

        )


        if not isinstance(

            result,

            dict,

        ):

            return Response(

                {

                    "error": (

                        "Analysis service returned "

                        "an invalid result."

                    )

                },

                status=status.HTTP_500_INTERNAL_SERVER_ERROR,

            )


        classification = result.get(

            "narrative_classification"

        )


        # ----------------------------------------------------

        # SAVE DATABASE RECORD

        # ----------------------------------------------------


        review = Review.objects.create(

            patient_reference=patient_reference,

            report_reference=report_reference,

            source_name=source_name,

            text=text,

            narrative_classification=classification,

            analysis_result=result,

        )


        # ----------------------------------------------------

        # RESPONSE

        # ----------------------------------------------------


        output_serializer = ReviewSerializer(

            review

        )


        return Response(

            output_serializer.data,

            status=status.HTTP_201_CREATED,

        )


    except Exception as exc:


        return Response(

            {

                "error": (

                    "Unable to analyze "

                    "and save review."

                ),

                "detail": str(exc),

            },

            status=status.HTTP_500_INTERNAL_SERVER_ERROR,

        )


# ============================================================

# GET / UPDATE / DELETE ONE REVIEW

# ============================================================


@api_view(["GET", "PATCH", "DELETE"])

def review_detail(request, review_id):

    """

    GET:

        Return one saved review.


    PATCH:

        Update reviewer classification and notes.


    DELETE:

        Delete one saved review.

    """


    review = get_object_or_404(

        Review,

        id=review_id,

    )


    # ========================================================

    # GET

    # ========================================================


    if request.method == "GET":


        serializer = ReviewSerializer(

            review

        )


        return Response(

            serializer.data,

            status=status.HTTP_200_OK,

        )


    # ========================================================

    # PATCH

    # ========================================================


    if request.method == "PATCH":


        serializer = ReviewerUpdateSerializer(

            review,

            data=request.data,

            partial=True,

        )


        serializer.is_valid(

            raise_exception=True

        )


        serializer.save()


        return Response(

            {

                "message": (

                    "Reviewer assessment "

                    "updated successfully."

                ),

                "id": review.id,

                "reviewer_classification": (

                    review.reviewer_classification

                ),

                "reviewer_notes": (

                    review.reviewer_notes

                ),

                "updated_at": (

                    review.updated_at

                ),

            },

            status=status.HTTP_200_OK,

        )


    # ========================================================

    # DELETE

    # ========================================================


    deleted_id = review.id

    review.delete()

    return Response(

        {

            "message": (

                "Review deleted successfully."

            ),

            "id": deleted_id,

        },

        status=status.HTTP_200_OK,

    )


# ============================================================

# RE-ANALYZE SAVED REVIEW

# ============================================================


@api_view(["POST"])

def reanalyze_review(request, review_id):

    """

    Re-run the latest NLP pipeline on an existing review.


    The review keeps the same database ID.

    Reviewer assessment is not modified.

    """


    review = get_object_or_404(

        Review,

        id=review_id,

    )


    try:


        result = analyze_review(

            review.text,

            patient_id=review.patient_reference,

            report_reference_id=(

                review.report_reference

            ),

            source_file=review.source_name,

        )


        if not isinstance(

            result,

            dict,

        ):

            return Response(

                {

                    "error": (

                        "Analysis service returned "

                        "an invalid result."

                    )

                },

                status=status.HTTP_500_INTERNAL_SERVER_ERROR,

            )


        review.analysis_result = result


        review.narrative_classification = (

            result.get(

                "narrative_classification"

            )

        )


        review.save(

            update_fields=[

                "analysis_result",

                "narrative_classification",

                "updated_at",

            ]

        )


        return Response(

            {

                "message": (

                    "Review re-analyzed successfully."

                ),

                "id": review.id,

                "narrative_classification": (

                    review.narrative_classification

                ),

                "analysis_result": (

                    review.analysis_result

                ),

                "updated_at": (

                    review.updated_at

                ),

            },

            status=status.HTTP_200_OK,

        )


    except Exception as exc:


        return Response(

            {

                "error": (

                    "Review re-analysis failed."

                ),

                "detail": str(exc),

            },

            status=status.HTTP_500_INTERNAL_SERVER_ERROR,

        )


# ============================================================

# REVIEW STATISTICS

# ============================================================


@api_view(["GET"])

def review_stats(request):

    """

    Return basic statistics for saved reviews.

    """


    # ========================================================

    # TOTAL REVIEWS

    # ========================================================


    total_reviews = (

        Review.objects.count()

    )


    # ========================================================

    # AUTOMATED CLASSIFICATION COUNTS

    # ========================================================


    classification_counts = (

        Review.objects

        .values(

            "narrative_classification"

        )

        .annotate(

            count=Count("id")

        )

        .order_by(

            "-count"

        )

    )


    # ========================================================

    # REVIEWER CLASSIFICATION COUNTS

    # ========================================================


    reviewer_counts = (

        Review.objects

        .exclude(

            reviewer_classification__isnull=True

        )

        .exclude(

            reviewer_classification=""

        )

        .values(

            "reviewer_classification"

        )

        .annotate(

            count=Count("id")

        )

        .order_by(

            "-count"

        )

    )


    return Response(

        {

            "total_reviews": (

                total_reviews

            ),

            "classification_counts": list(

                classification_counts

            ),

            "reviewer_classification_counts": list(

                reviewer_counts

            ),

        },

        status=status.HTTP_200_OK,

    )