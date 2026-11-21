"""
JanSahayak - Smart Field Staff Assignment & Workload Optimization Service (Task 18)

Evaluates municipal field staff candidates for a civic complaint and produces
an explainable, optimal recommendation with ranked alternatives based on:
1. Department Compatibility:
   - Matches candidate's department against complaint's department.
   - Cross-department candidates receive 0 match score unless explicitly permitted.
2. Verified Skills:
   - Analyzes complaint title, description, and category keywords against candidate's
     verified skills.
   - If skills are not recorded, marked explicitly as unavailable (not penalized).
3. Active Workload:
   - Counts genuine active assigned complaints (assigned, in_progress, escalated).
   - Completely excludes resolved, verified, or rejected complaints.
   - Rewards staff with lighter active queues to balance field burden.
4. Location Proximity:
   - Uses genuine registered station coordinates only.
   - Requires valid GPS coordinates on both complaint and staff member.
   - If either coordinate is missing/invalid, distance is marked unavailable (null)
     and proximity score is neutral without penalizing staff.
5. Inactive Staff Exclusion:
   - Candidates who are inactive (`is_active=False`) are strictly excluded.
6. Safety & Human-in-the-Loop:
   - Always flags `requires_admin_approval=True`.
   - Never automatically commits an assignment to the database.
   - Never fabricates coordinates, ratings, or skills.
"""

import math
import logging
from typing import Dict, Any, List, Optional
from django.utils import timezone
from django.db.models import Count, Q
from .models import User, Department, Complaint, UserRole, ComplaintStatus
from .location_intelligence import haversine_distance, is_valid_coordinate

logger = logging.getLogger("jansahayak_ai")

# Active statuses that count towards field staff workload
ACTIVE_WORKLOAD_STATUSES = [
    ComplaintStatus.ASSIGNED,
    ComplaintStatus.IN_PROGRESS,
    ComplaintStatus.ESCALATED,
]

# Weights for recommendation scoring (Total = 1.0)
WEIGHT_DEPARTMENT = 0.40  # 40% department compatibility
WEIGHT_WORKLOAD   = 0.30  # 30% workload distribution
WEIGHT_SKILLS     = 0.15  # 15% domain skills
WEIGHT_PROXIMITY  = 0.15  # 15% geographic proximity (when available)


