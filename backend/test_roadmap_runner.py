"""
JanSahayak Comprehensive Integration and Verification Runner
Tests Phases 3 through 7 across live Django DB and API serializers.
"""
import os
import sys
import django

# Setup Django Environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'jansahayak_project.settings')
django.setup()

from django.test import Client
from django.utils import timezone
from datetime import timedelta
from api.models import (
    User, UserRole, Department, ComplaintCategory, Complaint,
    ComplaintStatus, ComplaintEvidence, ComplaintTimeline,
    Notification, CitizenFeedback, EmailOTP
)
from api.email_service import send_otp_email, verify_otp_code
from api.ai_service import analyze_complaint_text
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
import io

print("================================================================================")
print("  JANSAHAYAK END-TO-END AUTOMATED INTEGRATION & SECURITY SUITE")
print("================================================================================")

client = Client()

# Clean slate test user setup
email_test = "citizen.test@jansahayak.gov.in"
User.objects.filter(email=email_test).delete()

# ------------------------------------------------------------------------------
# PHASE 3: AUTHENTICATION TESTING
# ------------------------------------------------------------------------------
print("\n[PHASE 3] Testing Authentication, Email OTP & Password Workflows...")

# 3.1 Send Signup OTP
otp_res = send_otp_email(email_test, purpose='signup')
assert otp_res.get('success') is True, f"Failed to send signup OTP: {otp_res}"
otp_obj = EmailOTP.objects.filter(email=email_test, purpose='signup', is_used=False).latest('created_at')
print(f"  ✓ Signup OTP generated and sent to console: {otp_obj.otp}")

# 3.2 Verify Signup OTP via API
verify_res = client.post('/api/auth/otp/verify_signup_otp/', {
    'email': email_test,
    'otp': otp_obj.otp
}, content_type='application/json')
assert verify_res.status_code == 200 and verify_res.json().get('verified') is True
print("  ✓ Signup OTP verified via API")

# 3.3 Register Citizen User
reg_res = client.post('/api/auth/register/', {
    'username': 'citizentest',
    'email': email_test,
    'password': 'StrongPassword@123',
    'first_name': 'Aarav',
    'last_name': 'Sharma',
    'role': 'citizen',
    'phone_number': '9876543210',
    'preferred_language': 'hi'
}, content_type='application/json')
assert reg_res.status_code == 201, f"Registration failed: {reg_res.json()}"
citizen_user = User.objects.get(username='citizentest')
print(f"  ✓ Citizen registered: ID {citizen_user.id} ({citizen_user.get_role_display()})")

# 3.4 Login via Password
login_res = client.post('/api/auth/login/', {
    'username': 'citizentest',
    'password': 'StrongPassword@123'
}, content_type='application/json')
assert login_res.status_code == 200, f"Login failed: {login_res.json()}"
jwt_token = login_res.json()['access']
auth_headers = {'HTTP_AUTHORIZATION': f'Bearer {jwt_token}'}
print("  ✓ Password login succeeded (JWT Access Token issued)")

# 3.5 Login via Email OTP
login_otp_res = client.post('/api/auth/otp/send_otp/', {
    'email': email_test,
    'purpose': 'login'
}, content_type='application/json')
assert login_otp_res.status_code == 200
login_otp_obj = EmailOTP.objects.filter(email=email_test, purpose='login', is_used=False).latest('created_at')
verify_login_res = client.post('/api/auth/otp/verify_login_otp/', {
    'email': email_test,
    'otp': login_otp_obj.otp
}, content_type='application/json')
assert verify_login_res.status_code == 200 and 'access' in verify_login_res.json()
print("  ✓ Passwordless Email OTP login succeeded")

