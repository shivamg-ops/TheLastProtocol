
import json

from app.ai.image_analyzer import analyze_image

print("\n===== JANSAHAYAK IMAGE ANALYSIS =====\n")

# Enter the actual image path here
image_path = r"D:\JanSahayak-AI\testing images\Screenshot 2026-11-21 210451.png"

complaint = "There is a pothole on the road."

try:
    result = analyze_image(
        image_path,
        complaint
    )

    print("\nIMAGE ANALYSIS RESULT:\n")

    print(json.dumps(
        result,
        indent=4,
        ensure_ascii=False
    ))

except Exception as error:
    print("\nImage analysis error:", error)
