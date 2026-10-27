
from rest_framework import serializers

from .models import Review


# ============================================================
# ANALYZE REVIEW SERIALIZER
# ============================================================

class ReviewAnalysisSerializer(serializers.Serializer):

    text = serializers.CharField(
        required=True,
        allow_blank=False,
        min_length=3,
        max_length=50000
    )

    patient_reference = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=100,
    )

    report_reference = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=100,
    )


# ============================================================
# CREATE AND SAVE REVIEW SERIALIZER
# ============================================================

class ReviewCreateSerializer(serializers.Serializer):

    text = serializers.CharField(
        required=True,
        allow_blank=False,
        min_length=3,
        max_length=50000,
    )

    patient_reference = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=100,
    )

    report_reference = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=100,
    )

    source_name = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=255,
    )


# ============================================================
# SAVED REVIEW OUTPUT SERIALIZER
# ============================================================

class ReviewSerializer(serializers.ModelSerializer):

    class Meta:

        model = Review

        fields = [
            "id",
            "patient_reference",
            "report_reference",
            "source_name",
            "text",
            "narrative_classification",
            "analysis_result",
            "reviewer_classification",
            "reviewer_notes",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "narrative_classification",
            "analysis_result",
            "created_at",
            "updated_at",
        ]


# ============================================================
# REVIEWER ASSESSMENT UPDATE SERIALIZER
# ============================================================

class ReviewerUpdateSerializer(serializers.ModelSerializer):

    class Meta:

        model = Review

        fields = [
            "reviewer_classification",
            "reviewer_notes",
        ]

    def validate_reviewer_classification(self, value):

        allowed_values = [
            "Needs Review",
            "Side Effect",
            "No Side Effect",
            "Mixed Evidence",
            "Insufficient Information",
        ]

        if value and value not in allowed_values:

            raise serializers.ValidationError(
                "Invalid reviewer classification."
            )

        return value


from rest_framework import serializers


def validate_text(self, value):
    text = value.strip()

    if not text:
        raise serializers.ValidationError(
            "Please enter a medicine review."
        )

    if not any(char.isalpha() for char in text):
        raise serializers.ValidationError(
            "Invalid review. Enter a meaningful text "
            "narrative instead of only numbers or symbols."
        )

    return text