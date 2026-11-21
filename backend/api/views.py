import os
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils import timezone
from django.db.models import Count, Q
from .models import (
    User, Department, ComplaintCategory, Complaint,
    ComplaintEvidence, ComplaintTimeline, Notification, CitizenFeedback, Subscription,
    UserRole, ComplaintStatus, EmailOTP
)
from .serializers import (
    UserSerializer, RegisterSerializer, DepartmentSerializer,
    ComplaintCategorySerializer, ComplaintSerializer, ComplaintEvidenceSerializer,
    ComplaintTimelineSerializer, NotificationSerializer, CitizenFeedbackSerializer, SubscriptionSerializer
)
from .ai_service import (
    analyze_complaint_text,
    analyze_image_evidence,
    detect_duplicate_evidence,
    check_possible_duplicates
)
from .notifications import (
    notify_complaint_submitted, notify_department_assigned,
    notify_staff_assigned, notify_status_update, notify_escalation,
    send_notification_idempotent, notify_resolution_awaiting_confirmation,
    notify_resolution_confirmed, notify_resolution_disputed
)
from .email_service import send_otp_email, verify_otp_code, notify_user_via_email

class RegisterView(viewsets.GenericViewSet):
    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response({
            "message": "User registered successfully",
            "user": UserSerializer(user).data
        }, status=status.HTTP_201_CREATED)