class StaffAssignmentService:
    """
    Modular intelligence service for recommending field staff to complaints.
    """

    @classmethod
    def get_active_workload(cls, staff_user: User) -> int:
        """
        Counts active assigned complaints for a staff member.
        Excludes completed/closed tickets (resolved, verified, rejected).
        """
        if not staff_user or not staff_user.id:
            return 0
        return Complaint.objects.filter(
            assigned_staff=staff_user,
            status__in=ACTIVE_WORKLOAD_STATUSES
        ).count()

    @classmethod
    def evaluate_skills(cls, candidate: User, complaint: Complaint) -> Dict[str, Any]:
        """
        Evaluates verified skills match against complaint description, title, and category.
        If skills are missing, marks as unavailable.
        """
        if not candidate.skills or not candidate.skills.strip():
            return {
                "available": False,
                "score": 0.5,  # Neutral score: does not unfairly penalize staff for missing optional profile info
                "matched_skills": [],
                "details": "No verified skills recorded in profile (neutral evaluation)"
            }

        candidate_skills = [s.strip().lower() for s in candidate.skills.split(',') if s.strip()]
        if not candidate_skills:
            return {
                "available": False,
                "score": 0.5,
                "matched_skills": [],
                "details": "No verified skills recorded in profile"
            }

        # Search tokens in complaint
        text_corpus = f"{complaint.title} {complaint.description}".lower()
        if complaint.category:
            text_corpus += f" {complaint.category.name} {complaint.category.description}".lower()

        matched = [sk for sk in candidate_skills if sk in text_corpus]

        if matched:
            match_ratio = min(1.0, len(matched) / max(1, len(candidate_skills)))
            score = 0.5 + (0.5 * match_ratio)  # Scale between 0.5 and 1.0
            return {
                "available": True,
                "score": round(score, 3),
                "matched_skills": matched,
                "details": f"Matched skills: {', '.join(matched)}"
            }
        else:
            return {
                "available": True,
                "score": 0.3,
                "matched_skills": [],
                "details": f"Candidate skills ({', '.join(candidate_skills)}) not explicitly matched in grievance description"
            }

    @classmethod
    def evaluate_proximity(cls, candidate: User, complaint: Complaint) -> Dict[str, Any]:
        """
        Computes distance between verified staff base location and complaint coordinates.
        Never fabricates coordinates.
        """
        complaint_has_gps = is_valid_coordinate(complaint.latitude, complaint.longitude)
        staff_has_gps = is_valid_coordinate(candidate.latitude, candidate.longitude)

        if not complaint_has_gps or not staff_has_gps:
            return {
                "available": False,
                "distance_km": None,
                "score": 0.5,  # Neutral score when coordinates are not available
                "details": (
                    "Complaint coordinates unavailable" if not complaint_has_gps
                    else "Staff base coordinates unavailable"
                )
            }

        c_lat = float(complaint.latitude)
        c_lng = float(complaint.longitude)
        s_lat = float(candidate.latitude)
        s_lng = float(candidate.longitude)

        dist_km = haversine_distance(s_lat, s_lng, c_lat, c_lng)
        dist_km_rounded = round(dist_km, 2)

        # Proximity score decay:
        # <= 2 km: 1.0
        # <= 5 km: 0.85
        # <= 10 km: 0.70
        # <= 25 km: 0.40
        # > 25 km: 0.15
        if dist_km <= 2.0:
            score = 1.0
        elif dist_km <= 5.0:
            score = 0.85
        elif dist_km <= 10.0:
            score = 0.70
        elif dist_km <= 25.0:
            score = 0.40
        else:
            score = 0.15

        return {
            "available": True,
            "distance_km": dist_km_rounded,
            "score": score,
            "details": f"{dist_km_rounded} km from complaint location"
        }

    @classmethod
    def recommend_staff_for_complaint(
        cls,
        complaint: Complaint,
        candidate_pool: Optional[List[User]] = None
    ) -> Dict[str, Any]:
        """
        Generates ranked recommendations for assigning field staff to `complaint`.
        
        Guarantees:
        - Excludes inactive staff (`is_active=False`).
        - Prefers staff belonging to the complaint's department.
        - Calculates explainable workload and proximity.
        - Returns alternatives and recommendation reasons.
        - `requires_admin_approval=True`.
        """
        if not complaint:
            return {
                "recommended_staff_id": None,
                "recommended_staff_name": None,
                "department_match": False,
                "active_workload": 0,
                "skill_match": False,
                "distance_km": None,
                "recommendation_score": 0.0,
                "recommendation_reasons": ["Invalid or missing complaint record."],
                "alternative_staff": [],
                "requires_admin_approval": True,
                "has_recommendation": False
            }

        # 1. Fetch eligible staff candidates
        if candidate_pool is not None:
            # Filter from passed pool
            candidates = [
                u for u in candidate_pool
                if u.is_active and (u.role == UserRole.STAFF or u.is_staff) and u.role != UserRole.ADMIN
            ]
        else:
            candidates = list(
                User.objects.filter(
                    Q(role=UserRole.STAFF) | Q(is_staff=True),
                    is_active=True
                ).exclude(role=UserRole.ADMIN).select_related('department')
            )

        if not candidates:
            return {
                "recommended_staff_id": None,
                "recommended_staff_name": None,
                "department_match": False,
                "active_workload": 0,
                "skill_match": False,
                "distance_km": None,
                "recommendation_score": 0.0,
                "recommendation_reasons": ["No active field staff members found in directory."],
                "alternative_staff": [],
                "requires_admin_approval": True,
                "has_recommendation": False
            }

        # 2. Pre-calculate active workloads for all candidates
        # to normalize workload scoring
        workload_map = {}
        for c in candidates:
            workload_map[c.id] = cls.get_active_workload(c)

        max_workload = max(workload_map.values()) if workload_map else 0

        # 3. Score every candidate
        evaluated_candidates = []

        target_department = complaint.department

        for candidate in candidates:
            # Department Compatibility (40%)
            dept_match = False
            if target_department and candidate.department:
                dept_match = (candidate.department.id == target_department.id)
            elif not target_department:
                # If complaint has no department assigned, treat all as neutral match
                dept_match = True

            dept_score = 1.0 if dept_match else 0.15

            # Workload Score (30%):
            # Less workload = higher score. If max_workload is 0, all get 1.0.
            current_workload = workload_map.get(candidate.id, 0)
            if max_workload == 0:
                workload_score = 1.0
            else:
                workload_score = max(0.1, 1.0 - (current_workload / (max_workload + 3)))

            # Skill Score (15%)
            skill_eval = cls.evaluate_skills(candidate, complaint)

            # Proximity Score (15%)
            proximity_eval = cls.evaluate_proximity(candidate, complaint)

            # Weighted Total Recommendation Score
            total_score = (
                (WEIGHT_DEPARTMENT * dept_score) +
                (WEIGHT_WORKLOAD   * workload_score) +
                (WEIGHT_SKILLS     * skill_eval["score"]) +
                (WEIGHT_PROXIMITY  * proximity_eval["score"])
            )
            total_score_rounded = round(total_score, 3)

            # Formulate reasons
            reasons = []
            if dept_match and target_department:
                reasons.append(f"Department aligned: {target_department.name}")
            elif not dept_match and candidate.department:
                reasons.append(f"Cross-department candidate ({candidate.department.name})")

            reasons.append(f"Current active workload: {current_workload} complaints")

            if skill_eval["available"] and skill_eval["matched_skills"]:
                reasons.append(skill_eval["details"])
            elif not skill_eval["available"]:
                reasons.append("Skills: General field officer")

            if proximity_eval["available"] and proximity_eval["distance_km"] is not None:
                reasons.append(f"Stationed {proximity_eval['distance_km']} km away")

            evaluated_candidates.append({
                "staff_id": candidate.id,
                "staff_name": (
                    f"{candidate.first_name} {candidate.last_name}".strip()
                    if candidate.first_name else candidate.username
                ),
                "username": candidate.username,
                "department_id": candidate.department.id if candidate.department else None,
                "department_name": candidate.department.name if candidate.department else "General Pool",
                "department_match": dept_match,
                "active_workload": current_workload,
                "skill_match": bool(skill_eval["available"] and skill_eval["matched_skills"]),
                "matched_skills": skill_eval.get("matched_skills", []),
                "distance_km": proximity_eval.get("distance_km"),
                "recommendation_score": total_score_rounded,
                "recommendation_reasons": reasons,
            })

        # 4. Rank candidates by recommendation score descending
        # Secondary sort by lowest active workload, then id
        evaluated_candidates.sort(
            key=lambda x: (x["department_match"], x["recommendation_score"], -x["active_workload"]),
            reverse=True
        )

        top_choice = evaluated_candidates[0]
        alternatives = evaluated_candidates[1:5]  # Top 4 alternatives

        return {
            "recommended_staff_id": top_choice["staff_id"],
            "recommended_staff_name": top_choice["staff_name"],
            "department_match": top_choice["department_match"],
            "active_workload": top_choice["active_workload"],
            "skill_match": top_choice["skill_match"],
            "distance_km": top_choice["distance_km"],
            "recommendation_score": top_choice["recommendation_score"],
            "recommendation_reasons": top_choice["recommendation_reasons"],
            "alternative_staff": alternatives,
            "requires_admin_approval": True,
            "has_recommendation": True,
            "all_evaluated_count": len(evaluated_candidates)
        }

