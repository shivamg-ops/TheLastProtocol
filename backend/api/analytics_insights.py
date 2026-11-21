"""
JanSahayak - AI-Powered Analytics & Statistical Insights Service (Task 14)

Provides:
1. Deterministic database aggregation for administrative grievance metrics.
2. Filter application (date_from, date_to, category, department, status).
3. Core statistics: volume, status breakdown, department performance, SLA compliance,
   average resolution time, daily trends.
4. Explanatory AI Insights: Uses Gemini solely to interpret pre-calculated metrics.
5. Deterministic rule-based fallback when Gemini is unavailable.
6. Guardrails:
   - Never allows Gemini to invent numbers or modify database statistics.
   - Never describes correlation as causation.
   - Never outputs unsupported future predictions.
   - Excludes citizen personally identifiable information (PII).
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from django.utils import timezone
from django.db.models import Count, Avg, F, Q, ExpressionWrapper, fields
from .models import Complaint, Department, ComplaintCategory, ComplaintStatus
from .sla_monitor import SLAMonitor, TERMINAL_STATUSES

logger = logging.getLogger("jansahayak_ai")


def parse_iso_datetime(date_str: Optional[str]) -> Optional[datetime]:
    """Safely parses ISO format datetime string with timezone awareness."""
    if not date_str:
        return None
    try:
        dt = datetime.fromisoformat(date_str.strip().replace('Z', '+00:00'))
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt)
        return dt
    except Exception:
        return None


def calculate_analytics_metrics(
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    category_id: Optional[int] = None,
    department_id: Optional[int] = None,
    status_filter: Optional[str] = None
) -> Dict[str, Any]:
    """
    Computes all administrative analytics strictly from database records.
    Filters affect all metrics consistently.
    """
    now = timezone.now()
    qs = Complaint.objects.all()

    # Apply filters consistently
    if date_from:
        qs = qs.filter(created_at__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__lte=date_to)
    if category_id:
        qs = qs.filter(category_id=category_id)
    if department_id:
        qs = qs.filter(department_id=department_id)
    if status_filter:
        qs = qs.filter(status=status_filter)

    total_complaints = qs.count()

    # Status counts
    resolved_count = qs.filter(status__in=[ComplaintStatus.RESOLVED, ComplaintStatus.VERIFIED]).count()
    in_progress_count = qs.filter(status=ComplaintStatus.IN_PROGRESS).count()
    pending_count = qs.filter(
        status__in=[ComplaintStatus.SUBMITTED, ComplaintStatus.ACKNOWLEDGED, ComplaintStatus.ASSIGNED]
    ).count()
    rejected_count = qs.filter(status=ComplaintStatus.REJECTED).count()

    # Resolution rate
    resolution_rate = round((resolved_count / total_complaints * 100), 1) if total_complaints > 0 else 0.0

    # Overdue and Approaching SLA calculation
    active_complaints = qs.exclude(status__in=TERMINAL_STATUSES).select_related('department')
    overdue_count = 0
    approaching_count = 0
    escalation_count = 0

    for comp in active_complaints:
        eval_res = SLAMonitor.evaluate_complaint_sla(comp, current_time=now)
        if eval_res.get("is_overdue"):
            overdue_count += 1
        if eval_res.get("approaching_deadline"):
            approaching_count += 1
        if eval_res.get("escalation_recommended") or comp.is_escalated:
            escalation_count += 1

    # SLA Compliance Calculation
    # Resolved tickets within SLA vs resolved tickets overdue
    resolved_tickets = qs.filter(status__in=[ComplaintStatus.RESOLVED, ComplaintStatus.VERIFIED]).select_related('department')
    compliant_resolved = 0
    non_compliant_resolved = 0
    total_evaluated_resolved = 0

    for comp in resolved_tickets:
        if comp.department and comp.department.sla_hours:
            eval_res = SLAMonitor.evaluate_complaint_sla(comp, current_time=now)
            total_evaluated_resolved += 1
            if eval_res.get("sla_status") == "completed_on_time":
                compliant_resolved += 1
            elif eval_res.get("sla_status") == "completed_overdue":
                non_compliant_resolved += 1

    sla_compliance_rate = (
        round((compliant_resolved / total_evaluated_resolved * 100), 1)
        if total_evaluated_resolved > 0 else (100.0 if resolved_count > 0 else 0.0)
    )

    # Average Resolution Time (in hours) using Django expression
    duration_expr = ExpressionWrapper(
        F('resolution_date') - F('created_at'),
        output_field=fields.DurationField()
    )
    avg_duration = qs.filter(
        resolution_date__isnull=False,
        status__in=[ComplaintStatus.RESOLVED, ComplaintStatus.VERIFIED]
    ).annotate(duration=duration_expr).aggregate(avg_time=Avg('duration'))['avg_time']

    avg_resolution_hours = round(avg_duration.total_seconds() / 3600.0, 1) if avg_duration else 0.0

    # Category Breakdown
    category_counts = list(
        qs.values('category__id', 'category__name')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    category_breakdown = [
        {
            "category_id": item['category__id'],
            "name": item['category__name'] or "Uncategorized",
            "count": item['count'],
            "percentage": round(item['count'] / total_complaints * 100, 1) if total_complaints > 0 else 0.0
        }
        for item in category_counts
    ]

    # Task 17: Citizen Trust, Resolution Verification & Feedback Metrics
    # Resolution verification distribution
    verif_counts = list(
        qs.values('resolution_verification_status')
        .annotate(count=Count('id'))
    )
    verif_map = {item['resolution_verification_status']: item['count'] for item in verif_counts}

    pending_confirmation_count = verif_map.get('pending_citizen_confirmation', 0)
    citizen_confirmed_count = verif_map.get('citizen_confirmed', 0)
    citizen_disputed_count = verif_map.get('citizen_disputed', 0)
    admin_review_count = verif_map.get('admin_review_required', 0)

    # Average citizen satisfaction score from CitizenFeedback (1 to 5)
    from .models import CitizenFeedback
    feedback_qs = CitizenFeedback.objects.filter(complaint__in=qs)
    avg_rating_val = feedback_qs.aggregate(avg=Avg('rating'))['avg']
    avg_citizen_satisfaction = round(float(avg_rating_val), 2) if avg_rating_val else 0.0
    total_feedback_count = feedback_qs.count()

    # Department Breakdown & Performance (Extended with avg satisfaction)
    dept_counts = list(
        qs.values('department__id', 'department__name', 'department__sla_hours')
        .annotate(
            total=Count('id'),
            resolved=Count('id', filter=Q(status__in=[ComplaintStatus.RESOLVED, ComplaintStatus.VERIFIED])),
            in_progress=Count('id', filter=Q(status=ComplaintStatus.IN_PROGRESS)),
            pending=Count('id', filter=Q(status__in=[ComplaintStatus.SUBMITTED, ComplaintStatus.ACKNOWLEDGED, ComplaintStatus.ASSIGNED])),
            disputed=Count('id', filter=Q(resolution_verification_status='citizen_disputed'))
        )
        .order_by('-total')
    )
    department_breakdown = []
    for item in dept_counts:
        dept_id = item['department__id']
        dept_feedbacks = feedback_qs.filter(complaint__department_id=dept_id)
        d_avg = dept_feedbacks.aggregate(avg=Avg('rating'))['avg']
        department_breakdown.append({
            "department_id": dept_id,
            "name": item['department__name'] or "Unassigned",
            "sla_hours": item['department__sla_hours'],
            "total_complaints": item['total'],
            "resolved_count": item['resolved'],
            "in_progress_count": item['in_progress'],
            "pending_count": item['pending'],
            "disputed_count": item['disputed'],
            "avg_satisfaction": round(float(d_avg), 1) if d_avg else 0.0,
            "resolution_rate": round(item['resolved'] / item['total'] * 100, 1) if item['total'] > 0 else 0.0
        })

    # Status Breakdown
    status_counts = list(
        qs.values('status')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    status_breakdown = [
        {
            "status": item['status'],
            "count": item['count'],
            "percentage": round(item['count'] / total_complaints * 100, 1) if total_complaints > 0 else 0.0
        }
        for item in status_counts
    ]

    # Daily Volume Trend (Last 14 days or filtered period)
    # Group by date
    trend_start = date_from or (now - timedelta(days=14))
    trend_end = date_to or now

    # Truncate to days
    daily_trend = []
    curr = trend_start.date()
    end_date = trend_end.date()

    # Pre-aggregate date counts
    day_counts_raw = (
        qs.filter(created_at__date__gte=curr, created_at__date__lte=end_date)
        .values('created_at__date')
        .annotate(count=Count('id'))
    )
    day_map = {item['created_at__date'].strftime('%Y-%m-%d'): item['count'] for item in day_counts_raw if item['created_at__date']}

    # Limit trend steps to max 31 days to keep payload efficient
    step_days = (end_date - curr).days
    if step_days > 31:
        curr = end_date - timedelta(days=30)

    while curr <= end_date:
        d_str = curr.strftime('%Y-%m-%d')
        daily_trend.append({
            "date": d_str,
            "label": curr.strftime('%d %b'),
            "count": day_map.get(d_str, 0)
        })
        curr += timedelta(days=1)

    return {
        "summary": {
            "total_complaints": total_complaints,
            "pending_complaints": pending_count,
            "in_progress_complaints": in_progress_count,
            "resolved_complaints": resolved_count,
            "rejected_complaints": rejected_count,
            "overdue_complaints": overdue_count,
            "approaching_sla_complaints": approaching_count,
            "escalated_complaints": escalation_count,
            "resolution_rate": resolution_rate,
            "sla_compliance_rate": sla_compliance_rate,
            "avg_resolution_hours": avg_resolution_hours,
            # Task 17 Verification & Trust Metrics
            "pending_citizen_confirmation_count": pending_confirmation_count,
            "citizen_confirmed_count": citizen_confirmed_count,
            "citizen_disputed_count": citizen_disputed_count,
            "admin_review_count": admin_review_count,
            "avg_citizen_satisfaction": avg_citizen_satisfaction,
            "total_feedback_count": total_feedback_count
        },
        "category_breakdown": category_breakdown,
        "department_performance": department_breakdown,
        "status_breakdown": status_breakdown,
        "volume_trend": daily_trend,
        "filters_applied": {
            "date_from": date_from.isoformat() if date_from else None,
            "date_to": date_to.isoformat() if date_to else None,
            "category_id": category_id,
            "department_id": department_id,
            "status": status_filter
        }
    }


def generate_deterministic_insights(metrics: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Produces deterministic rule-based explanations from database statistics.
    Used when Gemini is unavailable or disabled.
    """
    summary = metrics.get("summary", {})
    total = summary.get("total_complaints", 0)
    cat_breakdown = metrics.get("category_breakdown", [])
    dept_performance = metrics.get("department_performance", [])
    overdue = summary.get("overdue_complaints", 0)
    sla_rate = summary.get("sla_compliance_rate", 0)

    insights = []

    if total == 0:
        return [{
            "type": "info",
            "title": "No Grievance Activity",
            "description": "No complaints matched the selected filter criteria. System is currently idle.",
            "source": "deterministic"
        }]

    # Top category
    if cat_breakdown:
        top_cat = cat_breakdown[0]
        insights.append({
            "type": "volume",
            "title": f"High Grievance Volume: {top_cat['name']}",
            "description": f"{top_cat['name']} constitutes {top_cat['percentage']}% ({top_cat['count']} complaints) of all reported civic grievances in this window.",
            "source": "deterministic"
        })

    # SLA performance & Overdue
    if overdue > 0:
        insights.append({
            "type": "warning",
            "title": f"SLA Attention: {overdue} Overdue Complaints",
            "description": f"There are {overdue} active complaint(s) exceeding their department SLA deadlines. Administrative escalation or staff dispatch is recommended.",
            "source": "deterministic"
        })
    else:
        insights.append({
            "type": "success",
            "title": f"High SLA Adherence: {sla_rate}%",
            "description": f"All active tickets are proceeding within SLA deadlines with an overall compliance rate of {sla_rate}%.",
            "source": "deterministic"
        })

    # Department Attention
    if dept_performance:
        # Find department with lowest resolution rate (among depts with > 0 complaints)
        active_depts = [d for d in dept_performance if d["total_complaints"] > 0]
        if active_depts:
            active_depts.sort(key=lambda x: x["resolution_rate"])
            lowest_dept = active_depts[0]
            if lowest_dept["resolution_rate"] < 50.0 and lowest_dept["total_complaints"] >= 2:
                insights.append({
                    "type": "department",
                    "title": f"Department Resource Focus: {lowest_dept['name']}",
                    "description": f"{lowest_dept['name']} has an active resolution rate of {lowest_dept['resolution_rate']}% across {lowest_dept['total_complaints']} complaints.",
                    "source": "deterministic"
                })

    return insights


