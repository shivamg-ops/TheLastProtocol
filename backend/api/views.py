from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Count, Q
from .models import (
    User, Department, ComplaintCategory, Complaint,
    ComplaintEvidence, ComplaintTimeline, Notification, CitizenFeedback, Subscription,
    UserRole, ComplaintStatus
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

class UserProfileView(viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        if self.action == 'staff_list':
            return [permissions.IsAdminUser()]
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

        # Log timeline
        ComplaintTimeline.objects.create(
            complaint=complaint,
            performed_by=user,
            action="Complaint Filed",
            details="Complaint submitted by citizen.",
            to_status=complaint.status
        )

        # Notification to citizen
        Notification.objects.create(
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

        # Citizen notification
        Notification.objects.create(
            user=complaint.citizen,
            title=f"Complaint Update: {complaint.tracking_id}",
            message=f"Status has been updated to '{complaint.get_status_display()}'. Notes: {notes}",
            complaint=complaint
        )

        return Response(ComplaintSerializer(complaint).data)

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

            # Notify Staff
            Notification.objects.create(
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
        complaint = self.get_object()

        # Only the citizen who reported the complaint can submit feedback
        if complaint.citizen != request.user and request.user.role != UserRole.ADMIN:
            return Response({"error": "Forbidden: Only the reporting citizen can submit feedback for this complaint."}, status=status.HTTP_403_FORBIDDEN)

        if complaint.status != ComplaintStatus.RESOLVED and complaint.status != ComplaintStatus.VERIFIED:
            return Response({"error": "Feedback can only be submitted for resolved complaints."}, status=status.HTTP_400_BAD_REQUEST)

        rating = request.data.get('rating')
        feedback_text = request.data.get('feedback_text', '')
        satisfaction = request.data.get('resolution_satisfaction', True)

        if not rating or not str(rating).isdigit() or int(rating) < 1 or int(rating) > 5:
            return Response({"error": "A rating between 1 and 5 is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Check if feedback already exists (prevent duplicate submissions)
        feedback, created = CitizenFeedback.objects.get_or_create(
            complaint=complaint,
            defaults={
                'rating': int(rating),
                'feedback_text': feedback_text,
                'resolution_satisfaction': bool(satisfaction)
            }
        )

        if not created:
            return Response({"error": "Feedback has already been submitted for this complaint."}, status=status.HTTP_400_BAD_REQUEST)

        # Mark complaint status as verified by citizen
        complaint.status = ComplaintStatus.VERIFIED
        complaint.save(update_fields=['status'])

        # Audit timeline
        ComplaintTimeline.objects.create(
            complaint=complaint,
            performed_by=request.user,
            action="Resolution Verified & Feedback Submitted",
            details=f"Citizen rated resolution {rating}/5 stars. Notes: {feedback_text}",
            from_status=ComplaintStatus.RESOLVED,
            to_status=ComplaintStatus.VERIFIED
        )

        return Response(CitizenFeedbackSerializer(feedback).data, status=status.HTTP_201_CREATED)

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
        # Auto-run AI image description and duplicate detection if it is an image
        if evidence.file_type == 'image' and evidence.file:
            # 1. Duplicate Image Analysis (exact SHA-256 and perceptual pHash)
            dup_res = detect_duplicate_evidence(
                image_file_path=evidence.file.path,
                current_evidence_id=evidence.id,
                current_complaint_id=evidence.complaint_id if evidence.complaint else None
            )
            evidence.sha256_hash = dup_res.get("sha256_hash")
            evidence.phash = dup_res.get("phash")
            evidence.is_duplicate = dup_res.get("is_duplicate", False)
            evidence.duplicate_type = dup_res.get("duplicate_type", "none")
            evidence.similarity_score = dup_res.get("similarity_score", 0.0)
            evidence.review_required = dup_res.get("review_required", False)
            
            matched_id = dup_res.get("matched_evidence_id")
            if matched_id:
                try:
                    evidence.matched_evidence = ComplaintEvidence.objects.get(id=matched_id)
                    # Flag parent complaint for staff awareness without rejecting it
                    if evidence.complaint:
                        evidence.complaint.ai_duplicate_suspect = True
                        evidence.complaint.save(update_fields=['ai_duplicate_suspect'])
                except ComplaintEvidence.DoesNotExist:
                    pass

            # 2. Visual Quality & Multimodal Verification
            complaint_text = evidence.complaint.description if evidence.complaint else ""
            complaint_category = evidence.complaint.category.name if (evidence.complaint and evidence.complaint.category) else ""
            res = analyze_image_evidence(
                image_file_path=evidence.file.path,
                complaint_text=complaint_text,
                complaint_category=complaint_category
            )
            analysis_text = res.get('analysis', '')
            if evidence.is_duplicate:
                analysis_text += f" [Duplicate Notice: {dup_res['summary']}]"
            evidence.ai_analysis_description = analysis_text

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

class AnalyticsViewSet(viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'])
    def summary(self, request):
        total = Complaint.objects.count()
        resolved = Complaint.objects.filter(status=ComplaintStatus.RESOLVED).count()
        in_progress = Complaint.objects.filter(status=ComplaintStatus.IN_PROGRESS).count()
        pending = Complaint.objects.filter(status__in=[ComplaintStatus.SUBMITTED, ComplaintStatus.ACKNOWLEDGED, ComplaintStatus.ASSIGNED]).count()

        category_distribution = Complaint.objects.values('category__name').annotate(count=Count('id'))
        status_distribution = Complaint.objects.values('status').annotate(count=Count('id'))

        return Response({
            "total_complaints": total,
            "resolved_complaints": resolved,
            "in_progress_complaints": in_progress,
            "pending_complaints": pending,
            "resolution_rate": round((resolved / total * 100), 1) if total > 0 else 0,
            "category_breakdown": category_distribution,
            "status_breakdown": status_distribution
        })
