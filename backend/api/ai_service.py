import json
import re
import os
from datetime import timedelta
from django.utils import timezone
from .gemini_client import (
    call_gemini_safe,
    clean_and_parse_json,
    validate_gemini_complaint_payload,
    validate_gemini_image_payload,
    GeminiClientManager
)

SYSTEM_PROMPT = """
You are JanSahayak - an intelligent multilingual civic complaint management assistant.
You understand English, Hindi (हिंदी), Marathi (मराठी), and Hinglish.

Your role:
1. Identify the user's intent:
   - "complaint": Citizen reporting a civic grievance (pothole, water leak, garbage, streetlight, sewage, traffic, etc.)
   - "inquiry": Citizen asking how to use JanSahayak or about municipal services
   - "general": Non-civic or chit-chat greetings
2. For complaints, accurately classify into EXACTLY ONE of these standard civic categories:
   - "Garbage and Sanitation"
   - "Water Supply"
   - "Roads and Potholes"
   - "Streetlights"
   - "Drainage and Sewage"
   - "Traffic and Road Obstruction"
3. Assess severity/priority objectively: "low" | "medium" | "high" | "urgent"
   (Set "urgent" if life-threatening or hazardous: open manhole, fallen electric wire, major water burst).
4. Extract location/landmark, ward/zone, and duration if mentioned.
5. Provide a confidence score (float between 0.0 and 1.0) for the classification.
6. Return a STRICT JSON object without markdown formatting:
{
  "intent": "complaint | inquiry | general",
  "title": "Concise summary title in English (e.g. Broken streetlight on 2nd Avenue)",
  "category": "One of the 6 exact category names above, or 'General Inquiry' if not a civic complaint",
  "confidence_score": 0.95,
  "detected_language": "en | hi | mr | hinglish",
  "priority": "low | medium | high | urgent",
  "summary": "Clear, objective summary of the problem in English",
  "location_extracted": "Address or landmark if mentioned, else null",
  "ward_extracted": "Ward or zone if mentioned, else null",
  "duration_extracted": "Duration of problem if mentioned, else null",
  "missing_information": ["list of critical missing items like exact street/landmark or photo, if any"],
  "assistant_reply": "Empathetic, clear conversational response in the user's detected language asking for missing info or confirming ticket readiness",
  "ready_to_submit": true or false
}

Guidelines:
- Never hallucinate government submission or fake official contact numbers.
- If the problem is hazardous, elevate priority to "urgent".
- Set ready_to_submit = true only if intent is 'complaint' and both the issue description and location/landmark are known.
"""

