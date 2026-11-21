"""
JanSahayak - Multi-Signal Smart Duplicate Complaint Detector

Combines multiple signals to identify duplicate civic complaints:
1. Category Match (Binary gate / filter).
2. Location & Address Similarity (Fuzzy token matching, Ward/Zone, and Landmark overlap).
3. Complaint Description Similarity (Multilingual normalized token overlap & n-gram Jaccard).
4. Visual Evidence Similarity (Existing SHA-256 binary hash & pHash perceptual similarity).

Guarantees & Safeguards:
- Never invents complaint IDs or tracking IDs.
- Missing location is never treated as a matching location.
- Same category alone never marks complaints as duplicates.
- Never automatically rejects or deletes complaints.
- Returns comprehensive structured results with signal breakdowns.
"""

import re
import difflib
from datetime import timedelta
from typing import Dict, Any, Optional, List
from django.utils import timezone
import logging

logger = logging.getLogger("jansahayak_ai")

# Weights for multi-signal composite scoring
WEIGHT_TEXT = 0.40
WEIGHT_LOCATION = 0.35
WEIGHT_IMAGE = 0.25

# Threshold above which a complaint is flagged as possible duplicate
DUPLICATE_ALERT_THRESHOLD = 0.60


def normalize_multilingual_text(text: str) -> str:
    """
    Normalizes Hindi, Marathi, Hinglish, and English complaint strings.
    Strips punctuation, excessive whitespace, and lowercases latin tokens.
    """
    if not text:
        return ""
    text_clean = text.lower().strip()
    # Replace common punctuation while keeping Devanagari characters
    text_clean = re.sub(r'[\.,;:\-\_\(\)\[\]\{\}\"\'\!\?\/\\\+]', ' ', text_clean)
    # Collapse multiple whitespaces
    text_clean = re.sub(r'\s+', ' ', text_clean).strip()
    return text_clean


def compute_text_similarity(text1: str, text2: str) -> float:
    """
    Computes text similarity using token-based Jaccard overlap combined
    with SequenceMatcher ratio on normalized strings.
    """
    t1 = normalize_multilingual_text(text1)
    t2 = normalize_multilingual_text(text2)

    if not t1 or not t2:
        return 0.0

    if t1 == t2:
        return 1.0

    # 1. SequenceMatcher character-sequence ratio
    seq_ratio = difflib.SequenceMatcher(None, t1, t2).ratio()

    # 2. Token Jaccard index
    tokens1 = set(t1.split())
    tokens2 = set(t2.split())

    # Filter out common stop-words in Hindi/English/Hinglish
    stopwords = {
        'hai', 'me', 'mein', 'par', 'aur', 'ko', 'se', 'ka', 'ki', 'ke',
        'is', 'the', 'in', 'on', 'at', 'and', 'for', 'to', 'of', 'a', 'an',
        'आहे', 'नाही', 'आणि', 'च्या', 'वर', 'मध्ये', 'होता', 'होती'
    }
    filtered1 = {tok for tok in tokens1 if tok not in stopwords and len(tok) > 1}
    filtered2 = {tok for tok in tokens2 if tok not in stopwords and len(tok) > 1}

    if not filtered1 or not filtered2:
        jaccard = 0.0
    else:
        intersection = filtered1.intersection(filtered2)
        union = filtered1.union(filtered2)
        jaccard = len(intersection) / len(union) if union else 0.0

    # Weighted blend of sequence matching and keyword overlap
    similarity = round((0.4 * seq_ratio) + (0.6 * jaccard), 3)
    return min(max(similarity, 0.0), 1.0)


def compute_location_similarity(c1, c2) -> float:
    """
    Compares location details across two complaints:
    - Address string similarity
    - Landmark match
    - Ward / Zone match
    Missing location information yields 0.0 (never considered a match).
    """
    addr1 = getattr(c1, 'address', '') or ''
    addr2 = getattr(c2, 'address', '') or ''
    landmark1 = getattr(c1, 'landmark', '') or ''
    landmark2 = getattr(c2, 'landmark', '') or ''
    ward1 = getattr(c1, 'ward_or_zone', '') or ''
    ward2 = getattr(c2, 'ward_or_zone', '') or ''

    # If neither has address, missing location cannot match
    if (not addr1 or len(addr1.strip()) < 3) and (not addr2 or len(addr2.strip()) < 3):
        return 0.0

    scores = []

    # 1. Address similarity
    if addr1 and addr2 and len(addr1.strip()) >= 3 and len(addr2.strip()) >= 3:
        addr_sim = compute_text_similarity(addr1, addr2)
        scores.append(addr_sim)

    # 2. Landmark exact or partial match
    if landmark1 and landmark2:
        l1 = normalize_multilingual_text(landmark1)
        l2 = normalize_multilingual_text(landmark2)
        if l1 == l2:
            scores.append(1.0)
        elif l1 in l2 or l2 in l1:
            scores.append(0.85)
        else:
            scores.append(compute_text_similarity(l1, l2))

    # 3. Ward match
    if ward1 and ward2:
        w1 = ward1.lower().strip()
        w2 = ward2.lower().strip()
        if w1 == w2:
            scores.append(0.80)
        else:
            scores.append(0.0)

    if not scores:
        return 0.0

    return round(sum(scores) / len(scores), 3)


