
import json

from google.genai import types
from app.ai.gemini_client import (
    client,
    MODEL_NAME,
    COMPLAINT_SCHEMA
)


QUESTION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "question": {
            "type": "STRING"
        },
        "needs_clarification": {
            "type": "BOOLEAN"
        }
    },
    "required": [
        "question",
        "needs_clarification"
    ]
}


def generate_clarification_question(complaint_data):

    missing = complaint_data.get("missing_information", [])

    if not missing:
        return {
            "question": "Your complaint details are complete. Would you like to review them?",
            "needs_clarification": False
        }

    prompt = f"""
    You are JanSahayak AI, a multilingual civic assistant.

    Current complaint:
    {json.dumps(complaint_data, ensure_ascii=False)}

    Missing information:
    {json.dumps(missing, ensure_ascii=False)}

    Instructions:
    1. Ask only ONE useful follow-up question.
    2. Use the citizen's language: Hindi, Marathi, English or Hinglish.
    3. Prioritise the exact location if it is missing.
    4. Be polite and simple.
    5. Do not ask for information already provided.
    6. Do not invent any details.
    """

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=QUESTION_SCHEMA
        )
    )

    if not response.text:
        raise ValueError("Gemini returned an empty clarification question")

    return json.loads(response.text)


def update_complaint(complaint_data, citizen_reply):

    prompt = f"""
    You are JanSahayak AI's complaint update assistant.

    EXISTING COMPLAINT:
    {json.dumps(complaint_data, ensure_ascii=False)}

    CITIZEN'S NEW REPLY:
    {citizen_reply}

    Update the existing complaint using the citizen's reply.

    Rules:
    1. Preserve all previously confirmed information.
    2. Update only fields supported by the new reply.
    3. Never invent a location, duration or other detail.
    4. Do not replace existing information with null.
    5. Recalculate missing_information based on the complete complaint.
    6. Set needs_clarification to true if important details are still missing.
    7. Keep the original complaint category unless the new reply clearly corrects it.
    8. Return the complete updated complaint using the provided schema.
    """

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=COMPLAINT_SCHEMA
        )
    )

    if not response.text:
        raise ValueError("Gemini returned an empty complaint update")

    return json.loads(response.text)