def extract_location_entities(full_text: str, detected_lang: str = "en") -> dict:
    """
    Intelligent extraction of location entities across Hindi, Marathi, Hinglish, and English.
    Returns:
        {
            "location_extracted": str or None,
            "ward_extracted": str or None,
            "is_ambiguous": bool
        }
    """
    text_clean = full_text.strip()
    text_lower = text_clean.lower()

    # 1. Ward / Zone extraction
    ward_extracted = None
    ward_match = re.search(r'\b(?:ward|prabhag|zone|वॉर्ड|प्रभाग|वार्ड)\s*[:#-]?\s*(\d+|[A-Za-z]+)\b', text_clean, re.IGNORECASE)
    if ward_match:
        ward_extracted = f"Ward {ward_match.group(1).upper()}"

    # 2. Check for vague/ambiguous pseudo-locations
    # e.g., "hamare yahan", "gali me", "idhar", "yahan", "आमच्या इथे", "रस्त्यावर", "in my street", "near my house"
    vague_phrases = [
        'hamare yahan', 'hamaare yahan', 'mere ghar ke paas', 'idhar', 'yahan', 'gali me', 'sadak par',
        'near my house', 'in my street', 'outside', 'in our area', 'here',
        'आमच्या इथे', 'इथे', 'घरासमोर', 'माझ्या घरासमोर', 'रस्त्यावर', 'आमच्या भागात'
    ]

    has_specific_indicator = False
    extracted_locations = []

    # Patterns for Devanagari Hindi / Marathi locations
    # (A) Postpositional: "X के सामने / के पास / के पीछे / जवळ / समोर / शेजारी / कडे"
    devanagari_post = re.findall(
        r'([\u0900-\u097F0-9\s]{2,30}?)\s*(?:के\s*(?:सामने|पास|पीछे|बगल\s*में|निकट)|जवळ|समोर|शेजारी|लगत)',
        text_clean
    )
    for match in devanagari_post:
        candidate = match.strip()
        candidate = re.sub(r'^(?:और|तथा|तसेच|खूप|येथे|इथे|खड्डे|कचरा|घाण|समस्या|येथे)\s+', '', candidate).strip()
        if len(candidate) >= 3 and not any(v in candidate.lower() for v in vague_phrases):
            extracted_locations.append(candidate)
            has_specific_indicator = True

    # Patterns for Hindi / Marathi Named Landmarks: "मंदिर जवळ", "चौक", "नगर", "कॉलनी"
    devanagari_named = re.findall(
        r'([\u0900-\u097F0-9\s]{2,25}(?:मंदिर|मंदीर|चौक|नगर|कॉलनी|रोड|रस्ता|गल्ली|सोसायटी|इस्पितळ|दवाखाना|शाळा|स्टेशन|नाका))',
        text_clean
    )
    for match in devanagari_named:
        candidate = match.strip()
        candidate = re.sub(r'^(?:येथे|इथे|खूप|मोठा|नवीन|माझ्या)\s+', '', candidate).strip()
        if len(candidate) >= 3:
            extracted_locations.append(candidate)
            has_specific_indicator = True

    # Patterns for English / Hinglish:
    # (A) Keyword based: near, opposite, behind, in front of, next to, beside, at
    en_matches = re.findall(
        r'\b(?:near|opp(?:osite)?|behind|in\s*front\s*of|next\s*to|beside|at)\s+([A-Za-z0-9\s,-]{3,35}?)(?=\s+(?:and|is|are|very|since|se|par|me|ko|hai|ho|badboo|kooda|paani|overflow|causing|ward|\.|\,|$))',
        text_clean,
        re.IGNORECASE
    )
    for match in en_matches:
        candidate = match.strip(" ,.-")
        if candidate and not any(v in candidate.lower() for v in ['my house', 'our area', 'my street', 'here', 'road', 'gali']):
            extracted_locations.append(candidate)
            has_specific_indicator = True

    # (B) Named places: "X Road", "Y Street", "Z Nagar", "W Chowk", "V Colony", "U Sector", "T Hospital", "S School", "R Market"
    named_en = re.findall(
        r'\b(?:on|in|at)?\s*([0-9A-Za-z\s]{2,25}\s+(?:Chowk|Nagar|Colony|Apartment|Complex|Hospital|School|College|Station|Metro|Market|Mall|Bazaar|Sector\s*\d+|Road|Street|Avenue|Lane|Marg))\b',
        text_clean,
        re.IGNORECASE
    )
    for match in named_en:
        candidate = match.strip(" ,.-")
        candidate = re.sub(r'^(?:pothole|crater|leakage|water|sewage|wire|dark|streetlight|light|garbage|waste)\s*(?:on|in|at)?\s*', '', candidate, flags=re.IGNORECASE).strip()
        if len(candidate) >= 4 and not any(cand in candidate for cand in extracted_locations):
            extracted_locations.append(candidate)
            has_specific_indicator = True

    # Filter out empty or duplicate candidates
    final_locations = []
    for loc in extracted_locations:
        loc_clean = re.sub(r'\s+', ' ', loc).strip(" ,.-")
        if loc_clean and loc_clean not in final_locations:
            final_locations.append(loc_clean)

    location_str = None
    is_ambiguous = False

    if final_locations:
        location_str = ", ".join(final_locations)
        if any(v == location_str.lower() for v in vague_phrases):
            location_str = None
            is_ambiguous = True
    else:
        if any(v in text_lower for v in vague_phrases) or any(v in text_clean for v in ['गल्ली', 'रस्त्यावर', 'घरासमोर']):
            is_ambiguous = True

    return {
        "location_extracted": location_str,
        "ward_extracted": ward_extracted,
        "is_ambiguous": is_ambiguous
    }


