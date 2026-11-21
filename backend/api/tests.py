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









