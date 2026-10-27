
from django.urls import path

from .views import (
    analyze_review_api,
    api_health,
    review_list_create,
    review_detail,
    reanalyze_review,
    review_stats,
)


urlpatterns = [

    # ========================================================
    # ANALYZE REVIEW
    # ========================================================

    path(
        "analyze/",
        analyze_review_api,
        name="analyze-review",
    ),

    # ========================================================
    # HEALTH CHECK
    # ========================================================

    path(
        "health/",
        api_health,
        name="api-health",
    ),

    # ========================================================
    # REVIEW HISTORY + CREATE REVIEW
    # ========================================================

    path(
        "reviews/",
        review_list_create,
        name="review-list-create",
    ),

    # ========================================================
    # REVIEW STATISTICS
    # ========================================================

    path(
        "reviews/stats/",
        review_stats,
        name="review-stats",
    ),

    # ========================================================
    # SINGLE REVIEW
    # ========================================================

    path(
        "reviews/<int:review_id>/",
        review_detail,
        name="review-detail",
    ),

    # ========================================================
    # RE-ANALYZE REVIEW (BACKEND ONLY)
    # ========================================================

    path(
        "reviews/<int:review_id>/reanalyze/",
        reanalyze_review,
        name="reanalyze-review",
    ),

]
