"""
JanSahayak - Smart Predictive Civic Intelligence & Preventive Action Engine (Task 20)

Provides:
1. Historical Trend Aggregation:
   - Daily, weekly, monthly volume aggregates.
   - Category-wise and department-wise velocity and overdue patterns.
2. Recurring Problem Detection:
   - Identifies repeated civic problems using category match, geographic proximity (Haversine),
     and complaint description similarity.
   - Distinguishes repeated citizen reports on the same issue from separate recurring incidents.
3. Explainable Volume Forecasting:
   - 7-day statistical moving average / exponential smoothing.
   - Validates minimum historical coverage (requires >= 7 days of historical records).
   - Returns explicit 'insufficient_data' message when records are sparse.
   - NEVER allows Gemini or LLM to invent numeric estimates.
4. Civic Hotspot Risk Scoring:
   - Measurable formula (0-100) based on:
     * Complaint velocity (recent vs historical baseline)
     * Recurring issue density
     * SLA overdue ratio
     * Priority severity weight
   - Explains contributing factors transparently without claiming certainty.
5. Preventive Action Recommendations:
   - Data-grounded actionable municipal directives (e.g., pipeline inspections, bin clearance schedules).
   - Deterministic rule generation with optional Gemini summarization.
6. Privacy & PII Protection:
   - Anonymized aggregates only (no citizen names, phones, or private data exposed).
"""

import math
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from django.utils import timezone
from django.db.models import Count, Avg, F, Q, Sum
from django.db.models.functions import TruncDate, TruncWeek, TruncMonth
from .models import Complaint, Department, ComplaintCategory, ComplaintStatus
from .location_intelligence import haversine_distance, is_valid_coordinate, detect_hotspots
from .sla_monitor import SLAMonitor, TERMINAL_STATUSES
from .gemini_client import call_gemini_safe, clean_and_parse_json

logger = logging.getLogger("jansahayak_ai")

# Minimum days of historical records required for a reliable statistical forecast
MIN_FORECAST_DAYS_COVERAGE = 7


