"""
JanSahayak - Modular Ultralytics YOLO Civic Object Detector

Features:
1. Singleton Detector Pattern to prevent repeated model reloads on every request.
2. Configurable model path via `YOLO_MODEL_PATH` environment variable.
3. Class Truthfulness Enforcement:
   - Generic pretrained COCO models (e.g. yolov8n.pt) DO NOT support civic damage classes
     such as 'pothole', 'garbage_pile', or 'waterlogging'.
   - This detector checks the model's actual loaded class dictionary (`model.names`).
   - If an object class is not genuinely trained in the model, it is NEVER claimed as detected.
4. Comprehensive Error Handling:
   - Missing model files -> detection_status='model_not_found'
   - Corrupted or invalid images -> detection_status='invalid_image'
   - Inference failures -> detection_status='error'
5. Clean structured JSON output:
   {
       "detected_objects": list of dicts with [class_name, confidence, bounding_boxes],
       "civic_classes_supported": list of matched civic classes,
       "model_name": str,
       "detection_status": "success" | "no_detections" | "model_not_found" | "model_unsupported" | "error",
       "summary": str
   }
"""

import os
import logging
from typing import Dict, Any, List, Optional
from PIL import Image

logger = logging.getLogger("jansahayak_ai")

# Civic classes of interest in municipal complaints
TARGET_CIVIC_CLASSES = {
    'pothole', 'potholes', 'road_damage', 'crack', 'crater',
    'garbage', 'garbage_pile', 'trash', 'waste', 'dump',
    'waterlogging', 'water_puddle', 'flood', 'drain_block', 'sewage_leak'
}

DEFAULT_CONFIDENCE_THRESHOLD = 0.35


class YOLODetector:
    """
    Singleton Manager for Ultralytics YOLO Object Detection.
    """
    _instance: Optional['YOLODetector'] = None
    _model: Optional[Any] = None
    _loaded_path: Optional[str] = None
    _is_initialized: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(YOLODetector, cls).__new__(cls)
        return cls._instance

    @classmethod
    def get_configured_model_path(cls) -> str:
        return os.environ.get("YOLO_MODEL_PATH", "").strip()

    def load_model(self, model_path: Optional[str] = None) -> Optional[Any]:
        """
        Loads the YOLO model into memory once and caches it.
        """
        target_path = model_path or self.get_configured_model_path()
        if not target_path:
            logger.info("YOLO_MODEL_PATH not configured. Operating in safe stub mode.")
            return None

        # Return cached instance if already loaded
        if self._model is not None and self._loaded_path == target_path:
            return self._model

        if not os.path.exists(target_path):
            logger.warning(f"Configured YOLO model file not found at: {target_path}")
            return None

        try:
            from ultralytics import YOLO
            logger.info(f"Loading YOLO model weights from {target_path}...")
            self._model = YOLO(target_path)
            self._loaded_path = target_path
            self._is_initialized = True
            logger.info(f"YOLO model loaded successfully. Classes count: {len(self._model.names)}")
            return self._model
        except Exception as e:
            logger.error(f"Failed to load YOLO model from {target_path}: {e}")
            self._model = None
            self._loaded_path = None
            return None

    def get_supported_classes(self, model: Optional[Any] = None) -> List[str]:
        """
        Returns the list of classes actually trained and supported by the loaded model.
        """
        active_model = model or self._model
        if active_model and hasattr(active_model, 'names') and isinstance(active_model.names, dict):
            return list(active_model.names.values())
        return []

    def detect(
        self,
        image_path: str,
        model_path: Optional[str] = None,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD
    ) -> Dict[str, Any]:
        """
        Executes YOLO object detection on an image.
        Never hallucinates or fabricates civic classes that are not in the model.
        """
        # 1. Validate image file existence
        if not image_path or not os.path.exists(image_path):
            return {
                "detected_objects": [],
                "class_name": None,
                "confidence": 0.0,
                "bounding_boxes": [],
                "model_name": None,
                "detection_status": "invalid_image",
                "summary": "Image file does not exist on disk."
            }

        # 2. Validate image readability using PIL
        try:
            with Image.open(image_path) as img:
                img.verify()
        except Exception as img_err:
            return {
                "detected_objects": [],
                "class_name": None,
                "confidence": 0.0,
                "bounding_boxes": [],
                "model_name": None,
                "detection_status": "invalid_image",
                "summary": f"Image is corrupt or unreadable: {img_err}"
            }

        # 3. Model availability check
        target_path = model_path or self.get_configured_model_path()
        if not target_path or not os.path.exists(target_path):
            return {
                "detected_objects": [],
                "class_name": None,
                "confidence": 0.0,
                "bounding_boxes": [],
                "model_name": os.path.basename(target_path) if target_path else "None",
                "detection_status": "model_not_found",
                "summary": "No trained YOLO weights file configured or found. Fine-tuned civic model required."
            }

        model = self.load_model(target_path)
        if model is None:
            return {
                "detected_objects": [],
                "class_name": None,
                "confidence": 0.0,
                "bounding_boxes": [],
                "model_name": os.path.basename(target_path),
                "detection_status": "error",
                "summary": "Failed to initialize YOLO model instance."
            }

        # 4. Check model trained classes (Truthfulness Check)
        supported_classes = self.get_supported_classes(model)
        supported_civic = [c for c in supported_classes if any(tc in c.lower() for tc in TARGET_CIVIC_CLASSES)]

        # 5. Run Inference
        try:
            results = model.predict(source=image_path, conf=confidence_threshold, verbose=False)
            detected_objects = []

            for result in results:
                boxes = result.boxes
                for box in boxes:
                    cls_id = int(box.cls[0].item())
                    cls_name = model.names.get(cls_id, f"class_{cls_id}")
                    conf = round(float(box.conf[0].item()), 3)
                    
                    # Handle both torch tensor and list/numpy formats safely
                    raw_coords = box.xyxy[0]
                    if hasattr(raw_coords, 'tolist'):
                        coords_list = raw_coords.tolist()
                    else:
                        coords_list = list(raw_coords)
                    xyxy = [round(float(coord), 1) for coord in coords_list]

                    detected_objects.append({
                        "class_name": cls_name,
                        "confidence": conf,
                        "bounding_box": xyxy  # [xmin, ymin, xmax, ymax]
                    })

            # Check if any detected objects
            if detected_objects:
                top_obj = max(detected_objects, key=lambda x: x["confidence"])
                return {
                    "detected_objects": detected_objects,
                    "class_name": top_obj["class_name"],
                    "confidence": top_obj["confidence"],
                    "bounding_boxes": [obj["bounding_box"] for obj in detected_objects],
                    "model_name": os.path.basename(target_path),
                    "detection_status": "success",
                    "supported_civic_classes": supported_civic,
                    "summary": f"Detected {len(detected_objects)} object(s), top: {top_obj['class_name']} ({int(top_obj['confidence']*100)}%)."
                }
            else:
                return {
                    "detected_objects": [],
                    "class_name": None,
                    "confidence": 0.0,
                    "bounding_boxes": [],
                    "model_name": os.path.basename(target_path),
                    "detection_status": "no_detections",
                    "supported_civic_classes": supported_civic,
                    "summary": "No objects met the confidence threshold in the image."
                }

        except Exception as infer_err:
            logger.error(f"YOLO inference error on {image_path}: {infer_err}")
            return {
                "detected_objects": [],
                "class_name": None,
                "confidence": 0.0,
                "bounding_boxes": [],
                "model_name": os.path.basename(target_path),
                "detection_status": "error",
                "summary": f"Inference execution failed: {infer_err}"
            }
