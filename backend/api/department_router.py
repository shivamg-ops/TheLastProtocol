"""
JanSahayak - Intelligent Department / Team Routing Service

Evaluates incoming complaints and recommends the most suitable configured
department or team using multiple weighted signals:
1. Complaint Category mapping (Primary organizational relation).
2. Complaint Description keywords & intent (Cross-cutting / nuanced issues).
3. Image Analysis visual findings (e.g. detected objects, detected issue).
4. Priority & Urgency calibration (Escalates severe hazards).
5. Configurable department keywords / domain definitions.

Safety & Truthfulness Guarantees:
- Never invents departments, staff IDs, or team IDs.
- Only suggests departments that genuinely exist and are active in the database.
- If no suitable mapping or low confidence (<0.50), flags requires_manual_review=True.
- Does NOT automatically assign staff or mark complaints as assigned.
- Does NOT submit complaints to government departments.
- Operates completely deterministically without requiring Gemini (works offline / on API failure).
"""

import re
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger("jansahayak_ai")

# Minimum confidence required to recommend without mandating manual review
CONFIDENCE_THRESHOLD = 0.65

# Configurable domain keyword dictionaries for dynamic matching
# (Maps semantic concepts to standard civic departments)
DEPARTMENT_KEYWORD_PATTERNS = {
    "water": [
        "water", "leak", "pipeline", "pipe", "tap", "drinking", "burst", "supply",
        "जल", "पाणी", "पेयजल", "पाइप", "नळ", "jal", "pressure"
    ],
    "electrical": [
        "wire", "light", "streetlight", "electric", "pole", "shock", "current",
        "dark", "bulb", "बिजली", "खंभा", "स्ट्रीट लाइट", "दिवा", "अंधार", "batti", "roshni"
    ],
    "waste": [
        "garbage", "trash", "waste", "dump", "safai", "kachra", "kooda", "dustbin",
        "smell", "stench", "litter", "कचरा", "कूड़ा", "सफाई", "घाण", "दुर्गंधी", "sanitation"
    ],
    "sanitation": [
        "garbage", "trash", "waste", "dump", "safai", "kachra", "kooda", "dustbin",
        "smell", "stench", "litter", "कचरा", "कूड़ा", "सफाई", "घाण", "दुर्गंधी"
    ],
    "roads": [
        "pothole", "crater", "asphalt", "road", "tar", "footpath", "sidewalk",
        "गड्ढा", "सड़क", "रस्ता", "खड्डा", "खड्डे", "gaddha", "sadak"
    ],
    "road": [
        "pothole", "crater", "asphalt", "road", "tar", "footpath", "sidewalk",
        "गड्ढा", "सड़क", "रस्ता", "खड्डा", "खड्डे", "gaddha", "sadak"
    ],
    "drainage": [
        "drain", "sewage", "gutter", "manhole", "overflow", "stagnant", "smell",
        "नाली", "नाला", "गटार", "सीवर", "गंदा पानी", "sewer", "waterlogging"
    ],
    "traffic": [
        "traffic", "parking", "blocked", "obstruction", "encroachment", "jam",
        "वाहतूक", "अतिक्रमण", "जाम", "ट्रैफिक"
    ]
}


