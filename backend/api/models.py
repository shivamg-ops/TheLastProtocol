import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from .validators import validate_evidence_file

class UserRole(models.TextChoices):
    CITIZEN = 'citizen', 'Individual Citizen'
    NGO = 'ngo', 'NGO'
    SMALL_SOCIETY = 'small_society', 'Small Society'
    LARGE_SOCIETY = 'large_society', 'Large Society'
    ADMIN = 'admin', 'Administrator'
    STAFF = 'staff', 'Staff Member'

class SubscriptionTier(models.TextChoices):
    FREE = 'free', 'Free Citizen Tier'
    STANDARD = 'standard', 'Standard Community Tier'
    PRO = 'pro', 'Pro Society/Enterprise Tier'

class User(AbstractUser):
    role = models.CharField(max_length=20, choices=UserRole.choices, default=UserRole.CITIZEN)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    preferred_language = models.CharField(max_length=10, default='en') # en, hi, mr, hinglish
    organization_name = models.CharField(max_length=200, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

class Department(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, default='Building')
    sla_hours = models.PositiveIntegerField(default=48)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class ComplaintCategory(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='categories')
    description = models.TextField(blank=True)
    priority_default = models.CharField(max_length=10, choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('urgent', 'Urgent')], default='medium')
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class ComplaintStatus(models.TextChoices):
    DRAFT = 'draft', 'Draft'
    SUBMITTED = 'submitted', 'Submitted'
    ACKNOWLEDGED = 'acknowledged', 'Acknowledged'
    ASSIGNED = 'assigned', 'Assigned to Staff'
    IN_PROGRESS = 'in_progress', 'In Progress'
    RESOLVED = 'resolved', 'Resolved'
    VERIFIED = 'verified', 'Verified by Citizen'
    REJECTED = 'rejected', 'Rejected'
    ESCALATED = 'escalated', 'Escalated'

class PriorityLevel(models.TextChoices):
    LOW = 'low', 'Low'
    MEDIUM = 'medium', 'Medium'
    HIGH = 'high', 'High'
    URGENT = 'urgent', 'Urgent'

class Complaint(models.Model):
    tracking_id = models.CharField(max_length=20, unique=True, editable=False)
    citizen = models.ForeignKey(User, on_delete=models.CASCADE, related_name='complaints')
    title = models.CharField(max_length=255)
    description = models.TextField()
    category = models.ForeignKey(ComplaintCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='complaints')
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='complaints')
    status = models.CharField(max_length=20, choices=ComplaintStatus.choices, default=ComplaintStatus.SUBMITTED)
    priority = models.CharField(max_length=10, choices=PriorityLevel.choices, default=PriorityLevel.MEDIUM)
    
    # Location details
    address = models.TextField()
    landmark = models.CharField(max_length=255, blank=True, null=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    ward_or_zone = models.CharField(max_length=100, blank=True, null=True)
    duration_of_issue = models.CharField(max_length=100, blank=True, null=True)

    # Assignment
    assigned_staff = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_complaints')
    assigned_at = models.DateTimeField(null=True, blank=True)

    # AI Metadata
    ai_generated_summary = models.TextField(blank=True, null=True)
    ai_confidence_score = models.FloatField(default=0.0)
    ai_duplicate_suspect = models.BooleanField(default=False)
    duplicate_of = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='duplicates')
    detected_language = models.CharField(max_length=20, default='en')
    original_input_mode = models.CharField(max_length=20, default='text') # text, voice, media, chat

    # Resolution & SLA
    resolution_notes = models.TextField(blank=True, null=True)
    resolution_date = models.DateTimeField(null=True, blank=True)
    sla_target_date = models.DateTimeField(null=True, blank=True)
    is_escalated = models.BooleanField(default=False)
    escalation_reason = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.tracking_id:
            self.tracking_id = f"JSH-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.tracking_id} - {self.title}"

class ComplaintEvidence(models.Model):
    complaint = models.ForeignKey(Complaint, on_delete=models.CASCADE, related_name='evidences')
    file = models.FileField(upload_to='complaint_evidence/', validators=[validate_evidence_file])
    file_type = models.CharField(max_length=20, choices=[('image', 'Image'), ('video', 'Video'), ('audio', 'Audio'), ('document', 'Document')])
    ai_analysis_description = models.TextField(blank=True, null=True)
    is_resolution_proof = models.BooleanField(default=False)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    # Task 5: Duplicate Image Detection Hashes & Metadata
    sha256_hash = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    phash = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    is_duplicate = models.BooleanField(default=False)
    duplicate_type = models.CharField(max_length=20, blank=True, null=True)  # 'exact', 'perceptual', 'none'
    similarity_score = models.FloatField(default=0.0)
    matched_evidence = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='duplicate_instances')
    review_required = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

class ComplaintTimeline(models.Model):
    complaint = models.ForeignKey(Complaint, on_delete=models.CASCADE, related_name='timeline')
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=100)
    details = models.TextField(blank=True)
    from_status = models.CharField(max_length=20, blank=True, null=True)
    to_status = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    complaint = models.ForeignKey(Complaint, on_delete=models.CASCADE, null=True, blank=True)
    is_read = models.BooleanField(default=False)
    notification_type = models.CharField(max_length=50, default='status_update')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

class CitizenFeedback(models.Model):
    complaint = models.OneToOneField(Complaint, on_delete=models.CASCADE, related_name='feedback')
    rating = models.PositiveSmallIntegerField(choices=[(1, '1'), (2, '2'), (3, '3'), (4, '4'), (5, '5')])
    feedback_text = models.TextField(blank=True)
    resolution_satisfaction = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Subscription(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='subscription')
    tier = models.CharField(max_length=20, choices=SubscriptionTier.choices, default=SubscriptionTier.FREE)
    is_active = models.BooleanField(default=True)
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField(null=True, blank=True)
    max_complaints_monthly = models.IntegerField(default=10)
    priority_support = models.BooleanField(default=False)
    analytics_access = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} - {self.get_tier_display()}"
