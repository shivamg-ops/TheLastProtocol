"""
JanSahayak - Smart Civic Knowledge Assistant Service (Task 19)

Provides conversational citizen assistance using:
1. Ownership-protected database lookup for personal complaint inquiries.
2. Structured civic knowledge retrieval for general guidelines, filing help, and policies.
3. Multilingual AI synthesis (English, Hindi, Hinglish) via Gemini with strict JSON formatting.
4. Deterministic safe fallback when Gemini is unavailable or quotas are reached.

Safety & Truthfulness Guarantees:
- Enforces strict BOLA: Citizens can ONLY query complaints they own.
- Never invents complaint statuses, staff assignments, SLA deadlines, or official helpline numbers.
- Never fabricates government integrations or resolution guarantees.
- Answering filing guidance does NOT automatically create a complaint in the database.
- Strictly scrubs API keys and private personal information.
"""

import re
import json
import logging
from typing import Dict, Any, List, Optional
from django.utils import timezone
from .models import Complaint, User, ComplaintStatus, UserRole
from .sla_monitor import SLAMonitor
from .gemini_client import call_gemini_safe, clean_and_parse_json
from .civic_knowledge import search_civic_knowledge, CIVIC_KNOWLEDGE_BASE

logger = logging.getLogger("jansahayak_ai")


def detect_query_language(text: str) -> str:
    """
    Detects whether the inquiry is English, Hindi (Devanagari), or Hinglish.
    """
    if not text:
        return "en"

    # Check for Devanagari script (U+0900 to U+097F)
    if re.search(r'[\u0900-\u097f]', text):
        return "hi"

    # Common Hinglish marker words
    hinglish_markers = [
        "kya", "hai", "meri", "mera", "kaise", "kare", "kab", "tak", "hoga", "shikayat",
        "paani", "kachra", "sadak", "gaddha", "batti", "khamba", "nahi", "hua", "batao",
        "gali", "nukkad", "karwa", "do", "karo", "kyu", "der", "aahe", "ahe"
    ]
    tokens = set(re.findall(r'\b[a-zA-Z]+\b', text.lower()))
    if len(tokens.intersection(hinglish_markers)) >= 1:
        return "hinglish"

    return "en"