def analyze_complaint_text(user_input: str, conversation_history: list = None, api_key: str = None) -> dict:
    if api_key:
        os.environ['GEMINI_API_KEY'] = api_key

    full_text = user_input
    if conversation_history:
        history_str = "\n".join([f"{msg.get('sender', 'user')}: {msg.get('text', '')}" for msg in conversation_history])
        full_text = f"Conversation History:\n{history_str}\n\nLatest Citizen Message:\n{user_input}"

    # 1. Primary: Safe Central Gemini Query with Strict Validation
    prompt = f"{full_text}\n\nSTRICT JSON Output:"
    gemini_raw_response = call_gemini_safe(prompt=prompt, system_instruction=SYSTEM_PROMPT)
    if gemini_raw_response:
        parsed_json = clean_and_parse_json(gemini_raw_response)
        if parsed_json:
            validated = validate_gemini_complaint_payload(parsed_json)
            if validated:
                return validated

    # 2. Resilient Fallback: Multilingual Heuristic Rule Engine
    text_lower = full_text.lower()
    intent = "complaint"
    category = "Garbage and Sanitation"
    priority = "medium"
    detected_lang = "en"
    confidence = 0.85

    # Language detection - check Marathi specific markers first
    if any(term in full_text for term in ['आहे', 'नाही', 'रस्ता', 'रस्त्यावर', 'पाणी', 'कचरा', 'झाले', 'खड्डा', 'खड्डे', 'पडला', 'होत', 'गटार', 'दिवा']):
        detected_lang = "mr"
    elif any(term in full_text for term in ['कचरा', 'कूड़ा', 'सड़क', 'गड्ढा', 'पानी', 'है', 'में', 'और', 'खराब', 'नाला', 'बिजली', 'खंभा', 'सफाई']):
        detected_lang = "hi"
    elif any(word in text_lower for word in ['hai', 'nahi', 'karo', 'pani', 'kachra', 'kooda', 'sadak', 'bahut', 'bohot', 'kharab', 'gaddha', 'gutter', 'naali', 'batti']):
        detected_lang = "hinglish"

    # Intent Detection: Check if non-civic inquiry or greeting
    inquiry_keywords = [
        'who is', 'biography', 'what is', 'what are', 'tell me about', 'weather',
        'movie', 'song', 'joke', 'capital of', 'kaun hai', 'kya hai', 'kab khulta hai',
        'timings', 'working hours', 'office hours', 'how to use', 'help me'
    ]
    greeting_keywords = ['hello', 'hi', 'namaste', 'kem cho', 'good morning', 'good evening', 'hey']

    if any(ik in text_lower for ik in inquiry_keywords):
        intent = "inquiry"
        category = "General Inquiry"
        confidence = 0.90
    elif any(gk == text_lower.strip() for gk in greeting_keywords):
        intent = "general"
        category = "General Inquiry"
        confidence = 0.95
    else:
        # Category Matching with strict boundary and term checks
        # 1. Streetlights / Electrical (Check first before generic light/wire)
        if any(w in text_lower or w in full_text for w in [
            'streetlight', 'street light', 'pole', 'bulb', 'dark', 'light pole',
            'खंभा', 'स्ट्रीट लाइट', 'बिजली', 'दिवा', 'अंधार', 'batti', 'roshni', 'khamba'
        ]):
            category = "Streetlights"
            confidence = 0.92
            if any(w in text_lower or w in full_text for w in ['spark', 'shock', 'live wire', 'wire hanging', 'करंट', 'तारा']):
                priority = "urgent"

        # 2. Drainage and Sewage (Check before generic water)
        elif any(w in text_lower or w in full_text for w in [
            'drain', 'drainage', 'sewer', 'sewage', 'gutter', 'manhole', 'gali nala', 'overflowing drain',
            'गटर', 'गटार', 'नाली', 'नाला', 'मैनहोल', 'ड्रेनेज', 'गटाराचे'
        ]):
            category = "Drainage and Sewage"
            confidence = 0.92
            priority = "high"
            if any(w in text_lower or w in full_text for w in ['open manhole', 'child', 'flood', 'toxic', 'उघडे गटार']):
                priority = "urgent"

        # 3. Roads and Potholes
        elif any(w in text_lower or w in full_text for w in [
            'pothole', 'crater', 'asphalt', 'road damage', 'broken road', 'uneven road',
            'सड़क', 'गड्ढा', 'गड्ढे', 'रस्ता', 'रस्त्यावर', 'खड्डा', 'खड्डे', 'gaddha', 'sadak pe gaddha'
        ]):
            category = "Roads and Potholes"
            confidence = 0.94
            if any(w in text_lower or w in full_text for w in ['accident', 'deep', 'injury', 'bike slip', 'अपघात', 'मोठा']):
                priority = "urgent"

        # 4. Garbage and Sanitation (Check before generic traffic)
        elif any(w in text_lower or w in full_text for w in [
            'garbage', 'waste', 'trash', 'litter', 'dustbin', 'cleaning', 'sweep',
            'कचरा', 'कूड़ा', 'सफाई', 'कचऱ्याचे', 'झाडू', 'डस्टबिन',
            'kachra', 'kooda', 'safai', 'gandagi'
        ]):
            category = "Garbage and Sanitation"
            confidence = 0.94
            if any(w in text_lower or w in full_text for w in ['smell', 'stench', 'disease', 'days', 'बदबू', 'दुर्गंधी', 'सड़ांध']):
                priority = "high"

        # 5. Traffic and Road Obstruction
        elif any(w in text_lower or w in full_text for w in [
            'traffic jam', 'illegal parking', 'parking', 'obstruction', 'encroachment', 'footpath blocked',
            'sidewalk blocked', 'blocked road', 'वाहतूक', 'अतिक्रमण', 'ट्रैफिक', 'जाम', 'footpath'
        ]):
            category = "Traffic and Road Obstruction"
            confidence = 0.88
            if any(w in text_lower for w in ['ambulance', 'emergency']):
                priority = "urgent"

        # 6. Water Supply (Potable / Pipe Supply)
        elif any(w in text_lower or w in full_text for w in [
            'water supply', 'drinking water', 'pipeline', 'tap water', 'water burst', 'low pressure',
            'जल', 'पाणी', 'पेयजल', 'पाइप', 'नळ', 'jal', 'peene ka paani', 'pipe burst'
        ]):
            category = "Water Supply"
            confidence = 0.90
            if any(w in text_lower or w in full_text for w in ['burst', 'no water for 3 days', 'urgent', 'फुटली', 'फूट']):
                priority = "high"

        # Default fallback
        else:
            category = "Garbage and Sanitation"
            confidence = 0.75

    # Location & Ward Extraction using Smart Entity Extractor
    loc_data = extract_location_entities(full_text, detected_lang=detected_lang)
    location_extracted = loc_data["location_extracted"]
    ward_extracted = loc_data["ward_extracted"]
    is_ambiguous = loc_data["is_ambiguous"]

    # Duration Extraction
    dur_match = re.search(r'(\d+\s*(?:day|days|week|weeks|din|mahine|months|hours|ghante|दिवस|महिने|तास))\b', text_lower)
    if dur_match:
        duration_extracted = dur_match.group(1)
    else:
        duration_extracted = "Ongoing"

    # Missing Information & Clarification Questions
    missing = []
    clarification_question = None

    if not location_extracted:
        if is_ambiguous:
            missing.append("Specific street name or nearby landmark (Current location is too vague)")
            clarification_questions = {
                "hi": "आपने जो जगह बताई है वह स्पष्ट नहीं है। कृपया नजदीकी लैंडमार्क (जैसे मंदिर, स्कूल, अस्पताल या मुख्य सड़क) का नाम बताएं।",
                "mr": "दिलेले ठिकाण पुरेसे स्पष्ट नाही. कृपया जवळील लँडमार्क (उदा. मंदिर, शाळा, रुग्णालय किंवा मुख्य चौक) सांगा.",
                "hinglish": "Aapki batayi gayi location clear nahi hai. Please nearest landmark (jaise Mandir, School, Hospital ya Chowk) batayein.",
                "en": "The location provided is too vague. Could you please specify the exact street, chowk, or nearest landmark?"
            }
            clarification_question = clarification_questions.get(detected_lang, clarification_questions["en"])
        else:
            missing.append("Exact location or landmark")
            clarification_questions = {
                "hi": "कृपया समस्या की सटीक जगह, गली या नजदीकी लैंडमार्क बताएं।",
                "mr": "कृपया समस्येचे अचूक ठिकाण, गल्ली किंवा लँडमार्क सांगा.",
                "hinglish": "Please samasya ki exact location ya nearest landmark share karein.",
                "en": "Please provide the exact street name, area, or nearest landmark."
            }
            clarification_question = clarification_questions.get(detected_lang, clarification_questions["en"])

    ready = (len(missing) == 0 and len(user_input.strip()) > 10 and intent == "complaint")

    replies = {
        "hi": f"मैंने आपकी शिकायत ({category}) समझ ली है। " + (clarification_question if clarification_question else "सभी विवरण मिल गए हैं। कृपया नीचे दिए गए ड्राफ्ट को कन्फर्म करें।"),
        "mr": f"मी तुमची तक्रार ({category}) समजून घेतली आहे. " + (clarification_question if clarification_question else "सर्व माहिती मिळाली आहे. कृपया खालील मसुदा तपासा आणि कन्फर्म करा."),
        "hinglish": f"Maine aapki {category} ki complaint note kar li hai. " + (clarification_question if clarification_question else "Saari details mil gayi hain. Please draft review karke confirm karein."),
        "en": f"I have understood your grievance regarding {category}. " + (clarification_question if clarification_question else "All required details are noted. Please review and confirm the complaint draft below.")
    }

    if intent == "inquiry":
        replies["en"] = "JanSahayak assists you in filing civic complaints for roads, water, electricity, garbage and drainage. Please describe your municipal issue."
        replies["hi"] = "जनसहायक नागरिक समस्याओं (सड़क, पानी, कचरा, लाइट) के समाधान के लिए है। कृपया अपनी समस्या बताएं।"
        replies["mr"] = "जनसहायक नागरी तक्रारी (रस्ता, पाणी, कचरा, वीज) नोंदवण्यासाठी आहे. कृपया आपली तक्रार सांगा."
        replies["hinglish"] = "JanSahayak civic problems report karne ke liye hai. Please apni municipal samasya batayein."

    return {
        "intent": intent,
        "title": f"Civic Issue: {category}" if intent == "complaint" else "General Inquiry",
        "category": category,
        "confidence_score": confidence,
        "detected_language": detected_lang,
        "priority": priority,
        "summary": user_input[:200] + ("..." if len(user_input) > 200 else ""),
        "location_extracted": location_extracted,
        "ward_extracted": ward_extracted,
        "duration_extracted": duration_extracted,
        "missing_information": missing,
        "clarification_question": clarification_question,
        "assistant_reply": replies.get(detected_lang, replies["en"]),
        "ready_to_submit": ready
    }

