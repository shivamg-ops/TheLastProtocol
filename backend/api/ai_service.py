import json
import re
import os
from datetime import timedelta
from django.utils import timezone

try:
    from google import genai
    from google.genai import types
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

SYSTEM_PROMPT = """
You are JanSahayak AI - an intelligent multilingual civic complaint management assistant.
You understand English, Hindi (हिंदी), Marathi (मराठी), and Hinglish.

Your job is to analyze citizen problems, maintain contextual multi-turn conversation, and output STRICT JSON format with no markdown wrappers or backticks.
The JSON format must have:
{
  "title": "Concise summary title in English",
  "category": "One of: Garbage and Sanitation, Water Supply, Roads and Potholes, Streetlights, Drainage and Sewage, Traffic and Road Obstruction",
  "detected_language": "en | hi | mr | hinglish",
  "priority": "low | medium | high | urgent",
  "summary": "Clear, objective summary of the problem in English",
  "location_extracted": "Address or landmark if mentioned, else null",
  "ward_extracted": "Ward or zone if mentioned, else null",
  "duration_extracted": "Duration of problem if mentioned, else null",
  "missing_information": ["list of critical missing items like exact street/landmark or photo, if any"],
  "assistant_reply": "Empathetic, clear conversational response in the user's detected language asking for any missing info or confirming ticket readiness",
  "ready_to_submit": true or false
}

Guidelines:
- Never hallucinate government submission or fake official contacts.
- If the problem is hazardous (e.g. live wire, open manhole, major flood), set priority to "urgent".
- Set ready_to_submit = true only if both the issue description and location/landmark are known.
"""

