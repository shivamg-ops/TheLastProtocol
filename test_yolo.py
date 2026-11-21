
from app.ai.yolo_detector import detect_civic_issues

default_path = r"D:\JanSahayak-AI\testing images\Screenshot 2026-11-21 210451.png"
image_path = input(f"Enter image path [{default_path}]: ").strip().strip('"') or default_path


try:
    result = detect_civic_issues(image_path)

    print("\n===== JANSAHAYAK YOLO RESULTS =====")
    print("Detection count:", result["detection_count"])

    for detection in result["detections"]:
        print(
            f"Class: {detection['class']} | "
            f"Confidence: {detection['confidence']} | "
            f"Box: {detection['bbox_xyxy']}"
        )

except Exception as error:
    print("YOLO Error:", error)
