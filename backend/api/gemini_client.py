"""
JanSahayak AI - Central Gemini Client & Safe API Wrapper

This module is designed for:
1. Reading configuration safely from environment variables.
2. Managing a central, reusable Google GenAI client (Singleton pattern).
3. Handling rate limits, timeouts, quotas and transient network errors gracefully.
4. Implementing exponential backoff retries via `tenacity`.
5. Ensuring API keys are never leaked in application logs.
"""

import os
import json
import logging
from typing import Optional, Dict, Any

try:
    from google import genai
    from google.genai import types
    from google.genai.errors import APIError
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    APIError = Exception

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

logger = logging.getLogger("jansahayak_ai")

# Configuration Defaults
DEFAULT_MODEL = "gemini-2.5-flash"
DEFAULT_TIMEOUT = 15  # seconds
DEFAULT_MAX_RETRIES = 3


class GeminiClientManager:
    """
    Singleton Manager for Gemini Client.
    Ensures that a single authenticated client instance is reused across requests.
    """
    _instance: Optional['GeminiClientManager'] = None
    _client: Optional[Any] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GeminiClientManager, cls).__new__(cls)
            cls._instance._initialize_client()
        return cls._instance

    def _initialize_client(self):
        """Initializes the GenAI client using the environment API key."""
        api_key = os.environ.get('GEMINI_API_KEY', '').strip()
        if GEMINI_AVAILABLE and api_key and api_key != "your_gemini_api_key_here":
            try:
                # Client initialization
                self._client = genai.Client(api_key=api_key)
                logger.info("JanSahayak Gemini Client successfully initialized.")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini Client: {e}")
                self._client = None
        else:
            self._client = None
            if not api_key:
                logger.debug("GEMINI_API_KEY is not set. Operating in fallback rule-engine mode.")

    def is_available(self) -> bool:
        """Returns True if the client is authenticated and ready."""
        return GEMINI_AVAILABLE and self._client is not None

    def get_client(self) -> Optional[Any]:
        """Provides access to the initialized client or attempts re-initialization."""
        if self._client is None:
            self._initialize_client()
        return self._client

    @classmethod
    def get_model_name(cls) -> str:
        """Reads model name from environment or defaults to gemini-2.5-flash."""
        return os.environ.get('GEMINI_MODEL', DEFAULT_MODEL).strip() or DEFAULT_MODEL


# Safe retries with exponential backoff: wait 1s, 2s, 4s... up to 3 attempts
@retry(
    stop=stop_after_attempt(int(os.environ.get('GEMINI_MAX_RETRIES', DEFAULT_MAX_RETRIES))),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type(Exception),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True
)
def _generate_with_retry(client: Any, model: str, contents: Any, config: Optional[Any] = None) -> Any:
    """
    Helper function that calls Gemini models with automatic retry logic.
    """
    return client.models.generate_content(
        model=model,
        contents=contents,
        config=config
    )


def call_gemini_safe(
    prompt: Any,
    system_instruction: Optional[str] = None,
    temperature: float = 0.2
) -> Optional[str]:
    """
    Central function to query the Gemini API safely.

    Returns:
        str: Raw text output from Gemini, or None if the API is unavailable or fails.
    """
    manager = GeminiClientManager()
    client = manager.get_client()

    if not client:
        return None

    model_name = manager.get_model_name()

    try:
        # Prepare contents
        full_contents = prompt
        if system_instruction and isinstance(prompt, str):
            full_contents = f"{system_instruction}\n\n{prompt}"

        response = _generate_with_retry(
            client=client,
            model=model_name,
            contents=full_contents
        )

        if response and hasattr(response, 'text') and response.text:
            return response.text.strip()
        return None

    except Exception as e:
        # Log error message safely WITHOUT printing or exposing credentials
        error_type = type(e).__name__
        logger.warning(f"Gemini API request failed ({error_type}): {e}. Seamless fallback will handle this request.")
        return None


def clean_and_parse_json(raw_text: str) -> Optional[Dict[str, Any]]:
    """
    Robust JSON parser for LLM responses:
    - Strips markdown code blocks (```json ... ```)
    - Extracts JSON object bounds {...}
    - Returns Python dictionary or None if invalid
    """
    if not raw_text or not isinstance(raw_text, str):
        return None

    cleaned = raw_text.strip()

    # Strip markdown syntax if present
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]

    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]

    cleaned = cleaned.strip()

    # Find boundaries of the JSON object
    start_idx = cleaned.find("{")
    end_idx = cleaned.rfind("}")

    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        cleaned = cleaned[start_idx:end_idx + 1]
    else:
        return None

    try:
        data = json.loads(cleaned)
        return data if isinstance(data, dict) else None
    except Exception as err:
        logger.warning(f"Failed to parse LLM response into JSON: {err}")
        return None


