from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import (
    User, Department, ComplaintCategory, Complaint,
    ComplaintEvidence, ComplaintTimeline, Notification,
    CitizenFeedback, Subscription
)

# Customize Admin Site Branding
admin.site.site_header = "JanSahayak Administration Portal"
admin.site.site_title = "JanSahayak Admin"
admin.site.index_title = "Municipal Grievance & Systems Management"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_active', 'is_staff', 'created_at')
    list_filter = ('role', 'is_active', 'is_staff', 'preferred_language')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'phone_number', 'organization_name')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at', 'last_login', 'date_joined')

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'email', 'phone_number', 'avatar')}),
        ('Role & Affiliation', {'fields': ('role', 'preferred_language', 'organization_name', 'address')}),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',)
        }),
        ('Audit Timestamps', {'fields': ('created_at', 'updated_at', 'last_login', 'date_joined')}),
    )


class ComplaintEvidenceInline(admin.TabularInline):
    model = ComplaintEvidence
    extra = 0
    readonly_fields = ('file_type', 'is_resolution_proof', 'uploaded_by', 'created_at', 'preview')
    fields = ('file', 'preview', 'file_type', 'is_resolution_proof', 'ai_analysis_description', 'uploaded_by', 'created_at')

    def preview(self, obj):
        if obj.file and obj.file_type == 'image':
            return format_html('<img src="{}" style="height: 48px; border-radius: 6px;" />', obj.file.url)
        return "-"
    preview.short_description = "Thumbnail"


class ComplaintTimelineInline(admin.TabularInline):
    model = ComplaintTimeline
    extra = 0
    readonly_fields = ('performed_by', 'action', 'details', 'from_status', 'to_status', 'created_at')
    can_delete = False


class CitizenFeedbackInline(admin.StackedInline):
    model = CitizenFeedback
    extra = 0
    readonly_fields = ('rating', 'feedback_text', 'resolution_satisfaction', 'created_at')
    can_delete = False


@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = ('tracking_id', 'title', 'category', 'department', 'status_badge', 'priority', 'citizen', 'assigned_staff', 'ai_duplicate_suspect', 'created_at')
    list_filter = ('status', 'priority', 'department', 'category', 'ai_duplicate_suspect', 'detected_language', 'created_at')
    search_fields = ('tracking_id', 'title', 'description', 'address', 'ward_or_zone', 'citizen__username', 'assigned_staff__username')
    readonly_fields = ('tracking_id', 'created_at', 'updated_at', 'ai_generated_summary', 'ai_confidence_score', 'ai_duplicate_suspect', 'duplicate_of', 'detected_language', 'original_input_mode')
    ordering = ('-created_at',)
    inlines = [ComplaintEvidenceInline, ComplaintTimelineInline, CitizenFeedbackInline]

    fieldsets = (
        ('Ticket Information', {
            'fields': ('tracking_id', 'title', 'description', 'status', 'priority')
        }),
        ('Categorization & Assignment', {
            'fields': ('category', 'department', 'assigned_staff', 'assigned_at')
        }),
        ('Location Details', {
            'fields': ('address', 'landmark', 'ward_or_zone', 'duration_of_issue', 'latitude', 'longitude')
        }),
        ('AI Analysis Metadata', {
            'classes': ('collapse',),
            'fields': ('detected_language', 'original_input_mode', 'ai_generated_summary', 'ai_confidence_score', 'ai_duplicate_suspect', 'duplicate_of')
        }),
        ('Resolution & SLA', {
            'fields': ('resolution_notes', 'resolution_date', 'sla_target_date', 'is_escalated', 'escalation_reason')
        }),
        ('Audit Timestamps', {
            'fields': ('citizen', 'created_at', 'updated_at')
        }),
    )

    def status_badge(self, obj):
        colors = {
            'submitted': '#3B82F6',
            'assigned': '#8B5CF6',
            'in_progress': '#D97706',
            'resolved': '#10B981',
            'verified': '#059669',
            'escalated': '#EF4444',
            'rejected': '#6B7280',
        }
        color = colors.get(obj.status, '#6B7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 9999px; font-size: 11px; font-weight: bold; text-transform: uppercase;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = "Status"


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'sla_hours', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'code', 'description')
    ordering = ('name',)


@admin.register(ComplaintCategory)
class ComplaintCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'department', 'priority_default', 'is_active')
    list_filter = ('department', 'priority_default', 'is_active')
    search_fields = ('name', 'slug', 'description')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(ComplaintEvidence)
class ComplaintEvidenceAdmin(admin.ModelAdmin):
    list_display = ('id', 'complaint_link', 'file_type', 'is_duplicate', 'duplicate_type', 'similarity_score', 'review_required', 'uploaded_by', 'created_at')
    list_filter = ('file_type', 'is_duplicate', 'duplicate_type', 'review_required', 'is_resolution_proof', 'created_at')
    search_fields = ('complaint__tracking_id', 'uploaded_by__username', 'ai_analysis_description', 'sha256_hash')
    readonly_fields = ('sha256_hash', 'phash', 'is_duplicate', 'duplicate_type', 'similarity_score', 'matched_evidence', 'created_at')

    def complaint_link(self, obj):
        return f"{obj.complaint.tracking_id} - {obj.complaint.title[:30]}"
    complaint_link.short_description = "Complaint"


@admin.register(ComplaintTimeline)
class ComplaintTimelineAdmin(admin.ModelAdmin):
    list_display = ('complaint', 'action', 'from_status', 'to_status', 'performed_by', 'created_at')
    list_filter = ('from_status', 'to_status', 'created_at')
    search_fields = ('complaint__tracking_id', 'action', 'details', 'performed_by__username')
    readonly_fields = ('complaint', 'performed_by', 'action', 'details', 'from_status', 'to_status', 'created_at')

    def has_add_permission(self, request):
        return False  # Timelines are strictly audit trails created via app actions

    def has_change_permission(self, request, obj=None):
        return False  # Timelines cannot be tampered with


@admin.register(CitizenFeedback)
class CitizenFeedbackAdmin(admin.ModelAdmin):
    list_display = ('complaint', 'rating_stars', 'resolution_satisfaction', 'created_at')
    list_filter = ('rating', 'resolution_satisfaction', 'created_at')
    search_fields = ('complaint__tracking_id', 'feedback_text')
    readonly_fields = ('complaint', 'rating', 'feedback_text', 'resolution_satisfaction', 'created_at')

    def rating_stars(self, obj):
        return "★" * obj.rating + "☆" * (5 - obj.rating)
    rating_stars.short_description = "Rating"


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'complaint', 'is_read', 'notification_type', 'created_at')
    list_filter = ('is_read', 'notification_type', 'created_at')
    search_fields = ('user__username', 'title', 'message', 'complaint__tracking_id')
    readonly_fields = ('created_at',)


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'tier', 'is_active', 'max_complaints_monthly', 'start_date', 'end_date')
    list_filter = ('tier', 'is_active')
    search_fields = ('user__username', 'user__email')
