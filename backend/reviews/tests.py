from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from .models import Review


class ReviewApiWithoutCorrectionsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.review = Review.objects.create(
            text="I took Metformin 500 mg daily and felt nausea.",
            analysis_result={"narrative_classification": "Side Effect"},
            narrative_classification="Side Effect",
        )

    def test_health_check(self):
        self.assertEqual(self.client.get("/api/health/").status_code, 200)

    def test_retrieve_saved_case(self):
        response = self.client.get(f"/api/reviews/{self.review.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], self.review.pk)

    def test_reviewer_assessment_still_works(self):
        response = self.client.patch(
            f"/api/reviews/{self.review.pk}/",
            {"reviewer_classification": "Needs Review", "reviewer_notes": "Review evidence."},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.review.refresh_from_db()
        self.assertEqual(self.review.reviewer_notes, "Review evidence.")

    def test_corrections_endpoint_removed(self):
        response = self.client.get(f"/api/reviews/{self.review.pk}/corrections/")
        self.assertEqual(response.status_code, 404)

    def test_case_delete_still_works(self):
        pk = self.review.pk
        response = self.client.delete(f"/api/reviews/{pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Review.objects.filter(pk=pk).exists())
