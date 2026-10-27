from django.db import models


class Review(models.Model):
    patient_reference = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    report_reference = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    source_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    text = models.TextField()

    narrative_classification = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    analysis_result = models.JSONField(
        default=dict,
        blank=True,
    )

    # ========================================================
    # REVIEWER ASSESSMENT
    # ========================================================

    reviewer_classification = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    reviewer_notes = models.TextField(
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return (
            self.report_reference
            or self.patient_reference
            or f"Review {self.id}"
        )
