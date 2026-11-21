"""
JanSahayak - Smart Complaint Lifecycle & SLA Monitoring Service

Monitors municipal service level agreements (SLAs), complaint lifecycle stages,
overdue status, and escalation recommendations.

Rules & Guarantees:
1. Timezone-aware calculation using `django.utils.timezone`.
2. Uses active department SLA configuration (`sla_hours`).
3. If no department or SLA is configured, returns `sla_status="not_configured"`.
4. Excludes resolved and closed complaints from overdue lists.
5. Does not automatically alter complaint statuses or assign staff without authorized workflow.
6. Does not report fake notifications or false escalation events.
7. Avoids repeatedly creating duplicate escalation notifications.
"""

from datetime import timedelta
from typing import Dict, Any, List, Optional
from django.utils import timezone
from django.db.models import Q
import logging

logger = logging.getLogger("jansahayak_ai")

TERMINAL_STATUSES = ['resolved', 'verified', 'rejected']


class SLAMonitor:
    """
    Modular lifecycle and SLA monitoring specialist for JanSahayak complaints.
    """

    @classmethod
    def calculate_sla_deadline(cls, complaint) -> Optional[Any]:
        """
        Calculates and returns timezone-aware SLA target datetime based on department SLA hours.
        """
        if not complaint or not complaint.department:
            return None

        dept = complaint.department
        if not dept.is_active or not dept.sla_hours or dept.sla_hours <= 0:
            return None

        # Base creation time or fallback to now
        created = complaint.created_at or timezone.now()
        return created + timedelta(hours=dept.sla_hours)

    @classmethod
    def evaluate_complaint_sla(cls, complaint, current_time: Optional[Any] = None) -> Dict[str, Any]:
        """
        Detailed SLA evaluation for a single complaint instance.
        """
        now = current_time or timezone.now()

        # Terminal status check (resolved/verified/rejected)
        is_completed = complaint.status in TERMINAL_STATUSES

        # Retrieve or compute SLA target date
        target_date = complaint.sla_target_date
        if not target_date and complaint.department:
            target_date = cls.calculate_sla_deadline(complaint)

        dept_sla_hours = complaint.department.sla_hours if (complaint.department and complaint.department.is_active) else None

        if not target_date or not dept_sla_hours:
            return {
                "complaint_id": complaint.id,
                "tracking_id": complaint.tracking_id,
                "current_status": complaint.status,
                "department_name": complaint.department.name if complaint.department else None,
                "sla_hours": None,
                "sla_deadline": None,
                "sla_status": "not_configured",
                "remaining_seconds": None,
                "overdue_seconds": 0,
                "is_overdue": False,
                "approaching_deadline": False,
                "escalation_recommended": False,
                "escalation_reason": None,
                "lifecycle_stage": cls.get_lifecycle_stage(complaint)
            }

        diff_seconds = (target_date - now).total_seconds()

        if is_completed:
            # If resolved before deadline, on time; else resolved overdue
            resolved_at = complaint.resolution_date or complaint.updated_at or now
            was_overdue_on_resolution = (resolved_at > target_date)
            return {
                "complaint_id": complaint.id,
                "tracking_id": complaint.tracking_id,
                "current_status": complaint.status,
                "department_name": complaint.department.name,
                "sla_hours": dept_sla_hours,
                "sla_deadline": target_date.isoformat(),
                "sla_status": "completed_overdue" if was_overdue_on_resolution else "completed_on_time",
                "remaining_seconds": 0,
                "overdue_seconds": int((resolved_at - target_date).total_seconds()) if was_overdue_on_resolution else 0,
                "is_overdue": False,  # No longer active overdue
                "approaching_deadline": False,
                "escalation_recommended": False,
                "escalation_reason": None,
                "lifecycle_stage": cls.get_lifecycle_stage(complaint)
            }

        # Active Complaint: Evaluate SLA adherence
        if diff_seconds < 0:
            overdue_secs = int(abs(diff_seconds))
            overdue_hours = round(overdue_secs / 3600, 1)

            # Recommend escalation if overdue and not already escalated
            escalate = not complaint.is_escalated
            reason = f"Ticket is overdue by {overdue_hours}h beyond configured {dept_sla_hours}h SLA deadline." if escalate else "Already flagged for administrative escalation."

            return {
                "complaint_id": complaint.id,
                "tracking_id": complaint.tracking_id,
                "current_status": complaint.status,
                "department_name": complaint.department.name,
                "sla_hours": dept_sla_hours,
                "sla_deadline": target_date.isoformat(),
                "sla_status": "overdue",
                "remaining_seconds": 0,
                "overdue_seconds": overdue_secs,
                "is_overdue": True,
                "approaching_deadline": False,
                "escalation_recommended": escalate,
                "escalation_reason": reason,
                "lifecycle_stage": cls.get_lifecycle_stage(complaint)
            }
        else:
            remaining_secs = int(diff_seconds)
            # Approaching deadline: remaining time < 25% of total SLA duration or < 6 hours
            is_approaching = (remaining_secs <= (dept_sla_hours * 3600 * 0.25)) or (remaining_secs <= 6 * 3600)
            return {
                "complaint_id": complaint.id,
                "tracking_id": complaint.tracking_id,
                "current_status": complaint.status,
                "department_name": complaint.department.name,
                "sla_hours": dept_sla_hours,
                "sla_deadline": target_date.isoformat(),
                "sla_status": "approaching" if is_approaching else "within_sla",
                "remaining_seconds": remaining_secs,
                "overdue_seconds": 0,
                "is_overdue": False,
                "approaching_deadline": is_approaching,
                "escalation_recommended": False,
                "escalation_reason": None,
                "lifecycle_stage": cls.get_lifecycle_stage(complaint)
            }

    @classmethod
    def get_lifecycle_stage(cls, complaint) -> Dict[str, Any]:
        """
        Returns accurate, database-verified lifecycle history of the complaint.
        Does not claim a stage has happened unless the database records confirm it.
        """
        return {
            "submitted": {
                "completed": True,
                "timestamp": complaint.created_at.isoformat() if complaint.created_at else None
            },
            "department_assigned": {
                "completed": complaint.department_id is not None,
                "department_name": complaint.department.name if complaint.department else None,
                "department_id": complaint.department_id
            },
            "staff_assigned": {
                "completed": complaint.assigned_staff_id is not None,
                "staff_username": complaint.assigned_staff.username if complaint.assigned_staff else None,
                "timestamp": complaint.assigned_at.isoformat() if complaint.assigned_at else None
            },
            "in_progress": {
                "completed": complaint.status in ['in_progress', 'resolved', 'verified'],
                "is_active_now": complaint.status == 'in_progress'
            },
            "resolved": {
                "completed": complaint.status in ['resolved', 'verified'],
                "timestamp": complaint.resolution_date.isoformat() if complaint.resolution_date else None,
                "resolution_notes": complaint.resolution_notes or None
            },
            "verified_by_citizen": {
                "completed": complaint.status == 'verified' or hasattr(complaint, 'feedback')
            }
        }

    @classmethod
    def get_overdue_complaints(cls, current_time: Optional[Any] = None) -> List[Dict[str, Any]]:
        """
        Scans all active complaints and returns those exceeding their SLA deadline.
        Excludes resolved/rejected tickets.
        """
        from .models import Complaint
        now = current_time or timezone.now()

        # Active complaints with SLA deadline in the past
        active_complaints = Complaint.objects.exclude(
            status__in=TERMINAL_STATUSES
        ).filter(
            Q(sla_target_date__lt=now) | Q(department__isnull=False)
        ).select_related('department', 'assigned_staff')

        overdue_list = []
        for comp in active_complaints:
            eval_res = cls.evaluate_complaint_sla(comp, current_time=now)
            if eval_res["is_overdue"]:
                overdue_list.append(eval_res)

        return overdue_list

    @classmethod
    def recommend_escalations(cls, current_time: Optional[Any] = None) -> List[Dict[str, Any]]:
        """
        Returns all complaints currently qualifying for administrative escalation recommendation.
        Avoids duplicate recommendations if already escalated.
        """
        overdue_tickets = cls.get_overdue_complaints(current_time=current_time)
        return [t for t in overdue_tickets if t["escalation_recommended"]]

    @classmethod
    def apply_admin_escalation(cls, complaint, reason: str, user=None) -> bool:
        """
        Auditable execution of administrative escalation.
        Records reason, creates timeline entry and notifies citizen/staff.
        """
        from .models import ComplaintTimeline, Notification

        if complaint.is_escalated:
            return False  # Avoid duplicate escalation events

        complaint.is_escalated = True
        complaint.escalation_reason = reason.strip()
        complaint.save(update_fields=['is_escalated', 'escalation_reason'])

        ComplaintTimeline.objects.create(
            complaint=complaint,
            performed_by=user,
            action="Ticket Escalated by SLA Monitor",
            details=f"Escalation logged: {reason.strip()}",
            from_status=complaint.status,
            to_status=complaint.status
        )

        # Notify citizen (Safe and Idempotent - Task 13)
        from .notifications import notify_escalation
        notify_escalation(complaint, reason=reason)

        return True

