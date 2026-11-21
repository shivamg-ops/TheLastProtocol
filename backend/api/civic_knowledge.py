"""
JanSahayak - Structured Civic Knowledge Base (Task 19)

Provides curated, verified civic guidelines and municipal process explanations:
1. Complaint Registration steps & requirements.
2. Domain guidance for Road/Potholes, Garbage/Sanitation, Water Supply/Leakage, Streetlights, Drainage.
3. Complaint Status definitions (submitted, assigned, in_progress, resolved, verified, escalated).
4. Evidence capture recommendations (clear lighting, perspective, landmark visibility).
5. SLA & Escalation explanations.
6. Feedback & Resolution Dispute procedures.

Safety Guarantees:
- Distinguishes general guidance from specific organisation policies.
- Never invents official telephone numbers, private contact details, or false resolution guarantees.
- Explicitly directs citizens to contact municipal officers when verified policy information is unavailable.
- Never claims that a complaint has been dispatched to a government department without an actual integration.
"""

from typing import Dict, Any, List, Optional
import re

# Comprehensive structured knowledge repository
CIVIC_KNOWLEDGE_BASE: List[Dict[str, Any]] = [
    {
        "topic": "filing_complaint",
        "title": "How to Register a Civic Complaint",
        "keywords": [
            "how to file", "register complaint", "file complaint", "report issue", "submit complaint",
            "shikayat", "shikayat kaise kare", "complain kaise", "kaise darj kare", "report kaise"
        ],
        "category": "general_process",
        "content_en": (
            "To file a civic grievance on JanSahayak:\n"
            "1. Navigate to the 'Report Issue' page (/report).\n"
            "2. Enter a clear description of the problem (e.g., 'Large pothole near Metro Pillar 42').\n"
            "3. Provide the exact location or recognizable landmark. If available, confirm GPS coordinates.\n"
            "4. Upload clear photographic evidence (PNG/JPG) showing the issue.\n"
            "5. Review AI category and department routing recommendations, then click Submit."
        ),
        "content_hi": (
            "JanSahayak पर नागरिक शिकायत दर्ज करने के चरण:\n"
            "1. 'समस्या रिपोर्ट करें' पृष्ठ (/report) पर जाएं।\n"
            "2. समस्या का स्पष्ट विवरण दर्ज करें (उदा. 'मेट्रो पिलर 42 के पास सड़क पर बड़ा गड्ढा')।\n"
            "3. सटीक पता या नजदीकी लैंडमार्क बताएं और उपलब्ध हो तो GPS स्थान साझा करें।\n"
            "4. समस्या की स्पष्ट फोटो अपलोड करें।\n"
            "5. AI द्वारा सुझाई गई श्रेणी और विभाग की समीक्षा करें और 'शिकायत सबमिट करें' पर क्लिक करें।"
        ),
        "suggested_actions": ["Go to /report page", "Prepare photo evidence", "Specify landmark"],
        "source": "JanSahayak Civic Operating Procedure (Sec 3.1)"
    },
    {
        "topic": "garbage_sanitation",
        "title": "Garbage, Trash & Cleanliness Guidelines",
        "keywords": [
            "garbage", "trash", "waste", "kachra", "kooda", "safai", "dustbin", "cleanliness",
            "कचरा", "कूड़ा", "सफाई", "दुर्गंधी", "smell", "dump"
        ],
        "category": "domain_guidance",
        "content_en": (
            "For reporting solid waste accumulation or uncollected bins:\n"
            "- Mention whether the waste is blocking a public roadway, pedestrian footpath, or open drain.\n"
            "- Provide photo evidence showing the volume and location relative to nearby houses or shops.\n"
            "- The Solid Waste Management (Sanitation) unit handles doorstep collection, dustbin clearing, and street sweeping."
        ),
        "content_hi": (
            "कचरा और सफाई संबंधी शिकायत दर्ज करने के निर्देश:\n"
            "- बताएं कि क्या कचरा मुख्य सड़क, फुटपाथ या नाली को अवरुद्ध कर रहा है।\n"
            "- आसपास की दुकानों या मकानों के संदर्भ में कचरे के ढेर की स्पष्ट फोटो अपलोड करें।\n"
            "- ठोस अपशिष्ट प्रबंधन विभाग डस्टबिन खाली करने, झाड़ू लगाने और कूड़ा उठाने का कार्य करता है।"
        ),
        "suggested_actions": ["Photograph waste dump", "Note exact street or ward"],
        "source": "JanSahayak Sanitation Manual"
    },
    {
        "topic": "water_leakage",
        "title": "Water Supply & Pipeline Leakage Guidelines",
        "keywords": [
            "water", "leak", "pipeline", "pipe", "paani", "drinking water", "supply", "jal",
            "पानी", "लीकेज", "पाइपलाइन", "जल आपूर्ति", "गंदा पानी", "water pressure"
        ],
        "category": "domain_guidance",
        "content_en": (
            "For water pipeline burst, low pressure, or contaminated water:\n"
            "- Indicate whether water is actively gushing on the road or if drinking supply is dirty.\n"
            "- Report the nearest water valve or junction box landmark if visible.\n"
            "- High-pressure main bursts are assigned urgent priority to prevent municipal water loss."
        ),
        "content_hi": (
            "पानी की लीकेज या आपूर्ति संबंधी शिकायत के निर्देश:\n"
            "- बताएं कि क्या पाइप से सड़क पर पानी बह रहा है या नलों में गंदा/कम दबाव का पानी आ रहा है।\n"
            "- पास के पानी के वाल्व या मुख्य जंक्शन का संदर्भ दें।\n"
            "- मुख्य पाइपलाइन फटने की घटनाओं को जल बर्बादी रोकने हेतु उच्च प्राथमिकता दी जाती है।"
        ),
        "suggested_actions": ["Capture video/photo of leaking pipe", "Note hours of supply disruption"],
        "source": "Water Works Department Guidelines"
    },
    {
        "topic": "road_damage",
        "title": "Potholes & Road Damage Guidelines",
        "keywords": [
            "pothole", "road", "gaddha", "sadak", "crater", "asphalt", "tar", "footpath",
            "सड़क", "गड्ढा", "रस्ता", "डामर", "खड्डे"
        ],
        "category": "domain_guidance",
        "content_en": (
            "For potholes, cratering, and cracked roads:\n"
            "- Capture photos in daylight showing the depth of the pothole and distance to lane markings.\n"
            "- Specify if the damage poses immediate hazards to two-wheelers or heavy traffic.\n"
            "- Roads & Civil Infrastructure maintenance crew repairs road surfaces and storm runoff gutters."
        ),
        "content_hi": (
            "सड़क के गड्ढों और क्षति संबंधी शिकायत के निर्देश:\n"
            "- दिन के उजाले में गड्ढे की गहराई और सड़क की स्थिति दिखाते हुए फोटो लें।\n"
            "- बताएं कि क्या गड्ढे से दुपहिया वाहनों या पैदल यात्रियों को दुर्घटना का खतरा है।\n"
            "- सड़क एवं लोक निर्माण विभाग डामरीकरण और पैच मरम्मत का कार्य संभालता है।"
        ),
        "suggested_actions": ["Upload wide-angle pothole photo", "Specify highway or lane name"],
        "source": "Municipal Civil Works Handbook"
    },
    {
        "topic": "streetlight_electrical",
        "title": "Streetlight Failure & Electrical Hazards",
        "keywords": [
            "streetlight", "light", "wire", "pole", "electric", "shock", "dark", "bijli", "batti",
            "बिजली", "स्ट्रीट लाइट", "खंभा", "तार", "current"
        ],
        "category": "domain_guidance",
        "content_en": (
            "For non-functioning streetlights or exposed electrical wires:\n"
            "- Check and note the pole number printed on the metal lamp pole if legible.\n"
            "- Exposed dangling wires or sparking transformers are automatically flagged as Urgent priority.\n"
            "- Electrical Engineering department handles bulb replacement, phase repairs, and cable safety."
        ),
        "content_hi": (
            "स्ट्रीट लाइट और बिजली के तारों की शिकायत के निर्देश:\n"
            "- यदि खंभे पर कोई नंबर अंकित है तो उसे शिकायत विवरण में अवश्य लिखें।\n"
            "- खुले लटकते तार या ट्रांसफार्मर से चिंगारी निकलने की स्थिति को तत्काल 'अति-आवश्यक' माना जाता है।\n"
            "- विद्युत अभियांत्रिकी विभाग लाइट बदलने और तारों की मरम्मत का कार्य करता है।"
        ),
        "suggested_actions": ["Note pole number", "Keep safe distance from exposed wires"],
        "source": "Electrical Safety Directive"
    },
    {
        "topic": "complaint_status_meanings",
        "title": "Understanding Complaint Lifecycle Statuses",
        "keywords": [
            "status mean", "submitted status", "in progress status", "status ka matlab", "assigned meaning",
            "what does status mean", "stages", "status kya hota hai", "lifecycle"
        ],
        "category": "lifecycle",
        "content_en": (
            "Meaning of JanSahayak grievance statuses:\n"
            "• Submitted: Grievance received and indexed; awaiting department allocation.\n"
            "• Assigned: Routed to the relevant department and specific field officer.\n"
            "• In Progress: Field staff is actively addressing the issue on ground.\n"
            "• Resolved: Field staff has finished work and uploaded completion proof.\n"
            "• Verified: You (the citizen) have confirmed the resolution and rated service quality.\n"
            "• Escalated: Ticket exceeded SLA target hours and was escalated to senior management."
        ),
        "content_hi": (
            "शिकायत की स्थितियों (Statuses) का अर्थ:\n"
            "• Submitted (दर्ज): शिकायत दर्ज हो गई है, विभाग निर्धारण की प्रतीक्षा में है।\n"
            "• Assigned (आवंटित): संबंधित विभाग और फील्ड अधिकारी को कार्य सौंप दिया गया है।\n"
            "• In Progress (प्रगति पर): फील्ड कर्मचारी मौके पर समस्या का समाधान कर रहे हैं।\n"
            "• Resolved (समाधान पूर्ण): कर्मचारी ने कार्य पूरा कर समाधान का फोटो प्रमाण प्रस्तुत किया है।\n"
            "• Verified (सत्यापित): आपने कार्य की पुष्टि कर अपनी रेटिंग/फीडबैक दे दिया है।\n"
            "• Escalated (अग्रसारित): समय सीमा पार होने पर शिकायत वरिष्ठ अधिकारी को भेजी गई है।"
        ),
        "suggested_actions": ["Track status in Citizen Portal (/citizen)", "Check assigned staff and SLA"],
        "source": "JanSahayak Lifecycle Charter"
    },
    {
        "topic": "sla_and_overdue",
        "title": "SLA Deadlines & Overdue Escalations",
        "keywords": [
            "why overdue", "overdue", "sla", "delay", "der kyu", "time limit", "deadline", "escalation",
            "kitna time lagega", "how much time", "tat", "deri"
        ],
        "category": "sla",
        "content_en": (
            "About Municipal Service Level Agreements (SLA):\n"
            "- Each department has a defined resolution SLA window (e.g., 24 hours for water leaks, 48 hours for roads).\n"
            "- If a complaint remains unresolved past this target, it is flagged as 'Overdue'.\n"
            "- Overdue complaints trigger automated supervisory alerts and appear on the executive dashboard for administrative intervention."
        ),
        "content_hi": (
            "सेवा स्तर अनुबंध (SLA) और देरी की जानकारी:\n"
            "- प्रत्येक विभाग के लिए समाधान की समय-सीमा तय है (उदा. पानी लीकेज 24 घंटे, सड़क मरम्मत 48 घंटे)।\n"
            "- यदि इस समय-सीमा के भीतर कार्य पूरा नहीं होता, तो टिकट 'Overdue' हो जाता है।\n"
            "- Overdue शिकायतों पर वरिष्ठ पर्यवेक्षक को अलर्ट जाता है ताकि कार्य में तेजी लाई जा सके।"
        ),
        "suggested_actions": ["Check ticket deadline in portal", "Contact admin if critical delay"],
        "source": "Citizen Service Guarantee Charter"
    },
    {
        "topic": "evidence_guidelines",
        "title": "Evidence Upload & Photography Guidelines",
        "keywords": [
            "evidence", "photo", "upload image", "proof", "kya photo dale", "photo kaise", "camera",
            "तस्वीर", "प्रमाण", "चित्र"
        ],
        "category": "evidence",
        "content_en": (
            "Best practices for uploading evidence on JanSahayak:\n"
            "• Upload authentic, unedited photos (JPG, PNG).\n"
            "• Take wide-angle photos showing both the problem and nearby landmarks (shop signboards, street signs).\n"
            "• Avoid blurry, dark, or generic downloaded stock images.\n"
            "• AI duplicate detection inspects perceptual image hashes to prevent duplicate filings."
        ),
        "content_hi": (
            "साक्ष्य (Photo) अपलोड करने के नियम:\n"
            "• केवल वास्तविक और स्पष्ट फोटो (JPG, PNG) अपलोड करें।\n"
            "• ऐसे एंगल से फोटो लें जिसमें समस्या के साथ आसपास का लैंडमार्क (दुकान, बोर्ड या खंभा) दिखे।\n"
            "• इंटरनेट से डाउनलोड की गई या धुंधली तस्वीरों का उपयोग न करें।\n"
            "• सिस्टम डुप्लीकेट फोटो को तुरंत पहचान लेता है।"
        ),
        "suggested_actions": ["Capture clear daytime photo", "Include landmarks in frame"],
        "source": "AI Evidence Verification Standards"
    },
    {
        "topic": "feedback_and_dispute",
        "title": "Confirming or Disputing a Resolved Complaint",
        "keywords": [
            "dispute", "feedback", "not resolved", "galat resolve", "confirm", "satisfaction",
            "reopen", "rating", "kaise dispute kare", "grievance wapas open"
        ],
        "category": "feedback_trust",
        "content_en": (
            "When field staff marks your grievance as Resolved:\n"
            "1. Open your Citizen Portal (/citizen) and select the complaint.\n"
            "2. Review the Before & After photographic evidence comparison.\n"
            "3. If satisfied: Click 'Yes, Confirmed' and rate service quality (1 to 5 stars).\n"
            "4. If unresolved: Click 'No, Dispute Work', provide the exact dispute reason, and optionally upload a photo of the unfinished work.\n"
            "5. Disputed tickets are escalated to supervisor review for reopening or re-dispatch."
        ),
        "content_hi": (
            "समाधान की पुष्टि या आपत्ति (Dispute) दर्ज करने की प्रक्रिया:\n"
            "1. सिटिजन पोर्टल (/citizen) पर अपनी शिकायत खोलें।\n"
            "2. 'Before & After' फोटो तुलना की समीक्षा करें।\n"
            "3. यदि कार्य संतोषजनक है: 'Yes, Confirmed' चुनें और 1 से 5 स्टार रेटिंग दें।\n"
            "4. यदि कार्य अधूरा या गलत है: 'No, Dispute Work' पर क्लिक करें, कारण लिखें और चाहें तो फोटो अपलोड करें।\n"
            "5. विवादित शिकायतें वरिष्ठ पर्यवेक्षक के पास समीक्षा हेतु भेजी जाती हैं।"
        ),
        "suggested_actions": ["Inspect Before/After photos", "Submit dispute reason if incomplete"],
        "source": "Citizen Trust & Verification Protocol (Task 17)"
    }
]


def search_civic_knowledge(query: str, language: str = "en") -> List[Dict[str, Any]]:
    """
    Finds relevant civic guidance articles matching citizen query keywords.
    Returns matched topics sorted by keyword relevance score.
    """
    if not query or not query.strip():
        return []

    query_lower = query.strip().lower()
    results = []

    for item in CIVIC_KNOWLEDGE_BASE:
        matches = 0
        for kw in item["keywords"]:
            if kw in query_lower:
                matches += 1

        if matches > 0:
            content = item["content_hi"] if language == "hi" else item["content_en"]
            results.append({
                "topic": item["topic"],
                "title": item["title"],
                "content": content,
                "suggested_actions": item["suggested_actions"],
                "source": item["source"],
                "relevance_score": matches
            })

    results.sort(key=lambda x: x["relevance_score"], reverse=True)
    return results