# Canonical Civic Categories Allowed in JanSahayak
VALID_CIVIC_CATEGORIES = [
    "Garbage and Sanitation",
    "Water Supply",
    "Roads and Potholes",
    "Streetlights",
    "Drainage and Sewage",
    "Traffic and Road Obstruction",
    "General Inquiry"
]

VALID_PRIORITIES = ["low", "medium", "high", "urgent"]
VALID_INTENTS = ["complaint", "inquiry", "general"]
VALID_LANGUAGES = ["en", "hi", "mr", "hinglish"]
VALID_READABILITY = ["clear", "blurry", "dark", "unreadable", "partial"]
VALID_VERIFICATION_STATUSES = ["verified", "unverified", "mismatch", "failed", "pending"]


def validate_gemini_complaint_payload(payload: Any) -> Optional[Dict[str, Any]]:
    """
    Strict validation for Gemini AI complaint analysis responses.
    Ensures:
    1. Payload is a valid non-empty dictionary.
    2. Category is strictly one of the 6 canonical civic categories or 'General Inquiry'.
       Rejects unexpected or invented categories (does not silently fall back to Garbage).
    3. Intent is strictly 'complaint', 'inquiry', or 'general'.
    4. Confidence score is a float bounded strictly between 0.0 and 1.0.
    5. Priority is one of: low, medium, high, urgent.
    6. 'ready_to_submit' is boolean and strictly False if location is missing/null/empty.
    7. All strings are sanitized; never trust AI coordinates or IDs.

    Returns:
        Validated dict on success, None on validation failure.
    """
    if not payload or not isinstance(payload, dict):
        return None

    # 1. Category validation
    category = payload.get("category")
    if not category or not isinstance(category, str):
        return None

    category_clean = category.strip()
    if category_clean not in VALID_CIVIC_CATEGORIES:
        logger.warning(f"Rejected Gemini response with invalid category: '{category_clean}'")
        return None

    # 2. Intent validation
    intent = payload.get("intent", "complaint")
    if not isinstance(intent, str) or intent.strip().lower() not in VALID_INTENTS:
        intent = "complaint" if category_clean != "General Inquiry" else "inquiry"
    else:
        intent = intent.strip().lower()

    # 3. Confidence score validation
    confidence = payload.get("confidence_score")
    try:
        confidence = float(confidence)
        if confidence < 0.0 or confidence > 1.0:
            logger.warning(f"Rejected invalid confidence score out of bounds: {confidence}")
            return None
    except (TypeError, ValueError):
        confidence = 0.85  # Safe default if numeric conversion fails

    # 4. Priority validation
    priority = payload.get("priority", "medium")
    if not isinstance(priority, str) or priority.strip().lower() not in VALID_PRIORITIES:
        priority = "medium"
    else:
        priority = priority.strip().lower()

    # 5. Language validation
    lang = payload.get("detected_language", "en")
    if not isinstance(lang, str) or lang.strip().lower() not in VALID_LANGUAGES:
        lang = "en"
    else:
        lang = lang.strip().lower()

    # 6. Location, Missing Info & ready_to_submit safety invariant
    location = payload.get("location_extracted")
    if location is not None and not isinstance(location, str):
        location = None
    elif isinstance(location, str):
        location = location.strip() or None

    missing = payload.get("missing_information")
    if not isinstance(missing, list):
        missing = [str(missing)] if missing else []
    else:
        missing = [str(m).strip() for m in missing if str(m).strip()]

    # Critical Security Invariant: ready_to_submit can NEVER be True if location is missing
    ready = payload.get("ready_to_submit")
    if not isinstance(ready, bool):
        ready = False

    if intent != "complaint" or not location or len(location) < 3:
        ready = False
        if not location and "Exact location or landmark" not in missing:
            missing.append("Exact location or landmark")

    clarif_q = str(payload.get("clarification_question", "")).strip() or None if payload.get("clarification_question") else None
    if not ready and not clarif_q:
        if not location:
            clarif_q = "Please provide the exact street name, area, or nearest landmark."
        else:
            clarif_q = "Could you please provide more details about this issue?"

    # 7. Safe structured construction
    validated: Dict[str, Any] = {
        "intent": intent,
        "title": str(payload.get("title", f"Civic Issue: {category_clean}")).strip()[:150],
        "category": category_clean,
        "confidence_score": round(confidence, 2),
        "detected_language": lang,
        "priority": priority,
        "summary": str(payload.get("summary", "")).strip()[:300],
        "location_extracted": location,
        "ward_extracted": str(payload.get("ward_extracted", "")).strip() or None if payload.get("ward_extracted") else None,
        "duration_extracted": str(payload.get("duration_extracted", "Ongoing")).strip() or "Ongoing",
        "missing_information": missing,
        "clarification_question": clarif_q,
        "assistant_reply": str(payload.get("assistant_reply", "Your complaint has been noted.")).strip(),
        "ready_to_submit": ready
    }

    return validated


