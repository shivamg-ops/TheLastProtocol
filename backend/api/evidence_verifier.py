"""
JanSahayak - AI Evidence Verification & Trust Score Service

Evaluates civic grievance evidence across multiple verifiable signals:
1. File Integrity & Image Readability (PIL verify).
2. Gemini Multimodal Analysis (Issue detection, description match, confidence).
3. YOLO Object Detection (Bounding-box verification of visible civic damage).
4. Duplicate Image Analysis (Exact SHA-256 and perceptual pHash distance).
5. Cross-Model Agreement / Disagreement (Between Gemini description and YOLO detections).

Truthfulness & Safety Invariants:
- A high trust score only indicates consistency across available automated checks.
- It NEVER claims or proves the image is genuine or legally authenticated.
- It NEVER claims to detect deepfakes, photoshop manipulation, or GPS location validity.
- Missing signals (e.g. YOLO model missing or Gemini unavailable) are treated as neutral/unavailable,
  NEVER as positive confirmation.
- Disagreement between models automatically reduces trust and flags `review_required=True`.
- Duplicate evidence flags `review_required=True`, NEVER automatic complaint rejection.
- Clearly outputs:
  'verified' | 'unverified' | 'inconclusive' | 'flagged' | 'unavailable' | 'not_checked'
"""

import os
import logging
from typing import Dict, Any, Optional, List
from PIL import Image

logger = logging.getLogger("jansahayak_ai")