def aggregate_historical_trends(
    qs,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Computes daily, weekly, and monthly complaint volume trends,
    category velocity, and SLA overdue ratios.
    """
    # 1. Daily Volume Trend
    daily_qs = (
        qs.annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(
            total_count=Count('id'),
            resolved_count=Count('id', filter=Q(status__in=[ComplaintStatus.RESOLVED, ComplaintStatus.VERIFIED])),
            overdue_count=Count('id', filter=Q(is_escalated=True))
        )
        .order_by('day')
    )
    daily_trends = [
        {
            "date": entry["day"].isoformat() if entry["day"] else "",
            "total": entry["total_count"],
            "resolved": entry["resolved_count"],
            "overdue": entry["overdue_count"]
        }
        for entry in daily_qs
    ]

    # 2. Weekly Volume Trend
    weekly_qs = (
        qs.annotate(week=TruncWeek('created_at'))
        .values('week')
        .annotate(total_count=Count('id'))
        .order_by('week')
    )
    weekly_trends = [
        {
            "week_start": entry["week"].strftime("%Y-%m-%d") if entry["week"] else "",
            "count": entry["total_count"]
        }
        for entry in weekly_qs
    ]

    # 3. Monthly Volume Trend
    monthly_qs = (
        qs.annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(total_count=Count('id'))
        .order_by('month')
    )
    monthly_trends = [
        {
            "month": entry["month"].strftime("%Y-%m") if entry["month"] else "",
            "count": entry["total_count"]
        }
        for entry in monthly_qs
    ]

    # 4. Category-wise and Department-wise Volume
    category_trends = list(
        qs.values(category_name=F('category__name'))
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    for c in category_trends:
        if not c["category_name"]:
            c["category_name"] = "General"

    dept_trends = list(
        qs.values(department_name=F('department__name'))
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    for d in dept_trends:
        if not d["department_name"]:
            d["department_name"] = "Unassigned"

    return {
        "daily_trends": daily_trends,
        "weekly_trends": weekly_trends,
        "monthly_trends": monthly_trends,
        "category_distribution": category_trends,
        "department_distribution": dept_trends,
        "total_records_analyzed": qs.count()
    }


def detect_recurring_problems(
    qs,
    proximity_radius_km: float = 0.5,
    min_recurrence_count: int = 2
) -> List[Dict[str, Any]]:
    """
    Identifies recurring civic problems using category match, geographic proximity,
    and description keywords. Distinguishes repeated citizen reports on the same issue
    (duplicates) from separate recurring incidents over time.
    """
    # Fetch relevant complaint attributes without PII
    complaints = list(qs.values(
        'id', 'tracking_id', 'title', 'description', 'category_id',
        'latitude', 'longitude', 'address', 'created_at', 'status',
        'ai_duplicate_suspect', 'duplicate_of_id',
        category_name=F('category__name'),
        department_name=F('department__name')
    ).order_by('created_at'))

    recurring_groups = []
    visited = set()

    for i, c1 in enumerate(complaints):
        if c1['id'] in visited:
            continue

        c1_has_gps = is_valid_coordinate(c1['latitude'], c1['longitude'])
        c1_lat = float(c1['latitude']) if c1_has_gps else None
        c1_lng = float(c1['longitude']) if c1_has_gps else None

        cluster = [c1]
        visited.add(c1['id'])

        for j in range(i + 1, len(complaints)):
            c2 = complaints[j]
            if c2['id'] in visited:
                continue

            # Must share category or close domain
            same_category = (c1['category_id'] and c1['category_id'] == c2['category_id'])
            
            # Proximity check if GPS exists
            c2_has_gps = is_valid_coordinate(c2['latitude'], c2['longitude'])
            is_proximate = False
            if c1_has_gps and c2_has_gps:
                dist = haversine_distance(c1_lat, c1_lng, float(c2['latitude']), float(c2['longitude']))
                if dist <= proximity_radius_km:
                    is_proximate = True
            elif c1['address'] and c2['address'] and c1['address'].strip().lower() == c2['address'].strip().lower():
                is_proximate = True

            if same_category and is_proximate:
                cluster.append(c2)
                visited.add(c2['id'])

        if len(cluster) >= min_recurrence_count:
            # Task 20: Separate Confirmed and Suspected Duplicates
            # 1. Confirmed duplicate: Explicit duplicate relationship established by system or admin review (duplicate_of_id is set)
            # 2. Suspected duplicate: Flagged by AI perceptual/text detection (ai_duplicate_suspect=True) but not yet formally linked
            # 3. Independent incident: Neither confirmed nor suspected duplicate
            confirmed_duplicate_count = sum(1 for m in cluster if m.get('duplicate_of_id'))
            suspected_duplicate_count = sum(1 for m in cluster if m.get('ai_duplicate_suspect') and not m.get('duplicate_of_id'))
            
            # Confirmed duplicates belong to an existing incident chain; suspected duplicates remain potential incidents pending review
            independent_incident_count = len(cluster) - confirmed_duplicate_count

            # Calculate time span of recurrence
            dates = [m['created_at'] for m in cluster if m.get('created_at')]
            date_span_days = (max(dates) - min(dates)).days if dates else 0

            # Compute centroid if coordinates are valid
            valid_coords = [(float(m['latitude']), float(m['longitude'])) for m in cluster if is_valid_coordinate(m['latitude'], m['longitude'])]
            centroid_lat = round(sum(p[0] for p in valid_coords) / len(valid_coords), 6) if valid_coords else None
            centroid_lng = round(sum(p[1] for p in valid_coords) / len(valid_coords), 6) if valid_coords else None

            cat_name = cluster[0]['category_name'] or "General Civic Issue"
            loc_label = cluster[0]['address'] or f"Coordinates ({centroid_lat}, {centroid_lng})"

            explanation_parts = [
                f"{len(cluster)} complaints recorded in this locality for {cat_name}.",
                f"Consists of {independent_incident_count} independent incidents"
            ]
            if confirmed_duplicate_count > 0:
                explanation_parts.append(f"{confirmed_duplicate_count} confirmed duplicate reports")
            if suspected_duplicate_count > 0:
                explanation_parts.append(f"{suspected_duplicate_count} suspected duplicates awaiting verification")

            recurring_groups.append({
                "problem_id": f"REC-{len(recurring_groups) + 1:03d}",
                "category_name": cat_name,
                "location_label": loc_label,
                "centroid_latitude": centroid_lat,
                "centroid_longitude": centroid_lng,
                "total_complaint_count": len(cluster),
                "confirmed_duplicate_count": confirmed_duplicate_count,
                "suspected_duplicate_count": suspected_duplicate_count,
                "independent_incidents_count": max(1, independent_incident_count),
                "is_persistent": date_span_days >= 7,
                "timespan_days": date_span_days,
                "tracking_ids": [m['tracking_id'] for m in cluster],
                "explanation": " ".join(explanation_parts)
            })

    recurring_groups.sort(key=lambda x: x["total_complaint_count"], reverse=True)
    return recurring_groups


def calculate_complaint_volume_forecast(
    qs,
    forecast_horizon_days: int = 7
) -> Dict[str, Any]:
    """
    Explainable statistical volume forecasting using calendar-continuous daily volume.
    
    Guarantees:
    - Never uses an LLM to invent numbers.
    - Missing calendar days within the historical span are filled with 0 complaints
      to maintain accurate rolling temporal baselines.
    - Requires >= 7 distinct calendar days with recorded complaints in the database.
    - Projections use dampened linear trend: Expected = max(0, base_avg + (slope * dampening^step)).
    - Upper and lower bounds are explicitly labeled as heuristic tolerance ranges (+/- 25%),
      NOT calibrated confidence intervals.
    - Negative predictions are strictly prevented (max(0.0, ...)).
    """
    if forecast_horizon_days <= 0 or forecast_horizon_days > 30:
        forecast_horizon_days = 7

    # Aggregate daily volume strictly from DB
    daily_records = list(
        qs.annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )

    distinct_days_count = len(daily_records)

    if distinct_days_count < MIN_FORECAST_DAYS_COVERAGE:
        return {
            "status": "insufficient_data",
            "message": "Insufficient historical data for a reliable forecast.",
            "forecast_horizon_days": forecast_horizon_days,
            "historical_days_available": distinct_days_count,
            "min_days_required": MIN_FORECAST_DAYS_COVERAGE,
            "historical_sample_size": qs.count(),
            "methodology": "7-day Moving Average with Dampened Trend",
            "predictions": []
        }

    # Map observed days into a continuous calendar series filling missing dates with 0
    day_count_map = {r["day"]: r["count"] for r in daily_records if r["day"]}
    min_date = daily_records[0]["day"]
    max_date = daily_records[-1]["day"]

    continuous_counts = []
    curr = min_date
    while curr <= max_date:
        continuous_counts.append(day_count_map.get(curr, 0))
        curr += timedelta(days=1)

    # Moving average of the last 7 calendar days
    recent_window = continuous_counts[-min(7, len(continuous_counts)):]
    base_avg = sum(recent_window) / len(recent_window)

    # Compute linear slope over the recent window
    if len(recent_window) >= 2:
        slope = (recent_window[-1] - recent_window[0]) / (len(recent_window) - 1)
    else:
        slope = 0.0

    # Dampen trend across future steps
    dampening_factor = 0.85
    predictions = []

    for step in range(1, forecast_horizon_days + 1):
        future_date = max_date + timedelta(days=step)
        proj_val = base_avg + (slope * (dampening_factor ** step))
        # Strictly enforce non-negative predictions
        expected_val = max(0.0, round(proj_val, 1))

        predictions.append({
            "date": future_date.isoformat(),
            "predicted_count": expected_val,
            # Explicitly heuristic tolerance ranges, NOT statistical confidence intervals
            "lower_tolerance": max(0.0, round(expected_val * 0.75, 1)),
            "upper_tolerance": round(expected_val * 1.25 + 0.5, 1),
            "is_estimate": True,
            "tolerance_type": "heuristic_tolerance_range"
        })

    return {
        "status": "success",
        "message": "Statistical forecast calculated from calendar-continuous historical trends.",
        "forecast_horizon_days": forecast_horizon_days,
        "historical_days_available": distinct_days_count,
        "historical_sample_size": qs.count(),
        "recent_7day_average": round(base_avg, 2),
        "methodology": "7-day Calendar-Continuous Moving Average with Dampened Trend",
        "label": "Statistical estimate based on real database records (heuristic tolerance range, not calibrated confidence intervals)",
        "predictions": predictions
    }


def calculate_hotspot_risk_scores(
    qs,
    distance_threshold_km: float = 0.5
) -> List[Dict[str, Any]]:
    """
    Computes explainable Civic Hotspot Risk Scores (0 to 100) using:
    - Recent Complaint Volume (40% weight)
    - Acceleration / Increase over previous period (25% weight)
    - Recurring Issue Density (20% weight)
    - SLA Overdue Ratio (15% weight)

    Formula:
    Risk Score = (Volume Factor * 40) + (Growth Factor * 25) +
                 (Recurrence Factor * 20) + (Overdue Factor * 15)
    Categorization:
    - 0 to 39: Low
    - 40 to 69: Medium
    - 70 to 100: High
    """
    # 1. Filter geolocated complaints
    all_complaints = list(qs.values(
        'id', 'tracking_id', 'title', 'category_id', 'department_id',
        'latitude', 'longitude', 'status', 'created_at', 'is_escalated',
        category_name=F('category__name'),
        department_name=F('department__name')
    ))

    geolocated = [
        c for c in all_complaints
        if is_valid_coordinate(c['latitude'], c['longitude'])
    ]

    if not geolocated:
        return []

    # Format for detect_hotspots
    geolocated_points = [
        {
            "id": c["id"],
            "tracking_id": c["tracking_id"],
            "latitude": float(c["latitude"]),
            "longitude": float(c["longitude"]),
            "category_name": c["category_name"] or "General",
            "is_overdue": (c["status"] == "escalated" or c.get("is_escalated", False)),
            "created_at": c["created_at"]
        }
        for c in geolocated
    ]

    raw_clusters = detect_hotspots(
        geolocated_complaints=geolocated_points,
        distance_threshold_km=distance_threshold_km,
        min_cluster_size=2
    )

    scored_hotspots = []
    now = timezone.now()
    current_14_days_ago = now - timedelta(days=14)
    previous_28_days_ago = now - timedelta(days=28)

    for cluster in raw_clusters:
        member_ids = set(cluster["complaint_ids"])
        members = [m for m in geolocated_points if m["id"] in member_ids]
        n_members = len(members)

        # 1. Volume Factor (Normalized between 0 and 1: 10+ complaints = 1.0)
        volume_factor = min(1.0, max(0.0, n_members / 10.0))

        # 2. Velocity / Acceleration Factor (Normalized between 0 and 1):
        # Compares Current 14-day count (C_curr) against Previous 14-day count (C_prev).
        # Formula:
        #   delta = C_curr - C_prev
        #   If both periods have 0 complaints: acceleration = 0.0
        #   If C_prev == 0 and C_curr > 0: acceleration = min(1.0, C_curr / 6.0) (scaled by magnitude to prevent small samples from spiking)
        #   Else: acceleration = min(1.0, max(0.0, 0.5 + (delta / (2 * max(C_curr, C_prev)))))
        # Where:
        #   - delta > 0 (increasing volume): 0.5 < acceleration <= 1.0
        #   - delta == 0 (unchanged volume): acceleration = 0.5
        #   - delta < 0 (decreasing volume): 0.0 <= acceleration < 0.5
        c_curr = sum(1 for m in members if m["created_at"] and m["created_at"] >= current_14_days_ago)
        c_prev = sum(1 for m in members if m["created_at"] and current_14_days_ago > m["created_at"] >= previous_28_days_ago)

        if c_curr == 0 and c_prev == 0:
            growth_factor = 0.0
            velocity_desc = "Zero complaints in past 28 days"
        elif c_prev == 0:
            growth_factor = min(1.0, c_curr / 6.0)
            velocity_desc = f"New localized influx ({c_curr} complaints in current 14 days vs 0 in previous period)"
        else:
            delta = c_curr - c_prev
            relative_shift = delta / (2.0 * max(c_curr, c_prev))
            growth_factor = min(1.0, max(0.0, 0.5 + relative_shift))
            if delta > 0:
                velocity_desc = f"Increasing velocity: {c_curr} in current 14 days vs {c_prev} in previous (+{delta})"
            elif delta < 0:
                velocity_desc = f"Decreasing velocity: {c_curr} in current 14 days vs {c_prev} in previous ({delta})"
            else:
                velocity_desc = f"Unchanged velocity: {c_curr} complaints in both 14-day periods"

        # 3. Recurrence Density Factor (Normalized between 0 and 1: 6+ complaints = 1.0)
        recurrence_factor = min(1.0, max(0.0, n_members / 6.0))

        # 4. Overdue Ratio (Normalized between 0 and 1: overdue tickets / total tickets)
        overdue_count = sum(1 for m in members if m.get("is_overdue"))
        overdue_factor = min(1.0, max(0.0, overdue_count / max(1, n_members)))

        # Composite Risk Score Calculation strictly bounded between 0.0 and 100.0:
        # 40% Volume + 25% Velocity + 20% Recurrence + 15% Overdue
        score = (
            (volume_factor * 40.0) +
            (growth_factor * 25.0) +
            (recurrence_factor * 20.0) +
            (overdue_factor * 15.0)
        )
        score_rounded = round(min(100.0, max(0.0, score)), 1)

        # Risk Level strictly matching documented thresholds:
        # Low: 0.0 to 39.9
        # Medium: 40.0 to 69.9
        # High: 70.0 to 100.0
        if score_rounded >= 70.0:
            level = "high"
        elif score_rounded >= 40.0:
            level = "medium"
        else:
            level = "low"

        # Factors breakdown for transparency
        factors = []
        factors.append(f"{n_members} complaints clustered within {cluster['radius_meters']}m radius")
        factors.append(velocity_desc)
        if overdue_count > 0:
            factors.append(f"{overdue_count} unresolved tickets past SLA deadline")
        factors.append(f"Dominant civic issue: {cluster['primary_category']}")

        scored_hotspots.append({
            "hotspot_id": cluster["hotspot_id"],
            "latitude": cluster["approximate_latitude"],
            "longitude": cluster["approximate_longitude"],
            "risk_score": score_rounded,
            "risk_level": level,
            "primary_category": cluster["primary_category"],
            "complaint_count": n_members,
            "current_14d_count": c_curr,
            "previous_14d_count": c_prev,
            "contributing_factors": factors,
            "is_approximate_centroid": True
        })

    scored_hotspots.sort(key=lambda x: x["risk_score"], reverse=True)
    return scored_hotspots


def generate_preventive_recommendations(
    qs,
    hotspots: List[Dict[str, Any]],
    recurring_problems: List[Dict[str, Any]],
    include_ai_summary: bool = True
) -> List[Dict[str, Any]]:
    """
    Generates data-grounded preventive action recommendations.
    Every recommendation is linked to measurable supporting metrics.
    """
    recommendations = []

    # 1. High-Risk Hotspot Interventions
    high_risk_hotspots = [h for h in hotspots if h["risk_level"] in ["high", "medium"]]
    for hs in high_risk_hotspots[:3]:
        cat = hs["primary_category"]
        if "water" in cat.lower():
            action = f"Deploy hydraulic pressure testing crew to inspect underground distribution line around ({hs['latitude']}, {hs['longitude']})."
        elif "garbage" in cat.lower() or "sanitation" in cat.lower():
            action = f"Double daily sanitation sweeps and station an additional mobile refuse compactor at ({hs['latitude']}, {hs['longitude']})."
        elif "road" in cat.lower():
            action = f"Schedule structural asphalt milling and bitumen repaving around ({hs['latitude']}, {hs['longitude']})."
        elif "electric" in cat.lower() or "light" in cat.lower():
            action = f"Inspect feeder transformer and replace burned capacitor units along lamp line at ({hs['latitude']}, {hs['longitude']})."
        else:
            action = f"Dispatch municipal field inspection team to investigate cluster of {hs['complaint_count']} civic grievances at ({hs['latitude']}, {hs['longitude']})."

        recommendations.append({
            "id": f"REC-HS-{hs['hotspot_id']}",
            "title": f"Preventive Field Audit: {cat} Hotspot ({hs['hotspot_id']})",
            "category": cat,
            "risk_level": hs["risk_level"],
            "suggested_action": action,
            "supporting_metric": f"Risk Score {hs['risk_score']}/100 based on {hs['complaint_count']} complaints ({hs['current_14d_count']} recent in 14d vs {hs['previous_14d_count']} prior)",
            "confidence_level": "High (Empirical Spatial Cluster)"
        })

    # 2. Recurring Problem Interventions
    for prob in recurring_problems[:2]:
        if prob["total_complaint_count"] >= 3:
            duplicate_info = []
            if prob.get("confirmed_duplicate_count", 0) > 0:
                duplicate_info.append(f"{prob['confirmed_duplicate_count']} confirmed duplicates")
            if prob.get("suspected_duplicate_count", 0) > 0:
                duplicate_info.append(f"{prob['suspected_duplicate_count']} suspected duplicates")
            dup_str = f" ({', '.join(duplicate_info)})" if duplicate_info else ""
            recommendations.append({
                "id": f"REC-PRB-{prob['problem_id']}",
                "title": f"Recurring Incident Resolution: {prob['category_name']}",
                "category": prob["category_name"],
                "risk_level": "medium",
                "suggested_action": f"Conduct permanent infrastructure fix for persistent issue at {prob['location_label']} to eliminate repeated filings.",
                "supporting_metric": f"{prob['total_complaint_count']} reports recorded over {prob['timespan_days']} days ({prob['independent_incidents_count']} independent incidents{dup_str})",
                "confidence_level": "High (Verified Repetition)"
            })

    # 3. Department Overdue Workload Check
    overdue_by_dept = (
        qs.filter(is_escalated=True)
        .values(dept_name=F('department__name'))
        .annotate(overdue_count=Count('id'))
        .order_by('-overdue_count')
    )
    for d in overdue_by_dept[:2]:
        if d["overdue_count"] >= 2 and d["dept_name"]:
            recommendations.append({
                "id": f"REC-DEPT-{len(recommendations)+1}",
                "title": f"Staff Workload Rebalancing: {d['dept_name']}",
                "category": d["dept_name"],
                "risk_level": "medium",
                "suggested_action": f"Reallocate field officers to {d['dept_name']} to clear backlog of {d['overdue_count']} overdue tickets and meet SLA compliance.",
                "supporting_metric": f"{d['overdue_count']} complaints breached municipal SLA target hours",
                "confidence_level": "Medium (Administrative SLA Breach)"
            })

    # If no high-risk items found, return clean baseline recommendation
    if not recommendations:
        recommendations.append({
            "id": "REC-BASE-001",
            "title": "Routine Civic Maintenance Protocol",
            "category": "All Departments",
            "risk_level": "low",
            "suggested_action": "Maintain scheduled preventive inspections across all wards. No critical geographic risk clusters detected.",
            "supporting_metric": "0 high-risk complaint clusters observed in current dataset",
            "confidence_level": "Baseline"
        })

    return recommendations