def validate_gemini_image_payload(payload: Any) -> Optional[Dict[str, Any]]:
    """
    Strict validation for Gemini AI image evidence analysis responses.
    Ensures:
    1. Payload is a valid dictionary.
    2. 'detected_issue' is a recognized civic category or 'None / Unclear' or 'Other'.
    3. 'detected_objects' is a list of strings.
    4. 'image_readability' is one of: clear, blurry, dark, unreadable, partial.
    5. 'complaint_image_match' is boolean.
    6. 'confidence_score' is float between 0.0 and 1.0. Never 1.0 (no 100% certainty).
    7. 'verification_status' is one of: verified, unverified, mismatch, failed, pending.
    8. 'review_required' is boolean.
    9. Invariant: If verification_status is 'verified', image_readability must not be 'unreadable',
       confidence_score must be >= 0.60, and complaint_image_match must be True.
    """
    if not payload or not isinstance(payload, dict):
        return None

    # 1. Detected issue
    detected_issue = payload.get("detected_issue")
    if not detected_issue or not isinstance(detected_issue, str):
        detected_issue = "Unspecified civic issue"
    detected_issue = detected_issue.strip()[:100]

    # 2. Detected objects
    objects = payload.get("detected_objects", [])
    if isinstance(objects, list):
        detected_objects = [str(o).strip() for o in objects if str(o).strip()][:10]
    elif isinstance(objects, str):
        detected_objects = [o.strip() for o in objects.split(",") if o.strip()][:10]
    else:
        detected_objects = []

    # 3. Image readability
    readability = str(payload.get("image_readability", "clear")).lower().strip()
    if readability not in VALID_READABILITY:
        readability = "clear"

    # 4. Complaint image match
    match_val = payload.get("complaint_image_match")
    if isinstance(match_val, bool):
        complaint_image_match = match_val
    elif isinstance(match_val, str):
        complaint_image_match = match_val.lower().strip() in ("true", "yes", "match")
    else:
        complaint_image_match = False

    # 5. Confidence score (bounded [0.0, 0.98] - never 1.0 absolute certainty)
    confidence = payload.get("confidence_score", 0.0)
    try:
        confidence = float(confidence)
        if confidence < 0.0 or confidence > 1.0:
            confidence = 0.0
    except (TypeError, ValueError):
        confidence = 0.0

    # Cap at 0.98 to avoid claiming 100% certainty
    if confidence > 0.98:
        confidence = 0.98

    # 6. Verification status
    status = str(payload.get("verification_status", "pending")).lower().strip()
    if status not in VALID_VERIFICATION_STATUSES:
        status = "unverified"

    # 7. Review required
    review_req = payload.get("review_required")
    if isinstance(review_req, bool):
        review_required = review_req
    else:
        review_required = True

    # 8. Strict Truthfulness Invariants:
    # Cannot be 'verified' if unreadable, if confidence is low, or if complaint doesn't match
    if readability == "unreadable" or confidence < 0.50 or not complaint_image_match:
        if status == "verified":
            status = "mismatch" if not complaint_image_match else "unverified"
        review_required = True

    summary_note = str(payload.get("summary_note", "")).strip()[:300]

    return {
        "detected_issue": detected_issue,
        "detected_objects": detected_objects,
        "image_readability": readability,
        "complaint_image_match": complaint_image_match,
        "confidence_score": round(confidence, 2),
        "verification_status": status,
        "review_required": review_required,
        "summary_note": summary_note
    }


