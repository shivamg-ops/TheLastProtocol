from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
import io
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from .models import User, Department, ComplaintCategory, Complaint, ComplaintStatus, ComplaintEvidence, CitizenFeedback, UserRole

class JanSahayakAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.dept = Department.objects.create(name="Solid Waste Management", code="SWM", sla_hours=24)
        self.category = ComplaintCategory.objects.create(
            name="Garbage and Sanitation",
            slug="garbage-and-sanitation",
            department=self.dept
        )
        self.admin = User.objects.create_superuser(
            username="testadmin",
            password="testpassword",
            email="admin@test.com",
            role=UserRole.ADMIN
        )
        self.citizen = User.objects.create_user(
            username="testcitizen",
            password="testpassword",
            role=UserRole.CITIZEN
        )
        self.other_citizen = User.objects.create_user(
            username="othercitizen",
            password="testpassword",
            role=UserRole.CITIZEN
        )
        self.staff = User.objects.create_user(
            username="teststaff",
            password="testpassword",
            role=UserRole.STAFF
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

    def test_complete_resolution_lifecycle(self):
        # 1. Citizen creates complaint
        self.client.force_authenticate(user=self.citizen)
        r_comp = self.client.post('/api/complaints/', {
            'title': 'Broken sewer line',
            'description': 'Sewage overflowing on road',
            'category': self.category.id,
            'priority': 'high',
            'address': 'Sector 3'
        })
        comp_id = r_comp.data['id']

        # 2. Citizen uploads evidence
        img_io = io.BytesIO()
        Image.new('RGB', (50, 50), color='red').save(img_io, format='JPEG')
        img_io.seek(0)
        file = SimpleUploadedFile('evidence.jpg', img_io.read(), content_type='image/jpeg')
        r_ev = self.client.post('/api/evidence/', {
            'complaint': comp_id,
            'file': file,
            'file_type': 'image'
        }, format='multipart')
        self.assertEqual(r_ev.status_code, status.HTTP_201_CREATED)
        ev_id = r_ev.data['id']

        # 3. Unauthorized citizen attempts to access evidence (IDOR check)
        self.client.force_authenticate(user=self.other_citizen)
        r_idor = self.client.get(f'/api/evidence/{ev_id}/')
        self.assertEqual(r_idor.status_code, status.HTTP_404_NOT_FOUND)

        # 4. Admin assigns staff
        self.client.force_authenticate(user=self.admin)
        r_assign = self.client.post(f'/api/complaints/{comp_id}/assign_staff/', {
            'staff_id': self.staff.id
        })
        self.assertEqual(r_assign.status_code, status.HTTP_200_OK)

        # 5. Staff updates status to resolved
        self.client.force_authenticate(user=self.staff)
        r_status = self.client.post(f'/api/complaints/{comp_id}/update_status/', {
            'status': 'resolved',
            'notes': 'Sewer pipe cleared and sealed.'
        })
        self.assertEqual(r_status.status_code, status.HTTP_200_OK)

        # 6. Citizen rates resolution
        self.client.force_authenticate(user=self.citizen)
        r_feed = self.client.post(f'/api/complaints/{comp_id}/submit_feedback/', {
            'rating': 5,
            'feedback_text': 'Resolved cleanly!'
        })
        self.assertEqual(r_feed.status_code, status.HTTP_201_CREATED)

    def test_smart_location_extraction_multilingual(self):
        from .ai_service import analyze_complaint_text

        # 1. Hindi with Landmark
        res_hi = analyze_complaint_text("हनुमान मंदिर के सामने बहुत गहरा गड्ढा है")
        self.assertEqual(res_hi['detected_language'], 'hi')
        self.assertIsNotNone(res_hi['location_extracted'])
        self.assertIn("हनुमान मंदिर", res_hi['location_extracted'])
        self.assertTrue(res_hi['ready_to_submit'])

        # 2. Marathi with Landmark
        res_mr = analyze_complaint_text("दत्त मंदिरा जवळ रस्त्यावर घाण पाणी साचले आहे")
        self.assertEqual(res_mr['detected_language'], 'mr')
        self.assertIsNotNone(res_mr['location_extracted'])
        self.assertIn("दत्त मंदिर", res_mr['location_extracted'])
        self.assertTrue(res_mr['ready_to_submit'])

        # 3. English with Street + Ward
        res_en = analyze_complaint_text("Pothole on 5th Main Road near City Hospital, Ward 12")
        self.assertEqual(res_en['detected_language'], 'en')
        self.assertIn("5th Main Road", res_en['location_extracted'])
        self.assertEqual(res_en['ward_extracted'], 'Ward 12')
        self.assertTrue(res_en['ready_to_submit'])

        # 4. Hinglish with Chowk
        res_hing = analyze_complaint_text("Shivaji Chowk par sewage overflow ho raha hai")
        self.assertEqual(res_hing['detected_language'], 'hinglish')
        self.assertIn("Shivaji Chowk", res_hing['location_extracted'])
        self.assertTrue(res_hing['ready_to_submit'])

        # 5. Ambiguous / Vague Location -> must ask clarification and set ready_to_submit=False
        res_vague = analyze_complaint_text("Hamare yahan gali me kachra pada hai")
        self.assertIsNone(res_vague['location_extracted'])
        self.assertFalse(res_vague['ready_to_submit'])
        self.assertIsNotNone(res_vague['clarification_question'])

        # 6. Completely missing location
        res_miss = analyze_complaint_text("Paani nahi aa raha hai subah se")
        self.assertIsNone(res_miss['location_extracted'])
        self.assertFalse(res_miss['ready_to_submit'])
        self.assertIn("Exact location or landmark", res_miss['missing_information'])