def generate_ai_insights(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generates AI-powered statistical explanations using Gemini.
    Strictly forbids altering numbers or producing speculative future predictions.
    Gracefully falls back to deterministic rules if Gemini is unavailable or fails.
    """
    from .gemini_client import call_gemini_safe, GeminiClientManager

    deterministic_fallback = generate_deterministic_insights(metrics)
    summary = metrics.get("summary", {})
    total = summary.get("total_complaints", 0)

    if total == 0:
        return {
            "insights": deterministic_fallback,
            "generated_by": "deterministic",
            "disclaimer": "Rule-based analysis based on zero recorded complaints."
        }

    client_mgr = GeminiClientManager()
    if not client_mgr.is_available():
        return {
            "insights": deterministic_fallback,
            "generated_by": "deterministic",
            "disclaimer": "AI service unavailable. Showing deterministic statistical analysis."
        }

    # Pass strictly pre-aggregated data (no citizen personal information)
    data_payload = {
        "total_complaints": summary.get("total_complaints"),
        "pending": summary.get("pending_complaints"),
        "in_progress": summary.get("in_progress_complaints"),
        "resolved": summary.get("resolved_complaints"),
        "overdue": summary.get("overdue_complaints"),
        "sla_compliance_rate_percent": summary.get("sla_compliance_rate"),
        "avg_resolution_hours": summary.get("avg_resolution_hours"),
        "top_categories": metrics.get("category_breakdown", [])[:3],
        "top_departments": metrics.get("department_performance", [])[:4]
    }

    prompt = f"""
You are the statistical reporting assistant for the JanSahayak municipal governance platform.
Analyze the following PRE-CALCULATED civic grievance metrics and provide 3-4 concise, factual observations.

DATABASE METRICS:
{json.dumps(data_payload, indent=2)}

STRICT RULES:
1. Cite only the exact numbers provided in the metrics above. NEVER invent, guess or alter any numerical statistics.
2. Clearly distinguish between volume, department performance, and SLA timeliness.
3. Do not claim correlation implies causation (e.g., do not say rain caused potholes unless explicitly stated in data).
4. Do not make future forecasts or predictions.
5. Return strictly valid JSON array of objects with the following keys:
   - "type": "volume" | "warning" | "success" | "department" | "info"
   - "title": A short informative heading (max 8 words)
   - "description": 1-2 factual sentences explaining what the data shows
"""

    try:
        raw_text = call_gemini_safe(
            prompt=prompt,
            system_instruction="You are a strict statistical data explainer. Output only valid JSON arrays.",
            temperature=0.1
        )

        if raw_text:
            raw_text = raw_text.strip()
            # Clean markdown code block fences if present
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.startswith("```"):
                raw_text = raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]

            parsed = json.loads(raw_text.strip())
            if isinstance(parsed, list) and len(parsed) > 0:
                formatted_insights = []
                for item in parsed[:4]:
                    if isinstance(item, dict) and "title" in item and "description" in item:
                        formatted_insights.append({
                            "type": str(item.get("type", "info")),
                            "title": str(item["title"]).strip(),
                            "description": str(item["description"]).strip(),
                            "source": "gemini_ai"
                        })
                if formatted_insights:
                    return {
                        "insights": formatted_insights,
                        "generated_by": "gemini_ai",
                        "disclaimer": "AI-generated statistical explanation based strictly on real database aggregates."
                    }
    except Exception as e:
        logger.warning(f"[Analytics AI Insights] Gemini call failed or returned invalid JSON ({e}). Falling back.")

    return {
        "insights": deterministic_fallback,
        "generated_by": "deterministic",
        "disclaimer": "Showing deterministic statistical analysis."
    }