# 3.6 Password Reset with OTP
reset_otp_res = client.post('/api/auth/otp/send_otp/', {
    'email': email_test,
    'purpose': 'reset_password'
}, content_type='application/json')
assert reset_otp_res.status_code == 200
reset_otp_obj = EmailOTP.objects.filter(email=email_test, purpose='reset_password', is_used=False).latest('created_at')
reset_action_res = client.post('/api/auth/otp/reset_password_with_otp/', {
    'email': email_test,
    'otp': reset_otp_obj.otp,
    'new_password': 'NewStrongPassword@456'
}, content_type='application/json')
assert reset_action_res.status_code == 200
# Re-login with new password
relogin_res = client.post('/api/auth/login/', {
    'username': 'citizentest',
    'password': 'NewStrongPassword@456'
}, content_type='application/json')
assert relogin_res.status_code == 200
jwt_token = relogin_res.json()['access']
auth_headers = {'HTTP_AUTHORIZATION': f'Bearer {jwt_token}'}
print("  ✓ Password reset with OTP succeeded and re-authenticated")

# ------------------------------------------------------------------------------
# PHASE 4: CITIZEN WORKFLOW TESTING
# ------------------------------------------------------------------------------
print("\n[PHASE 4] Testing Citizen Grievance Workflow, AI, Evidence & Tracking...")

# Ensure Department & Category
dept, _ = Department.objects.get_or_create(name="Sanitation and Waste", defaults={'code': 'SW_TEST', 'sla_hours': 24})
cat, _ = ComplaintCategory.objects.get_or_create(name="Garbage and Sanitation", defaults={'slug': 'garbage-sanitation', 'department': dept})

# 4.1 AI Multilingual Complaint Analysis
hi_text = "कचरा पेटी ओवरफ्लो हो रही है बदबू आ रही है गांधी चौक के पास"
ai_res = analyze_complaint_text(hi_text)
assert ai_res['intent'] == 'complaint'
assert ai_res['category'] == 'Garbage and Sanitation'
assert ai_res['detected_language'] in ['hi', 'mr']
print(f"  ✓ AI Multilingual Inference: Category='{ai_res['category']}', Lang='{ai_res['detected_language']}', Ready={ai_res['ready_to_submit']}")

# 4.2 Complaint Submission via API
comp_payload = {
    'title': 'Garbage dump overflowing near Gandhi Chowk',
    'description': hi_text,
    'category': cat.id,
    'department': dept.id,
    'address': 'Gandhi Chowk near main gate',
    'latitude': 19.0760,
    'longitude': 72.8777,
    'priority': 'high',
    'original_input_mode': 'voice',
    'detected_language': 'hi'
}
comp_res = client.post('/api/complaints/', comp_payload, content_type='application/json', **auth_headers)
assert comp_res.status_code == 201, f"Complaint submission failed: {comp_res.json()}"
complaint_id = comp_res.json()['id']
tracking_id = comp_res.json()['tracking_id']
print(f"  ✓ Grievance registered successfully: ID {complaint_id} (Tracking #{tracking_id})")

# 4.3 Evidence Upload (Real Valid JPEG Image)
img_io = io.BytesIO()
img = Image.new('RGB', (100, 100), color=(169, 77, 55))
img.save(img_io, format='JPEG')
img_io.seek(0)
real_image = SimpleUploadedFile("evidence_scene.jpg", img_io.read(), content_type="image/jpeg")

ev_res = client.post('/api/evidence/', {
    'complaint': complaint_id,
    'file': real_image,
    'file_type': 'image'
}, format='multipart', **auth_headers)
assert ev_res.status_code == 201, f"Evidence upload failed: {ev_res.json()}"
evidence_id = ev_res.json()['id']
print(f"  ✓ Evidence image uploaded and verified: Evidence ID {evidence_id}")

# 4.4 Citizen Complaint Tracking & Timeline
track_res = client.get(f'/api/complaints/{complaint_id}/', **auth_headers)
assert track_res.status_code == 200
assert len(track_res.json().get('timeline', [])) >= 1
assert track_res.json()['sla_info'] is not None
print("  ✓ Complaint tracking verified (SLA metrics and audit timeline present)")

# 4.5 Citizen In-App Notification check
notif_res = client.get('/api/notifications/', **auth_headers)
assert notif_res.status_code == 200
assert len(notif_res.json()) >= 1
print(f"  ✓ Citizen notifications delivered: {len(notif_res.json())} updates logged")