class DepartmentRouter:
    """
    Modular department and team routing specialist for JanSahayak.
    """

    @classmethod
    def route_complaint(
        cls,
        complaint=None,
        category=None,
        description: str = "",
        detected_issue: str = "",
        priority: str = "medium",
        threshold: float = CONFIDENCE_THRESHOLD
    ) -> Dict[str, Any]:
        """
        Determines the optimal department recommendation for a complaint.
        """
        from .models import Department, ComplaintCategory

        # 1. Extract context from complaint object if provided
        target_description = description
        target_category = category
        target_priority = priority

        if complaint:
            target_description = complaint.description or description
            target_category = complaint.category or category
            target_priority = complaint.priority or priority

        # 2. Query active configured departments from the database
        active_departments = list(Department.objects.filter(is_active=True))
        if not active_departments:
            return {
                "suggested_department": None,
                "suggested_team_id": None,
                "routing_confidence": 0.0,
                "routing_reason": "No active departments configured in the organization.",
                "alternative_departments": [],
                "requires_manual_review": True,
                "routing_status": "manual_review_required"
            }

        dept_scores: Dict[int, float] = {d.id: 0.0 for d in active_departments}
        dept_reasons: Dict[int, List[str]] = {d.id: [] for d in active_departments}

        desc_lower = (target_description or "").lower()
        issue_lower = (detected_issue or "").lower()

        # 3. Signal A: Direct Category Association (Strongest institutional signal)
        if target_category and hasattr(target_category, 'department') and target_category.department:
            cat_dept_id = target_category.department_id
            if cat_dept_id in dept_scores:
                dept_scores[cat_dept_id] += 0.50
                dept_reasons[cat_dept_id].append(f"Linked by primary category '{target_category.name}'")

        # 4. Signal B: Description Keyword Matching
        for dept in active_departments:
            d_name_lower = dept.name.lower()
            d_code_lower = dept.code.lower()

            # Match dept name tokens directly in text
            if d_name_lower in desc_lower or d_code_lower in desc_lower:
                dept_scores[dept.id] += 0.30
                dept_reasons[dept.id].append(f"Explicit mention of department '{dept.name}' in grievance text")

            # Match domain patterns across department name, code, or description
            for domain_key, keywords in DEPARTMENT_KEYWORD_PATTERNS.items():
                if domain_key in d_name_lower or domain_key in dept.description.lower():
                    matched_kw = [kw for kw in keywords if kw in desc_lower]
                    if matched_kw:
                        boost = min(0.55, len(matched_kw) * 0.15)
                        dept_scores[dept.id] += boost
                        dept_reasons[dept.id].append(f"Problem description matches {domain_key} indicators ({', '.join(matched_kw[:3])})")

        # 5. Signal C: Visual Evidence Issue Matching (From Image Analysis)
        if issue_lower:
            for dept in active_departments:
                d_name_lower = dept.name.lower()
                for domain_key, keywords in DEPARTMENT_KEYWORD_PATTERNS.items():
                    if domain_key in d_name_lower:
                        if any(kw in issue_lower for kw in keywords):
                            dept_scores[dept.id] += 0.25
                            dept_reasons[dept.id].append(f"Visual AI detected relevant condition: '{detected_issue}'")

        # 6. Priority / Severity Calibration
        if target_priority in ["high", "urgent"]:
            for dept_id in dept_scores:
                if dept_scores[dept_id] > 0.0:
                    dept_scores[dept_id] += 0.05

        # 7. Rank candidate departments
        sorted_depts = sorted(
            active_departments,
            key=lambda d: dept_scores.get(d.id, 0.0),
            reverse=True
        )

        top_dept = sorted_depts[0]
        top_score = min(round(dept_scores.get(top_dept.id, 0.0), 2), 1.0)
        top_reasons = dept_reasons.get(top_dept.id, [])

        # Gather alternatives (departments with non-zero scores)
        alternatives = [
            {
                "department_id": d.id,
                "department_name": d.name,
                "confidence": round(dept_scores[d.id], 2)
            }
            for d in sorted_depts[1:]
            if dept_scores[d.id] > 0.20
        ]

        # 8. Truthfulness & Confidence Gate
        if top_score < 0.40:
            # Low confidence / ambiguous issue
            return {
                "suggested_department": None,
                "suggested_team_id": None,
                "routing_confidence": top_score,
                "routing_reason": "Low confidence match: issue text does not distinctly map to a single department.",
                "alternative_departments": alternatives,
                "requires_manual_review": True,
                "routing_status": "manual_review_required"
            }

        requires_review = (top_score < threshold)
        reason_str = "; ".join(top_reasons) if top_reasons else f"Mapped based on institutional configuration for {top_dept.name}."

        return {
            "suggested_department": {
                "id": top_dept.id,
                "name": top_dept.name,
                "code": top_dept.code,
                "sla_hours": top_dept.sla_hours
            },
            "suggested_team_id": top_dept.id,  # Uses real department primary key (never fake IDs)
            "routing_confidence": top_score,
            "routing_reason": reason_str,
            "alternative_departments": alternatives,
            "requires_manual_review": requires_review,
            "routing_status": "manual_review_required" if requires_review else "routed"
        }