def analyze_image_evidence(image_file_path: str, complaint_text: str = "", complaint_category: str = "", api_key: str = None) -> dict:
    """
    Truthful multimodal visual analysis of civic complaint evidence.
    1. Validates physical file presence, size (<25MB), and readability (via PIL).
    2. Sends the image + citizen complaint context to Gemini with a strict schema.
    3. Validates response with validate_gemini_image_payload().
    4. Enforces truthfulness invariants:
       - Never claims 100% certainty or authenticity based on file metadata.
       - If Gemini fails, times out, or image is unreadable, returns verification_status='failed' or 'pending',
         NEVER 'verified'.
       - If the image does not match the complaint description, flags as 'mismatch'.
    """
    import logging
    logger = logging.getLogger("jansahayak_ai")

    if api_key:
        os.environ['GEMINI_API_KEY'] = api_key

    # 1. File existence check
    if not image_file_path or not os.path.exists(image_file_path):
        return {
            "status": "error",
            "detected_issue": "File not found",
            "detected_objects": [],
            "image_readability": "unreadable",
            "complaint_image_match": False,
            "confidence_score": 0.0,
            "verification_status": "failed",
            "review_required": True,
            "summary_note": "Image file could not be located on the server filesystem.",
            "analysis": "Verification failed: Evidence file could not be found."
        }

    # 2. File size and extension check
    file_size = os.path.getsize(image_file_path)
    if file_size > 25 * 1024 * 1024:
        return {
            "status": "error",
            "detected_issue": "File exceeds size limit",
            "detected_objects": [],
            "image_readability": "unreadable",
            "complaint_image_match": False,
            "confidence_score": 0.0,
            "verification_status": "failed",
            "review_required": True,
            "summary_note": "Image file exceeds maximum allowable 25 MB limit.",
            "analysis": "Verification failed: File size exceeds 25 MB."
        }

    # 3. Image integrity / readability check via PIL
    try:
        from PIL import Image
        with Image.open(image_file_path) as img:
            img.verify()
        # Re-open for actual processing (verify closes file handles in some PIL versions)
        pil_img = Image.open(image_file_path)
    except Exception as img_err:
        logger.warning(f"Corrupt or unreadable image uploaded ({image_file_path}): {img_err}")
        return {
            "status": "error",
            "detected_issue": "Corrupt or unreadable image format",
            "detected_objects": [],
            "image_readability": "unreadable",
            "complaint_image_match": False,
            "confidence_score": 0.0,
            "verification_status": "failed",
            "review_required": True,
            "summary_note": "Uploaded file is corrupted, not a valid image, or unreadable.",
            "analysis": "Verification failed: Corrupt or unreadable image file. Manual inspection required."
        }

    # 4. Multimodal Analysis via Central Gemini Manager
    manager = GeminiClientManager()
    client = manager.get_client()

    image_prompt = f"""You are the JanSahayak Civic Evidence Verification specialist.
Analyze this civic grievance image carefully and compare it against the citizen's complaint details:
- Complaint Category: {complaint_category or 'Not specified'}
- Complaint Description: {complaint_text or 'Not specified'}

Analyze the image and return a STRICT JSON object without markdown formatting:
{{
  "detected_issue": "Brief civic issue name (e.g. Road pothole, Garbage overflow, Leaking pipe, Broken streetlight, Sewage water, Road obstruction, or None/Unclear)",
  "detected_objects": ["list", "of", "visible", "objects", "debris", "road", "water", "pole"],
  "image_readability": "clear | blurry | dark | unreadable | partial",
  "complaint_image_match": true or false,
  "confidence_score": 0.88,
  "verification_status": "verified | mismatch | unverified | failed",
  "review_required": true or false,
  "summary_note": "1 concise factual sentence describing what is visually visible and whether it matches the complaint."
}}

Guidelines:
1. If the photo shows a completely different subject from the complaint (e.g. food/pet for a pothole complaint), set complaint_image_match=false, verification_status='mismatch', and review_required=true.
2. If image is too dark, blurry, or unreadable to identify civic infrastructure, set image_readability='blurry' or 'dark', verification_status='unverified', and review_required=true.
3. Never claim 100% certainty (maximum confidence 0.95).
4. Do not assume file metadata proves authenticity.
"""

    if client:
        try:
            response = client.models.generate_content(
                model=manager.get_model_name(),
                contents=[pil_img, image_prompt]
            )
            if response and hasattr(response, 'text') and response.text:
                parsed = clean_and_parse_json(response.text)
                if parsed:
                    validated = validate_gemini_image_payload(parsed)
                    if validated:
                        # Optional YOLO Civic Object Detection Enrichment
                        try:
                            from .yolo_detector import YOLODetector
                            yolo_res = YOLODetector().detect(image_path=image_file_path)
                            validated["yolo_analysis"] = yolo_res
                            if yolo_res.get("detection_status") == "success" and yolo_res.get("detected_objects"):
                                top_obj = yolo_res.get("class_name")
                                validated["detected_objects"] = list(set(validated["detected_objects"] + [top_obj]))
                        except Exception as yolo_err:
                            logger.debug(f"Optional YOLO detection bypassed: {yolo_err}")

                        # Construct clean human-readable analysis summary
                        summary = validated.get("summary_note") or f"Visual analysis detected {validated['detected_issue']}."
                        status_str = validated["verification_status"].capitalize()
                        validated["status"] = "success"
                        validated["analysis"] = f"[{status_str}] {summary} (Confidence: {int(validated['confidence_score']*100)}%, Match: {validated['complaint_image_match']})"
                        return validated
        except Exception as e:
            logger.warning(f"Gemini image vision API call failed: {e}")

    # 5. Truthful Fallback When Gemini is Unavailable, Times Out, or Fails
    # CRITICAL: Never falsely mark image as verified when AI fails
    return {
        "status": "pending",
        "detected_issue": "Pending manual review",
        "detected_objects": [],
        "image_readability": "partial",
        "complaint_image_match": False,
        "confidence_score": 0.0,
        "verification_status": "pending",
        "review_required": True,
        "summary_note": "Automated visual verification is currently unavailable; evidence queued for staff verification.",
        "analysis": "[Pending Staff Verification] Automated image analysis could not be completed. Flagged for manual review."
    }