def compute_evidence_image_similarity(c1, c2) -> float:
    """
    Checks if evidence images between two complaints match via SHA-256 or pHash.
    Returns maximum similarity score (0.0 to 1.0).
    """
    if not hasattr(c1, 'pk') or not c1.pk or not hasattr(c2, 'pk') or not c2.pk:
        return 0.0

    if not hasattr(c1, 'evidences') or not hasattr(c2, 'evidences'):
        return 0.0

    try:
        evs1 = c1.evidences.filter(file_type='image')
        evs2 = c2.evidences.filter(file_type='image')
    except (ValueError, Exception):
        return 0.0

    max_sim = 0.0

    for e1 in evs1:
        # Check if e1 was already marked as duplicate of an evidence belonging to c2
        if e1.matched_evidence and e1.matched_evidence.complaint_id == c2.id:
            max_sim = max(max_sim, e1.similarity_score or 1.0)

        for e2 in evs2:
            # Exact SHA-256
            if e1.sha256_hash and e2.sha256_hash and e1.sha256_hash == e2.sha256_hash:
                return 1.0

            # Perceptual pHash
            if e1.phash and e2.phash:
                try:
                    import imagehash
                    h1 = imagehash.hex_to_hash(e1.phash)
                    h2 = imagehash.hex_to_hash(e2.phash)
                    dist = h1 - h2
                    sim = round(1.0 - (dist / 64.0), 3)
                    if sim > max_sim:
                        max_sim = sim
                except Exception:
                    continue

    return max_sim


class DuplicateDetector:
    """
    Intelligent Multi-Signal Duplicate Complaint Detector.
    """

    @classmethod
    def find_duplicate(
        cls,
        new_complaint,
        existing_complaints_queryset=None,
        days_window: int = 14,
        threshold: float = DUPLICATE_ALERT_THRESHOLD
    ) -> Dict[str, Any]:
        """
        Scans recent relevant complaints and returns a structured match verdict.
        """
        from .models import Complaint

        if existing_complaints_queryset is None:
            existing_complaints_queryset = Complaint.objects.all()

        # Sensible filtering: Only scan within active days window and same category
        cutoff_date = timezone.now() - timedelta(days=days_window)
        candidates = existing_complaints_queryset.filter(
            created_at__gte=cutoff_date
        )

        if new_complaint.id:
            candidates = candidates.exclude(id=new_complaint.id)

        # Gate 1: Category filter if category is specified
        if new_complaint.category:
            candidates = candidates.filter(category=new_complaint.category)

        best_match = None
        best_composite_score = 0.0
        best_signal_breakdown = {}
        best_reasons = []

        for candidate in candidates:
            # 1. Text Similarity
            text_sim = compute_text_similarity(new_complaint.description, candidate.description)

            # 2. Location Similarity
            loc_sim = compute_location_similarity(new_complaint, candidate)

            # 3. Image Evidence Similarity
            img_sim = compute_evidence_image_similarity(new_complaint, candidate)

            # Calculate composite score based on available signals
            reasons = []
            if text_sim >= 0.60:
                reasons.append(f"High description similarity ({int(text_sim*100)}%)")

            if loc_sim >= 0.70:
                reasons.append(f"Matching location / landmark ({int(loc_sim*100)}%)")
            elif loc_sim == 0.0:
                # Penalty: Same text in completely different locations should not easily trigger duplicates
                pass

            if img_sim >= 0.85:
                reasons.append(f"Visual evidence match ({int(img_sim*100)}%)")

            # Composite Formula:
            # If visual evidence matches exactly (1.0), it's almost certainly a duplicate
            if img_sim >= 0.95:
                composite = round(0.50 * img_sim + 0.30 * loc_sim + 0.20 * text_sim, 3)
            else:
                # Balanced weight across text, location, and optional image
                if img_sim > 0.0:
                    composite = round(
                        (WEIGHT_TEXT * text_sim) + (WEIGHT_LOCATION * loc_sim) + (WEIGHT_IMAGE * img_sim),
                        3
                    )
                else:
                    # No image attached: normalize text and location
                    composite = round((0.55 * text_sim) + (0.45 * loc_sim), 3)

            # Crucial Safety: Same category alone never marks duplicates
            # If location similarity is 0.0 (e.g. completely different places), cap score
            if loc_sim == 0.0 and img_sim < 0.80:
                composite = min(composite, 0.45)

            if composite > best_composite_score:
                best_composite_score = composite
                best_match = candidate
                best_reasons = reasons
                best_signal_breakdown = {
                    "text_similarity": text_sim,
                    "location_similarity": loc_sim,
                    "image_similarity": img_sim,
                    "composite_score": composite
                }

        is_duplicate = (best_match is not None and best_composite_score >= threshold)

        return {
            "is_possible_duplicate": is_duplicate,
            "similarity_score": best_composite_score,
            "matched_complaint_id": best_match.id if is_duplicate and best_match else None,
            "matched_tracking_id": best_match.tracking_id if is_duplicate and best_match else None,
            "match_reasons": best_reasons if is_duplicate else [],
            "signal_breakdown": best_signal_breakdown,
            "review_required": is_duplicate,
            "detection_status": "duplicate_suspect" if is_duplicate else "unique"
        }
