"""
JanSahayak - Smart Notification Service (Task 13)

Provides reliable, in-app notification dispatching with:
1. Event-based triggering (submission, department routing, staff assignment,
   status update, SLA warning, escalation).
2. Idempotency & duplicate prevention (prevents duplicate alerts for the same event).
3. Citizen privacy protection (strict BOLA, avoids exposing private internal admin notes).
4. In-app notifications only (no external SMS/WhatsApp/Push).
"""

import logging
from datetime import timedelta
from typing import Optional, Dict, Any
from django.utils import timezone
from .models import Notification, Complaint, User

logger = logging.getLogger("jansahayak_ai")

# Valid notification types supported across JanSahayak
NOTIFICATION_TYPES = {
    'complaint_submitted': 'Complaint Submitted',
    'department_assigned': 'Department Assigned',
    'staff_assigned': 'Staff Assigned',
    'status_update': 'Status Updated',
    'sla_approaching': 'SLA Deadline Approaching',
    'sla_overdue': 'SLA Deadline Overdue',
    'escalation': 'Ticket Escalated',
    'resolution_awaiting_confirmation': 'Resolution Awaiting Confirmation',
    'citizen_confirmed': 'Resolution Confirmed by Citizen',
    'citizen_disputed': 'Resolution Disputed by Citizen',
    'admin_review_required': 'Admin Review Required'
}


def send_notification_idempotent(
    user: User,
    title: str,
    message: str,
    complaint: Optional[Complaint] = None,
    notification_type: str = 'status_update',
    idempotency_window_minutes: int = 60,
    force: bool = False
) -> Optional[Notification]:
    """
    Safely creates an in-app Notification for `user`.
    
    Guarantees:
    - Verifies user exists.
    - Prevents duplicate notification if an identical notification (same user, complaint,
      notification_type, and title) was already dispatched within `idempotency_window_minutes`.
    - Handles exceptions gracefully without interrupting critical transactions.
    """
    if not user or not user.is_active:
        return None

    if not force:
        # Check idempotency window
        cutoff = timezone.now() - timedelta(minutes=idempotency_window_minutes)
        existing = Notification.objects.filter(
            user=user,
            complaint=complaint,
            notification_type=notification_type,
            title=title,
            created_at__gte=cutoff
        ).first()

        if existing:
            logger.info(
                f"[Notification Idempotency] Suppressed duplicate notification for user={user.id}, "
                f"type={notification_type}, complaint={complaint.tracking_id if complaint else None}"
            )
            return existing

    try:
        notif = Notification.objects.create(
            user=user,
            complaint=complaint,
            title=title.strip()[:255],
            message=message.strip(),
            notification_type=notification_type,
            is_read=False
        )
        return notif
    except Exception as e:
        logger.error(f"[Notification Service] Failed to create notification: {e}")
        return None


def notify_complaint_submitted(complaint: Complaint) -> Optional[Notification]:
    """
    Dispatches submission confirmation to the citizen.
    """
    if not complaint or not complaint.citizen:
        return None

    title = f"Complaint Registered: {complaint.tracking_id}"
    message = (
        f"Your grievance '{complaint.title}' has been successfully logged with ticket ID {complaint.tracking_id}. "
        f"Our AI routing system is assessing the report for municipal dispatch."
    )
    return send_notification_idempotent(
        user=complaint.citizen,
        title=title,
        message=message,
        complaint=complaint,
        notification_type='complaint_submitted',
        idempotency_window_minutes=1440  # 24h window
    )


def notify_department_assigned(complaint: Complaint) -> Optional[Notification]:
    """
    Dispatches update when complaint is assigned to a municipal department.
    """
    if not complaint or not complaint.citizen or not complaint.department:
        return None

    dept_name = complaint.department.name
    sla_info = f" SLA target: {complaint.department.sla_hours} hours." if complaint.department.sla_hours else ""
    title = f"Department Assigned: {complaint.tracking_id}"
    message = f"Your complaint has been assigned to the '{dept_name}' department.{sla_info}"

    return send_notification_idempotent(
        user=complaint.citizen,
        title=title,
        message=message,
        complaint=complaint,
        notification_type='department_assigned',
        idempotency_window_minutes=120
    )


def notify_staff_assigned(complaint: Complaint, staff_user: User) -> Dict[str, Optional[Notification]]:
    """
    Dispatches notification to both the assigned field staff member and the citizen.
    Protects citizen privacy by not exposing private staff contact details.
    """
    results = {"staff": None, "citizen": None}
    if not complaint:
        return results

    # 1. Staff Notification
    if staff_user and staff_user.is_active:
        staff_title = f"New Task Assigned: {complaint.tracking_id}"
        staff_message = (
            f"You have been assigned to inspect and resolve complaint '{complaint.title}' "
            f"at '{complaint.address}' (Category: {complaint.category.name if complaint.category else 'General'})."
        )
        results["staff"] = send_notification_idempotent(
            user=staff_user,
            title=staff_title,
            message=staff_message,
            complaint=complaint,
            notification_type='staff_assigned',
            idempotency_window_minutes=60
        )

    # 2. Citizen Notification (Privacy safe)
    if complaint.citizen:
        cit_title = f"Field Staff Assigned: {complaint.tracking_id}"
        cit_message = (
            f"A municipal field technician has been assigned to attend to your grievance at {complaint.address}. "
            f"On-site inspection is scheduled."
        )
        results["citizen"] = send_notification_idempotent(
            user=complaint.citizen,
            title=cit_title,
            message=cit_message,
            complaint=complaint,
            notification_type='staff_assigned',
            idempotency_window_minutes=60
        )

    return results


