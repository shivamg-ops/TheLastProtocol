
import json
from app.ai.image_analyzer import analyze_image

default_path = r"D:\JanSahayak-AI\testing images\Screenshot 2026-11-21 210451.png"

image_path = input(
    f"Enter image path [{default_path}]: "
).strip().strip('"') or default_path

complaint = input("Enter citizen complaint: ").strip()

try:
    result = analyze_image(image_path, complaint)

    print("\n===== JANSAHAYAK COMPLETE AI PIPELINE =====")

    print("\n1. ISSUE DETECTED:")
    print(result["issue_detected"])

    print("\n2. GEMINI CATEGORY:")
    print(result["category"])

    print("\n3. YOLO DETECTIONS:")
    print(json.dumps(
        result["ai_models"]["yolo"],
        indent=4
    ))

    print("\n4. MODEL AGREEMENT:")
    print(result["model_agreement"])

    print("\n5. COMPLAINT-EVIDENCE MATCH:")
    print(result["complaint_evidence_match"])

    print("\n6. HUMAN REVIEW REQUIRED:")
    print(result["needs_human_review"])

    print("\n7. COMPLETE JSON RESPONSE:")
    print(json.dumps(
        result,
        indent=4,
        ensure_ascii=False
    ))

except Exception as error:
    print("\nPipeline Error:", error)