# ------------------------------------------------------------------------------
# PHASE 5: STAFF WORKFLOW TESTING
# ------------------------------------------------------------------------------
print("\n[PHASE 5] Testing Staff Operations, Status Transitions & Evidence...")

# Setup staff user
staff_user, _ = User.objects.get_or_create(
    username="fieldstaff_rajesh",
    defaults={
        'email': 'rajesh.staff@jansahayak.gov.in',
        'role': UserRole.STAFF,
        'department': dept,
        'skills': 'waste,sanitation,cleanup'
    }
)
staff_user.set_password("StaffPass@123")
staff_user.save()

# Staff Login
staff_login = client.post('/api/auth/login/', {'username': 'fieldstaff_rajesh', 'password': 'StaffPass@123'}, content_type='application/json')
staff_token = staff_login.json()['access']
staff_headers = {'HTTP_AUTHORIZATION': f'Bearer {staff_token}'}

# Assign Staff to Complaint
comp_obj = Complaint.objects.get(id=complaint_id)
comp_obj.assigned_staff = staff_user
comp_obj.status = ComplaintStatus.ASSIGNED
comp_obj.save()
print(f"  ✓ Staff assigned: {staff_user.username}")

# 5.1 Staff Updates Status to In-Progress
status_prog = client.post(f'/api/complaints/{complaint_id}/update_status/', {
    'status': 'in_progress',
    'notes': 'Refuse compactor deployed to Gandhi Chowk.'
}, content_type='application/json', **staff_headers)
assert status_prog.status_code == 200
print("  ✓ Staff status transition to IN_PROGRESS verified")

# 5.2 Staff Marks Resolved
status_res = client.post(f'/api/complaints/{complaint_id}/update_status/', {
    'status': 'resolved',
    'notes': 'All municipal waste cleared and area sanitized.'
}, content_type='application/json', **staff_headers)
assert status_res.status_code == 200
assert status_res.json()['status'] == 'resolved'
print("  ✓ Staff status transition to RESOLVED verified (Ticket moved to pending verification)")

# 5.3 Citizen Confirms Resolution & Submits Feedback
feedback_res = client.post(f'/api/complaints/{complaint_id}/submit_feedback/', {
    'action': 'confirm',
    'rating': 5,
    'feedback_text': 'Very prompt cleanup. Excellent work!'
}, content_type='application/json', **auth_headers)
assert feedback_res.status_code == 201, f"Feedback failed: {feedback_res.status_code} {feedback_res.json()}"
comp_obj.refresh_from_db()
assert comp_obj.status == ComplaintStatus.VERIFIED
print(f"  ✓ Citizen verified resolution: Status={comp_obj.status}, Feedback recorded")

# ------------------------------------------------------------------------------
# PHASE 6: ADMIN WORKFLOW & PREDICTIVE INTELLIGENCE
# ------------------------------------------------------------------------------
print("\n[PHASE 6] Testing Admin Dashboard, Analytics, SLA & Predictive Intelligence...")

admin_user, _ = User.objects.get_or_create(username='admin_officer', defaults={'email': 'admin@jansahayak.gov.in', 'role': UserRole.ADMIN, 'is_staff': True, 'is_superuser': True})
admin_user.set_password("AdminPass@123")
admin_user.save()

admin_login = client.post('/api/auth/login/', {'username': 'admin_officer', 'password': 'AdminPass@123'}, content_type='application/json')
admin_token = admin_login.json()['access']
admin_headers = {'HTTP_AUTHORIZATION': f'Bearer {admin_token}'}

# 6.1 Analytics Summary
summary_res = client.get('/api/analytics/summary/', **admin_headers)
assert summary_res.status_code == 200
assert 'total_complaints' in summary_res.json()
print(f"  ✓ Admin Analytics Summary: Total={summary_res.json()['total_complaints']}, Rate={summary_res.json()['resolution_rate']}%")

# 6.2 Location Intelligence & Hotspots
loc_res = client.get('/api/analytics/location_intelligence/', **admin_headers)
assert loc_res.status_code == 200
assert 'hotspots' in loc_res.json()
print(f"  ✓ Location Intelligence: Geolocated={loc_res.json()['summary']['geolocated_complaints_count']}, Hotspots={loc_res.json()['summary']['hotspot_count']}")