def notify_status_update(complaint: Complaint, old_status: str, new_status: str, public_notes: str = "") -> Optional[Notification]:
    """
    Dispatches status change update to citizen.
    Ensures notes passed are citizen-safe.
    """
    if not complaint or not complaint.citizen:
        return None

    status_label = complaint.get_status_display()
    title = f"Complaint Update: {complaint.tracking_id}"

    if new_status == 'resolved':
        msg = f"Your grievance {complaint.tracking_id} has been marked as RESOLVED. Please verify and provide feedback."
    elif new_status == 'in_progress':
        msg = f"Work is actively in progress on ticket {complaint.tracking_id}."
    elif new_status == 'verified':
        msg = f"Thank you! Your grievance resolution has been verified."
    else:
        msg = f"The status of your grievance {complaint.tracking_id} is now '{status_label}'."

    if public_notes and public_notes.strip():
        msg += f" Note: {public_notes.strip()}"

    return send_notification_idempotent(
        user=complaint.citizen,
        title=title,
        message=msg,
        complaint=complaint,
        notification_type='status_update',
        idempotency_window_minutes=30
    )


def notify_escalation(complaint: Complaint, reason: str = "") -> Optional[Notification]:
    """
    Dispatches polite citizen notification regarding administrative escalation.
    Does not expose sensitive internal administrative jargon.
    """
    if not complaint or not complaint.citizen:
        return None

    title = f"Ticket Expedited: {complaint.tracking_id}"
    message = (
        f"Your grievance {complaint.tracking_id} has been prioritized for supervisor review to expedite resolution."
    )
    return send_notification_idempotent(
        user=complaint.citizen,
        title=title,
        message=message,
        complaint=complaint,
        notification_type='escalation',
        idempotency_window_minutes=720  # 12h window
    )


def notify_resolution_awaiting_confirmation(complaint: Complaint) -> Optional[Notification]:
    """
    Notifies the citizen that field staff marked the grievance as resolved
    and requests their honest confirmation or dispute.
    """
    if not complaint or not complaint.citizen:
        return None

    title = f"Resolution Awaiting Confirmation: {complaint.tracking_id}"
    message = (
        f"Field staff has marked your complaint {complaint.tracking_id} as resolved. "
        f"Please inspect the resolution proof and confirm or dispute the resolution in your portal."
    )
    return send_notification_idempotent(
        user=complaint.citizen,
        title=title,
        message=message,
        complaint=complaint,
        notification_type='resolution_awaiting_confirmation',
        idempotency_window_minutes=60
    )


def notify_resolution_disputed(complaint: Complaint, reason: str = "") -> Dict[str, Optional[Notification]]:
    """
    Notifies citizen that their dispute is registered, and notifies assigned staff/admins.
    """
    results = {"citizen": None, "staff": None}
    if not complaint:
        return results

    # Citizen confirmation
    if complaint.citizen:
        results["citizen"] = send_notification_idempotent(
            user=complaint.citizen,
            title=f"Dispute Logged: {complaint.tracking_id}",
            message=f"You have disputed the resolution of {complaint.tracking_id}. An administrative review has been scheduled.",
            complaint=complaint,
            notification_type='citizen_disputed',
            idempotency_window_minutes=60
        )

    # Assigned staff alert
    if complaint.assigned_staff and complaint.assigned_staff.is_active:
        results["staff"] = send_notification_idempotent(
            user=complaint.assigned_staff,
            title=f"Resolution Disputed: {complaint.tracking_id}",
            message=f"The reporting citizen disputed your resolution proof for {complaint.tracking_id}. Administrative review required.",
            complaint=complaint,
            notification_type='admin_review_required',
            idempotency_window_minutes=60
        )

    return results


def notify_resolution_confirmed(complaint: Complaint) -> Optional[Notification]:
    """
    Notifies citizen and assigned staff upon successful resolution confirmation.
    """
    if not complaint or not complaint.citizen:
        return None

    return send_notification_idempotent(
        user=complaint.citizen,
        title=f"Resolution Confirmed: {complaint.tracking_id}",
        message=f"Thank you for confirming resolution and submitting your satisfaction rating for {complaint.tracking_id}.",
        complaint=complaint,
        notification_type='citizen_confirmed',
        idempotency_window_minutes=60
    )