def extract_tracking_id(text: str) -> Optional[str]:
    """
    Finds a standard JanSahayak tracking code (e.g. JSH-A1B2C3D4 or 8-char hex) in user text.
    """
    if not text:
        return None
    match = re.search(r'\b(JSH-[A-Za-z0-9]{6,12})\b', text, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return None


class CivicAssistantService:
    """
    Modular intelligence service orchestrating citizen queries and database-backed knowledge.
    """

    @classmethod
    def process_citizen_query(
        cls,
        user: Optional[User],
        message: str,
        complaint_identifier: Optional[str] = None,
        requested_language: str = "auto"
    ) -> Dict[str, Any]:
        """
        Main query entrypoint for JanSahayak Civic Assistant.
        
        Guarantees:
        - Rejects empty messages.
        - Enforces ownership on personal complaint lookups.
        - Employs deterministic fallbacks if LLM fails.
        """
        if not message or not message.strip():
            return {
                "answer": "Please ask a question regarding your complaint or civic services.",
                "language": "en",
                "intent": "general",
                "related_complaint": None,
                "suggested_actions": ["Ask about filing a complaint", "Check status of tracking ID"],
                "sources": [],
                "requires_human_support": False
            }

        clean_message = message.strip()
        lang = requested_language if requested_language in ["en", "hi", "hinglish"] else detect_query_language(clean_message)

        # 1. Determine if a complaint tracking ID is mentioned in parameter or message text
        extracted_id = complaint_identifier or extract_tracking_id(clean_message)

        # 2. Check for personal complaint lookup intent:
        # A personal complaint lookup is triggered if:
        # - An explicit tracking ID is present (e.g. JSH-12345678), OR
        # - The user explicitly asks about THEIR OWN complaint ("my complaint", "meri complaint", "meri shikayat")
        is_complaint_query = bool(
            extracted_id or
            re.search(r'\b(meri complaint|my complaint|meri shikayat|my ticket|status of my|status of complaint)\b', clean_message, re.IGNORECASE)
        )

        complaint_context = None
        complaint_data = None

        if is_complaint_query:
            complaint_res = cls._resolve_complaint(user, extracted_id, clean_message, lang)
            if complaint_res.get("handled"):
                return complaint_res["response"]
            complaint_context = complaint_res.get("context")
            complaint_data = complaint_res.get("complaint_dict")

        # 3. Retrieve relevant Civic Knowledge
        knowledge_articles = search_civic_knowledge(clean_message, language="hi" if lang == "hi" else "en")

        # If user is asking how to file / register or saying "I want to file", prioritize filing action
        is_filing_intent = bool(re.search(r'\b(file|register|report|darj|shikayat karni)\b', clean_message, re.IGNORECASE))
        if is_filing_intent and not complaint_data:
            suggested_actions = ["Go to /report page", "Provide location landmark", "Upload photo proof"]
        else:
            suggested_actions = []

        if knowledge_articles:
            for art in knowledge_articles[:2]:
                suggested_actions.extend(art.get("suggested_actions", []))

        # 4. Generate structured answer via Gemini (with robust fallback)
        return cls._generate_assistant_response(
            message=clean_message,
            lang=lang,
            complaint_context=complaint_context,
            complaint_data=complaint_data,
            knowledge_articles=knowledge_articles,
            base_actions=suggested_actions
        )

    @classmethod
    def _resolve_complaint(
        cls,
        user: Optional[User],
        extracted_id: Optional[str],
        message: str,
        lang: str
    ) -> Dict[str, Any]:
        """
        Handles ownership verification and database retrieval for personal complaints.
        """
        # A. Unauthenticated check
        if not user or not user.is_authenticated:
            msg = (
                "To check the status of your personal complaint, please log in to your JanSahayak account."
                if lang == "en" else
                "अपनी व्यक्तिगत शिकायत की स्थिति जानने के लिए कृपया अपने JanSahayak खाते में लॉगिन करें।"
            )
            return {
                "handled": True,
                "response": {
                    "answer": msg,
                    "language": lang,
                    "intent": "complaint_status",
                    "related_complaint": None,
                    "suggested_actions": ["Log in to view complaints", "Register a new grievance"],
                    "sources": ["Authentication Gateway"],
                    "requires_human_support": False
                }
            }

        # B. If specific tracking ID was provided
        if extracted_id:
            try:
                complaint = Complaint.objects.select_related('department', 'category', 'assigned_staff').get(
                    tracking_id__iexact=extracted_id
                )
            except Complaint.DoesNotExist:
                # Tracking code does not exist in system
                msg = (
                    f"No complaint found with tracking ID '{extracted_id}'. Please verify the tracking code from your receipt."
                    if lang == "en" else
                    f"ट्रैकिंग कोड '{extracted_id}' से कोई शिकायत नहीं मिली। कृपया रसीद से सही ट्रैकिंग कोड जांचें।"
                )
                return {
                    "handled": True,
                    "response": {
                        "answer": msg,
                        "language": lang,
                        "intent": "complaint_status",
                        "related_complaint": None,
                        "suggested_actions": ["Check tracking code in /citizen portal"],
                        "sources": ["Database Verification"],
                        "requires_human_support": False
                    }
                }

            # STRICT BOLA OWNERSHIP CHECK:
            # Citizens can ONLY view their own complaints. Admins can view any complaint.
            if complaint.citizen != user and user.role != UserRole.ADMIN:
                msg = (
                    "Access restricted: You do not have permission to view this complaint record."
                    if lang == "en" else
                    "सुरक्षा प्रतिबंध: आपके पास इस शिकायत विवरण को देखने की अनुमति नहीं है।"
                )
                return {
                    "handled": True,
                    "response": {
                        "answer": msg,
                        "language": lang,
                        "intent": "complaint_status",
                        "related_complaint": None,
                        "suggested_actions": ["View your filed complaints at /citizen"],
                        "sources": ["Security Access Control"],
                        "requires_human_support": False
                    }
                }

            # Format complaint details securely
            sla_info = SLAMonitor.evaluate_complaint_sla(complaint)
            comp_dict = {
                "id": complaint.id,
                "tracking_id": complaint.tracking_id,
                "title": complaint.title,
                "status": complaint.status,
                "department": complaint.department.name if complaint.department else "Unassigned",
                "assigned_staff": complaint.assigned_staff.username if complaint.assigned_staff else "Pending Assignment",
                "created_at": complaint.created_at.strftime("%Y-%m-%d %H:%M"),
                "is_overdue": sla_info.get("is_overdue", False),
                "sla_status": sla_info.get("sla_status", "not_configured"),
                "verification_status": complaint.resolution_verification_status,
                "resolution_notes": complaint.resolution_notes or ""
            }

            context_str = (
                f"Complaint ID: {comp_dict['tracking_id']}\n"
                f"Title: {comp_dict['title']}\n"
                f"Status: {comp_dict['status']}\n"
                f"Department: {comp_dict['department']}\n"
                f"Assigned Staff: {comp_dict['assigned_staff']}\n"
                f"Filed Date: {comp_dict['created_at']}\n"
                f"SLA Overdue: {comp_dict['is_overdue']}\n"
                f"Verification Status: {comp_dict['verification_status']}\n"
                f"Staff Notes: {comp_dict['resolution_notes']}"
            )
            return {"handled": False, "context": context_str, "complaint_dict": comp_dict}

        # C. If no tracking ID was mentioned, check user's most recent complaint
        recent_complaint = Complaint.objects.filter(citizen=user).order_by('-created_at').first()
        if recent_complaint:
            sla_info = SLAMonitor.evaluate_complaint_sla(recent_complaint)
            comp_dict = {
                "id": recent_complaint.id,
                "tracking_id": recent_complaint.tracking_id,
                "title": recent_complaint.title,
                "status": recent_complaint.status,
                "department": recent_complaint.department.name if recent_complaint.department else "Unassigned",
                "assigned_staff": recent_complaint.assigned_staff.username if recent_complaint.assigned_staff else "Pending Assignment",
                "created_at": recent_complaint.created_at.strftime("%Y-%m-%d %H:%M"),
                "is_overdue": sla_info.get("is_overdue", False),
                "sla_status": sla_info.get("sla_status", "not_configured"),
                "verification_status": recent_complaint.resolution_verification_status,
                "resolution_notes": recent_complaint.resolution_notes or ""
            }
            context_str = (
                f"User's Most Recent Complaint: {comp_dict['tracking_id']} - {comp_dict['title']}\n"
                f"Status: {comp_dict['status']}\n"
                f"Department: {comp_dict['department']}\n"
                f"Assigned Staff: {comp_dict['assigned_staff']}\n"
                f"Overdue: {comp_dict['is_overdue']}"
            )
            return {"handled": False, "context": context_str, "complaint_dict": comp_dict}

        # D. User has no complaints at all
        msg = (
            "You currently have no complaints on file. To report a civic issue, visit the Report page."
            if lang == "en" else
            "वर्तमान में आपका कोई दर्ज शिकायत रिकॉर्ड नहीं है। नई शिकायत दर्ज करने के लिए 'Report' पृष्ठ पर जाएं।"
        )
        return {
            "handled": True,
            "response": {
                "answer": msg,
                "language": lang,
                "intent": "complaint_status",
                "related_complaint": None,
                "suggested_actions": ["File a new complaint at /report"],
                "sources": ["Database Verification"],
                "requires_human_support": False
            }
        }

    @classmethod
    def _generate_assistant_response(
        cls,
        message: str,
        lang: str,
        complaint_context: Optional[str],
        complaint_data: Optional[Dict[str, Any]],
        knowledge_articles: List[Dict[str, Any]],
        base_actions: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Synthesizes an answer using Gemini with structured JSON output or uses a deterministic fallback.
        """
        # Prepare context blocks
        kb_text = ""
        sources = []
        suggested_actions = list(base_actions or [])

        if knowledge_articles:
            for art in knowledge_articles[:2]:
                kb_text += f"\n--- {art['title']} ---\n{art['content']}\nSource: {art['source']}\n"
                sources.append(art["source"])
                suggested_actions.extend(art.get("suggested_actions", []))

        if complaint_data:
            sources.append("JanSahayak Database")
            if complaint_data["status"] == "resolved":
                suggested_actions.append("Confirm resolution or dispute in /citizen")
            elif complaint_data["status"] == "submitted":
                suggested_actions.append("Await department triage")

        # Fallback response generator in case Gemini is offline or fails
        fallback_answer = cls._generate_deterministic_fallback(
            message=message,
            lang=lang,
            complaint_data=complaint_data,
            knowledge_articles=knowledge_articles
        )

        # Attempt Gemini Generation
        prompt = (
            f"You are the JanSahayak Civic Assistant. Help the citizen with their civic grievance query.\n"
            f"User Query: \"{message}\"\n"
            f"Detected Language: {lang}\n\n"
            f"VERIFIED DATABASE CONTEXT:\n{complaint_context or 'None'}\n\n"
            f"VERIFIED CIVIC KNOWLEDGE CONTEXT:\n{kb_text or 'None'}\n\n"
            f"RULES:\n"
            f"1. Answer ONLY using the facts from verified database and knowledge context above.\n"
            f"2. Never fabricate phone numbers, government links, or resolution guarantees.\n"
            f"3. Never claim complaints have been dispatched to government authorities unless stated.\n"
            f"4. If verified information is missing, politely say so and recommend contacting the supervisor.\n"
            f"5. Keep answer concise (2-4 sentences max), friendly, and directly actionable.\n"
            f"6. Respond in {lang} language.\n"
            f"7. Return STRICT JSON with keys: 'answer', 'intent', 'suggested_actions', 'requires_human_support'."
        )

        try:
            raw_gemini = call_gemini_safe(prompt)
            if raw_gemini:
                parsed = clean_and_parse_json(raw_gemini)
                if parsed and parsed.get("answer"):
                    actions = parsed.get("suggested_actions", [])
                    if not actions and suggested_actions:
                        actions = suggested_actions[:3]

                    return {
                        "answer": parsed["answer"].strip(),
                        "language": lang,
                        "intent": parsed.get("intent", "civic_guidance"),
                        "related_complaint": complaint_data,
                        "suggested_actions": list(dict.fromkeys(actions))[:3],
                        "sources": list(dict.fromkeys(sources)),
                        "requires_human_support": bool(parsed.get("requires_human_support", False))
                    }
        except Exception as e:
            logger.warning(f"Civic Assistant Gemini call failed: {e}. Using deterministic fallback.")

        # Return validated deterministic fallback
        return {
            "answer": fallback_answer,
            "language": lang,
            "intent": "complaint_status" if complaint_data else "civic_guidance",
            "related_complaint": complaint_data,
            "suggested_actions": list(dict.fromkeys(suggested_actions))[:3],
            "sources": list(dict.fromkeys(sources)) or ["JanSahayak Standard Operating Guidance"],
            "requires_human_support": False
        }

    @classmethod
    def _generate_deterministic_fallback(
        cls,
        message: str,
        lang: str,
        complaint_data: Optional[Dict[str, Any]],
        knowledge_articles: List[Dict[str, Any]]
    ) -> str:
        """
        Safe, reliable deterministic answer generator when AI is offline.
        """
        # If personal complaint inquiry
        if complaint_data:
            if lang == "hi":
                status_hi = {
                    "submitted": "दर्ज (समीक्षा लंबित)",
                    "assigned": "फील्ड अधिकारी को आवंटित",
                    "in_progress": "प्रगति पर",
                    "resolved": "समाधान पूर्ण (पुष्टि हेतु प्रतीक्षारत)",
                    "verified": "सत्यापित एवं बंद",
                    "escalated": "अग्रसारित"
                }.get(complaint_data["status"], complaint_data["status"])

                overdue_txt = " (समय-सीमा समाप्त / Overdue)" if complaint_data.get("is_overdue") else ""
                ans = (
                    f"आपकी शिकायत ({complaint_data['tracking_id']}) वर्तमान में '{status_hi}' स्थिति में है{overdue_txt}। "
                    f"यह '{complaint_data['department']}' विभाग को सौंपी गई है। "
                )
                if complaint_data["status"] == "resolved":
                    ans += "कृपया सिटिजन पोर्टल (/citizen) पर जाकर समाधान की पुष्टि या आपत्ति (Dispute) दर्ज करें।"
                else:
                    ans += "फील्ड अधिकारी कार्य पूरा होते ही समाधान का फोटो प्रमाण अपलोड करेंगे।"
                return ans
            else:
                overdue_txt = " [Overdue]" if complaint_data.get("is_overdue") else ""
                ans = (
                    f"Your complaint ({complaint_data['tracking_id']}) is currently '{complaint_data['status'].replace('_', ' ').title()}'{overdue_txt}, "
                    f"allocated to the {complaint_data['department']} department. "
                )
                if complaint_data["status"] == "resolved":
                    ans += "Please visit your Citizen Portal (/citizen) to verify the resolution or dispute it if incomplete."
                else:
                    ans += "The assigned field officer will upload resolution proof once work concludes."
                return ans

        # If matching knowledge article exists
        if knowledge_articles:
            top = knowledge_articles[0]
            return top["content"]

        # Default general guidance
        if lang == "hi":
            return (
                "JanSahayak नागरिक सहायता में आपका स्वागत है। आप नई शिकायत दर्ज करने के नियम, "
                "अपनी शिकायत की स्थिति (Status), अथवा जल, सड़क, कचरा और बिजली संबंधी दिशानिर्देश पूछ सकते हैं।"
            )
        else:
            return (
                "Welcome to JanSahayak Civic Assistant. You can ask how to file a complaint, "
                "check your grievance tracking status, or learn about road, water, waste, and electrical municipal guidelines."
            )