class EvidenceVerifier:
    """
    Modular Multi-Signal Evidence Verification & Trust Score Specialist.
    """

    @classmethod
    def verify_evidence(
        cls,
        image_file_path: Optional[str] = None,
        complaint_text: str = "",
        complaint_category: str = "",
        current_evidence_id: Optional[int] = None,
        current_complaint_id: Optional[int] = None,
        api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes comprehensive evidence verification and computes an explainable trust score.
        """
        review_reasons: List[str] = []
        verification_reasons: List[str] = []

        # 1. Missing / Non-Existent Evidence Check
        if not image_file_path:
            return {
                "evidence_status": "not_checked",
                "trust_score": 0.0,
                "verification_reasons": ["No evidence file supplied for verification."],
                "gemini_result": None,
                "yolo_result": None,
                "duplicate_result": None,
                "review_required": False,
                "review_reasons": [],
                "summary": "No evidence attached to evaluate."
            }

        if not os.path.exists(image_file_path):
            return {
                "evidence_status": "flagged",
                "trust_score": 0.0,
                "verification_reasons": ["Evidence file could not be found on server disk."],
                "gemini_result": None,
                "yolo_result": None,
                "duplicate_result": None,
                "review_required": True,
                "review_reasons": ["Evidence file missing from disk."],
                "summary": "Verification failed: file missing."
            }

        # 2. File Integrity & Readability Verification via PIL
        is_readable = False
        try:
            with Image.open(image_file_path) as img:
                img.verify()
            is_readable = True
            verification_reasons.append("Image file format and binary integrity verified.")
        except Exception as e:
            review_reasons.append(f"Corrupted or invalid image file: {e}")
            return {
                "evidence_status": "flagged",
                "trust_score": 0.0,
                "verification_reasons": ["File integrity check failed."],
                "gemini_result": None,
                "yolo_result": None,
                "duplicate_result": None,
                "review_required": True,
                "review_reasons": review_reasons,
                "summary": "Corrupted or unreadable image uploaded."
            }

        # 3. Duplicate Detection Signal (SHA-256 + pHash)
        from .ai_service import detect_duplicate_evidence
        dup_res = detect_duplicate_evidence(
            image_file_path=image_file_path,
            current_evidence_id=current_evidence_id,
            current_complaint_id=current_complaint_id
        )

        is_duplicate = dup_res.get("is_duplicate", False)
        if is_duplicate:
            dup_type = dup_res.get("duplicate_type", "exact")
            dup_score = dup_res.get("similarity_score", 1.0)
            review_reasons.append(
                f"Duplicate evidence detected ({dup_type} match, similarity {int(dup_score*100)}% with evidence #{dup_res.get('matched_evidence_id')})."
            )

        # 4. Gemini Multimodal Analysis Signal
        from .ai_service import analyze_image_evidence
        gemini_res = analyze_image_evidence(
            image_file_path=image_file_path,
            complaint_text=complaint_text,
            complaint_category=complaint_category,
            api_key=api_key
        )

        gemini_available = (gemini_res.get("status") == "success")
        gemini_match = gemini_res.get("complaint_image_match", False)
        gemini_conf = gemini_res.get("confidence_score", 0.0)
        gemini_readability = gemini_res.get("image_readability", "partial")

        if gemini_available:
            if gemini_match:
                verification_reasons.append(
                    f"Gemini confirmed visual consistency with grievance (Confidence: {int(gemini_conf*100)}%)."
                )
            else:
                review_reasons.append("Gemini flagged mismatch between complaint description and photo content.")
            if gemini_readability in ["blurry", "dark", "unreadable"]:
                review_reasons.append(f"Gemini reported poor image readability: {gemini_readability}.")
        else:
            verification_reasons.append("Gemini vision analysis unavailable; automated multimodal check skipped.")

        # 5. YOLO Object Detection Signal
        from .yolo_detector import YOLODetector
        yolo_res = YOLODetector().detect(image_path=image_file_path)

        yolo_status = yolo_res.get("detection_status")
        yolo_detected = yolo_res.get("detected_objects", [])
        yolo_conf = yolo_res.get("confidence", 0.0)
        yolo_class = yolo_res.get("class_name")

        if yolo_status == "success" and yolo_detected:
            verification_reasons.append(f"YOLO detected civic object '{yolo_class}' (Confidence: {int(yolo_conf*100)}%).")
        elif yolo_status == "model_not_found":
            verification_reasons.append("YOLO custom civic weights not configured; local bounding-box check skipped.")
        elif yolo_status == "no_detections":
            verification_reasons.append("YOLO did not detect civic damage objects meeting threshold.")

        # 6. Cross-Model Agreement Check
        # Check if Gemini and YOLO contradict each other
        if gemini_available and yolo_status == "success":
            # If YOLO found a positive object (e.g. pothole) but Gemini claims mismatch
            if not gemini_match and yolo_conf >= 0.70:
                review_reasons.append(f"Model Disagreement: YOLO identified '{yolo_class}' but Gemini flagged complaint mismatch.")
            elif gemini_match and yolo_status == "no_detections" and gemini_conf >= 0.90:
                # Moderate note: Gemini saw issue, but YOLO didn't detect bounding box
                pass

        # 7. Explainable Trust Score Computation
        # Score components:
        # File Integrity: 0.20 (Prerequisite base)
        # Gemini Match: up to 0.45
        # YOLO Detection: up to 0.25
        # Duplicate Penalty: -0.40
        # Disagreement Penalty: -0.25
        score = 0.0

        if is_readable:
            score += 0.20

        # Gemini contribution
        if gemini_available:
            if gemini_match:
                score += min(0.45, gemini_conf * 0.45)
            else:
                score -= 0.20  # Penalty for explicit visual mismatch
        # If Gemini is unavailable, do NOT give points (missing is NOT positive evidence)

        # YOLO contribution
        if yolo_status == "success" and yolo_detected:
            score += min(0.25, yolo_conf * 0.25)
        # If YOLO model is missing or no detections, score is not boosted

        # Duplicate Penalty
        if is_duplicate:
            score -= 0.35

        # Disagreement Penalty
        if gemini_available and yolo_status == "success" and not gemini_match:
            score -= 0.20

        # Clamp trust score strictly between 0.0 and 0.95
        # (Never 1.0 because AI cannot legally authenticate real-world events or detect all edits)
        trust_score = round(max(0.0, min(0.95, score)), 2)

        # 8. Determine Final Evidence Status & Review Requirement
        review_required = False

        if is_duplicate:
            evidence_status = "flagged"
            review_required = True
        elif gemini_available and not gemini_match:
            evidence_status = "flagged"
            review_required = True
        elif not gemini_available and yolo_status in ["model_not_found", "no_detections"]:
            # All automated visual models were unavailable
            evidence_status = "inconclusive"
            review_required = True
            review_reasons.append("Automated visual models unavailable or inconclusive; manual inspection required.")
        elif trust_score >= 0.60:
            evidence_status = "verified"
            review_required = False
        else:
            evidence_status = "unverified"
            review_required = True
            review_reasons.append("Evidence trust score is below the verification threshold (0.60).")

        return {
            "evidence_status": evidence_status,
            "trust_score": trust_score,
            "verification_reasons": verification_reasons,
            "gemini_result": {
                "available": gemini_available,
                "detected_issue": gemini_res.get("detected_issue"),
                "complaint_image_match": gemini_match,
                "confidence_score": gemini_conf,
                "image_readability": gemini_readability
            },
            "yolo_result": {
                "available": (yolo_status in ["success", "no_detections"]),
                "detection_status": yolo_status,
                "detected_objects": yolo_detected,
                "class_name": yolo_class,
                "confidence": yolo_conf
            },
            "duplicate_result": {
                "is_duplicate": is_duplicate,
                "duplicate_type": dup_res.get("duplicate_type", "none"),
                "similarity_score": dup_res.get("similarity_score", 0.0),
                "matched_evidence_id": dup_res.get("matched_evidence_id")
            },
            "review_required": review_required,
            "review_reasons": review_reasons,
            "summary": f"[{evidence_status.upper()}] Trust score {int(trust_score*100)}/100. " + (
                "Review required." if review_required else "Passed automated consistency checks."
            )
        }

