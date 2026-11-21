from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from .models import User, Department, ComplaintCategory, Complaint, UserRole

class JanSahayakAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.dept = Department.objects.create(name="Solid Waste Management", code="SWM", sla_hours=24)
        self.category = ComplaintCategory.objects.create(
            name="Garbage and Sanitation",
            slug="garbage-and-sanitation",
            department=self.dept
        )
        self.citizen = User.objects.create_user(
            username="testcitizen",
            password="testpassword",
            role=UserRole.CITIZEN
        )

    def test_ai_analysis_endpoint(self):
        response = self.client.post('/api/ai/process_text/', {
            'text': 'Hamare gali me kachra pada hai aur badboo aa rahi hai'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('category', response.data)
        self.assertEqual(response.data['category'], 'Garbage and Sanitation')

    def test_create_and_track_complaint(self):
        self.client.force_authenticate(user=self.citizen)
        response = self.client.post('/api/complaints/', {
            'title': 'Pothole issue on Main Road',
            'description': 'Deep potholes causing risk of accidents',
            'category': self.category.id,
            'priority': 'urgent',
            'address': 'Ward 5, Main Road'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['tracking_id'].startswith('JSH-'))