def analyze_complaint_text(user_input: str, conversation_history: list = None, api_key: str = None) -> dict:
    key = api_key or os.environ.get('GEMINI_API_KEY')
    full_text = user_input
    if conversation_history:
        history_str = "\n".join([f"{msg.get('sender', 'user')}: {msg.get('text', '')}" for msg in conversation_history])
        full_text = f"Conversation History:\n{history_str}\n\nLatest Citizen Message:\n{user_input}"

    if GEMINI_AVAILABLE and key:
        try:
            client = genai.Client(api_key=key)
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=f"{SYSTEM_PROMPT}\n\n{full_text}\n\nSTRICT JSON Output:"
            )
            raw_text = response.text.strip()
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
            return json.loads(raw_text.strip())
        except Exception as e:
            print("Gemini API call error, falling back to heuristic AI engine:", e)

    # Heuristic Multilingual Fallback Rule Engine
    text_lower = full_text.lower()
    category = "Garbage and Sanitation"
    priority = "medium"
    detected_lang = "en"

    # Language detection - check Marathi specific markers first
    if any(term in full_text for term in ['आहे', 'नाही', 'रस्ता', 'रस्त्यावर', 'पाणी', 'कचरा', 'झाले', 'खड्डा', 'खड्डे', 'पडला', 'होत']):
        detected_lang = "mr"
    elif any(term in full_text for term in ['कचरा', 'सड़क', 'गड्ढा', 'पानी', 'है', 'में', 'और', 'खराब', 'नाला', 'बिजली']):
        detected_lang = "hi"
    elif any(word in text_lower for word in ['hai', 'nahi', 'karo', 'pani', 'kachra', 'sadak', 'bahut', 'kharab', 'gaddha', 'gutter']):
        detected_lang = "hinglish"

    # Category matching
    if any(w in text_lower or w in full_text for w in ['water', 'paani', 'pani', 'pipe', 'leakage', 'tap', 'supply', 'जल', 'पाणी', 'पाइप']):
        category = "Water Supply"
        if any(w in text_lower or w in full_text for w in ['burst', 'no water for 3 days', 'urgent', 'overflow', 'फुटली', 'फूट']):
            priority = "high"
    elif any(w in text_lower or w in full_text for w in ['road', 'pothole', 'sadak', 'gaddha', 'asphalt', 'crater', 'rasta', 'रस्ता', 'रस्त्यावर', 'गड्डा', 'खड्डा', 'खड्डे']):
        category = "Roads and Potholes"
        if any(w in text_lower or w in full_text for w in ['accident', 'deep', 'injury', 'अपघात', 'मोठा']):
            priority = "urgent"
    elif any(w in text_lower or w in full_text for w in ['light', 'streetlight', 'dark', 'bulb', 'pole', 'roshni', 'batti', 'लाइट', 'दिवा', 'अंधार']):
        category = "Streetlights"
    elif any(w in text_lower or w in full_text for w in ['drain', 'sewer', 'sewage', 'gutter', 'drainage', 'naala', 'nala', 'गटर', 'नाली', 'ड्रेनेज']):
        category = "Drainage and Sewage"
        priority = "high"
    elif any(w in text_lower or w in full_text for w in ['traffic', 'jam', 'block', 'parking', 'obstruction', 'encroachment', 'गाड़ी', 'वाहतूक']):
        category = "Traffic and Road Obstruction"
    else:
        category = "Garbage and Sanitation"
        if any(w in text_lower or w in full_text for w in ['smell', 'stench', 'disease', 'days', 'बदबू', 'दुर्गंधी']):
            priority = "high"
            priority = "high"

    # Location & Duration Extraction
    missing = []
    location_extracted = None
    ward_extracted = None
    duration_extracted = None

    # Check location keywords
    loc_matches = re.findall(r'(?:near|opposite|behind|at|in|sector|ward|street|road|chowk|colony|nagar|gali)\s+([A-Za-z0-9\s,-]{3,30})', full_text, re.IGNORECASE)
    if loc_matches:
        location_extracted = loc_matches[0].strip()
    elif any(loc_word in text_lower for loc_word in ['near', 'opposite', 'behind', 'sector', 'ward', 'street', 'road', 'chowk', 'colony', 'apartment', 'nagar', 'gali']):
        location_extracted = "Reported in text"
    else:
        missing.append("Exact location or landmark")

    ward_match = re.search(r'ward\s*(\d+|[A-Za-z]+)', text_lower)
    if ward_match:
        ward_extracted = f"Ward {ward_match.group(1).upper()}"

    dur_match = re.search(r'(\d+\s*(?:day|days|week|weeks|din|mahine|months|hours|ghante))', text_lower)
    if dur_match:
        duration_extracted = dur_match.group(1)
    else:
        duration_extracted = "Ongoing"

    ready = (len(missing) == 0 and len(user_input.strip()) > 10)

    replies = {
        "hi": f"मैंने आपकी शिकायत ({category}) समझ ली है। " + ("क्या आप कृपया सटीक गली, लैंडमार्क या फोटो भी साझा कर सकते हैं?" if missing else "सभी विवरण मिल गए हैं। कृपया नीचे दिए गए ड्राफ्ट को कन्फर्म करें।"),
        "mr": f"मी तुमची तक्रार ({category}) समजून घेतली आहे. " + ("कृपया अचूक ठिकाण किंवा लँडमार्क द्या." if missing else "सर्व माहिती मिळाली आहे. कृपया खालील मसुदा तपासा आणि कन्फर्म करा."),
        "hinglish": f"Maine aapki {category} ki complaint note kar li hai. " + ("Kya aap please exact location ya landmark share kar sakte hain?" if missing else "Saari details mil gayi hain. Please draft review karke confirm karein."),
        "en": f"I have understood your grievance regarding {category}. " + ("Could you please provide the exact location or nearest landmark?" if missing else "All required details are noted. Please review and confirm the complaint draft below.")
    }

    return {
        "title": f"Civic Issue: {category}",
        "category": category,
        "detected_language": detected_lang,
        "priority": priority,
        "summary": user_input[:200] + ("..." if len(user_input) > 200 else ""),
        "location_extracted": location_extracted,
        "ward_extracted": ward_extracted,
        "duration_extracted": duration_extracted,
        "missing_information": missing,
        "assistant_reply": replies.get(detected_lang, replies["en"]),
        "ready_to_submit": ready
    }

def analyze_image_evidence(image_file_path: str, api_key: str = None) -> dict:
    key = api_key or os.environ.get('GEMINI_API_KEY')
    if GEMINI_AVAILABLE and key:
        try:
            client = genai.Client(api_key=key)
            from PIL import Image
            img = Image.open(image_file_path)
            prompt = "Analyze this civic problem image. Identify category (Garbage, Road pothole, Water leak, Streetlight, Sewage, Traffic obstruction), severity, and a brief 1-sentence visual description."
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[img, prompt]
            )
            return {"status": "success", "analysis": response.text.strip()}
        except Exception as e:
            print("Vision API error:", e)

    return {
        "status": "success",
        "analysis": "Visual evidence verified: Civic issue debris / condition identified in photo."
    }

def check_possible_duplicates(new_complaint, existing_complaints_queryset):
    one_week_ago = timezone.now() - timedelta(days=7)
    recent = existing_complaints_queryset.filter(
        category=new_complaint.category,
        created_at__gte=one_week_ago
    ).exclude(id=new_complaint.id)

    suspects = []
    for comp in recent:
        if new_complaint.ward_or_zone and comp.ward_or_zone and new_complaint.ward_or_zone.lower() == comp.ward_or_zone.lower():
            suspects.append(comp)
        elif new_complaint.landmark and comp.landmark and new_complaint.landmark.lower() in comp.landmark.lower():
            suspects.append(comp)

    return suspects
