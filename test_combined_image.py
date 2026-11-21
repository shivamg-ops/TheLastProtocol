
import json
from app.ai.image_analyzer import analyze_image

default_path = r"D:\JanSahayak-AI\testing images\Screenshot 2026-11-21 210451.png"
image_path = input(f"Enter image path [{default_path}]: ").strip().strip('"') or default_path

complaint = input(
    "Enter citizen complaint: "
).strip()

try:
    result = analyze_image(
        image_path,
        complaint
    )

    print("\n===== JANSAHAYAK COMBINED AI ANALYSIS =====")

    print(json.dumps(
        result,
        indent=4,
        ensure_ascii=False
    ))

except Exception as error:
    print("\nAnalysis Error:", error)
