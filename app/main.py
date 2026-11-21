
import json

from app.ai.gemini_client import analyze_complaint
from app.ai.department_router import route_complaint
from app.ai.clarification_engine import (
    generate_clarification_question,
    update_complaint
)


complaint = "Mere area mein 3 din se kachra nahi uthaya gaya hai."

try:
    print("\n===== JANSAHAYAK AI =====\n")

    # 1. Analyse original complaint
    result = analyze_complaint(complaint)
    complaint_data = json.loads(result)

    # 2. Find responsible department
    complaint_data["routing"] = route_complaint(
        complaint_data["category"]
    )

    print("INITIAL COMPLAINT:")
    print(json.dumps(complaint_data, indent=4, ensure_ascii=False))

    # 3. Ask citizen for missing information
    clarification = generate_clarification_question(
        complaint_data
    )

    print("\nJANSAHAYAK ASKS:")
    print(clarification["question"])

    # 4. Receive citizen's reply
    if clarification["needs_clarification"]:
        citizen_reply = input("\nCITIZEN REPLY: ")

        if citizen_reply.strip():
            updated_data = update_complaint(
                complaint_data,
                citizen_reply
            )

            # Recheck department routing
            updated_data["routing"] = route_complaint(
                updated_data["category"]
            )

            print("\nUPDATED COMPLAINT:")
            print(json.dumps(
                updated_data,
                indent=4,
                ensure_ascii=False
            ))

except Exception as error:
    print("\nError:", error)
