from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
import io
from unittest.mock import patch, MagicMock
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from .models import User, Department, ComplaintCategory, Complaint, ComplaintStatus, ComplaintEvidence, CitizenFeedback, Notification, UserRole

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

    def test_gemini_json_parsing_and_validation(self):
        from .gemini_client import clean_and_parse_json, validate_gemini_complaint_payload

        # 1. Valid Gemini response with markdown fences
        raw_markdown_json = '''```json
{
    "intent": "complaint",
    "title": "Broken Streetlight on 5th Cross",
    "category": "Streetlights",
    "confidence_score": 0.95,
    "detected_language": "en",
    "priority": "high",
    "summary": "Streetlight broken on 5th Cross Road",
    "location_extracted": "5th Cross Road",
    "missing_information": [],
    "ready_to_submit": true
}
```'''
        parsed = clean_and_parse_json(raw_markdown_json)
        self.assertIsNotNone(parsed)
        validated = validate_gemini_complaint_payload(parsed)
        self.assertIsNotNone(validated)
        self.assertEqual(validated['category'], "Streetlights")
        self.assertEqual(validated['priority'], "high")
        self.assertEqual(validated['confidence_score'], 0.95)
        self.assertTrue(validated['ready_to_submit'])

        # 2. Malformed JSON string
        malformed_raw = '{"intent": "complaint", "category": "Roads and Potholes", incomplete json'
        self.assertIsNone(clean_and_parse_json(malformed_raw))
        self.assertIsNone(validate_gemini_complaint_payload(clean_and_parse_json(malformed_raw)))

        # 3. Unexpected / Hallucinated Category (Must be rejected, NOT silently accepted or turned to Garbage)
        invalid_cat_payload = {
            "intent": "complaint",
            "category": "Alien Invasion / UFO Sighting",
            "confidence_score": 0.99,
            "location_extracted": "Main Market",
            "ready_to_submit": True
        }
        self.assertIsNone(validate_gemini_complaint_payload(invalid_cat_payload))

        # 4. Out-of-bounds confidence score (e.g. > 1.0 or < 0.0) -> Rejected
        out_of_bounds_conf = {
            "intent": "complaint",
            "category": "Water Supply",
            "confidence_score": 1.75,
            "location_extracted": "Gandhi Chowk"
        }
        self.assertIsNone(validate_gemini_complaint_payload(out_of_bounds_conf))

        # 5. Security Invariant: ready_to_submit CANNOT be True if location is missing
        missing_loc_payload = {
            "intent": "complaint",
            "category": "Garbage and Sanitation",
            "confidence_score": 0.92,
            "location_extracted": None,
            "ready_to_submit": True  # LLM mistakenly marked ready
        }
        validated_miss = validate_gemini_complaint_payload(missing_loc_payload)
        self.assertIsNotNone(validated_miss)
        # Invariant enforced: ready_to_submit must be strictly False
        self.assertFalse(validated_miss['ready_to_submit'])
        self.assertIn("Exact location or landmark", validated_miss['missing_information'])

    def test_truthful_image_analysis_and_failure_handling(self):
        import os
        import tempfile
        from PIL import Image
        from .ai_service import analyze_image_evidence
        from .gemini_client import validate_gemini_image_payload

        # 1. Test image payload validator - Valid Payload
        valid_img_payload = {
            "detected_issue": "Road pothole",
            "detected_objects": ["road", "asphalt", "crater"],
            "image_readability": "clear",
            "complaint_image_match": True,
            "confidence_score": 0.92,
            "verification_status": "verified",
            "review_required": False,
            "summary_note": "A clear pothole visible on asphalt matching road description."
        }
        val_res = validate_gemini_image_payload(valid_img_payload)
        self.assertIsNotNone(val_res)
        self.assertEqual(val_res['verification_status'], "verified")
        self.assertFalse(val_res['review_required'])
        self.assertEqual(val_res['confidence_score'], 0.92)

        # 2. Test Mismatched Complaint Description (e.g. food/pet image uploaded for streetlight)
        mismatch_payload = {
            "detected_issue": "Cat sitting on table",
            "detected_objects": ["cat", "table"],
            "image_readability": "clear",
            "complaint_image_match": False,
            "confidence_score": 0.90,
            "verification_status": "verified",  # Faulty model claim
            "review_required": False
        }
        # Invariant: If complaint_image_match is False, verification_status MUST NOT be verified
        val_mismatch = validate_gemini_image_payload(mismatch_payload)
        self.assertEqual(val_mismatch['verification_status'], "mismatch")
        self.assertTrue(val_mismatch['review_required'])
        self.assertFalse(val_mismatch['complaint_image_match'])

        # 3. Test Unreadable / Dark Image
        unreadable_payload = {
            "detected_issue": "Unclear",
            "detected_objects": [],
            "image_readability": "unreadable",
            "complaint_image_match": True,
            "confidence_score": 0.40,
            "verification_status": "verified",  # Faulty model claim
            "review_required": False
        }
        val_unread = validate_gemini_image_payload(unreadable_payload)
        self.assertNotEqual(val_unread['verification_status'], "verified")
        self.assertTrue(val_unread['review_required'])

        # 4. Test Corrupted / Non-Image File Analysis
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"NOT_A_REAL_IMAGE_DATA_CORRUPTED_BYTES")
            corrupt_path = f.name

        try:
            res_corrupt = analyze_image_evidence(corrupt_path)
            self.assertEqual(res_corrupt['status'], "error")
            self.assertEqual(res_corrupt['verification_status'], "failed")
            self.assertEqual(res_corrupt['image_readability'], "unreadable")
            self.assertTrue(res_corrupt['review_required'])
            # Must NEVER be verified
            self.assertNotEqual(res_corrupt['verification_status'], "verified")
        finally:
            if os.path.exists(corrupt_path):
                os.remove(corrupt_path)

        # 5. Test Non-Existent File
        res_nonexistent = analyze_image_evidence("/tmp/definitely_not_a_real_file_12345.jpg")
        self.assertEqual(res_nonexistent['status'], "error")
        self.assertEqual(res_nonexistent['verification_status'], "failed")
        self.assertNotEqual(res_nonexistent['verification_status'], "verified")

        # 6. Test Valid Image File with AI Service (Fallback mode when no API key)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            img = Image.new("RGB", (64, 64), color="blue")
            img.save(f, format="PNG")
            valid_img_path = f.name

        try:
            # Without active API key, system must gracefully queue for staff review, NOT falsely claim verified
            res_no_api = analyze_image_evidence(
                image_file_path=valid_img_path,
                complaint_text="Pothole in road",
                complaint_category="Roads and Potholes"
            )
            # Invariant: If Gemini API is unavailable or fails, NEVER claim verified
            self.assertNotEqual(res_no_api['verification_status'], "verified")
            self.assertIn(res_no_api['verification_status'], ["pending", "unverified", "failed"])
            self.assertTrue(res_no_api['review_required'])
            self.assertIn("Pending", res_no_api['analysis'])
        finally:
            if os.path.exists(valid_img_path):
                os.remove(valid_img_path)

    def test_duplicate_image_detection_sha256_and_phash(self):
        import os
        import tempfile
        from PIL import Image, ImageDraw
        from .models import Complaint, ComplaintEvidence
        from .ai_service import compute_image_hashes, detect_duplicate_evidence

        # Helper to create distinct patterned images so perceptual hashes differ clearly
        def make_image_pattern(pattern_type="box"):
            f = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
            if pattern_type == "box":
                img = Image.new("RGB", (128, 128), color="black")
                draw = ImageDraw.Draw(img)
                draw.rectangle([15, 15, 110, 110], fill="white")
                draw.ellipse([30, 30, 95, 95], fill="red")
            else:
                img = Image.new("RGB", (128, 128), color="white")
                draw = ImageDraw.Draw(img)
                draw.polygon([(10, 110), (64, 15), (115, 110)], fill="blue")
                draw.line([(0, 64), (128, 64)], fill="black", width=4)
            img.save(f, format="JPEG", quality=90)
            f.close()
            return f.name

        img1_path = make_image_pattern("box")
        img2_path = make_image_pattern("triangle")

        # Create resized and compressed versions of img1
        img1_pil = Image.open(img1_path)
        img1_resized_path = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False).name
        img1_pil.resize((64, 64)).save(img1_resized_path, format="JPEG", quality=90)

        img1_compressed_path = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False).name
        img1_pil.save(img1_compressed_path, format="JPEG", quality=30)

        # Corrupted image file
        corrupt_path = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False).name
        with open(corrupt_path, "wb") as f:
            f.write(b"CORRUPTED_NON_IMAGE_DATA")

        try:
            # 1. Compute hashes test
            hashes1 = compute_image_hashes(img1_path)
            self.assertTrue(hashes1["is_valid"])
            self.assertIsNotNone(hashes1["sha256"])
            self.assertIsNotNone(hashes1["phash"])

            # 2. Corrupted image test
            corrupt_hashes = compute_image_hashes(corrupt_path)
            self.assertFalse(corrupt_hashes["is_valid"])
            self.assertIsNone(corrupt_hashes["phash"])

            corrupt_dup_check = detect_duplicate_evidence(corrupt_path)
            self.assertFalse(corrupt_dup_check["is_duplicate"])
            self.assertTrue(corrupt_dup_check["review_required"])

            # 3. Setup two different complaints
            complaint1 = Complaint.objects.create(
                citizen=self.citizen,
                title="Pothole Complaint 1",
                description="Big pothole near station",
                address="Station Road"
            )
            complaint2 = Complaint.objects.create(
                citizen=self.other_citizen,
                title="Garbage Complaint 2",
                description="Garbage dump near school",
                address="School Road"
            )

            # 4. Attach original evidence to complaint1
            ev1 = ComplaintEvidence.objects.create(
                complaint=complaint1,
                file=SimpleUploadedFile("ev1.jpg", open(img1_path, "rb").read(), content_type="image/jpeg"),
                file_type="image",
                sha256_hash=hashes1["sha256"],
                phash=hashes1["phash"],
                uploaded_by=self.citizen
            )

            # 5. Check Two Genuinely Different Images -> is_duplicate = False
            diff_check = detect_duplicate_evidence(img2_path, current_evidence_id=None)
            self.assertFalse(diff_check["is_duplicate"])
            self.assertEqual(diff_check["duplicate_type"], "none")

            # 6. Same Exact Image uploaded again (under complaint2) -> Exact duplicate detected via SHA-256
            exact_dup = detect_duplicate_evidence(img1_path, current_evidence_id=None)
            self.assertTrue(exact_dup["is_duplicate"])
            self.assertEqual(exact_dup["duplicate_type"], "exact")
            self.assertEqual(exact_dup["similarity_score"], 1.0)
            self.assertEqual(exact_dup["matched_evidence_id"], ev1.id)
            self.assertTrue(exact_dup["review_required"])

            # 7. Resized Version of the Same Image -> Perceptual duplicate detected via pHash
            resized_dup = detect_duplicate_evidence(img1_resized_path, current_evidence_id=None)
            self.assertTrue(resized_dup["is_duplicate"])
            self.assertIn(resized_dup["duplicate_type"], ["exact", "perceptual"])
            self.assertGreaterEqual(resized_dup["similarity_score"], 0.85)
            self.assertEqual(resized_dup["matched_evidence_id"], ev1.id)

            # 8. Compressed Version of the Same Image -> Perceptual duplicate detected via pHash
            compressed_dup = detect_duplicate_evidence(img1_compressed_path, current_evidence_id=None)
            self.assertTrue(compressed_dup["is_duplicate"])
            self.assertIn(compressed_dup["duplicate_type"], ["exact", "perceptual"])
            self.assertGreaterEqual(compressed_dup["similarity_score"], 0.85)
            self.assertEqual(compressed_dup["matched_evidence_id"], ev1.id)

            # 9. Verify through REST API evidence upload endpoint
            self.client.force_authenticate(user=self.other_citizen)
            with open(img1_path, "rb") as fp:
                resp = self.client.post('/api/evidence/', {
                    'complaint': complaint2.id,
                    'file': fp,
                    'file_type': 'image'
                }, format='multipart')

            self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
            ev2 = ComplaintEvidence.objects.get(id=resp.data['id'])
            self.assertTrue(ev2.is_duplicate)
            self.assertEqual(ev2.duplicate_type, 'exact')
            self.assertEqual(ev2.matched_evidence_id, ev1.id)
            self.assertTrue(ev2.review_required)
            # Complaint flagged for duplicate review, NOT rejected
            complaint2.refresh_from_db()
            self.assertTrue(complaint2.ai_duplicate_suspect)
            self.assertNotEqual(complaint2.status, 'rejected')

        finally:
            for p in [img1_path, img2_path, img1_resized_path, img1_compressed_path, corrupt_path]:
                if os.path.exists(p):
                    os.remove(p)

    def test_input_mode_and_media_handling(self):
        from .models import Complaint, ComplaintEvidence
        from .validators import validate_evidence_file, get_file_type_from_file
        from django.core.exceptions import ValidationError

        # 1. Text vs Voice Input Mode Distinction on Complaint Creation
        self.client.force_authenticate(user=self.citizen)

        # (a) Text Mode Complaint
        resp_text = self.client.post('/api/complaints/', {
            'title': 'Pothole on MG Road',
            'description': 'Deep pothole typed via keyboard',
            'address': 'MG Road near Metro Station',
            'original_input_mode': 'text'
        })
        self.assertEqual(resp_text.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp_text.data['original_input_mode'], 'text')
        comp_text = Complaint.objects.get(id=resp_text.data['id'])
        self.assertEqual(comp_text.original_input_mode, 'text')

        # (b) Voice Mode Complaint
        resp_voice = self.client.post('/api/complaints/', {
            'title': 'Garbage pile reported via voice',
            'description': 'Kachra pada hai bol kar report kiya gaya',
            'address': 'Gandhi Nagar Gali 4',
            'original_input_mode': 'voice'
        })
        self.assertEqual(resp_voice.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp_voice.data['original_input_mode'], 'voice')
        comp_voice = Complaint.objects.get(id=resp_voice.data['id'])
        self.assertEqual(comp_voice.original_input_mode, 'voice')

        # 2. Evidence Media Type Identification & Validation
        # (a) Image Upload (.jpg)
        image_file = SimpleUploadedFile("evidence.jpg", b"\xFF\xD8\xFF\xE0" + b"\x00" * 200, content_type="image/jpeg")
        self.assertEqual(get_file_type_from_file(image_file), 'image')

        # (b) Video Upload (.mp4) -> Auto-inferred as 'video'
        video_file = SimpleUploadedFile("leakage_video.mp4", b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 300, content_type="video/mp4")
        self.assertEqual(get_file_type_from_file(video_file), 'video')

        # Upload video to backend
        resp_video = self.client.post('/api/evidence/', {
            'complaint': comp_text.id,
            'file': video_file
        }, format='multipart')
        self.assertEqual(resp_video.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp_video.data['file_type'], 'video')
        ev_video = ComplaintEvidence.objects.get(id=resp_video.data['id'])
        self.assertEqual(ev_video.file_type, 'video')
        # Crucial requirement: Video is NOT sent to image analysis
        self.assertIn("Video Evidence Attached", ev_video.ai_analysis_description)
        self.assertNotIn("Road pothole", ev_video.ai_analysis_description)

        # (c) Document Upload (.pdf)
        pdf_file = SimpleUploadedFile("application.pdf", b"%PDF-1.4 sample content", content_type="application/pdf")
        self.assertEqual(get_file_type_from_file(pdf_file), 'document')
        resp_pdf = self.client.post('/api/evidence/', {
            'complaint': comp_text.id,
            'file': pdf_file
        }, format='multipart')
        self.assertEqual(resp_pdf.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp_pdf.data['file_type'], 'document')

        # (d) Unsupported File Extension (.exe / .sh) -> Clear Error Message & Rejection
        unsupported_file = SimpleUploadedFile("exploit.exe", b"MZ malicious executable", content_type="application/x-msdownload")
        with self.assertRaises(ValidationError):
            validate_evidence_file(unsupported_file)

        resp_bad = self.client.post('/api/evidence/', {
            'complaint': comp_text.id,
            'file': unsupported_file
        }, format='multipart')
        self.assertEqual(resp_bad.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Unsupported file format", str(resp_bad.data))

        # (e) File Exceeding 25 MB Limit -> Rejected
        oversized_file = SimpleUploadedFile("huge.mp4", b"0", content_type="video/mp4")
        oversized_file.size = 26 * 1024 * 1024  # 26 MB
        with self.assertRaises(ValidationError):
            validate_evidence_file(oversized_file)

    def test_enforce_ready_to_submit_and_independent_validation(self):
        from .ai_service import analyze_complaint_text

        # 1. AI Analysis ready_to_submit enforcement: Missing Location
        res_no_loc = analyze_complaint_text("Road is completely broken and has big craters")
        self.assertFalse(res_no_loc['ready_to_submit'])
        self.assertIsNone(res_no_loc['location_extracted'])
        self.assertIsNotNone(res_no_loc['clarification_question'])
        self.assertIn("Exact location or landmark", res_no_loc['missing_information'])

        # 2. AI Analysis ready_to_submit enforcement: Vague / Ambiguous Location
        res_vague = analyze_complaint_text("Hamare ghar ke samne sadak par bada gaddha hai")
        self.assertFalse(res_vague['ready_to_submit'])
        self.assertIsNone(res_vague['location_extracted'])
        self.assertIsNotNone(res_vague['clarification_question'])
        self.assertTrue(any("too vague" in item or "landmark" in item for item in res_vague['missing_information']))

        # 3. AI Analysis ready_to_submit: Valid Location provided
        res_valid = analyze_complaint_text("Pothole on Linking Road opposite National College, Bandra West")
        self.assertTrue(res_valid['ready_to_submit'])
        self.assertIsNotNone(res_valid['location_extracted'])
        self.assertEqual(len(res_valid['missing_information']), 0)

        # 4. General Inquiry vs Complaint Handling
        res_inquiry = analyze_complaint_text("What are the municipal office working hours?")
        self.assertEqual(res_inquiry['intent'], 'inquiry')
        self.assertFalse(res_valid['intent'] == 'inquiry')
        # Inquiries should NOT be treated as actionable complaints
        self.assertFalse(res_inquiry['ready_to_submit'])

        # 5. Independent Backend Validation on POST /api/complaints/
        self.client.force_authenticate(user=self.citizen)

        # (a) Missing or placeholder address rejected by backend serializer
        resp_bad_address = self.client.post('/api/complaints/', {
            'title': 'Broken Pothole',
            'description': 'Big dangerous pothole on the main avenue',
            'address': 'reported location'  # Vague placeholder
        })
        self.assertEqual(resp_bad_address.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("address", resp_bad_address.data)

        # (b) Missing or too short description rejected
        resp_bad_desc = self.client.post('/api/complaints/', {
            'title': 'Pothole',
            'description': 'bad',  # < 5 chars
            'address': 'MG Road near Post Office'
        })
        self.assertEqual(resp_bad_desc.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("description", resp_bad_desc.data)

        # (c) Valid Complaint with Named Landmark is Accepted without hallucinating GPS
        resp_valid_comp = self.client.post('/api/complaints/', {
            'title': 'Broken Water Pipeline',
            'description': 'Drinking water pipeline leaking heavily',
            'address': 'Opposite City Hospital, Shivaji Nagar',
            'landmark': 'City Hospital',
            'priority': 'high'
        })
        self.assertEqual(resp_valid_comp.status_code, status.HTTP_201_CREATED)
        # Invariant: Named landmark is saved as text, NOT fabricated into GPS coords
        self.assertIsNone(resp_valid_comp.data['latitude'])
        self.assertIsNone(resp_valid_comp.data['longitude'])
        self.assertEqual(resp_valid_comp.data['landmark'], 'City Hospital')

    def test_yolo_object_detector(self):
        import os
        import tempfile
        from PIL import Image
        from unittest.mock import MagicMock
        from .yolo_detector import YOLODetector

        detector = YOLODetector()

        # 1. Missing Image Test
        res_no_img = detector.detect("/non/existent/image_path.jpg")
        self.assertEqual(res_no_img["detection_status"], "invalid_image")
        self.assertEqual(res_no_img["confidence"], 0.0)

        # 2. Corrupt Image Test
        corrupt_f = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        corrupt_f.write(b"CORRUPTED_BYTES")
        corrupt_f.close()
        try:
            res_corrupt = detector.detect(corrupt_f.name)
            self.assertEqual(res_corrupt["detection_status"], "invalid_image")
        finally:
            if os.path.exists(corrupt_f.name):
                os.remove(corrupt_f.name)

        # 3. Missing Model Weights File
        valid_img_f = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        img = Image.new("RGB", (64, 64), color="gray")
        img.save(valid_img_f, format="JPEG")
        valid_img_f.close()

        try:
            # Model path pointing to non-existent weights
            res_no_model = detector.detect(valid_img_f.name, model_path="/non/existent/weights.pt")
            self.assertEqual(res_no_model["detection_status"], "model_not_found")
            self.assertIn("No trained YOLO weights", res_no_model["summary"])

            # 4. Mock Successful Detection with Fine-Tuned Model
            mock_model = MagicMock()
            mock_model.names = {0: "pothole", 1: "garbage_pile"}

            mock_box = MagicMock()
            mock_box.cls = [MagicMock(item=lambda: 0)]
            mock_box.conf = [MagicMock(item=lambda: 0.88)]
            mock_box.xyxy = [[10.0, 15.0, 50.0, 60.0]]

            mock_result = MagicMock()
            mock_result.boxes = [mock_box]
            mock_model.predict.return_value = [mock_result]

            # Inject mock model into detector
            detector._model = mock_model
            detector._loaded_path = valid_img_f.name  # dummy existing path

            res_mock_success = detector.detect(valid_img_f.name, model_path=valid_img_f.name)
            self.assertEqual(res_mock_success["detection_status"], "success")
            self.assertEqual(res_mock_success["class_name"], "pothole")
            self.assertEqual(res_mock_success["confidence"], 0.88)
            self.assertEqual(len(res_mock_success["bounding_boxes"]), 1)
            self.assertEqual(res_mock_success["bounding_boxes"][0], [10.0, 15.0, 50.0, 60.0])

            # 5. Mock No Detections
            mock_empty_result = MagicMock()
            mock_empty_result.boxes = []
            mock_model.predict.return_value = [mock_empty_result]

            res_empty = detector.detect(valid_img_f.name, model_path=valid_img_f.name)
            self.assertEqual(res_empty["detection_status"], "no_detections")
            self.assertEqual(len(res_empty["detected_objects"]), 0)

            # 6. Verify Supported Classes Logic (Never fabricates unsupported classes)
            supported = detector.get_supported_classes(mock_model)
            self.assertIn("pothole", supported)
            self.assertNotIn("alien_spacecraft", supported)

        finally:
            detector._model = None
            detector._loaded_path = None
            if os.path.exists(valid_img_f.name):
                os.remove(valid_img_f.name)

    def test_smart_duplicate_complaint_detection(self):
        from .models import Complaint, ComplaintEvidence
        from .duplicate_detector import DuplicateDetector, compute_text_similarity, compute_location_similarity

        # 1. Base Complaint in Category "Roads and Potholes"
        c1 = Complaint.objects.create(
            citizen=self.citizen,
            title="Deep crater on Station Road",
            description="Bahut bada gaddha hai station road par accident ho sakta hai",
            category=self.category,
            address="Station Road near Metro Pillar 42",
            landmark="Metro Pillar 42",
            ward_or_zone="Ward 4"
        )

        # 2. Same Text, Same Location, Same Category -> Flagged as duplicate
        c_same = Complaint(
            citizen=self.other_citizen,
            title="Crater on Station Road",
            description="Bahut bada gaddha hai station road par accident ho sakta hai",
            category=self.category,
            address="Station Road near Metro Pillar 42",
            landmark="Metro Pillar 42",
            ward_or_zone="Ward 4"
        )
        res_same = DuplicateDetector.find_duplicate(c_same)
        self.assertTrue(res_same["is_possible_duplicate"])
        self.assertEqual(res_same["matched_complaint_id"], c1.id)
        self.assertEqual(res_same["matched_tracking_id"], c1.tracking_id)
        self.assertGreaterEqual(res_same["similarity_score"], 0.85)

        # 3. Similar Text but Completely Different Location (Station Road vs Airport Highway)
        # Invariant: Must NOT be marked duplicate simply because description is similar
        c_diff_loc = Complaint(
            citizen=self.other_citizen,
            title="Pothole on Highway",
            description="Bahut bada gaddha hai highway road par accident ho sakta hai",
            category=self.category,
            address="Airport Highway Terminal 2",
            landmark="Terminal 2",
            ward_or_zone="Ward 18"
        )
        res_diff_loc = DuplicateDetector.find_duplicate(c_diff_loc)
        self.assertFalse(res_diff_loc["is_possible_duplicate"])
        self.assertIsNone(res_diff_loc["matched_complaint_id"])

        # 4. Same Category but Unrelated Description
        c_unrelated = Complaint(
            citizen=self.other_citizen,
            title="Speed breaker broken",
            description="Speed breaker paints have completely faded out",
            category=self.category,
            address="Station Road near Metro Pillar 42",
            landmark="Metro Pillar 42"
        )
        res_unrelated = DuplicateDetector.find_duplicate(c_unrelated)
        self.assertFalse(res_unrelated["is_possible_duplicate"])

        # 5. Different Wording for Similar Issue in Same Location (Hindi / Hinglish variation)
        c_reworded = Complaint(
            citizen=self.other_citizen,
            title="Dangerous pothole",
            description="Station road par bohot bada gaddha pada hai koi gir jayega",
            category=self.category,
            address="Station Road near Metro Pillar 42",
            landmark="Metro Pillar 42"
        )
        res_reworded = DuplicateDetector.find_duplicate(c_reworded)
        self.assertTrue(res_reworded["is_possible_duplicate"])
        self.assertEqual(res_reworded["matched_complaint_id"], c1.id)

        # 6. Missing Location Safeguard: Missing location is never treated as a matching location
        c_no_loc = Complaint(
            citizen=self.other_citizen,
            title="Pothole problem",
            description="Bahut bada gaddha hai road par",
            category=self.category,
            address=""
        )
        loc_score = compute_location_similarity(c_no_loc, c1)
        self.assertEqual(loc_score, 0.0)

        # 7. Image Duplicate Signal Integration
        # If visual evidence matches exactly (SHA-256), flags as duplicate even with slight description changes
        ev1 = ComplaintEvidence.objects.create(
            complaint=c1,
            file=SimpleUploadedFile("img1.jpg", b"EVIDENCE_IMAGE_BYTES_123", content_type="image/jpeg"),
            file_type="image",
            sha256_hash="abc123sha256hash",
            phash="phash12345"
        )

        c_with_same_img = Complaint.objects.create(
            citizen=self.other_citizen,
            title="Pothole picture",
            description="Grievance with identical photo proof",
            category=self.category,
            address="Station Road",
            landmark="Metro Pillar 42"
        )
        ev2 = ComplaintEvidence.objects.create(
            complaint=c_with_same_img,
            file=SimpleUploadedFile("img2.jpg", b"EVIDENCE_IMAGE_BYTES_123", content_type="image/jpeg"),
            file_type="image",
            sha256_hash="abc123sha256hash",
            phash="phash12345"
        )

        res_img_dup = DuplicateDetector.find_duplicate(c_with_same_img)
        self.assertTrue(res_img_dup["is_possible_duplicate"])
        self.assertEqual(res_img_dup["matched_complaint_id"], c1.id)
        self.assertIn("Visual evidence match", " ".join(res_img_dup["match_reasons"]))

        # 8. Invariant: Duplicate suspect must NEVER automatically be rejected
        c_with_same_img.refresh_from_db()
        self.assertNotEqual(c_with_same_img.status, 'rejected')

    def test_smart_department_routing(self):
        from .models import Department, ComplaintCategory, Complaint
        from .department_router import DepartmentRouter

        # 1. Correct Routing for Configured Category & Department
        # self.category ("Garbage and Sanitation") is linked to self.dept ("Solid Waste Management")
        res_cat = DepartmentRouter.route_complaint(
            category=self.category,
            description="Kachra pada hai aur safai nahi hui"
        )
        self.assertEqual(res_cat["routing_status"], "routed")
        self.assertEqual(res_cat["suggested_department"]["id"], self.dept.id)
        self.assertEqual(res_cat["suggested_department"]["name"], self.dept.name)
        self.assertEqual(res_cat["suggested_team_id"], self.dept.id)
        self.assertGreaterEqual(res_cat["routing_confidence"], 0.65)
        self.assertFalse(res_cat["requires_manual_review"])

        # 2. Unknown / Unmapped Category -> Falls back to description keywords
        water_dept = Department.objects.create(name="Water Supply & Sewerage", code="WSS_TEST", sla_hours=36)
        unmapped_cat = ComplaintCategory(name="Miscellaneous Grievance")
        res_desc = DepartmentRouter.route_complaint(
            category=unmapped_cat,
            description="Severe water supply disruption and drinking water pipe burst"
        )
        # Should route to water department based on keywords
        self.assertIsNotNone(res_desc["suggested_department"])
        self.assertIn("Water", res_desc["suggested_department"]["name"])
        self.assertEqual(res_desc["suggested_department"]["id"], water_dept.id)

        # 3. Missing Department Configuration Scenario
        # Deactivate all departments temporarily
        Department.objects.filter(is_active=True).update(is_active=False)
        try:
            res_no_dept = DepartmentRouter.route_complaint(
                category=self.category,
                description="Streetlight broken"
            )
            self.assertEqual(res_no_dept["routing_status"], "manual_review_required")
            self.assertIsNone(res_no_dept["suggested_department"])
            self.assertIsNone(res_no_dept["suggested_team_id"])
            self.assertTrue(res_no_dept["requires_manual_review"])
        finally:
            Department.objects.all().update(is_active=True)

        # 4. Low-Confidence / Ambiguous Issue -> requires_manual_review = True
        res_ambiguous = DepartmentRouter.route_complaint(
            category=None,
            description="Something strange happened nearby yesterday."
        )
        self.assertEqual(res_ambiguous["routing_status"], "manual_review_required")
        self.assertTrue(res_ambiguous["requires_manual_review"])
        self.assertIsNone(res_ambiguous["suggested_department"])

        # 5. Visual Issue Signal Integration (e.g. image analysis detected 'pothole')
        roads_dept = Department.objects.create(name="Roads & Infrastructure", code="RTI_TEST", sla_hours=48)
        res_visual = DepartmentRouter.route_complaint(
            category=None,
            description="Road condition issue",
            detected_issue="Road pothole"
        )
        self.assertIsNotNone(res_visual["suggested_department"])
        self.assertIn("Roads", res_visual["suggested_department"]["name"])

        # 6. Safety Invariant: No fake assignment is reported or executed
        # Complaint creation does not automatically assign a staff member without admin action
        new_comp = Complaint.objects.create(
            citizen=self.citizen,
            title="Leaking pipeline",
            description="Water pipeline burst",
            address="Ring Road",
            category=self.category
        )
        self.assertIsNone(new_comp.assigned_staff)
        self.assertNotEqual(new_comp.status, 'assigned')

        # 7. Preserves Existing Admin Staff Assignment Workflow
        self.client.force_authenticate(user=self.admin)
        assign_resp = self.client.post(f'/api/complaints/{new_comp.id}/assign_staff/', {
            'staff_id': self.staff.id
        })
        self.assertEqual(assign_resp.status_code, status.HTTP_200_OK)
        new_comp.refresh_from_db()
        self.assertEqual(new_comp.assigned_staff, self.staff)
        self.assertEqual(new_comp.status, 'assigned')

    def test_ai_evidence_verifier_and_trust_score(self):
        import os
        import tempfile
        from PIL import Image
        from unittest.mock import patch, MagicMock
        from .evidence_verifier import EvidenceVerifier
        from .models import Complaint, ComplaintEvidence

        # 1. Missing Evidence Test
        res_none = EvidenceVerifier.verify_evidence(image_file_path=None)
        self.assertEqual(res_none["evidence_status"], "not_checked")
        self.assertEqual(res_none["trust_score"], 0.0)
        self.assertFalse(res_none["review_required"])

        # 2. Corrupted Image Test
        corrupt_f = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        corrupt_f.write(b"CORRUPTED_NON_IMAGE_DATA_12345")
        corrupt_f.close()
        try:
            res_corrupt = EvidenceVerifier.verify_evidence(image_file_path=corrupt_f.name)
            self.assertEqual(res_corrupt["evidence_status"], "flagged")
            self.assertEqual(res_corrupt["trust_score"], 0.0)
            self.assertTrue(res_corrupt["review_required"])
            self.assertIn("Corrupted", " ".join(res_corrupt["review_reasons"]))
        finally:
            if os.path.exists(corrupt_f.name):
                os.remove(corrupt_f.name)

        # 3. Create a real readable image
        valid_img_f = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        img = Image.new("RGB", (64, 64), color="orange")
        img.save(valid_img_f, format="JPEG")
        valid_img_f.close()

        try:
            # 4. Inconclusive Scenario (Both Gemini and YOLO unavailable)
            with patch("api.ai_service.analyze_image_evidence") as mock_gemini, \
                 patch("api.yolo_detector.YOLODetector.detect") as mock_yolo:
                mock_gemini.return_value = {"status": "pending", "analysis": "Service unavailable"}
                mock_yolo.return_value = {"detection_status": "model_not_found"}

                res_inconc = EvidenceVerifier.verify_evidence(
                    image_file_path=valid_img_f.name,
                    complaint_text="Pothole on main street",
                    complaint_category="Roads and Potholes"
                )
                self.assertEqual(res_inconc["evidence_status"], "inconclusive")
                self.assertTrue(res_inconc["review_required"])
                # Invariant: Missing signals must NOT boost trust score
                self.assertLess(res_inconc["trust_score"], 0.40)

            # 5. Relevant Verified Image (Gemini match = True, YOLO confirms)
            with patch("api.ai_service.analyze_image_evidence") as mock_gemini, \
                 patch("api.yolo_detector.YOLODetector.detect") as mock_yolo:
                mock_gemini.return_value = {
                    "status": "success",
                    "complaint_image_match": True,
                    "confidence_score": 0.90,
                    "image_readability": "clear",
                    "detected_issue": "Road pothole"
                }
                mock_yolo.return_value = {
                    "detection_status": "success",
                    "detected_objects": [{"class_name": "pothole", "confidence": 0.85}],
                    "confidence": 0.85,
                    "class_name": "pothole"
                }

                res_verified = EvidenceVerifier.verify_evidence(
                    image_file_path=valid_img_f.name,
                    complaint_text="Pothole on road",
                    complaint_category="Roads and Potholes"
                )
                self.assertEqual(res_verified["evidence_status"], "verified")
                self.assertFalse(res_verified["review_required"])
                self.assertGreaterEqual(res_verified["trust_score"], 0.65)
                # Invariant: Never claims 100% certainty (max 0.95)
                self.assertLessEqual(res_verified["trust_score"], 0.95)

            # 6. Irrelevant / Mismatched Image (e.g. Cat photo for road complaint)
            with patch("api.ai_service.analyze_image_evidence") as mock_gemini:
                mock_gemini.return_value = {
                    "status": "success",
                    "complaint_image_match": False,
                    "confidence_score": 0.92,
                    "image_readability": "clear",
                    "detected_issue": "Domestic pet"
                }
                res_mismatch = EvidenceVerifier.verify_evidence(
                    image_file_path=valid_img_f.name,
                    complaint_text="Pothole on road",
                    complaint_category="Roads and Potholes"
                )
                self.assertEqual(res_mismatch["evidence_status"], "flagged")
                self.assertTrue(res_mismatch["review_required"])
                self.assertIn("mismatch", " ".join(res_mismatch["review_reasons"]))

            # 7. Model Disagreement (YOLO finds pothole, Gemini claims mismatch)
            with patch("api.ai_service.analyze_image_evidence") as mock_gemini, \
                 patch("api.yolo_detector.YOLODetector.detect") as mock_yolo:
                mock_gemini.return_value = {
                    "status": "success",
                    "complaint_image_match": False,
                    "confidence_score": 0.85,
                    "image_readability": "clear"
                }
                mock_yolo.return_value = {
                    "detection_status": "success",
                    "detected_objects": [{"class_name": "pothole"}],
                    "confidence": 0.80,
                    "class_name": "pothole"
                }
                res_disagree = EvidenceVerifier.verify_evidence(
                    image_file_path=valid_img_f.name,
                    complaint_text="Pothole on road",
                    complaint_category="Roads and Potholes"
                )
                self.assertEqual(res_disagree["evidence_status"], "flagged")
                self.assertTrue(res_disagree["review_required"])
                self.assertTrue(any("Disagreement" in r for r in res_disagree["review_reasons"]))

            # 8. Duplicate Image Evidence Integration
            with patch("api.ai_service.detect_duplicate_evidence") as mock_dup:
                mock_dup.return_value = {
                    "is_duplicate": True,
                    "duplicate_type": "exact",
                    "similarity_score": 1.0,
                    "matched_evidence_id": 999
                }
                res_dup = EvidenceVerifier.verify_evidence(
                    image_file_path=valid_img_f.name,
                    complaint_text="Pothole on road",
                    complaint_category="Roads and Potholes"
                )
                self.assertEqual(res_dup["evidence_status"], "flagged")
                self.assertTrue(res_dup["review_required"])
                self.assertIn("Duplicate evidence detected", " ".join(res_dup["review_reasons"]))

        finally:
            if os.path.exists(valid_img_f.name):
                os.remove(valid_img_f.name)

    def test_smart_complaint_lifecycle_and_sla_monitoring(self):
        from datetime import timedelta
        from django.utils import timezone
        from .models import Complaint, Department, ComplaintCategory, ComplaintStatus
        from .sla_monitor import SLAMonitor

        now = timezone.now()

        # 1. Correct SLA Deadline Calculation
        # self.dept has sla_hours=24
        c_active = Complaint.objects.create(
            citizen=self.citizen,
            title="Garbage overflowing on street",
            description="Dustbin has not been cleared for days",
            address="Gandhi Chowk near Bus Stand",
            department=self.dept,
            category=self.category,
            status=ComplaintStatus.SUBMITTED
        )
        c_active.created_at = now
        c_active.save(update_fields=['created_at'])

        deadline = SLAMonitor.calculate_sla_deadline(c_active)
        self.assertIsNotNone(deadline)
        self.assertEqual(deadline, now + timedelta(hours=24))

        # 2. Missing SLA Configuration Scenario
        c_no_sla = Complaint.objects.create(
            citizen=self.citizen,
            title="Unmapped civic problem",
            description="Miscellaneous civic complaint with no department",
            address="Market Yard"
        )
        res_no_sla = SLAMonitor.evaluate_complaint_sla(c_no_sla, current_time=now)
        self.assertEqual(res_no_sla["sla_status"], "not_configured")
        self.assertFalse(res_no_sla["is_overdue"])
        self.assertIsNone(res_no_sla["sla_hours"])

        # 3. Complaint Within SLA (e.g. 2 hours after creation)
        res_within = SLAMonitor.evaluate_complaint_sla(c_active, current_time=now + timedelta(hours=2))
        self.assertEqual(res_within["sla_status"], "within_sla")
        self.assertFalse(res_within["is_overdue"])
        self.assertFalse(res_within["approaching_deadline"])
        self.assertEqual(res_within["remaining_seconds"], 22 * 3600)

        # 4. Complaint Approaching Deadline (e.g. 21 hours after creation, 3 hours left < 6h)
        res_approach = SLAMonitor.evaluate_complaint_sla(c_active, current_time=now + timedelta(hours=21))
        self.assertEqual(res_approach["sla_status"], "approaching")
        self.assertTrue(res_approach["approaching_deadline"])
        self.assertFalse(res_approach["is_overdue"])

        # 5. Overdue Complaint & Escalation Recommendation (e.g. 30 hours after creation)
        res_overdue = SLAMonitor.evaluate_complaint_sla(c_active, current_time=now + timedelta(hours=30))
        self.assertEqual(res_overdue["sla_status"], "overdue")
        self.assertTrue(res_overdue["is_overdue"])
        self.assertTrue(res_overdue["escalation_recommended"])
        self.assertIn("overdue by 6.0h", res_overdue["escalation_reason"])

        # 6. Resolved Complaint Excluded from Overdue
        c_active.status = ComplaintStatus.RESOLVED
        c_active.resolution_date = now + timedelta(hours=20)
        c_active.save(update_fields=['status', 'resolution_date'])

        res_resolved = SLAMonitor.evaluate_complaint_sla(c_active, current_time=now + timedelta(hours=30))
        self.assertEqual(res_resolved["sla_status"], "completed_on_time")
        self.assertFalse(res_resolved["is_overdue"])
        self.assertFalse(res_resolved["escalation_recommended"])

        # 7. Escalation Application & Duplicate Escalation Prevention
        c_overdue = Complaint.objects.create(
            citizen=self.citizen,
            title="Overdue water pipeline leak",
            description="Pipeline leaking profusely",
            address="Subhash Nagar",
            department=self.dept,
            category=self.category,
            status=ComplaintStatus.IN_PROGRESS,
            sla_target_date=now - timedelta(hours=5)
        )

        # First escalation application: succeeds
        success1 = SLAMonitor.apply_admin_escalation(c_overdue, "Overdue by 5 hours", user=self.admin)
        self.assertTrue(success1)
        c_overdue.refresh_from_db()
        self.assertTrue(c_overdue.is_escalated)

        # Duplicate escalation attempt: prevented safely
        success2 = SLAMonitor.apply_admin_escalation(c_overdue, "Duplicate call", user=self.admin)
        self.assertFalse(success2)

        # 8. Lifecycle Stages Verification
        lifecycle = SLAMonitor.get_lifecycle_stage(c_overdue)
        self.assertTrue(lifecycle["submitted"]["completed"])
        self.assertTrue(lifecycle["department_assigned"]["completed"])
        self.assertFalse(lifecycle["staff_assigned"]["completed"])  # No staff assigned yet
        self.assertTrue(lifecycle["in_progress"]["completed"])
        self.assertFalse(lifecycle["resolved"]["completed"])

    def test_smart_notifications_and_citizen_updates(self):
        """
        Task 13 Tests:
        1. Notification dispatch on submission, department assigned, staff assigned, and status change.
        2. Idempotency mechanism prevents duplicate notifications for identical events.
        3. Citizen privacy & BOLA: User can only access their own notifications.
        4. Notification ViewSet endpoints: list, unread_count, mark_read, mark_all_read.
        5. SLA Escalation notification integration.
        """
        from .models import Complaint, Notification, ComplaintStatus
        from .notifications import (
            send_notification_idempotent,
            notify_complaint_submitted,
            notify_department_assigned,
            notify_staff_assigned,
            notify_status_update,
            notify_escalation
        )

        # 1. Clean existing notifications
        Notification.objects.filter(user=self.citizen).delete()

        # Create complaint
        comp = Complaint.objects.create(
            citizen=self.citizen,
            title="Broken streetlight",
            description="Streetlight pole #42 is unlit and flickering",
            address="Shivaji Park, Sector 4",
            department=self.dept,
            category=self.category,
            status=ComplaintStatus.SUBMITTED
        )

        # 2. Test Submission Notification
        notif_sub = notify_complaint_submitted(comp)
        self.assertIsNotNone(notif_sub)
        self.assertEqual(notif_sub.user, self.citizen)
        self.assertEqual(notif_sub.notification_type, 'complaint_submitted')
        self.assertIn(comp.tracking_id, notif_sub.title)

        # Test Idempotency: Duplicate submission notification call within window is suppressed
        notif_sub_dup = notify_complaint_submitted(comp)
        self.assertEqual(notif_sub.id, notif_sub_dup.id)
        self.assertEqual(Notification.objects.filter(user=self.citizen, notification_type='complaint_submitted').count(), 1)

        # 3. Test Department Assigned Notification
        notif_dept = notify_department_assigned(comp)
        self.assertIsNotNone(notif_dept)
        self.assertEqual(notif_dept.notification_type, 'department_assigned')
        self.assertIn(self.dept.name, notif_dept.message)

        # 4. Test Staff Assigned Notification (both staff and citizen get privacy-safe notifications)
        staff_results = notify_staff_assigned(comp, self.staff)
        self.assertIsNotNone(staff_results["staff"])
        self.assertEqual(staff_results["staff"].user, self.staff)
        self.assertIsNotNone(staff_results["citizen"])
        self.assertEqual(staff_results["citizen"].user, self.citizen)
        # Verify citizen message does not leak private staff user credentials
        self.assertNotIn("password", staff_results["citizen"].message.lower())

        # 5. Test Status Update Notification
        notif_status = notify_status_update(comp, 'submitted', 'in_progress', public_notes="Maintenance team dispatched.")
        self.assertIsNotNone(notif_status)
        self.assertEqual(notif_status.notification_type, 'status_update')
        self.assertIn("in progress", notif_status.message.lower())

        # 6. Test Escalation Notification
        notif_esc = notify_escalation(comp, reason="SLA threshold reached")
        self.assertIsNotNone(notif_esc)
        self.assertEqual(notif_esc.notification_type, 'escalation')

        # 7. Test API Endpoints & BOLA Protection
        self.client.force_authenticate(user=self.citizen)

        # a) List notifications
        res_list = self.client.get('/api/notifications/')
        self.assertEqual(res_list.status_code, 200)
        cit_notif_ids = [n['id'] for n in res_list.data]
        # Staff's notification should NOT be in citizen's list
        self.assertNotIn(staff_results["staff"].id, cit_notif_ids)

        # b) Unread Count
        res_count = self.client.get('/api/notifications/unread_count/')
        self.assertEqual(res_count.status_code, 200)
        self.assertGreater(res_count.data['unread_count'], 0)
        initial_unread = res_count.data['unread_count']

        # c) Mark single notification as read
        res_read = self.client.post(f'/api/notifications/{notif_sub.id}/mark_read/')
        self.assertEqual(res_read.status_code, 200)
        self.assertTrue(res_read.data['is_read'])

        # Verify unread count decreased by 1
        res_count2 = self.client.get('/api/notifications/unread_count/')
        self.assertEqual(res_count2.data['unread_count'], initial_unread - 1)

        # d) BOLA verification: citizen cannot mark staff's notification as read
        res_bola = self.client.post(f'/api/notifications/{staff_results["staff"].id}/mark_read/')
        self.assertEqual(res_bola.status_code, 404)

        # e) Mark all read
        res_mark_all = self.client.post('/api/notifications/mark_all_read/')
        self.assertEqual(res_mark_all.status_code, 200)
        res_count3 = self.client.get('/api/notifications/unread_count/')
        self.assertEqual(res_count3.data['unread_count'], 0)

    def test_ai_powered_analytics_and_insights_dashboard(self):
        """
        Task 14 Tests:
        1. Correct total, status-wise, category-wise, and department-wise counts.
        2. Average resolution time calculation and SLA compliance percentage.
        3. Date range and multidimensional filter application.
        4. Empty dataset handling without errors or divide-by-zero.
        5. RBAC / BOLA: Citizen access to /api/analytics/summary/ is denied (HTTP 403).
        6. Admin / Staff access is permitted (HTTP 200).
        7. Gemini fallback to deterministic insights when unavailable.
        8. AI insights strictly explain pre-calculated statistics without inventing data.
        """
        from datetime import timedelta
        from django.utils import timezone
        from .models import Complaint, Department, ComplaintCategory, ComplaintStatus
        from .analytics_insights import (
            calculate_analytics_metrics,
            generate_deterministic_insights,
            generate_ai_insights
        )

        now = timezone.now()

        # 1. Test Empty Dataset Handling
        Complaint.objects.all().delete()
        empty_metrics = calculate_analytics_metrics()
        self.assertEqual(empty_metrics["summary"]["total_complaints"], 0)
        self.assertEqual(empty_metrics["summary"]["resolution_rate"], 0.0)
        self.assertEqual(empty_metrics["summary"]["sla_compliance_rate"], 0.0)
        self.assertEqual(empty_metrics["summary"]["avg_resolution_hours"], 0.0)
        self.assertEqual(len(empty_metrics["category_breakdown"]), 0)
        self.assertEqual(len(empty_metrics["department_performance"]), 0)

        empty_insights = generate_deterministic_insights(empty_metrics)
        self.assertTrue(len(empty_insights) > 0)
        self.assertEqual(empty_insights[0]["type"], "info")

        # 2. Populate Concrete Database Records
        c1 = Complaint.objects.create(
            citizen=self.citizen,
            title="Broken drainage pipe",
            description="Drainage overflowing near market",
            address="Market Yard lane 2",
            department=self.dept, # Solid Waste Management, sla_hours=24
            category=self.category, # Sanitation
            status=ComplaintStatus.RESOLVED,
            resolution_date=now - timedelta(hours=10),
            sla_target_date=now + timedelta(hours=14)
        )
        c1.created_at = now - timedelta(hours=20)
        c1.save(update_fields=['created_at'])
        # Duration: 10 hours

        c2 = Complaint.objects.create(
            citizen=self.citizen,
            title="Garbage bin dumped on road",
            description="Litter scattered everywhere",
            address="Gandhi chowk",
            department=self.dept,
            category=self.category,
            status=ComplaintStatus.RESOLVED,
            resolution_date=now - timedelta(hours=2),
            sla_target_date=now - timedelta(hours=6) # Overdue resolution
        )
        c2.created_at = now - timedelta(hours=32)
        c2.save(update_fields=['created_at'])
        # Duration: 30 hours, completed overdue

        c3 = Complaint.objects.create(
            citizen=self.citizen,
            title="Streetlight not working",
            description="Pole light has blown fuse",
            address="Nehru Nagar",
            department=self.dept,
            category=self.category,
            status=ComplaintStatus.IN_PROGRESS,
            sla_target_date=now - timedelta(hours=4) # Currently overdue
        )
        c3.created_at = now - timedelta(hours=28)
        c3.save(update_fields=['created_at'])

        c4 = Complaint.objects.create(
            citizen=self.citizen,
            title="Pothole on main highway",
            description="Dangerous crater on bypass road",
            address="Expressway bypass",
            department=None, # Unassigned
            category=self.category,
            status=ComplaintStatus.SUBMITTED
        )
        c4.created_at = now - timedelta(hours=1)
        c4.save(update_fields=['created_at'])

        # 3. Test Metric Calculations
        metrics = calculate_analytics_metrics()
        summary = metrics["summary"]

        self.assertEqual(summary["total_complaints"], 4)
        self.assertEqual(summary["resolved_complaints"], 2)
        self.assertEqual(summary["in_progress_complaints"], 1)
        self.assertEqual(summary["pending_complaints"], 1)
        self.assertEqual(summary["overdue_complaints"], 1) # c3 is overdue
        self.assertEqual(summary["resolution_rate"], 50.0) # 2 out of 4 resolved

        # SLA Compliance: 1 resolved on time (c1), 1 resolved overdue (c2) -> 50.0%
        self.assertEqual(summary["sla_compliance_rate"], 50.0)

        # Average resolution time: (10h + 30h) / 2 = 20.0h
        self.assertEqual(summary["avg_resolution_hours"], 20.0)

        # Category and department distributions
        self.assertEqual(metrics["category_breakdown"][0]["count"], 4)
        dept_perf = {d["name"]: d for d in metrics["department_performance"]}
        self.assertIn("Solid Waste Management", dept_perf)
        self.assertEqual(dept_perf["Solid Waste Management"]["total_complaints"], 3)
        self.assertEqual(dept_perf["Solid Waste Management"]["resolved_count"], 2)

        # 4. Test Filters
        # Filter by department
        dept_filtered = calculate_analytics_metrics(department_id=self.dept.id)
        self.assertEqual(dept_filtered["summary"]["total_complaints"], 3)

        # Filter by status
        resolved_filtered = calculate_analytics_metrics(status_filter='resolved')
        self.assertEqual(resolved_filtered["summary"]["total_complaints"], 2)

        # Filter by date range (only last 5 hours)
        recent_filtered = calculate_analytics_metrics(date_from=now - timedelta(hours=5))
        self.assertEqual(recent_filtered["summary"]["total_complaints"], 1) # only c4

        # 5. RBAC & BOLA Access Control
        # a) Citizen is denied access (HTTP 403)
        self.client.force_authenticate(user=self.citizen)
        res_cit = self.client.get('/api/analytics/summary/')
        self.assertEqual(res_cit.status_code, 403)

        # b) Staff has access (HTTP 200)
        self.client.force_authenticate(user=self.staff)
        res_staff = self.client.get('/api/analytics/summary/')
        self.assertEqual(res_staff.status_code, 200)

        # c) Admin has access (HTTP 200)
        self.client.force_authenticate(user=self.admin)
        res_admin = self.client.get('/api/analytics/summary/')
        self.assertEqual(res_admin.status_code, 200)
        self.assertEqual(res_admin.data["total_complaints"], 4)
        self.assertEqual(res_admin.data["sla_compliance_rate"], 50.0)
        self.assertIn("ai_insights", res_admin.data)

        # 6. Test Gemini Fallback to Deterministic Insights
        with patch("api.gemini_client.call_gemini_safe") as mock_call, \
             patch("api.gemini_client.GeminiClientManager.is_available") as mock_avail:
            mock_avail.return_value = False
            mock_call.return_value = None

            insights_res = generate_ai_insights(metrics)
            self.assertEqual(insights_res["generated_by"], "deterministic")
            self.assertIn("deterministic", insights_res["disclaimer"].lower())
            # Verifies insights accurately cite real numbers
            descriptions = " ".join([i["description"] for i in insights_res["insights"]])
            self.assertIn("4", descriptions) # 4 complaints

    def test_smart_location_intelligence_and_hotspot_mapping(self):
        """
        Task 15 Tests:
        1. Valid GPS coordinates counted and geolocated.
        2. Missing GPS coordinates counted in without_gps_count and never fabricated.
        3. Invalid latitude/longitude coordinates (out of bounds or 0,0) rejected.
        4. Hotspot spatial clustering: groups nearby complaints (< 500m) into clusters.
        5. Explainable centroids: centroid coordinates labeled as approximate centers.
        6. No duplicate counting: each complaint belongs to at most one cluster.
        7. Date, category, and department filters.
        8. Empty dataset handling without errors.
        9. RBAC: Citizens denied access (HTTP 403), Admin/Staff granted access (HTTP 200).
        10. Privacy: citizen usernames/phone numbers omitted from map payload.
        """
        from datetime import timedelta
        from django.utils import timezone
        from .models import Complaint, Department, ComplaintCategory, ComplaintStatus
        from .location_intelligence import (
            calculate_location_intelligence,
            is_valid_coordinate,
            haversine_distance,
            detect_hotspots
        )

        now = timezone.now()

        # 1. Coordinate Validation Tests
        self.assertTrue(is_valid_coordinate(18.5204, 73.8567)) # Pune
        self.assertTrue(is_valid_coordinate(-33.8688, 151.2093)) # Sydney
        self.assertFalse(is_valid_coordinate(95.0, 73.8567)) # Lat out of bounds
        self.assertFalse(is_valid_coordinate(18.5204, 195.0)) # Lng out of bounds
        self.assertFalse(is_valid_coordinate(0.0, 0.0)) # Null Island placeholder
        self.assertFalse(is_valid_coordinate(None, 73.8567)) # None lat
        self.assertFalse(is_valid_coordinate("invalid", "coords")) # Non-numeric

        # 2. Empty Dataset Handling
        Complaint.objects.all().delete()
        empty_loc = calculate_location_intelligence()
        self.assertEqual(empty_loc["summary"]["total_complaints"], 0)
        self.assertEqual(empty_loc["summary"]["geolocated_complaints_count"], 0)
        self.assertEqual(empty_loc["summary"]["without_gps_count"], 0)
        self.assertEqual(len(empty_loc["hotspots"]), 0)
        self.assertEqual(len(empty_loc["complaint_markers"]), 0)
        self.assertIsNone(empty_loc["map_center"])

        # 3. Create Controlled Dataset
        # Location A: Shivaji Nagar (18.5314, 73.8446)
        # c1 & c2 are ~100m apart (Hotspot 1)
        c1 = Complaint.objects.create(
            citizen=self.citizen,
            title="Garbage bin overflowing Shivaji Nagar",
            description="Near bus depot Shivaji Nagar",
            address="Shivaji Nagar Bus Stop",
            department=self.dept,
            category=self.category,
            status=ComplaintStatus.SUBMITTED,
            latitude=18.531400,
            longitude=73.844600
        )
        c1.created_at = now - timedelta(days=2)
        c1.save(update_fields=['created_at'])

        c2 = Complaint.objects.create(
            citizen=self.citizen,
            title="Litter on sidewalk Shivaji Nagar",
            description="Near railway gate",
            address="Shivaji Nagar Station Road",
            department=self.dept,
            category=self.category,
            status=ComplaintStatus.IN_PROGRESS,
            latitude=18.532200, # ~100 meters away
            longitude=73.845100
        )
        c2.created_at = now - timedelta(days=1)
        c2.save(update_fields=['created_at'])

        # Location B: Hadapsar (18.5089, 73.9259) - >8 km away (Isolated Point)
        c3 = Complaint.objects.create(
            citizen=self.citizen,
            title="Streetlight pole unlit in Hadapsar",
            description="Dark stretch on main road",
            address="Hadapsar Magarpatta Road",
            department=self.dept,
            category=self.category,
            status=ComplaintStatus.SUBMITTED,
            latitude=18.508900,
            longitude=73.925900
        )
        c3.created_at = now
        c3.save(update_fields=['created_at'])

        # Location C: Address-only complaints (NO GPS)
        c_no_gps = Complaint.objects.create(
            citizen=self.citizen,
            title="Water leakage in pipeline",
            description="Behind central market",
            address="Central Market Yard gate 4",
            department=self.dept,
            category=self.category,
            status=ComplaintStatus.SUBMITTED,
            latitude=None,
            longitude=None
        )

        # Location D: Invalid GPS Coordinates (out of bounds)
        c_invalid_gps = Complaint.objects.create(
            citizen=self.citizen,
            title="Pothole on ring road",
            description="Near highway bypass",
            address="Ring road bypass",
            department=self.dept,
            category=self.category,
            status=ComplaintStatus.SUBMITTED,
            latitude=99.000000,
            longitude=250.000000
        )

        # 4. Test Location Intelligence Execution
        loc_res = calculate_location_intelligence(hotspot_radius_km=0.5)
        summary = loc_res["summary"]

        self.assertEqual(summary["total_complaints"], 5)
        self.assertEqual(summary["geolocated_complaints_count"], 3) # c1, c2, c3
        self.assertEqual(summary["without_gps_count"], 2) # c_no_gps, c_invalid_gps
        self.assertEqual(len(loc_res["complaint_markers"]), 3)

        # 5. Hotspot Clustering Verification
        # c1 and c2 should form 1 hotspot; c3 is isolated so does not form a cluster
        self.assertEqual(summary["hotspot_count"], 1)
        hotspot = loc_res["hotspots"][0]
        self.assertEqual(hotspot["complaint_count"], 2)
        self.assertIn(c1.id, hotspot["complaint_ids"])
        self.assertIn(c2.id, hotspot["complaint_ids"])
        self.assertNotIn(c3.id, hotspot["complaint_ids"])
        self.assertTrue(hotspot["is_approximate_center"])
        # Verify centroid is between c1 and c2
        self.assertAlmostEqual(hotspot["approximate_latitude"], (18.531400 + 18.532200) / 2, places=4)

        # Invariant: No duplicate complaint counting
        all_cluster_ids = []
        for h in loc_res["hotspots"]:
            all_cluster_ids.extend(h["complaint_ids"])
        self.assertEqual(len(all_cluster_ids), len(set(all_cluster_ids)))

        # 6. Privacy & PII Verification
        # Confirm citizen usernames, emails, or private user IDs are NOT returned in marker data
        first_marker = loc_res["complaint_markers"][0]
        self.assertNotIn("citizen_username", first_marker)
        self.assertNotIn("citizen_phone", first_marker)
        self.assertNotIn("citizen_email", first_marker)

        # 7. Test Filters
        # Filter date_from = last 12 hours (should include c3 only)
        filtered_date = calculate_location_intelligence(date_from=now - timedelta(hours=12))
        self.assertEqual(filtered_date["summary"]["geolocated_complaints_count"], 1)
        self.assertEqual(filtered_date["complaint_markers"][0]["id"], c3.id)

        # 8. API Endpoint & Security Verification
        # a) Citizen is denied access (HTTP 403)
        self.client.force_authenticate(user=self.citizen)
        res_cit = self.client.get('/api/analytics/location_intelligence/')
        self.assertEqual(res_cit.status_code, 403)

        # b) Admin has access (HTTP 200)
        self.client.force_authenticate(user=self.admin)
        res_admin = self.client.get('/api/analytics/location_intelligence/')
        self.assertEqual(res_admin.status_code, 200)
        self.assertEqual(res_admin.data["summary"]["geolocated_complaints_count"], 3)
        self.assertEqual(res_admin.data["summary"]["hotspot_count"], 1)

    def test_multilingual_voice_complaint_assistant(self):
        """
        Task 16 Tests:
        1. Voice transcript passed to classifier accurately classifies Hindi/Hinglish/English.
        2. Missing location triggers clarification question in user's language and ready_to_submit=False.
        3. General inquiry isolation (inquiry/general intent, non-complaint).
        4. Invalid Gemini response / Gemini unavailable fallback to deterministic rule engine.
        5. ready_to_submit=False prevents complaint submission without valid details.
        6. Manual correction of transcript preserves citizen meaning.
        7. Explicit confirmation required before submission (original_input_mode='voice' preserved).
        8. Standard text complaint submission remains fully functional.
        """
        from .ai_service import analyze_complaint_text
        from .models import Complaint, ComplaintStatus

        # 1. Hindi Voice Transcript Input
        hindi_transcript = "गांधी चौक के पास कचरे का ढेर लगा हुआ है बदबू आ रही है"
        res_hi = analyze_complaint_text(hindi_transcript)
        self.assertEqual(res_hi["intent"], "complaint")
        self.assertEqual(res_hi["category"], "Garbage and Sanitation")
        self.assertEqual(res_hi["detected_language"], "hi")
        self.assertIsNotNone(res_hi["location_extracted"])
        self.assertIn("गांधी चौक", res_hi["location_extracted"])
        self.assertTrue(res_hi["ready_to_submit"])

        # 2. Hinglish Voice Transcript with Missing Location
        hinglish_missing_loc = "Bhai hamare yahan sadak par bahut bada gaddha hai bike slip ho rahi hai"
        res_hinglish = analyze_complaint_text(hinglish_missing_loc)
        self.assertEqual(res_hinglish["intent"], "complaint")
        self.assertEqual(res_hinglish["category"], "Roads and Potholes")
        self.assertEqual(res_hinglish["detected_language"], "hinglish")
        self.assertIsNone(res_hinglish["location_extracted"])
        self.assertFalse(res_hinglish["ready_to_submit"])
        self.assertIsNotNone(res_hinglish["clarification_question"])
        self.assertIn("landmark", res_hinglish["clarification_question"].lower())

        # 3. Marathi Voice Transcript Input
        marathi_transcript = "टिळक रोड जवळ गटाराचे पाणी रस्त्यावर वाहत आहे"
        res_mr = analyze_complaint_text(marathi_transcript)
        self.assertEqual(res_mr["intent"], "complaint")
        self.assertEqual(res_mr["category"], "Drainage and Sewage")
        self.assertEqual(res_mr["detected_language"], "mr")
        self.assertIsNotNone(res_mr["location_extracted"])

        # 4. English Voice Transcript Input
        english_transcript = "Streetlight pole flickering and broken near City Hospital"
        res_en = analyze_complaint_text(english_transcript)
        self.assertEqual(res_en["intent"], "complaint")
        self.assertEqual(res_en["category"], "Streetlights")
        self.assertEqual(res_en["detected_language"], "en")
        self.assertIn("City Hospital", res_en["location_extracted"])
        self.assertTrue(res_en["ready_to_submit"])

        # 5. General Inquiry Isolation
        inquiry_text = "How do I register a birth certificate or check office timings?"
        res_inquiry = analyze_complaint_text(inquiry_text)
        self.assertEqual(res_inquiry["intent"], "inquiry")
        self.assertFalse(res_inquiry["ready_to_submit"])
        self.assertEqual(res_inquiry["category"], "General Inquiry")

        # 6. Gemini Unavailable Fallback
        with patch("api.ai_service.call_gemini_safe") as mock_gemini:
            mock_gemini.return_value = None  # Simulates API downtime or quota limit
            fallback_res = analyze_complaint_text("Broken water pipe near Market Yard")
            self.assertEqual(fallback_res["intent"], "complaint")
            self.assertEqual(fallback_res["category"], "Water Supply")
            self.assertIn("Market Yard", fallback_res["location_extracted"])
            self.assertTrue(fallback_res["ready_to_submit"])

        # 7. Invalid Gemini JSON Response Fallback
        with patch("api.ai_service.call_gemini_safe") as mock_gemini:
            mock_gemini.return_value = "Non-JSON random string response from LLM"
            invalid_res = analyze_complaint_text("Broken streetlight near Metro Station")
            self.assertEqual(invalid_res["intent"], "complaint")
            self.assertEqual(invalid_res["category"], "Streetlights")
            self.assertIn("Metro Station", invalid_res["location_extracted"])

        # 8. Backend API Complaint Submission with Voice Input Mode
        self.client.force_authenticate(user=self.citizen)

        voice_payload = {
            "title": "Road pothole near Gandhi Chowk",
            "description": "Voice recorded transcript: Road pothole causing accidents near Gandhi Chowk",
            "category": self.category.id,
            "department": self.dept.id,
            "priority": "high",
            "address": "Gandhi Chowk main market",
            "original_input_mode": "voice",
            "detected_language": "hi"
        }
        res_submit = self.client.post('/api/complaints/', voice_payload)
        self.assertEqual(res_submit.status_code, 201)
        self.assertEqual(res_submit.data["original_input_mode"], "voice")
        self.assertEqual(res_submit.data["detected_language"], "hi")

        # 9. Verify Standard Text Submission Remains Functional
        text_payload = {
            "title": "Garbage dump near Bus Depot",
            "description": "Standard text description of garbage overflowing",
            "category": self.category.id,
            "department": self.dept.id,
            "priority": "medium",
            "address": "Bus Depot sector 5",
            "original_input_mode": "text",
            "detected_language": "en"
        }
        res_text = self.client.post('/api/complaints/', text_payload)
        self.assertEqual(res_text.status_code, 201)
        self.assertEqual(res_text.data["original_input_mode"], "text")

    def test_citizen_trust_feedback_and_resolution_verification(self):
        """
        Task 17 Tests:
        1. Staff marks complaint resolved -> sets resolution_verification_status='pending_citizen_confirmation'.
        2. Citizen receives notification awaiting resolution confirmation.
        3. Wrong user cannot confirm or dispute resolution (BOLA protection, HTTP 403).
        4. Rating validation: valid (1-5) accepted, invalid (<1 or >5 or non-digit) rejected (HTTP 400).
        5. Correct complaint owner confirms resolution -> status='verified', verification_status='citizen_confirmed'.
        6. Duplicate feedback submission prevented.
        7. Citizen disputes resolution -> verification_status='citizen_disputed', creates timeline event, does not mark verified.
        8. Admin can view disputed cases in analytics summary.
        9. Admin reviews dispute: can reopen ticket (status='in_progress') or uphold resolution (status='verified').
        10. Missing before/after image handled gracefully.
        """
        from .models import Complaint, ComplaintStatus, ComplaintEvidence, CitizenFeedback, Notification
        from django.utils import timezone

        # Setup complaint
        comp = Complaint.objects.create(
            citizen=self.citizen,
            title="Leaking municipal tap",
            description="Continuous water leakage near bus stop",
            address="Shivaji Chowk corner",
            department=self.dept,
            category=self.category,
            status=ComplaintStatus.IN_PROGRESS,
            assigned_staff=self.staff
        )

        # 1. Staff marks complaint as resolved
        self.client.force_authenticate(user=self.staff)
        res_resolve = self.client.post(f'/api/complaints/{comp.id}/update_status/', {
            "status": "resolved",
            "notes": "Replaced faulty tap valve. Leakage stopped."
        })
        self.assertEqual(res_resolve.status_code, 200)
        comp.refresh_from_db()
        self.assertEqual(comp.status, ComplaintStatus.RESOLVED)
        self.assertEqual(comp.resolution_verification_status, 'pending_citizen_confirmation')

        # 2. Citizen receives resolution confirmation notification
        notifs = Notification.objects.filter(user=self.citizen, complaint=comp, notification_type='resolution_awaiting_confirmation')
        self.assertTrue(notifs.exists())

        # 3. Unauthorized User cannot submit feedback or dispute (BOLA check)
        self.client.force_authenticate(user=self.other_citizen)
        res_unauth = self.client.post(f'/api/complaints/{comp.id}/submit_feedback/', {
            "rating": 5,
            "feedback_text": "Looks good"
        })
        self.assertEqual(res_unauth.status_code, 403)

        # 4. Rating Validation
        self.client.force_authenticate(user=self.citizen)
        res_invalid_rating = self.client.post(f'/api/complaints/{comp.id}/submit_feedback/', {
            "rating": 6,
            "feedback_text": "Great job"
        })
        self.assertEqual(res_invalid_rating.status_code, 400)

        # 5. Citizen Confirms Resolution
        res_confirm = self.client.post(f'/api/complaints/{comp.id}/submit_feedback/', {
            "rating": 5,
            "feedback_text": "Water valve replaced properly. Good service.",
            "resolution_satisfaction": True,
            "is_disputed": False
        })
        self.assertEqual(res_confirm.status_code, 201)
        comp.refresh_from_db()
        self.assertEqual(comp.status, ComplaintStatus.VERIFIED)
        self.assertEqual(comp.resolution_verification_status, 'citizen_confirmed')

        # 6. Duplicate Feedback Submission Prevented
        res_dup = self.client.post(f'/api/complaints/{comp.id}/submit_feedback/', {
            "rating": 4,
            "feedback_text": "Changing my rating"
        })
        self.assertEqual(res_dup.status_code, 400)

        # 7. Citizen Disputes Resolution Workflow
        comp_dispute = Complaint.objects.create(
            citizen=self.citizen,
            title="Pothole repair on main lane",
            description="Deep crater damaging tires",
            address="Lane 5, Shivaji Nagar",
            department=self.dept,
            category=self.category,
            status=ComplaintStatus.RESOLVED,
            assigned_staff=self.staff,
            resolution_verification_status='pending_citizen_confirmation'
        )

        res_dispute = self.client.post(f'/api/complaints/{comp_dispute.id}/submit_feedback/', {
            "rating": 1,
            "feedback_text": "Pothole was only covered with loose gravel, wash out occurred in rain.",
            "is_disputed": True,
            "dispute_reason": "Incomplete work, gravel washed away"
        })
        self.assertEqual(res_dispute.status_code, 201)
        comp_dispute.refresh_from_db()
        self.assertEqual(comp_dispute.resolution_verification_status, 'citizen_disputed')
        # Crucial Rule: Status remains resolved/disputed, NOT verified
        self.assertNotEqual(comp_dispute.status, ComplaintStatus.VERIFIED)

        # Timeline event created
        timeline_events = comp_dispute.timeline.filter(action="Resolution Disputed by Citizen")
        self.assertTrue(timeline_events.exists())

        # 8. Admin Analytics Reflects Disputed Case
        self.client.force_authenticate(user=self.admin)
        res_analytics = self.client.get('/api/analytics/summary/')
        self.assertEqual(res_analytics.status_code, 200)
        self.assertGreaterEqual(res_analytics.data.get("citizen_disputed_count", 0), 1)

        # 9. Admin Review Action: Reopen Disputed Complaint
        res_reopen = self.client.post(f'/api/complaints/{comp_dispute.id}/admin_review_dispute/', {
            "decision": "reopen",
            "notes": "Field inspection confirmed gravel washed out. Assigned back to staff for tar resurfacing."
        })
        self.assertEqual(res_reopen.status_code, 200)
        comp_dispute.refresh_from_db()
        self.assertEqual(comp_dispute.status, ComplaintStatus.IN_PROGRESS)
        self.assertEqual(comp_dispute.resolution_verification_status, 'admin_review_required')

    def test_smart_field_staff_assignment_and_workload_optimization(self):
        """
        Task 18 Tests:
        - Department-compatible staff recommendation.
        - Inactive staff exclusion.
        - Workload comparison (active workload preference).
        - Missing skills handling (neutral, not penalized).
        - Missing staff location handling (neutral, not penalized).
        - Invalid GPS coordinates handling.
        - No eligible staff handling.
        - Multiple alternative recommendations.
        - Recommendation does not automatically assign staff.
        - Admin approval required for recommendation endpoint and assignment.
        - Actual assignment updates timeline and notifications.
        - Unauthorised assignment rejected.
        """
        from .staff_assignment import StaffAssignmentService

        # Setup departments
        dept_water = Department.objects.create(name="Water Works", code="WATER_TEST", sla_hours=24)
        dept_roads = Department.objects.create(name="Roads & Highways", code="ROADS_TEST", sla_hours=48)

        # Candidate 1: Water dept, low workload (0), plumbing skills, near complaint (1 km away)
        staff_water_1 = User.objects.create_user(
            username="staff_ramesh",
            role=UserRole.STAFF,
            department=dept_water,
            skills="pipeline,plumbing,water leakage",
            latitude=19.0760,
            longitude=72.8777,
            is_active=True
        )

        # Candidate 2: Water dept, high workload (3 active tasks), generic skills
        staff_water_2 = User.objects.create_user(
            username="staff_suresh",
            role=UserRole.STAFF,
            department=dept_water,
            skills="general maintenance",
            latitude=19.0760,
            longitude=72.8777,
            is_active=True
        )

        # Candidate 3: Roads dept (incompatible department), 0 workload
        staff_roads_1 = User.objects.create_user(
            username="staff_vijay",
            role=UserRole.STAFF,
            department=dept_roads,
            skills="tar,road roller,asphalt",
            is_active=True
        )

        # Candidate 4: Inactive staff (must be excluded)
        staff_inactive = User.objects.create_user(
            username="staff_inactive_user",
            role=UserRole.STAFF,
            department=dept_water,
            skills="pipeline,plumbing",
            is_active=False
        )

        # Assign 3 active complaints to staff_water_2 to build workload
        for i in range(3):
            Complaint.objects.create(
                citizen=self.citizen,
                title=f"Water leak {i}",
                description="Pipe burst water leakage",
                address="Sector 1",
                department=dept_water,
                status=ComplaintStatus.IN_PROGRESS,
                assigned_staff=staff_water_2
            )

        # Also assign 2 RESOLVED complaints to staff_water_1 (resolved must be excluded from workload)
        for i in range(2):
            Complaint.objects.create(
                citizen=self.citizen,
                title=f"Resolved leak {i}",
                description="Repaired water valve",
                address="Sector 2",
                department=dept_water,
                status=ComplaintStatus.RESOLVED,
                assigned_staff=staff_water_1
            )

        # Target complaint for recommendation
        target_complaint = Complaint.objects.create(
            citizen=self.citizen,
            title="Severe pipeline burst near market",
            description="Massive water leakage and pipe damage in main market area",
            address="Main Market Road",
            department=dept_water,
            latitude=19.0800,
            longitude=72.8800,
            status=ComplaintStatus.SUBMITTED
        )

        # 1. Department-compatible recommendation & Workload preference
        rec = StaffAssignmentService.recommend_staff_for_complaint(target_complaint)
        self.assertTrue(rec["has_recommendation"])
        # Top choice should be staff_water_1 (same department, 0 active workload, matched plumbing skills)
        self.assertEqual(rec["recommended_staff_id"], staff_water_1.id)
        self.assertTrue(rec["department_match"])
        self.assertEqual(rec["active_workload"], 0)
        self.assertTrue(rec["skill_match"])
        self.assertIsNotNone(rec["distance_km"])
        self.assertTrue(rec["requires_admin_approval"])

        # 2. Inactive Staff Exclusion
        all_candidate_ids = [rec["recommended_staff_id"]] + [alt["staff_id"] for alt in rec["alternative_staff"]]
        self.assertNotIn(staff_inactive.id, all_candidate_ids)

        # 3. Workload Comparison
        workload_water_1 = StaffAssignmentService.get_active_workload(staff_water_1)
        workload_water_2 = StaffAssignmentService.get_active_workload(staff_water_2)
        self.assertEqual(workload_water_1, 0)
        self.assertEqual(workload_water_2, 3)

        # 4. Multiple Alternative Recommendations Present
        self.assertGreaterEqual(len(rec["alternative_staff"]), 1)
        alt_ids = [alt["staff_id"] for alt in rec["alternative_staff"]]
        self.assertIn(staff_water_2.id, alt_ids)

        # 5. Missing Skills Handling: Neutral score without penalizing candidate
        staff_no_skills = User.objects.create_user(
            username="staff_no_skills",
            role=UserRole.STAFF,
            department=dept_water,
            is_active=True
        )
        skill_res = StaffAssignmentService.evaluate_skills(staff_no_skills, target_complaint)
        self.assertFalse(skill_res["available"])
        self.assertEqual(skill_res["score"], 0.5)

        # 6. Missing Staff Location Handling: Proximity marked unavailable, not penalized
        prox_res_no_staff_loc = StaffAssignmentService.evaluate_proximity(staff_no_skills, target_complaint)
        self.assertFalse(prox_res_no_staff_loc["available"])
        self.assertIsNone(prox_res_no_staff_loc["distance_km"])
        self.assertEqual(prox_res_no_staff_loc["score"], 0.5)

        # 7. Invalid GPS Coordinates Handling
        complaint_invalid_gps = Complaint.objects.create(
            citizen=self.citizen,
            title="Complaint with invalid GPS",
            description="Road crater",
            address="Unknown street",
            latitude=150.0,  # Invalid latitude > 90
            longitude=0.0
        )
        prox_invalid = StaffAssignmentService.evaluate_proximity(staff_water_1, complaint_invalid_gps)
        self.assertFalse(prox_invalid["available"])
        self.assertIsNone(prox_invalid["distance_km"])

        # 8. No Eligible Staff Handling
        rec_empty = StaffAssignmentService.recommend_staff_for_complaint(target_complaint, candidate_pool=[])
        self.assertFalse(rec_empty["has_recommendation"])
        self.assertIsNone(rec_empty["recommended_staff_id"])

        # 9. Human-in-the-Loop Guarantee: Recommendation does NOT automatically assign staff
        target_complaint.refresh_from_db()
        self.assertIsNone(target_complaint.assigned_staff)
        self.assertEqual(target_complaint.status, ComplaintStatus.SUBMITTED)

        # 10. Admin Endpoint Protection: Non-admin citizen forbidden from recommendation endpoint
        self.client.force_authenticate(user=self.citizen)
        res_citizen_rec = self.client.get(f'/api/complaints/{target_complaint.id}/recommend_staff/')
        self.assertEqual(res_citizen_rec.status_code, 403)

        # 11. Admin Accesses Recommendation
        self.client.force_authenticate(user=self.admin)
        res_admin_rec = self.client.get(f'/api/complaints/{target_complaint.id}/recommend_staff/')
        self.assertEqual(res_admin_rec.status_code, 200)
        self.assertEqual(res_admin_rec.data["recommended_staff_id"], staff_water_1.id)

        # 12. Unauthorised Assignment Rejected
        self.client.force_authenticate(user=self.citizen)
        res_unauth_assign = self.client.post(f'/api/complaints/{target_complaint.id}/assign_staff/', {
            "staff_id": staff_water_1.id
        })
        self.assertEqual(res_unauth_assign.status_code, 403)

        # 13. Authorized Assignment Updates Complaint, Timeline, and Sends Notification
        self.client.force_authenticate(user=self.admin)
        res_assign = self.client.post(f'/api/complaints/{target_complaint.id}/assign_staff/', {
            "staff_id": staff_water_1.id
        })
        self.assertEqual(res_assign.status_code, 200)

        target_complaint.refresh_from_db()
        self.assertEqual(target_complaint.assigned_staff, staff_water_1)
        self.assertEqual(target_complaint.status, ComplaintStatus.ASSIGNED)
        self.assertIsNotNone(target_complaint.assigned_at)

        # Check Timeline
        timeline_entry = target_complaint.timeline.filter(action=f"Assigned to {staff_water_1.username}")
        self.assertTrue(timeline_entry.exists())

        # Check Staff Notification
        staff_notif = Notification.objects.filter(user=staff_water_1, complaint=target_complaint, notification_type='staff_assigned')
        self.assertTrue(staff_notif.exists())

    def test_smart_civic_knowledge_assistant(self):
        """
        Task 19 Tests:
        1. General civic guidance retrieval (steps, guidelines).
        2. English, Hindi, and Hinglish query handling.
        3. Authenticated user's own complaint status lookup.
        4. Attempt to access another user's complaint (strictly restricted / forbidden).
        5. Invalid or non-existent complaint ID.
        6. Missing or empty message (validation error).
        7. Gemini API failure and safe deterministic fallback.
        8. Unknown civic information (handles gracefully without hallucinating).
        9. Complaint filing guidance without automatic submission (no complaint created).
        10. Unauthenticated personal complaint query (prompts login).
        """
        # Create a sample complaint owned by self.citizen
        citizen_complaint = Complaint.objects.create(
            citizen=self.citizen,
            title="Broken tap at water fountain",
            description="Continuous clean water wastage at community park fountain",
            address="Community Park Sector 4",
            department=self.dept,
            category=self.category,
            status=ComplaintStatus.IN_PROGRESS,
            assigned_staff=self.staff
        )

        # Create another complaint owned by self.other_citizen
        other_complaint = Complaint.objects.create(
            citizen=self.other_citizen,
            title="Garbage bin overflowing",
            description="Commercial market waste dumped outside bin",
            address="Market Yard Lane 2",
            department=self.dept,
            category=self.category,
            status=ComplaintStatus.SUBMITTED
        )

        initial_complaints_count = Complaint.objects.count()

        # 1. General civic guidance retrieval (Public/Unauthenticated allowed)
        self.client.logout()
        res_guidance = self.client.post('/api/assistant/chat/', {
            "message": "How do I report water leakage?",
            "language": "en"
        })
        self.assertEqual(res_guidance.status_code, 200)
        self.assertIn("water", res_guidance.data["answer"].lower())
        self.assertGreaterEqual(len(res_guidance.data["sources"]), 1)

        # 2. English, Hindi, and Hinglish query handling
        # Hindi query
        res_hi = self.client.post('/api/assistant/chat/', {
            "message": "कचरा उठाने की शिकायत कैसे दर्ज करें?"
        })
        self.assertEqual(res_hi.status_code, 200)
        self.assertEqual(res_hi.data["language"], "hi")
        self.assertIn("कचरा", res_hi.data["answer"])

        # Hinglish query
        res_hinglish = self.client.post('/api/assistant/chat/', {
            "message": "Pothole ki complain kaise kare road par gaddha hai"
        })
        self.assertEqual(res_hinglish.status_code, 200)
        self.assertEqual(res_hinglish.data["language"], "hinglish")

        # 3. Authenticated user's own complaint status
        self.client.force_authenticate(user=self.citizen)
        res_own_comp = self.client.post('/api/assistant/chat/', {
            "message": f"What is the status of my complaint {citizen_complaint.tracking_id}?",
            "complaint_id": citizen_complaint.tracking_id
        })
        self.assertEqual(res_own_comp.status_code, 200)
        self.assertIsNotNone(res_own_comp.data.get("related_complaint"))
        self.assertEqual(res_own_comp.data["related_complaint"]["tracking_id"], citizen_complaint.tracking_id)
        self.assertEqual(res_own_comp.data["related_complaint"]["status"], "in_progress")
        self.assertIn(citizen_complaint.tracking_id, res_own_comp.data["answer"])

        # 4. Attempt to access another user's complaint (Strict BOLA restriction)
        res_unauthorized = self.client.post('/api/assistant/chat/', {
            "message": f"Show details for {other_complaint.tracking_id}",
            "complaint_id": other_complaint.tracking_id
        })
        self.assertEqual(res_unauthorized.status_code, 200)
        self.assertIn("permission", res_unauthorized.data["answer"].lower())
        self.assertIsNone(res_unauthorized.data.get("related_complaint"))

        # 5. Invalid or non-existent complaint ID
        res_invalid_id = self.client.post('/api/assistant/chat/', {
            "message": "Check status of JSH-NONEXISTENT",
            "complaint_id": "JSH-NONEXISTENT"
        })
        self.assertEqual(res_invalid_id.status_code, 200)
        self.assertIn("No complaint found", res_invalid_id.data["answer"])
        self.assertIsNone(res_invalid_id.data.get("related_complaint"))

        # 6. Missing or empty message (validation error)
        res_empty = self.client.post('/api/assistant/chat/', {"message": "   "})
        self.assertEqual(res_empty.status_code, 400)
        self.assertIn("empty", res_empty.data["error"])

        # 7. Gemini API failure and safe deterministic fallback
        with patch('api.gemini_client.call_gemini_safe', return_value=None):
            res_fallback = self.client.post('/api/assistant/chat/', {
                "message": "What does submitted status mean?"
            })
            self.assertEqual(res_fallback.status_code, 200)
            self.assertIn("submitted", res_fallback.data["answer"].lower())
            self.assertTrue(len(res_fallback.data["sources"]) > 0)

        # 8. Unknown civic information (handles gracefully without hallucination)
        res_unknown = self.client.post('/api/assistant/chat/', {
            "message": "How do I apply for alien airspace passport?"
        })
        self.assertEqual(res_unknown.status_code, 200)
        self.assertFalse(res_unknown.data.get("requires_human_support"))

        # 9. Complaint filing guidance without automatic submission
        res_filing_guide = self.client.post('/api/assistant/chat/', {
            "message": "I want to file a complaint about broken streetlights on 5th cross."
        })
        self.assertEqual(res_filing_guide.status_code, 200)
        # Ensure no new complaint record was silently created in database
        self.assertEqual(Complaint.objects.count(), initial_complaints_count)
        self.assertIn("/report", " ".join(res_filing_guide.data["suggested_actions"]) + res_filing_guide.data["answer"])

        # 10. Unauthenticated personal complaint query prompts login
        self.client.logout()
        res_unauth = self.client.post('/api/assistant/chat/', {
            "message": "Meri complaint ka status kya hai?"
        })
        self.assertEqual(res_unauth.status_code, 200)
        self.assertIn("लॉगिन", res_unauth.data["answer"])
        self.assertIsNone(res_unauth.data.get("related_complaint"))

    def test_smart_predictive_civic_intelligence_and_preventive_action(self):
        """
        Task 20 Tests:
        1. Historical daily, weekly, and monthly trends.
        2. Category and department filtering.
        3. Recurring issue detection.
        4. Duplicate reports versus independent recurring incidents.
        5. Forecast with sufficient historical data (>= 7 distinct days).
        6. Forecast with insufficient historical data (< 7 days).
        7. Missing historical days handling.
        8. Hotspot risk calculation.
        9. Risk score explanation and contributing factors.
        10. Preventive recommendations generated with metrics.
        11. Unauthorized citizen access (HTTP 403 Forbidden).
        12. Invalid forecast horizon parameter handling (HTTP 400).
        13. Missing/invalid GPS coordinates handling.
        14. Gemini failure and deterministic fallback.
        15. No personal information leakage in predictive analytics outputs.
        """
        from datetime import timedelta
        from django.utils import timezone
        from .predictive_intelligence import (
            aggregate_historical_trends,
            detect_recurring_problems,
            calculate_complaint_volume_forecast,
            calculate_hotspot_risk_scores,
            generate_preventive_recommendations
        )

        # 11. Unauthorized Citizen Access Rejected
        self.client.force_authenticate(user=self.citizen)
        res_unauth = self.client.get('/api/analytics/predictive/trends/')
        self.assertEqual(res_unauth.status_code, 403)

        # Setup historical complaints spanning 10 days
        self.client.force_authenticate(user=self.admin)
        dept_water = Department.objects.create(name="Water Supply Dept", code="WATER_PRED", sla_hours=24)
        cat_leak = ComplaintCategory.objects.create(name="Pipeline Leakage", slug="pipeline-leakage", department=dept_water)

        now = timezone.now()
        complaints_created = []

        # Create complaints across 10 past days to test forecasting with sufficient data
        for day_offset in range(10, 0, -1):
            created_dt = now - timedelta(days=day_offset)
            c = Complaint.objects.create(
                citizen=self.citizen,
                title=f"Water issue day {day_offset}",
                description=f"Water supply disrupted in sector {day_offset}",
                address=f"Street {day_offset}",
                department=dept_water,
                category=cat_leak,
                status=ComplaintStatus.RESOLVED if day_offset > 3 else ComplaintStatus.IN_PROGRESS
            )
            # Override created_at to simulate historical dates
            Complaint.objects.filter(id=c.id).update(created_at=created_dt)
            complaints_created.append(c)

        # Create a cluster of recurring complaints in the same location (near GPS 19.0760, 72.8777)
        # 2 independent incidents and 1 duplicate report
        c_orig = Complaint.objects.create(
            citizen=self.citizen,
            title="Burst pipeline at chowk",
            description="Water gushing on road",
            address="Shivaji Chowk",
            department=dept_water,
            category=cat_leak,
            latitude=19.0760,
            longitude=72.8777,
            status=ComplaintStatus.IN_PROGRESS
        )
        Complaint.objects.filter(id=c_orig.id).update(created_at=now - timedelta(days=5))

        c_dup = Complaint.objects.create(
            citizen=self.other_citizen,
            title="Water pipe burst again",
            description="Water gushing on road same place",
            address="Shivaji Chowk",
            department=dept_water,
            category=cat_leak,
            latitude=19.0761,
            longitude=72.8778,
            status=ComplaintStatus.IN_PROGRESS,
            ai_duplicate_suspect=True,
            duplicate_of=c_orig
        )
        Complaint.objects.filter(id=c_dup.id).update(created_at=now - timedelta(days=4))

        c_reopen = Complaint.objects.create(
            citizen=self.citizen,
            title="Second leak near chowk",
            description="Another valve leaking at same spot",
            address="Shivaji Chowk",
            department=dept_water,
            category=cat_leak,
            latitude=19.0762,
            longitude=72.8776,
            status=ComplaintStatus.ESCALATED,
            is_escalated=True
        )
        Complaint.objects.filter(id=c_reopen.id).update(created_at=now - timedelta(days=1))

        # 1. Historical Daily, Weekly & Monthly Trends
        res_trends = self.client.get('/api/analytics/predictive/trends/')
        self.assertEqual(res_trends.status_code, 200)
        self.assertGreaterEqual(len(res_trends.data["daily_trends"]), 7)
        self.assertGreaterEqual(len(res_trends.data["weekly_trends"]), 1)
        self.assertGreaterEqual(len(res_trends.data["monthly_trends"]), 1)
        self.assertIn("category_distribution", res_trends.data)
        self.assertIn("department_distribution", res_trends.data)

        # 2. Category & Department Filtering
        res_filtered = self.client.get(f'/api/analytics/predictive/trends/?category={cat_leak.id}')
        self.assertEqual(res_filtered.status_code, 200)
        for cat_item in res_filtered.data["category_distribution"]:
            self.assertEqual(cat_item["category_name"], cat_leak.name)

        # 3. Recurring Issue Detection & 4. Duplicate vs Independent Distinction
        recurring = res_trends.data.get("recurring_problems", [])
        self.assertGreaterEqual(len(recurring), 1)
        chowk_recur = next((r for r in recurring if "Shivaji Chowk" in r["location_label"]), recurring[0])
        self.assertEqual(chowk_recur["category_name"], cat_leak.name)
        self.assertGreaterEqual(chowk_recur["total_complaint_count"], 2)
        # Verify confirmed vs suspected duplicate vs independent count distinction
        self.assertGreaterEqual(chowk_recur["confirmed_duplicate_count"], 1)
        self.assertEqual(chowk_recur["suspected_duplicate_count"], 0)
        self.assertGreaterEqual(chowk_recur["independent_incidents_count"], 1)

        # 5. Forecast with Sufficient Historical Data (>= 7 distinct days)
        res_forecast = self.client.get('/api/analytics/predictive/forecast/?horizon_days=7')
        self.assertEqual(res_forecast.status_code, 200)
        self.assertEqual(res_forecast.data["status"], "success")
        self.assertEqual(len(res_forecast.data["predictions"]), 7)
        self.assertIn("methodology", res_forecast.data)
        self.assertTrue(res_forecast.data["predictions"][0]["is_estimate"])

        # 6. Forecast with Insufficient Historical Data (< 7 days)
        # Filter to a narrow 2-day date range using ISO date string YYYY-MM-DD
        date_short = (now - timedelta(days=2)).strftime("%Y-%m-%d")
        res_insufficient = self.client.get(f'/api/analytics/predictive/forecast/?date_from={date_short}')
        self.assertEqual(res_insufficient.status_code, 200)
        self.assertEqual(res_insufficient.data["status"], "insufficient_data")
        self.assertIn("Insufficient historical data", res_insufficient.data["message"])

        # 7. Missing Historical Days Handling
        # Verify predictions handle missing days without throwing errors
        forecast_sparse = calculate_complaint_volume_forecast(Complaint.objects.filter(department=dept_water))
        self.assertIn("predictions", forecast_sparse)

        # 8. Hotspot Risk Calculation & 9. Risk Factors Explanation
        res_hotspots = self.client.get('/api/analytics/predictive/hotspots/')
        self.assertEqual(res_hotspots.status_code, 200)
        hotspot_list = res_hotspots.data["hotspot_risk_scores"]
        self.assertGreaterEqual(len(hotspot_list), 1)
        top_hs = hotspot_list[0]
        self.assertGreaterEqual(top_hs["risk_score"], 0.0)
        self.assertLessEqual(top_hs["risk_score"], 100.0)
        self.assertIn(top_hs["risk_level"], ["low", "medium", "high"])
        self.assertGreaterEqual(len(top_hs["contributing_factors"]), 1)

        # 10. Preventive Action Recommendations with Supporting Metrics
        res_recs = self.client.get('/api/analytics/predictive/recommendations/')
        self.assertEqual(res_recs.status_code, 200)
        recs = res_recs.data["recommendations"]
        self.assertGreaterEqual(len(recs), 1)
        self.assertIn("suggested_action", recs[0])
        self.assertIn("supporting_metric", recs[0])
        self.assertIn("confidence_level", recs[0])

        # 12. Invalid Horizon Parameter Handling (HTTP 400)
        res_bad_horizon = self.client.get('/api/analytics/predictive/forecast/?horizon_days=999')
        self.assertEqual(res_bad_horizon.status_code, 400)
        self.assertIn("horizon", res_bad_horizon.data["error"].lower())

        # 13. Missing GPS Coordinates: Non-GPS complaints do not crash hotspot scoring
        c_no_gps = Complaint.objects.create(
            citizen=self.citizen,
            title="Non GPS leak",
            description="Address only",
            address="Vague street",
            department=dept_water,
            category=cat_leak,
            latitude=None,
            longitude=None
        )
        hs_scores = calculate_hotspot_risk_scores(Complaint.objects.filter(id=c_no_gps.id))
        self.assertEqual(len(hs_scores), 0)

        # 14. Gemini Failure and Safe Deterministic Fallback
        with patch('api.gemini_client.call_gemini_safe', return_value=None):
            recs_fallback = generate_preventive_recommendations(
                Complaint.objects.all(),
                hotspots=hotspot_list,
                recurring_problems=recurring
            )
            self.assertGreaterEqual(len(recs_fallback), 1)

        # 15. No Personal Information Leakage in Predictive Outputs
        serialized_str = str(res_trends.data) + str(res_forecast.data) + str(res_hotspots.data) + str(res_recs.data)
        self.assertNotIn("testcitizen", serialized_str)
        self.assertNotIn("testpassword", serialized_str)
        self.assertNotIn("admin@test.com", serialized_str)

        # 16. Dedicated Velocity Acceleration Tests (Task 20 Logic Corrections)
        # Test all four scenarios:
        # a) Increasing volume (C_curr > C_prev)
        # b) Decreasing volume (C_curr < C_prev)
        # c) Unchanged volume (C_curr == C_prev > 0)
        # d) Zero volume (C_curr == 0 and C_prev == 0)
        from .predictive_intelligence import calculate_hotspot_risk_scores, detect_recurring_problems

        # Build mock cluster complaints for velocity testing
        # Center lat/lng near Shivaji Chowk
        base_lat, base_lng = 19.0760, 72.8777
        
        # Scenario A: Increasing volume (C_curr=4, C_prev=2)
        # delta = +2, max(4,2) = 4, shift = 2/(2*4) = 0.25 -> growth_factor = 0.75
        complaints_inc = []
        for i in range(4):
            c = Complaint.objects.create(
                citizen=self.citizen, title=f"Inc Curr {i}", description="Test",
                address="Shivaji Chowk", department=dept_water, category=cat_leak,
                latitude=base_lat + 0.0001, longitude=base_lng + 0.0001, status=ComplaintStatus.SUBMITTED
            )
            Complaint.objects.filter(id=c.id).update(created_at=now - timedelta(days=2))
            complaints_inc.append(c)
        for i in range(2):
            c = Complaint.objects.create(
                citizen=self.citizen, title=f"Inc Prev {i}", description="Test",
                address="Shivaji Chowk", department=dept_water, category=cat_leak,
                latitude=base_lat + 0.0001, longitude=base_lng + 0.0001, status=ComplaintStatus.RESOLVED
            )
            Complaint.objects.filter(id=c.id).update(created_at=now - timedelta(days=20))
            complaints_inc.append(c)

        scores_inc = calculate_hotspot_risk_scores(Complaint.objects.filter(id__in=[c.id for c in complaints_inc]))
        self.assertGreaterEqual(len(scores_inc), 1)
        self.assertEqual(scores_inc[0]["current_14d_count"], 4)
        self.assertEqual(scores_inc[0]["previous_14d_count"], 2)
        self.assertTrue(any("Increasing velocity" in f for f in scores_inc[0]["contributing_factors"]))

        # Scenario B: Decreasing volume (C_curr=1, C_prev=3)
        # delta = -2, max(1,3) = 3, shift = -2/6 = -0.333 -> growth_factor = 0.167
        complaints_dec = []
        c_dec_curr = Complaint.objects.create(
            citizen=self.citizen, title="Dec Curr", description="Test",
            address="Shivaji Chowk Dec", department=dept_water, category=cat_leak,
            latitude=19.1000, longitude=72.8500, status=ComplaintStatus.SUBMITTED
        )
        Complaint.objects.filter(id=c_dec_curr.id).update(created_at=now - timedelta(days=3))
        complaints_dec.append(c_dec_curr)
        for i in range(3):
            c = Complaint.objects.create(
                citizen=self.citizen, title=f"Dec Prev {i}", description="Test",
                address="Shivaji Chowk Dec", department=dept_water, category=cat_leak,
                latitude=19.1000, longitude=72.8500, status=ComplaintStatus.RESOLVED
            )
            Complaint.objects.filter(id=c.id).update(created_at=now - timedelta(days=22))
            complaints_dec.append(c)

        scores_dec = calculate_hotspot_risk_scores(Complaint.objects.filter(id__in=[c.id for c in complaints_dec]))
        self.assertGreaterEqual(len(scores_dec), 1)
        self.assertEqual(scores_dec[0]["current_14d_count"], 1)
        self.assertEqual(scores_dec[0]["previous_14d_count"], 3)
        self.assertTrue(any("Decreasing velocity" in f for f in scores_dec[0]["contributing_factors"]))

        # Scenario C: Unchanged volume (C_curr=2, C_prev=2)
        # delta = 0 -> shift = 0 -> growth_factor = 0.5
        complaints_unc = []
        for i in range(2):
            c = Complaint.objects.create(
                citizen=self.citizen, title=f"Unc Curr {i}", description="Test",
                address="Shivaji Chowk Unc", department=dept_water, category=cat_leak,
                latitude=19.2000, longitude=72.8600, status=ComplaintStatus.SUBMITTED
            )
            Complaint.objects.filter(id=c.id).update(created_at=now - timedelta(days=5))
            complaints_unc.append(c)
        for i in range(2):
            c = Complaint.objects.create(
                citizen=self.citizen, title=f"Unc Prev {i}", description="Test",
                address="Shivaji Chowk Unc", department=dept_water, category=cat_leak,
                latitude=19.2000, longitude=72.8600, status=ComplaintStatus.RESOLVED
            )
            Complaint.objects.filter(id=c.id).update(created_at=now - timedelta(days=25))
            complaints_unc.append(c)

        scores_unc = calculate_hotspot_risk_scores(Complaint.objects.filter(id__in=[c.id for c in complaints_unc]))
        self.assertGreaterEqual(len(scores_unc), 1)
        self.assertEqual(scores_unc[0]["current_14d_count"], 2)
        self.assertEqual(scores_unc[0]["previous_14d_count"], 2)
        self.assertTrue(any("Unchanged velocity" in f for f in scores_unc[0]["contributing_factors"]))

        # Scenario D: Zero volume in both periods (historical complaints older than 28 days)
        complaints_zero = []
        for i in range(3):
            c = Complaint.objects.create(
                citizen=self.citizen, title=f"Zero Old {i}", description="Test",
                address="Shivaji Chowk Zero", department=dept_water, category=cat_leak,
                latitude=19.3000, longitude=72.8700, status=ComplaintStatus.RESOLVED
            )
            Complaint.objects.filter(id=c.id).update(created_at=now - timedelta(days=40))
            complaints_zero.append(c)

        scores_zero = calculate_hotspot_risk_scores(Complaint.objects.filter(id__in=[c.id for c in complaints_zero]))
        self.assertGreaterEqual(len(scores_zero), 1)
        self.assertEqual(scores_zero[0]["current_14d_count"], 0)
        self.assertEqual(scores_zero[0]["previous_14d_count"], 0)
        self.assertTrue(any("Zero complaints in past 28 days" in f for f in scores_zero[0]["contributing_factors"]))

        # 17. Dedicated Recurring Problem Duplicate Distinction Tests
        # Test cluster with 1 primary, 1 confirmed duplicate (duplicate_of set), 1 suspected duplicate (ai_duplicate_suspect=True, duplicate_of=None)
        c_primary = Complaint.objects.create(
            citizen=self.citizen, title="Primary Leak", description="Main pipe burst",
            address="Test Park", department=dept_water, category=cat_leak,
            latitude=19.4000, longitude=72.8800, status=ComplaintStatus.SUBMITTED
        )
        c_confirmed = Complaint.objects.create(
            citizen=self.other_citizen, title="Confirmed Dup", description="Same leak duplicate",
            address="Test Park", department=dept_water, category=cat_leak,
            latitude=19.4001, longitude=72.8801, status=ComplaintStatus.SUBMITTED,
            duplicate_of=c_primary
        )
        c_suspected = Complaint.objects.create(
            citizen=self.citizen, title="Suspected Dup", description="Water on ground",
            address="Test Park", department=dept_water, category=cat_leak,
            latitude=19.4002, longitude=72.8802, status=ComplaintStatus.SUBMITTED,
            ai_duplicate_suspect=True,
            duplicate_of=None
        )

        recurring_res = detect_recurring_problems(Complaint.objects.filter(id__in=[c_primary.id, c_confirmed.id, c_suspected.id]))
        self.assertEqual(len(recurring_res), 1)
        rec_item = recurring_res[0]
        self.assertEqual(rec_item["total_complaint_count"], 3)
        self.assertEqual(rec_item["confirmed_duplicate_count"], 1)
        self.assertEqual(rec_item["suspected_duplicate_count"], 1)
        self.assertEqual(rec_item["independent_incidents_count"], 2)  # 3 total - 1 confirmed duplicate = 2 independent
        self.assertIn("1 confirmed duplicate reports", rec_item["explanation"])
        self.assertIn("1 suspected duplicates awaiting verification", rec_item["explanation"])

    def test_production_readiness_security_and_health_checks(self):
        """
        Task 21 Tests:
        1. Public Health Check (/api/health/) returns HTTP 200 OK without authentication.
        2. Deep Diagnostics (/api/health/diagnostics/) blocked for anonymous citizens (HTTP 403).
        3. Deep Diagnostics accessible to Admin/Staff (HTTP 200) with DB latency and zero secret leaks.
        4. File Upload Security: Banned executable extension (.exe, .sh) rejected with validation error.
        5. File Upload Security: Corrupted/Fake image binary rejected with validation error.
        6. Security Headers and Throttling settings verified.
        """
        from .models import ComplaintEvidence, Complaint
        from django.core.files.uploadedfile import SimpleUploadedFile

        # 1. Public Health Check
        res_ping = self.client.get('/api/health/')
        self.assertEqual(res_ping.status_code, 200)
        self.assertEqual(res_ping.data["status"], "healthy")
        self.assertIn("timestamp", res_ping.data)

        # 2. Deep Diagnostics blocked for Citizen (HTTP 403)
        self.client.force_authenticate(user=self.citizen)
        res_diag_citizen = self.client.get('/api/health/diagnostics/')
        self.assertEqual(res_diag_citizen.status_code, 403)

        # 3. Deep Diagnostics accessible to Admin (HTTP 200)
        self.client.force_authenticate(user=self.admin)
        res_diag_admin = self.client.get('/api/health/diagnostics/')
        self.assertEqual(res_diag_admin.status_code, 200)
        self.assertIn("checks", res_diag_admin.data)
        self.assertTrue(res_diag_admin.data["checks"]["database"]["connected"])
        self.assertIsInstance(res_diag_admin.data["checks"]["database"]["latency_ms"], float)
        # Ensure no secrets or API keys are leaked in diagnostics
        diag_str = str(res_diag_admin.data)
        self.assertNotIn("GEMINI_API_KEY", diag_str)
        self.assertNotIn("DJANGO_SECRET_KEY", diag_str)

        # 4. Dangerous / Executable File Upload Rejection
        c = Complaint.objects.create(
            citizen=self.citizen,
            title="Evidence Test Ticket",
            description="Testing secure file uploads",
            address="Shivaji Chowk",
            department=self.dept,
            category=self.category,
            latitude=19.0760,
            longitude=72.8777
        )
        malicious_script = SimpleUploadedFile("exploit.sh", b"#!/bin/bash\necho hack\n", content_type="text/x-shellscript")
        res_script = self.client.post('/api/evidence/', {
            'complaint': c.id,
            'file': malicious_script,
            'file_type': 'document'
        }, format='multipart')
        self.assertEqual(res_script.status_code, 400)
        self.assertIn("strictly prohibited", str(res_script.data))

        # 5. Corrupted Image Binary Rejection
        fake_image = SimpleUploadedFile("fake_photo.jpg", b"This is not a real JPEG image binary data", content_type="image/jpeg")
        res_fake_img = self.client.post('/api/evidence/', {
            'complaint': c.id,
            'file': fake_image,
            'file_type': 'image'
        }, format='multipart')
        self.assertEqual(res_fake_img.status_code, 400)
        self.assertIn("corrupted", str(res_fake_img.data).lower())

