class IsAdminOrStaff(permissions.BasePermission):
    """
    Permission check granting access to verified Admin or Staff users.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated and (
                request.user.role in [UserRole.ADMIN, UserRole.STAFF] or
                request.user.is_staff or
                request.user.is_superuser
            )
        )

class UserProfileView(viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        if self.action == 'staff_list':
            return [IsAdminOrStaff()]
        return [permissions.IsAuthenticated()]

    @action(detail=False, methods=['get'])
    def me(self, request):
        serializer = UserSerializer(request.user)
        sub = getattr(request.user, 'subscription', None)
        sub_data = SubscriptionSerializer(sub).data if sub else None
        return Response({
            "user": serializer.data,
            "subscription": sub_data
        })

    @action(detail=False, methods=['get'])
    def staff_list(self, request):
        staff_users = User.objects.filter(Q(role=UserRole.STAFF) | Q(is_staff=True)).exclude(role=UserRole.ADMIN)
        serializer = UserSerializer(staff_users, many=True)
        return Response(serializer.data)

class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

class ComplaintCategoryViewSet(viewsets.ModelViewSet):
    queryset = ComplaintCategory.objects.all()
    serializer_class = ComplaintCategorySerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

class ComplaintViewSet(viewsets.ModelViewSet):
    serializer_class = ComplaintSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.role == UserRole.ADMIN:
            return Complaint.objects.all().order_by('-created_at')
        elif user.role == UserRole.STAFF:
            return Complaint.objects.filter(assigned_staff=user).order_by('-created_at')
        else:
            return Complaint.objects.filter(citizen=user).order_by('-created_at')

    def perform_create(self, serializer):
        user = self.request.user
        category_id = self.request.data.get('category')
        dept = None
        if category_id:
            try:
                cat = ComplaintCategory.objects.get(id=category_id)
                dept = cat.department
            except ComplaintCategory.DoesNotExist:
                pass

        complaint = serializer.save(citizen=user, department=dept)

        # Set timezone-aware SLA target date from department SLA configuration
        from .sla_monitor import SLAMonitor
        sla_deadline = SLAMonitor.calculate_sla_deadline(complaint)
        if sla_deadline:
            complaint.sla_target_date = sla_deadline
            complaint.save(update_fields=['sla_target_date'])

        # Log timeline
        ComplaintTimeline.objects.create(
            complaint=complaint,
            performed_by=user,
            action="Complaint Filed",
            details="Complaint submitted by citizen.",
            to_status=complaint.status
        )

        # Notification to citizen (Safe and Idempotent - Task 13)
        notify_complaint_submitted(complaint)
        if complaint.department:
            notify_department_assigned(complaint)

        # In-app + SMTP Email notification
        notify_user_via_email(
            user=user,
            title="Complaint Registered Successfully",
            message=f"Your complaint ticket {complaint.tracking_id} has been logged.",
            complaint=complaint
        )

        # Check duplicate
        duplicates = check_possible_duplicates(complaint, Complaint.objects.all())
        if duplicates:
            complaint.ai_duplicate_suspect = True
            complaint.duplicate_of = duplicates[0]
            complaint.save(update_fields=['ai_duplicate_suspect', 'duplicate_of'])

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def update_status(self, request, pk=None):
        complaint = self.get_object()
        
        # BOLA Protection: Only admins or assigned staff can update complaint status
        if request.user.role != UserRole.ADMIN and complaint.assigned_staff != request.user:
            return Response(
                {"error": "Forbidden: Only municipal administrators or the assigned field staff member can update ticket status."},
                status=status.HTTP_403_FORBIDDEN
            )

        new_status = request.data.get('status')
        notes = request.data.get('notes', '')

        if not new_status:
            return Response({"error": "Status is required"}, status=400)

        old_status = complaint.status
        complaint.status = new_status
        if notes:
            complaint.resolution_notes = notes
        if new_status == ComplaintStatus.RESOLVED:
            complaint.resolution_date = timezone.now()
            # Task 17: Staff marking resolved triggers citizen confirmation awaiting state
            complaint.resolution_verification_status = 'pending_citizen_confirmation'
        complaint.save()

        # Record timeline
        ComplaintTimeline.objects.create(
            complaint=complaint,
            performed_by=request.user,
            action=f"Status changed to {complaint.get_status_display()}",
            details=notes,
            from_status=old_status,
            to_status=new_status
        )

        # Citizen notification (Safe and Idempotent - Task 13 & 17)
        notify_status_update(complaint, old_status, new_status, public_notes=notes)
        if new_status == ComplaintStatus.RESOLVED:
            notify_resolution_awaiting_confirmation(complaint)

        # In-app + SMTP Email notification
        notify_user_via_email(
            user=complaint.citizen,
            title=f"Complaint Update: {complaint.tracking_id}",
            message=f"Status has been updated to '{complaint.get_status_display()}'. Notes: {notes}",
            complaint=complaint
        )

        return Response(ComplaintSerializer(complaint).data)

    @action(detail=True, methods=['get'], permission_classes=[permissions.IsAdminUser])
    def recommend_staff(self, request, pk=None):
        """
        Task 18: Smart Field Staff Recommendation
        - Recommends optimal staff using department match, verified skills, active workload,
          and geographic proximity.
        - Human-in-the-loop guarantee: This endpoint NEVER automatically commits staff assignment.
        - Admin approval required.
        """
        complaint = self.get_object()
        from .staff_assignment import StaffAssignmentService
        recommendation = StaffAssignmentService.recommend_staff_for_complaint(complaint)
        return Response(recommendation)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def assign_staff(self, request, pk=None):
        complaint = self.get_object()
        staff_id = request.data.get('staff_id')
        try:
            staff_user = User.objects.get(id=staff_id)
            if staff_user.role != UserRole.STAFF and not staff_user.is_staff:
                return Response({"error": "Selected user is not a field staff member."}, status=status.HTTP_400_BAD_REQUEST)

            complaint.assigned_staff = staff_user
            complaint.assigned_at = timezone.now()
            complaint.status = ComplaintStatus.ASSIGNED
            complaint.save()

            ComplaintTimeline.objects.create(
                complaint=complaint,
                performed_by=request.user,
                action=f"Assigned to {staff_user.username}",
                details="Staff member assigned for resolution."
            )

            # Notify Staff & Citizen (Safe and Idempotent - Task 13)
            notify_staff_assigned(complaint, staff_user)

            # Notify Staff (in-app + SMTP Email)
            notify_user_via_email(
                user=staff_user,
                title="New Task Assigned",
                message=f"You have been assigned to handle complaint {complaint.tracking_id}.",
                complaint=complaint
            )

            return Response(ComplaintSerializer(complaint).data)
        except User.DoesNotExist:
            return Response({"error": "Staff user not found"}, status=404)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def submit_feedback(self, request, pk=None):
        """
        Task 17: Citizen Trust, Feedback & Resolution Verification
        - Allows the reporting citizen to confirm or dispute resolution.
        - Records satisfaction rating (1-5), optional comments, and dispute reasons.
        - Automatically marks complaint status as VERIFIED upon confirmation.
        - Flags resolution_verification_status as 'citizen_confirmed' or 'citizen_disputed'.
        - Prevents duplicate feedback submissions.
        """
        # Look up complaint across all complaints to ensure proper 403 authorization check
        try:
            complaint = Complaint.objects.get(pk=pk)
        except Complaint.DoesNotExist:
            return Response({"error": "Complaint not found."}, status=status.HTTP_404_NOT_FOUND)

        # Only the citizen who reported the complaint can submit feedback (or admin)
        if complaint.citizen != request.user and request.user.role != UserRole.ADMIN:
            return Response(
                {"error": "Forbidden: Only the reporting citizen can confirm, dispute or rate resolution."},
                status=status.HTTP_403_FORBIDDEN
            )

        if complaint.status != ComplaintStatus.RESOLVED and complaint.status != ComplaintStatus.VERIFIED:
            return Response(
                {"error": "Resolution feedback can only be submitted for complaints marked as resolved."},
                status=status.HTTP_400_BAD_REQUEST
            )

        rating = request.data.get('rating')
        feedback_text = request.data.get('feedback_text', '')
        satisfaction_raw = request.data.get('resolution_satisfaction', True)
        is_disputed_raw = request.data.get('is_disputed', False)
        dispute_reason = request.data.get('dispute_reason', '')

        # Safe boolean parsing handling both JSON and form-urlencoded strings
        is_disputed = is_disputed_raw is True or str(is_disputed_raw).lower() in ['true', '1']
        satisfaction = (satisfaction_raw is True or str(satisfaction_raw).lower() in ['true', '1']) and not is_disputed

        if not rating or not str(rating).isdigit() or int(rating) < 1 or int(rating) > 5:
            return Response({"error": "A rating between 1 and 5 is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Check if feedback already exists (prevent duplicate submissions)
        feedback, created = CitizenFeedback.objects.get_or_create(
            complaint=complaint,
            defaults={
                'rating': int(rating),
                'feedback_text': feedback_text.strip(),
                'resolution_satisfaction': bool(satisfaction) and not bool(is_disputed),
                'is_disputed': bool(is_disputed),
                'dispute_reason': dispute_reason.strip() if is_disputed else ""
            }
        )

        if not created:
            return Response({"error": "Feedback has already been submitted for this complaint."}, status=status.HTTP_400_BAD_REQUEST)

        if is_disputed:
            complaint.resolution_verification_status = 'citizen_disputed'
            # Disputed complaint timeline
            ComplaintTimeline.objects.create(
                complaint=complaint,
                performed_by=request.user,
                action="Resolution Disputed by Citizen",
                details=f"Citizen disputed resolution with rating {rating}/5. Reason: {dispute_reason or feedback_text}",
                from_status=complaint.status,
                to_status=complaint.status
            )
            complaint.save(update_fields=['resolution_verification_status'])
            # Notify citizen and assigned staff / admin review
            notify_resolution_disputed(complaint, reason=dispute_reason)
        else:
            complaint.status = ComplaintStatus.VERIFIED
            complaint.resolution_verification_status = 'citizen_confirmed'
            complaint.save(update_fields=['status', 'resolution_verification_status'])
            # Confirmed complaint timeline
            ComplaintTimeline.objects.create(
                complaint=complaint,
                performed_by=request.user,
                action="Resolution Confirmed & Feedback Submitted",
                details=f"Citizen confirmed resolution and rated {rating}/5 stars. Notes: {feedback_text}",
                from_status=ComplaintStatus.RESOLVED,
                to_status=ComplaintStatus.VERIFIED
            )
            notify_resolution_confirmed(complaint)

        return Response(CitizenFeedbackSerializer(feedback).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def admin_review_dispute(self, request, pk=None):
        """
        Task 17: Administrative review of a disputed complaint resolution.
        Admin can choose to:
        - Reopen ticket for staff work (sets status back to IN_PROGRESS)
        - Uphold resolution with supervisor confirmation (sets status to VERIFIED)
        """
        complaint = self.get_object()
        action_decision = request.data.get('decision')  # 'reopen' | 'uphold'
        review_notes = request.data.get('notes', '')

        if action_decision not in ['reopen', 'uphold']:
            return Response({"error": "Decision must be 'reopen' or 'uphold'."}, status=status.HTTP_400_BAD_REQUEST)

        old_status = complaint.status
        if action_decision == 'reopen':
            complaint.status = ComplaintStatus.IN_PROGRESS
            complaint.resolution_verification_status = 'admin_review_required'
            complaint.save(update_fields=['status', 'resolution_verification_status'])
            ComplaintTimeline.objects.create(
                complaint=complaint,
                performed_by=request.user,
                action="Admin Reopened Disputed Grievance",
                details=f"Administrator review reopened ticket for further field work. Notes: {review_notes}",
                from_status=old_status,
                to_status=ComplaintStatus.IN_PROGRESS
            )
            notify_status_update(complaint, old_status, ComplaintStatus.IN_PROGRESS, public_notes=review_notes)
        else:
            complaint.status = ComplaintStatus.VERIFIED
            complaint.resolution_verification_status = 'citizen_confirmed'
            complaint.save(update_fields=['status', 'resolution_verification_status'])
            ComplaintTimeline.objects.create(
                complaint=complaint,
                performed_by=request.user,
                action="Admin Verified & Closed Resolution",
                details=f"Supervisor reviewed and confirmed resolution. Notes: {review_notes}",
                from_status=old_status,
                to_status=ComplaintStatus.VERIFIED
            )
            notify_status_update(complaint, old_status, ComplaintStatus.VERIFIED, public_notes=review_notes)

        return Response(ComplaintSerializer(complaint).data)

class AIAnalysisView(viewsets.GenericViewSet):
    permission_classes = [permissions.AllowAny]

    @action(detail=False, methods=['post'])
    def process_text(self, request):
        text = request.data.get('text', '')
        history = request.data.get('history', [])
        if not text:
            return Response({"error": "Text is required"}, status=400)
        
        result = analyze_complaint_text(text, conversation_history=history)
        # Attempt to map to backend Category and Department via DepartmentRouter
        cat_obj = ComplaintCategory.objects.filter(name__icontains=result.get('category')).first()
        from .department_router import DepartmentRouter
        routing_info = DepartmentRouter.route_complaint(
            category=cat_obj,
            description=text,
            priority=result.get('priority', 'medium')
        )

        dept_obj = None
        if routing_info.get("suggested_department"):
            dept_id = routing_info["suggested_department"]["id"]
            dept_obj = Department.objects.filter(id=dept_id).first()
        elif cat_obj:
            dept_obj = cat_obj.department

        result['matched_category_id'] = cat_obj.id if cat_obj else None
        result['matched_department_name'] = dept_obj.name if dept_obj else None
        result['routing_recommendation'] = routing_info

        return Response(result)

class EvidenceUploadView(viewsets.ModelViewSet):
    serializer_class = ComplaintEvidenceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.role == UserRole.ADMIN:
            return ComplaintEvidence.objects.all().order_by('-created_at')
        elif user.role == UserRole.STAFF:
            # Staff can see evidence for complaints assigned to them
            return ComplaintEvidence.objects.filter(
                Q(uploaded_by=user) | Q(complaint__assigned_staff=user)
            ).order_by('-created_at')
        else:
            # Citizen can only see evidence for their own complaints or uploaded by them
            return ComplaintEvidence.objects.filter(
                Q(uploaded_by=user) | Q(complaint__citizen=user)
            ).order_by('-created_at')

    def perform_create(self, serializer):
        evidence = serializer.save(uploaded_by=self.request.user)
        # Auto-run AI image description, duplicate detection and evidence trust verification
        if evidence.file_type == 'image' and evidence.file:
            from .evidence_verifier import EvidenceVerifier
            complaint_text = evidence.complaint.description if evidence.complaint else ""
            complaint_category = evidence.complaint.category.name if (evidence.complaint and evidence.complaint.category) else ""

            # Unified Multi-Signal Verification
            v_res = EvidenceVerifier.verify_evidence(
                image_file_path=evidence.file.path,
                complaint_text=complaint_text,
                complaint_category=complaint_category,
                current_evidence_id=evidence.id,
                current_complaint_id=evidence.complaint_id if evidence.complaint else None
            )

            dup_info = v_res.get("duplicate_result", {})
            evidence.is_duplicate = dup_info.get("is_duplicate", False)
            evidence.duplicate_type = dup_info.get("duplicate_type", "none")
            evidence.similarity_score = dup_info.get("similarity_score", 0.0)
            evidence.review_required = v_res.get("review_required", False)

            # Hashes from duplicate detector
            from .ai_service import compute_image_hashes
            hashes = compute_image_hashes(evidence.file.path)
            evidence.sha256_hash = hashes.get("sha256")
            evidence.phash = hashes.get("phash")

            matched_id = dup_info.get("matched_evidence_id")
            if matched_id:
                try:
                    evidence.matched_evidence = ComplaintEvidence.objects.get(id=matched_id)
                    if evidence.complaint:
                        evidence.complaint.ai_duplicate_suspect = True
                        evidence.complaint.save(update_fields=['ai_duplicate_suspect'])
                except ComplaintEvidence.DoesNotExist:
                    pass

            evidence.ai_analysis_description = f"{v_res['summary']} Details: {'; '.join(v_res['verification_reasons'][:2])}"
            if v_res.get("review_reasons"):
                evidence.ai_analysis_description += f" [Review Notes: {'; '.join(v_res['review_reasons'][:2])}]"

            evidence.save(update_fields=[
                'sha256_hash', 'phash', 'is_duplicate', 'duplicate_type',
                'similarity_score', 'review_required', 'matched_evidence',
                'ai_analysis_description'
            ])
        elif evidence.file_type == 'video' and evidence.file:
            # Task 6: Videos are NOT sent to Gemini image analysis
            evidence.ai_analysis_description = "[Video Evidence Attached] Queued for municipal staff playback and review."
            evidence.save(update_fields=['ai_analysis_description'])
        elif evidence.file:
            evidence.ai_analysis_description = f"[{evidence.get_file_type_display()} Attached] Standard evidence record."
            evidence.save(update_fields=['ai_analysis_description'])

class AuthOTPViewSet(viewsets.GenericViewSet):
    permission_classes = [permissions.AllowAny]

    @action(detail=False, methods=['post'])
    def send_otp(self, request):
        email = request.data.get('email', '').strip().lower()
        purpose = request.data.get('purpose', 'login')

        if not email:
            return Response({"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)

        # For login OTP or reset, verify that user exists
        if purpose in ['login', 'reset_password']:
            user_exists = User.objects.filter(email__iexact=email).exists()
            if not user_exists:
                return Response(
                    {"error": "No account found with this email address. Please sign up first."},
                    status=status.HTTP_404_NOT_FOUND
                )

        result = send_otp_email(email, purpose)
        if result.get("success"):
            return Response({"message": f"Verification code sent to {email}"}, status=status.HTTP_200_OK)
        else:
            return Response({"error": result.get("error", "Failed to send OTP")}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def verify_login_otp(self, request):
        email = request.data.get('email', '').strip().lower()
        otp = request.data.get('otp', '').strip()

        if not email or not otp:
            return Response({"error": "Email and OTP are required"}, status=status.HTTP_400_BAD_REQUEST)

        if not verify_otp_code(email, otp, purpose='login'):
            return Response({"error": "Invalid or expired OTP. Please check your code or request a new one."}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.filter(email__iexact=email).first()
        if not user:
            return Response({"error": "User account not found"}, status=status.HTTP_404_NOT_FOUND)

        refresh = RefreshToken.for_user(user)
        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": UserSerializer(user).data
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    def verify_signup_otp(self, request):
        email = request.data.get('email', '').strip().lower()
        otp = request.data.get('otp', '').strip()

        if not email or not otp:
            return Response({"error": "Email and OTP are required"}, status=status.HTTP_400_BAD_REQUEST)

        if not verify_otp_code(email, otp, purpose='signup'):
            return Response({"error": "Invalid or expired OTP code."}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"verified": True, "message": "Email verified successfully."}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    def reset_password_with_otp(self, request):
        email = request.data.get('email', '').strip().lower()
        otp = request.data.get('otp', '').strip()
        new_password = request.data.get('new_password', '')

        if not email or not otp or not new_password:
            return Response({"error": "Email, OTP, and new password are required"}, status=status.HTTP_400_BAD_REQUEST)

        if not verify_otp_code(email, otp, purpose='reset_password'):
            return Response({"error": "Invalid or expired OTP code."}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.filter(email__iexact=email).first()
        if not user:
            return Response({"error": "User account not found"}, status=status.HTTP_404_NOT_FOUND)

        user.set_password(new_password)
        user.save()
        return Response({"message": "Password reset successfully. You can now log in."}, status=status.HTTP_200_OK)

class AnalyticsViewSet(viewsets.GenericViewSet):
    """
    Task 14: Data-Driven Analytics & AI Insights for JanSahayak
    - Permission: Admin and Authorized Municipal Staff only
    - Filters: date_from, date_to, category, department, status
    - Metrics: total, pending, in_progress, resolved, overdue, SLA compliance %,
               average resolution time, category breakdown, department performance,
               volume trend
    - AI Insights: Optional explanatory insights via Gemini with deterministic fallback
    """
    permission_classes = [permissions.IsAuthenticated]

    def check_permissions(self, request):
        super().check_permissions(request)
        # BOLA / RBAC: Sensitive administrative municipal analytics only accessible to Admin & Staff
        if request.user.role not in [UserRole.ADMIN, UserRole.STAFF] and not request.user.is_staff:
            self.permission_denied(
                request,
                message="Forbidden: Municipal analytics dashboard requires administrative or staff clearance."
            )

    @action(detail=False, methods=['get'])
    def summary(self, request):
        from .analytics_insights import (
            calculate_analytics_metrics,
            generate_ai_insights,
            parse_iso_datetime
        )

        # Parse query filters
        date_from_str = request.query_params.get('date_from')
        date_to_str = request.query_params.get('date_to')
        category_id_str = request.query_params.get('category')
        department_id_str = request.query_params.get('department')
        status_str = request.query_params.get('status')
        include_ai = request.query_params.get('include_ai', 'true').lower() in ['true', '1']

        date_from = parse_iso_datetime(date_from_str)
        date_to = parse_iso_datetime(date_to_str)
        category_id = int(category_id_str) if category_id_str and category_id_str.isdigit() else None
        department_id = int(department_id_str) if department_id_str and department_id_str.isdigit() else None
        status_filter = status_str.strip().lower() if status_str and status_str.strip() else None

        # Calculate database metrics
        metrics = calculate_analytics_metrics(
            date_from=date_from,
            date_to=date_to,
            category_id=category_id,
            department_id=department_id,
            status_filter=status_filter
        )

        # Optional AI/Deterministic Insights
        insights_data = generate_ai_insights(metrics) if include_ai else None

        # Flatten response maintaining backward-compatibility with older frontend keys
        summary = metrics["summary"]
        response_data = {
            # Backward-compatible summary fields
            "total_complaints": summary["total_complaints"],
            "pending_complaints": summary["pending_complaints"],
            "in_progress_complaints": summary["in_progress_complaints"],
            "resolved_complaints": summary["resolved_complaints"],
            "overdue_complaints_count": summary["overdue_complaints"],
            "approaching_deadline_count": summary["approaching_sla_complaints"],
            "resolution_rate": summary["resolution_rate"],
            "category_breakdown": metrics["category_breakdown"],
            "status_breakdown": metrics["status_breakdown"],
            # Extended Task 14 & 17 metrics
            "sla_compliance_rate": summary["sla_compliance_rate"],
            "avg_resolution_hours": summary["avg_resolution_hours"],
            "escalated_complaints_count": summary["escalated_complaints"],
            "pending_citizen_confirmation_count": summary.get("pending_citizen_confirmation_count", 0),
            "citizen_confirmed_count": summary.get("citizen_confirmed_count", 0),
            "citizen_disputed_count": summary.get("citizen_disputed_count", 0),
            "admin_review_count": summary.get("admin_review_count", 0),
            "avg_citizen_satisfaction": summary.get("avg_citizen_satisfaction", 0.0),
            "total_feedback_count": summary.get("total_feedback_count", 0),
            "department_performance": metrics["department_performance"],
            "volume_trend": metrics["volume_trend"],
            "filters_applied": metrics["filters_applied"],
            "ai_insights": insights_data
        }

        return Response(response_data)

    @action(detail=False, methods=['get'])
    def location_intelligence(self, request):
        """
        Task 15: Smart Location Intelligence & Hotspot Mapping Endpoint
        - Access: Admin & Staff only (enforced by check_permissions)
        - Uses actual GPS coordinates only (-90 <= lat <= 90, -180 <= lng <= 180)
        - Groups nearby complaints into explainable cluster hotspots
        - Excludes citizen PII
        - Supports filters: date_from, date_to, category, department, status, radius_km
        """
        from .location_intelligence import calculate_location_intelligence
        from .analytics_insights import parse_iso_datetime

        date_from_str = request.query_params.get('date_from')
        date_to_str = request.query_params.get('date_to')
        category_id_str = request.query_params.get('category')
        department_id_str = request.query_params.get('department')
        status_str = request.query_params.get('status')
        radius_str = request.query_params.get('radius_km', '0.5')

        date_from = parse_iso_datetime(date_from_str)
        date_to = parse_iso_datetime(date_to_str)
        category_id = int(category_id_str) if category_id_str and category_id_str.isdigit() else None
        department_id = int(department_id_str) if department_id_str and department_id_str.isdigit() else None
        status_filter = status_str.strip().lower() if status_str and status_str.strip() else None

        try:
            radius_km = float(radius_str)
            if radius_km <= 0 or radius_km > 50:
                radius_km = 0.5
        except (ValueError, TypeError):
            radius_km = 0.5

        data = calculate_location_intelligence(
            date_from=date_from,
            date_to=date_to,
            category_id=category_id,
            department_id=department_id,
            status_filter=status_filter,
            hotspot_radius_km=radius_km
        )
        return Response(data)

    def _get_filtered_predictive_qs(self, request):
        from .analytics_insights import parse_iso_datetime
        date_from_str = request.query_params.get('date_from')
        date_to_str = request.query_params.get('date_to')
        category_id_str = request.query_params.get('category')
        department_id_str = request.query_params.get('department')

        date_from = parse_iso_datetime(date_from_str)
        date_to = parse_iso_datetime(date_to_str)
        category_id = int(category_id_str) if category_id_str and category_id_str.isdigit() else None
        department_id = int(department_id_str) if department_id_str and department_id_str.isdigit() else None

        qs = Complaint.objects.all()
        if date_from:
            qs = qs.filter(created_at__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__lte=date_to)
        if category_id:
            qs = qs.filter(category_id=category_id)
        if department_id:
            qs = qs.filter(department_id=department_id)
        return qs, date_from, date_to

    @action(detail=False, methods=['get'])
    def predictive_trends(self, request):
        """Task 20: Historical Daily, Weekly & Monthly Complaint Trends & Recurring Problems"""
        from .predictive_intelligence import aggregate_historical_trends, detect_recurring_problems
        qs, date_from, date_to = self._get_filtered_predictive_qs(request)
        trends = aggregate_historical_trends(qs, date_from=date_from, date_to=date_to)
        recurring = detect_recurring_problems(qs)
        trends["recurring_problems"] = recurring
        return Response(trends)

    @action(detail=False, methods=['get'])
    def predictive_forecast(self, request):
        """Task 20: 7-Day Explainable Statistical Complaint Volume Forecast"""
        from .predictive_intelligence import calculate_complaint_volume_forecast
        qs, _, _ = self._get_filtered_predictive_qs(request)
        horizon_str = request.query_params.get('horizon_days', '7')
        try:
            horizon = int(horizon_str)
            if horizon <= 0 or horizon > 30:
                return Response(
                    {"error": "Forecast horizon must be between 1 and 30 days."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except (ValueError, TypeError):
            return Response(
                {"error": "Invalid horizon_days parameter. Must be an integer."},
                status=status.HTTP_400_BAD_REQUEST
            )

        forecast = calculate_complaint_volume_forecast(qs, forecast_horizon_days=horizon)
        return Response(forecast)

    @action(detail=False, methods=['get'])
    def predictive_hotspots(self, request):
        """Task 20: Civic Hotspot Risk Scoring (0 to 100)"""
        from .predictive_intelligence import calculate_hotspot_risk_scores
        qs, _, _ = self._get_filtered_predictive_qs(request)
        hotspots = calculate_hotspot_risk_scores(qs)
        return Response({"hotspot_risk_scores": hotspots, "count": len(hotspots)})

    @action(detail=False, methods=['get'])
    def predictive_recommendations(self, request):
        """Task 20: Grounded Preventive Action Recommendations"""
        from .predictive_intelligence import (
            calculate_hotspot_risk_scores,
            detect_recurring_problems,
            generate_preventive_recommendations
        )
        qs, _, _ = self._get_filtered_predictive_qs(request)
        hotspots = calculate_hotspot_risk_scores(qs)
        recurring = detect_recurring_problems(qs)
        recommendations = generate_preventive_recommendations(qs, hotspots=hotspots, recurring_problems=recurring)
        return Response({"recommendations": recommendations, "count": len(recommendations)})


class NotificationViewSet(viewsets.ModelViewSet):
    """
    Task 13: In-App Notification ViewSet
    - User-specific isolation (BOLA protected: users can ONLY access their own notifications)
    - Supports filtering by read status (?is_read=false)
    - Provides unread count endpoint
    - Provides mark_read and mark_all_read actions
    """
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'post', 'patch', 'delete']

    def get_queryset(self):
        user = self.request.user
        qs = Notification.objects.filter(user=user).select_related('complaint').order_by('-created_at')
        is_read_param = self.request.query_params.get('is_read')
        if is_read_param is not None:
            if is_read_param.lower() in ['true', '1']:
                qs = qs.filter(is_read=True)
            elif is_read_param.lower() in ['false', '0']:
                qs = qs.filter(is_read=False)
        return qs

    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        """Returns the total number of unread in-app notifications for the authenticated user."""
        count = Notification.objects.filter(user=request.user, is_read=False).count()
        return Response({"unread_count": count})

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Marks an individual notification as read."""
        notification = self.get_object()  # Automatically checks user ownership via get_queryset
        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=['is_read'])
        return Response(NotificationSerializer(notification).data)

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """Marks all unread notifications for the authenticated user as read."""
        updated = Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({"status": "success", "marked_read_count": updated})


