
from pathlib import Path
from ultralytics import YOLO

# Locate the project root and trained model
PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = PROJECT_ROOT / "models" / "best.pt"

if not MODEL_PATH.exists():
    raise FileNotFoundError(
        f"Trained YOLO model not found: {MODEL_PATH}"
    )

# Load model once when this module is imported
model = YOLO(str(MODEL_PATH))


def detect_civic_issues(image_path, confidence=0.25):
    """
    Detect garbage, potholes and waterlogging in an image.
    """

    image_path = Path(image_path)

    if not image_path.is_file():
        raise FileNotFoundError(
            f"Image not found: {image_path}"
        )

    results = model.predict(
        source=str(image_path),
        conf=confidence,
        verbose=False
    )

    result = results[0]
    detections = []

    for box in result.boxes:
        class_id = int(box.cls[0])
        score = float(box.conf[0])

        coordinates = [
            round(float(value), 2)
            for value in box.xyxy[0].tolist()
        ]

        detections.append({
            "class": model.names[class_id],
            "confidence": round(score, 4),
            "bbox_xyxy": coordinates
        })

    return {
        "detection_count": len(detections),
        "detections": detections
    }