def compute_image_hashes(image_file_path: str) -> dict:
    """
    Computes both exact SHA-256 binary hash and perceptual pHash for an image.
    Handles corrupted files and unsupported formats gracefully.
    Returns:
        {
            "sha256": str or None,
            "phash": str or None,
            "is_valid": bool,
            "error": str or None
        }
    """
    import hashlib
    if not image_file_path or not os.path.exists(image_file_path):
        return {"sha256": None, "phash": None, "is_valid": False, "error": "File does not exist"}

    # 1. Exact SHA-256 Hash
    try:
        sha256 = hashlib.sha256()
        with open(image_file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha256.update(chunk)
        sha256_hex = sha256.hexdigest()
    except Exception as e:
        return {"sha256": None, "phash": None, "is_valid": False, "error": f"Failed to read file: {e}"}

    # 2. Perceptual Hash (pHash)
    phash_str = None
    try:
        from PIL import Image
        import imagehash
        with Image.open(image_file_path) as img:
            # Convert to RGB if needed to handle palette / RGBA
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            phash_obj = imagehash.phash(img)
            phash_str = str(phash_obj)
    except Exception as e:
        # Corrupted or unreadable image
        return {"sha256": sha256_hex, "phash": None, "is_valid": False, "error": f"Corrupted or invalid image: {e}"}

    return {
        "sha256": sha256_hex,
        "phash": phash_str,
        "is_valid": True,
        "error": None
    }


def detect_duplicate_evidence(
    image_file_path: str,
    current_evidence_id: int = None,
    current_complaint_id: int = None,
    similarity_threshold: float = 0.85
) -> dict:
    """
    Detects whether an uploaded image evidence is an exact or perceptual duplicate.
    - Compares against existing ComplaintEvidence in the database.
    - Evaluates exact SHA-256 match first.
    - Evaluates perceptual pHash Hamming distance (distance <= 10 or similarity >= threshold).
    - Preserves privacy: only returns ID and similarity score, never reveals other citizens' info.
    - Never automatically rejects a complaint; sets review_required=True.
    
    Returns:
        {
            "is_duplicate": bool,
            "duplicate_type": 'exact' | 'perceptual' | 'none',
            "similarity_score": float,
            "review_required": bool,
            "matched_evidence_id": int or None,
            "sha256_hash": str or None,
            "phash": str or None,
            "summary": str
        }
    """
    from .models import ComplaintEvidence

    hash_res = compute_image_hashes(image_file_path)
    if not hash_res["is_valid"]:
        return {
            "is_duplicate": False,
            "duplicate_type": "none",
            "similarity_score": 0.0,
            "review_required": True,  # Corrupted images should be flagged for review
            "matched_evidence_id": None,
            "sha256_hash": hash_res.get("sha256"),
            "phash": None,
            "summary": "Image hash computation failed; manual inspection needed."
        }

    sha256_hex = hash_res["sha256"]
    phash_str = hash_res["phash"]

    # Exclude current evidence and evidence from the exact same complaint (if already attached)
    queryset = ComplaintEvidence.objects.filter(file_type='image')
    if current_evidence_id:
        queryset = queryset.exclude(id=current_evidence_id)

    # 1. Exact Duplicate Check (SHA-256)
    exact_match = queryset.filter(sha256_hash=sha256_hex).first()
    if exact_match:
        return {
            "is_duplicate": True,
            "duplicate_type": "exact",
            "similarity_score": 1.0,
            "review_required": True,
            "matched_evidence_id": exact_match.id,
            "sha256_hash": sha256_hex,
            "phash": phash_str,
            "summary": f"Exact binary duplicate of existing evidence (ID #{exact_match.id})."
        }

    # 2. Perceptual Duplicate Check (pHash Hamming distance)
    # 64-bit hash: Hamming distance max 64.
    # Similarity = 1.0 - (distance / 64.0)
    best_match_evidence = None
    best_similarity = 0.0

    if phash_str:
        import imagehash
        try:
            curr_hash = imagehash.hex_to_hash(phash_str)
            existing_phashes = queryset.exclude(phash__isnull=True).exclude(phash='').values_list('id', 'phash')

            for ev_id, other_phash_str in existing_phashes:
                try:
                    other_hash = imagehash.hex_to_hash(other_phash_str)
                    distance = curr_hash - other_hash  # Hamming distance
                    similarity = round(1.0 - (distance / 64.0), 3)
                    if similarity > best_similarity:
                        best_similarity = similarity
                        best_match_evidence = ev_id
                except Exception:
                    continue
        except Exception:
            pass

    if best_match_evidence and best_similarity >= similarity_threshold:
        return {
            "is_duplicate": True,
            "duplicate_type": "perceptual",
            "similarity_score": best_similarity,
            "review_required": True,
            "matched_evidence_id": best_match_evidence,
            "sha256_hash": sha256_hex,
            "phash": phash_str,
            "summary": f"Perceptually similar to evidence #{best_match_evidence} ({int(best_similarity*100)}% visual match)."
        }

    return {
        "is_duplicate": False,
        "duplicate_type": "none",
        "similarity_score": round(best_similarity, 3) if best_similarity > 0 else 0.0,
        "review_required": False,
        "matched_evidence_id": None,
        "sha256_hash": sha256_hex,
        "phash": phash_str,
        "summary": "Unique civic grievance photo evidence."
    }

def check_possible_duplicates(new_complaint, existing_complaints_queryset):
    """
    Backwards-compatible wrapper delegating to DuplicateDetector.
    Returns list of suspect complaints if possible duplicate found.
    """
    from .duplicate_detector import DuplicateDetector
    res = DuplicateDetector.find_duplicate(
        new_complaint=new_complaint,
        existing_complaints_queryset=existing_complaints_queryset
    )
    if res["is_possible_duplicate"] and res["matched_complaint_id"]:
        from .models import Complaint
        try:
            return [Complaint.objects.get(id=res["matched_complaint_id"])]
        except Complaint.DoesNotExist:
            return []
    return []