class CivicAssistantViewSet(viewsets.GenericViewSet):
    """
    Task 19: Smart Civic Knowledge Assistant ViewSet
    - Endpoint: POST /api/assistant/chat/
    - Provides conversational answers to citizen queries on complaint status,
      filing help, municipal guidelines, SLA policies, and feedback/disputes.
    - Supports English, Hindi, and Hinglish.
    - Enforces BOLA: Personal complaint lookups verify user ownership.
    - Employs deterministic fallbacks if Gemini is offline or quota is exhausted.
    """
    permission_classes = [permissions.AllowAny]  # General civic guidance is public; personal complaint queries check authentication internally

    @action(detail=False, methods=['post'])
    def chat(self, request):
        message = request.data.get('message', '')
        if not message or not str(message).strip():
            return Response(
                {"error": "Message content cannot be empty."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if len(str(message)) > 2000:
            return Response(
                {"error": "Message exceeds maximum permitted character length (2000 characters)."},
                status=status.HTTP_400_BAD_REQUEST
            )

        complaint_id = request.data.get('complaint_id')
        language = request.data.get('language', 'auto')

        from .civic_assistant import CivicAssistantService
        user = request.user if request.user.is_authenticated else None

        result = CivicAssistantService.process_citizen_query(
            user=user,
            message=str(message).strip(),
            complaint_identifier=str(complaint_id).strip() if complaint_id else None,
            requested_language=language
        )
        return Response(result, status=status.HTTP_200_OK)


class HealthCheckView(viewsets.GenericViewSet):
    """
    Task 21: Production Health Check & Monitoring
    - /api/health/ : Lightweight public status check for load balancers & orchestrators.
    - /api/health/diagnostics/ : Deep system diagnostics (DB ping, storage access, AI status)
      strictly restricted to Admin/Staff to prevent reconnaissance.
    """
    permission_classes = [permissions.AllowAny]

    @action(detail=False, methods=['get'])
    def ping(self, request):
        return Response({
            "status": "healthy",
            "service": "JanSahayak Civic Platform",
            "timestamp": timezone.now().isoformat()
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def diagnostics(self, request):
        # Sensitive operational metrics are restricted to authenticated staff/admin
        if not request.user.is_authenticated or (request.user.role != UserRole.ADMIN and not request.user.is_staff):
            return Response(
                {"error": "Access denied. Diagnostic telemetry requires administrative credentials."},
                status=status.HTTP_403_FORBIDDEN
            )

        import time
        from django.db import connection

        # 1. Database Ping & Latency
        db_ok = False
        db_latency_ms = None
        try:
            t0 = time.perf_counter()
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                row = cursor.fetchone()
                if row and row[0] == 1:
                    db_ok = True
            db_latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        except Exception:
            db_ok = False

        # 2. Storage write/read check
        storage_ok = False
        try:
            from django.conf import settings
            test_path = os.path.join(settings.MEDIA_ROOT, '.health_check_tmp')
            os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
            with open(test_path, 'w') as f:
                f.write('health_check')
            if os.path.exists(test_path):
                os.remove(test_path)
                storage_ok = True
        except Exception:
            storage_ok = False

        # 3. AI Service status (safe check, no secrets exposed)
        gemini_configured = bool(os.environ.get('GEMINI_API_KEY', '').strip())

        overall_status = "healthy" if (db_ok and storage_ok) else "degraded"

        return Response({
            "status": overall_status,
            "checks": {
                "database": {
                    "connected": db_ok,
                    "latency_ms": db_latency_ms
                },
                "media_storage": {
                    "writable": storage_ok
                },
                "ai_service": {
                    "provider": "Google Gemini",
                    "configured": gemini_configured,
                    "mode": "hybrid-fallback" if gemini_configured else "rule-engine"
                }
            },
            "timestamp": timezone.now().isoformat()
        }, status=status.HTTP_200_OK if overall_status == "healthy" else status.HTTP_503_SERVICE_UNAVAILABLE)