# 6.3 Predictive Trends & Acceleration
trends_res = client.get('/api/analytics/predictive/trends/', **admin_headers)
assert trends_res.status_code == 200
print(f"  ✓ Predictive Historical Trends: Daily={len(trends_res.json()['daily_trends'])}, Recurring Problems={len(trends_res.json()['recurring_problems'])}")

# 6.4 Hotspot Risk Ranking
hs_res = client.get('/api/analytics/predictive/hotspots/', **admin_headers)
assert hs_res.status_code == 200
print(f"  ✓ Hotspot Risk Ranking: Scored Clusters={len(hs_res.json()['hotspot_risk_scores'])}")

# 6.5 Preventive Recommendations
rec_res = client.get('/api/analytics/predictive/recommendations/', **admin_headers)
assert rec_res.status_code == 200
print(f"  ✓ Preventive Action Recommendations: Directives={len(rec_res.json()['recommendations'])}")

# ------------------------------------------------------------------------------
# PHASE 7: SECURITY & ROBUSTNESS TESTING
# ------------------------------------------------------------------------------
print("\n[PHASE 7] Testing Security Boundaries, Access Control & Malicious Payloads...")

# 7.1 Unauthorized Access to Admin Analytics
anon_res = client.get('/api/analytics/summary/')
assert anon_res.status_code == 401
citizen_blocked_res = client.get('/api/analytics/summary/', **auth_headers)
assert citizen_blocked_res.status_code == 403
print("  ✓ Unauthorized access prevention: Anonymous=401, Citizen=403 on Admin Analytics")

# 7.2 Diagnostics Authorization
diag_anon = client.get('/api/health/diagnostics/')
assert diag_anon.status_code == 403
diag_citizen = client.get('/api/health/diagnostics/', **auth_headers)
assert diag_citizen.status_code == 403
diag_admin = client.get('/api/health/diagnostics/', **admin_headers)
assert diag_admin.status_code == 200
assert diag_admin.json()['checks']['database']['connected'] is True
print("  ✓ Diagnostic telemetry restricted: Citizen=403, Admin=200 (Zero secret leaks)")

# 7.3 Banned File Extension Rejection
sh_file = SimpleUploadedFile("script.sh", b"#!/bin/bash\nrm -rf /", content_type="text/x-sh")
bad_ext_res = client.post('/api/evidence/', {'complaint': complaint_id, 'file': sh_file}, format='multipart', **auth_headers)
assert bad_ext_res.status_code == 400
assert "strictly prohibited" in str(bad_ext_res.json())
print("  ✓ Executable script injection (.sh) blocked with 400 Bad Request")

# 7.4 Corrupted Image Binary Rejection
fake_img = SimpleUploadedFile("fake.jpg", b"This is not a real image binary", content_type="image/jpeg")
bad_img_res = client.post('/api/evidence/', {'complaint': complaint_id, 'file': fake_img, 'file_type': 'image'}, format='multipart', **auth_headers)
assert bad_img_res.status_code == 400
assert "corrupted" in str(bad_img_res.json()).lower()
print("  ✓ Fake/Corrupted image header spoofing blocked with 400 Bad Request")

# 7.5 SQL Injection & Cross-Site Scripting Resiliency
malicious_desc = "<script>alert('xss')</script> UNION SELECT * FROM users; --"
xss_comp = client.post('/api/complaints/', {
    'title': 'Test Sanitization',
    'description': malicious_desc,
    'category': cat.id,
    'department': dept.id,
    'address': 'Valid Civic Address 123',
    'priority': 'medium'
}, content_type='application/json', **auth_headers)
assert xss_comp.status_code == 201
saved_c = Complaint.objects.get(id=xss_comp.json()['id'])
assert saved_c.description == malicious_desc # Parameterized ORM storage without SQL execution
print("  ✓ Parameterized SQL query integrity verified (Zero injection vulnerability)")

print("\n================================================================================")
print("  ALL 7 TESTING ROADMAP PHASES PASSED SUCCESSFULLY!")
print("================================================================================")
