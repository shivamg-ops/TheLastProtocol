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
    if not raw_text:
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

    try:
        return json.loads(cleaned)
    except Exception as err:
        logger.warning(f"Failed to parse LLM response into JSON: {err}")
        return None

