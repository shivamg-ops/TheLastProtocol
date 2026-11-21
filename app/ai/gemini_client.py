
import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load environment variables
load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.5-flash-lite"
)

if not API_KEY:
    raise ValueError("Gemini API key not found in .env file")

# Initialize Gemini client
client = genai.Client(api_key=API_KEY)


# Structured complaint JSON schema
COMPLAINT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "problem_summary": {
            "type": "STRING"
        },
        "language": {
            "type": "STRING"
        },
        "category": {
            "type": "STRING",
            "enum": [
                "Garbage Collection",
                "Roads and Potholes",
                "Water Supply",
                "Drainage and Sewage",
                "Streetlights",
                "Other"
            ]
        },
        "duration": {
            "type": "STRING",
            "nullable": True
        },
        "urgency": {
            "type": "STRING",
            "enum": [
                "Low",
                "Medium",
                "High",
                "Critical"
            ]
        },
        "suggested_department": {
            "type": "STRING",
            "nullable": True
        },
        "location": {
            "type": "STRING",
            "nullable": True
        },
        "missing_information": {
            "type": "ARRAY",
            "items": {
                "type": "STRING"
            }
        },
        "needs_clarification": {
            "type": "BOOLEAN"
        }
    },
    "required": [
        "problem_summary",
        "language",
        "category",
        "duration",
        "urgency",
        "suggested_department",
        "location",
        "missing_information",
        "needs_clarification"
    ]
}


# Analyze citizen complaint
def analyze_complaint(complaint):

    prompt = f"""
    You are JanSahayak AI, a civic complaint analysis assistant.

    Analyze the following citizen complaint:

    {complaint}

    Instructions:
    1. Understand Hindi, English, Marathi and Hinglish.
    2. Extract only information supported by the complaint.
    3. Never invent location or duration.
    4. Suggest a general department, not an officially confirmed assignment.
    5. Identify missing information.
    6. Use Critical only for immediate serious danger.
    7. Return the information using the provided JSON schema.
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
        raise ValueError("Gemini returned an empty response")

    return response.text
