"""
Smart Home Assistant - Object Detection Service Module

Integrates YOLO for fast local object detection to identify motion events
worth processing with LLM vision. Filters out empty frames to save LLM calls.

WP-11.1: YOLO Object Detection Integration
- Local object detection using YOLOv8
- Identifies "interesting" objects (person, pet, package, vehicle)
- Runs in < 200ms per frame
- Resource usage < 5% CPU when idle
"""

import io
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.config import DATA_DIR
from src.utils import setup_logging


logger = setup_logging("object_detection")

# =============================================================================
# Configuration
# =============================================================================

# Default model - yolov8n.pt is the nano model (fastest, smallest)
# Other options: yolov8s.pt (small), yolov8m.pt (medium), yolov8l.pt (large)
DEFAULT_MODEL_NAME = "yolov8n.pt"

# Default confidence threshold
DEFAULT_CONFIDENCE_THRESHOLD = 0.5

# Maximum detections per frame
DEFAULT_MAX_DETECTIONS = 20

# Default interesting classes for smart home monitoring
# These are the COCO class names that YOLO detects
DEFAULT_INTERESTING_CLASSES = [
    "person",
    "cat",
    "dog",
    "bird",
    "car",
    "truck",
    "motorcycle",
    "bicycle",
    "bus",
    "backpack",  # Could be a package
    "suitcase",  # Could be a package
    "handbag",   # Could be a package
]

# Mapping from COCO classes to smart home categories
PACKAGE_CLASS_MAPPINGS = ["backpack", "suitcase", "handbag"]

# COCO class ID to name mapping (subset of common classes)
# Full list at https://github.com/ultralytics/ultralytics/blob/main/ultralytics/cfg/datasets/coco.yaml
COCO_CLASSES = {
    0: "person",
    1: "bicycle",
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
    14: "bird",
    15: "cat",
    16: "dog",
    17: "horse",
    24: "backpack",
    26: "handbag",
    28: "suitcase",
    67: "cell phone",
}


# =============================================================================
# Configuration Dataclass
# =============================================================================


@dataclass
class ObjectDetectorConfig:
    """Configuration for the object detector."""

    model_name: str = DEFAULT_MODEL_NAME
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD
    max_detections: int = DEFAULT_MAX_DETECTIONS
    interesting_classes: list[str] = field(default_factory=lambda: DEFAULT_INTERESTING_CLASSES.copy())
    device: str = "cpu"  # "cpu" or "cuda" for GPU

    @classmethod
    def from_dict(cls, config_dict: dict[str, Any]) -> "ObjectDetectorConfig":
        """Create config from dictionary."""
        return cls(
            model_name=config_dict.get("model_name", DEFAULT_MODEL_NAME),
            confidence_threshold=config_dict.get("confidence_threshold", DEFAULT_CONFIDENCE_THRESHOLD),
            max_detections=config_dict.get("max_detections", DEFAULT_MAX_DETECTIONS),
            interesting_classes=config_dict.get("interesting_classes", DEFAULT_INTERESTING_CLASSES.copy()),
            device=config_dict.get("device", "cpu"),
        )


# =============================================================================
# Object Detector
# =============================================================================


class ObjectDetector:
    """
    YOLO-based object detector for camera snapshots.

    Provides fast local object detection to filter frames before
    sending to LLM for detailed description.
    """

    def __init__(self, config: ObjectDetectorConfig | None = None):
        """
        Initialize the object detector.

        Args:
            config: Optional configuration. Uses defaults if not provided.
        """
        self.config = config or ObjectDetectorConfig()
        self._model = None
        self._lock = threading.Lock()

        # Metrics tracking
        self._total_detections = 0
        self._total_processing_time_ms = 0
        self._detection_history: list[dict] = []

    def _load_model(self) -> Any:
        """
        Lazily load the YOLO model.

        Returns:
            YOLO model instance
        """
        if self._model is None:
            with self._lock:
                if self._model is None:  # Double-check locking
                    try:
                        from ultralytics import YOLO

                        logger.info(f"Loading YOLO model: {self.config.model_name}")
                        self._model = YOLO(self.config.model_name)
                        logger.info("YOLO model loaded successfully")
                    except ImportError:
                        raise RuntimeError(
                            "ultralytics package not installed. "
                            "Install with: pip install ultralytics"
                        )
        return self._model

    def detect(self, image_data: bytes | None) -> dict[str, Any]:
        """
        Detect objects in an image.

        Args:
            image_data: Raw image bytes (JPEG or PNG)

        Returns:
            Detection result dict with:
            - success: bool
            - detections: list of detected objects
            - has_interesting_objects: bool
            - interesting_classes: list of detected interesting class names
            - processing_time_ms: int
            - error: str (if success is False)
        """
        start_time = time.time()

        # Validate input
        if image_data is None:
            return {
                "success": False,
                "error": "Image data is None",
                "detections": [],
                "has_interesting_objects": False,
                "interesting_classes": [],
                "processing_time_ms": 0,
            }

        if len(image_data) == 0:
            return {
                "success": False,
                "error": "Image data is empty",
                "detections": [],
                "has_interesting_objects": False,
                "interesting_classes": [],
                "processing_time_ms": 0,
            }

        try:
            # Load model if needed
            model = self._load_model()

            # Convert bytes to image
            from PIL import Image
            image = Image.open(io.BytesIO(image_data))

            # Run detection
            results = model.predict(
                source=image,
                conf=self.config.confidence_threshold,
                verbose=False,
                device=self.config.device,
            )

            # Process results
            detections = []
            interesting_classes = set()

            if results and len(results) > 0:
                result = results[0]

                # Get detections from boxes
                boxes = result.boxes.xyxy.cpu().numpy()
                confidences = result.boxes.conf.cpu().numpy()
                class_ids = result.boxes.cls.cpu().numpy()
                names = result.names

                for i, (box, conf, cls_id) in enumerate(zip(boxes, confidences, class_ids)):
                    if i >= self.config.max_detections:
                        break

                    class_name = names.get(int(cls_id), f"class_{int(cls_id)}")

                    # Filter by confidence (should already be filtered, but double-check)
                    if conf < self.config.confidence_threshold:
                        continue

                    # Check if this is an interesting class
                    is_interesting = class_name in self.config.interesting_classes

                    if is_interesting:
                        interesting_classes.add(class_name)
                        detections.append({
                            "class_name": class_name,
                            "class_id": int(cls_id),
                            "confidence": float(conf),
                            "bbox": {
                                "x1": int(box[0]),
                                "y1": int(box[1]),
                                "x2": int(box[2]),
                                "y2": int(box[3]),
                            },
                        })

            # Calculate processing time
            processing_time_ms = int((time.time() - start_time) * 1000)

            # Update metrics
            self._total_detections += 1
            self._total_processing_time_ms += processing_time_ms

            result_dict = {
                "success": True,
                "detections": detections,
                "has_interesting_objects": len(interesting_classes) > 0,
                "interesting_classes": list(interesting_classes),
                "processing_time_ms": processing_time_ms,
                "total_objects_found": len(boxes) if results and len(results) > 0 else 0,
            }

            if interesting_classes:
                logger.debug(
                    f"Detected {len(detections)} interesting objects: {interesting_classes} "
                    f"in {processing_time_ms}ms"
                )

            return result_dict

        except Exception as error:
            processing_time_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Object detection failed: {error}")
            return {
                "success": False,
                "error": str(error),
                "detections": [],
                "has_interesting_objects": False,
                "interesting_classes": [],
                "processing_time_ms": processing_time_ms,
            }

    def get_metrics(self) -> dict[str, Any]:
        """
        Get detection metrics.

        Returns:
            Metrics dict with detection statistics
        """
        avg_time = (
            self._total_processing_time_ms / self._total_detections
            if self._total_detections > 0
            else 0
        )

        return {
            "total_detections": self._total_detections,
            "total_processing_time_ms": self._total_processing_time_ms,
            "avg_processing_time_ms": round(avg_time, 2),
            "model_name": self.config.model_name,
            "confidence_threshold": self.config.confidence_threshold,
        }

    def get_resource_usage(self) -> dict[str, Any]:
        """
        Get resource usage information.

        Returns:
            Resource usage dict
        """
        model_loaded = self._model is not None

        result = {
            "model_loaded": model_loaded,
            "model_name": self.config.model_name,
            "device": self.config.device,
        }

        if model_loaded:
            # Try to get memory usage
            try:
                import sys
                model_size = sys.getsizeof(self._model)
                result["model_memory_mb"] = round(model_size / (1024 * 1024), 2)
            except Exception:
                result["model_memory_mb"] = None

        return result

    def unload_model(self) -> None:
        """
        Unload the model to free memory.

        Useful when detector is not being used.
        """
        with self._lock:
            if self._model is not None:
                logger.info("Unloading YOLO model")
                self._model = None


# =============================================================================
# Module-Level Convenience Functions
# =============================================================================


_detector: ObjectDetector | None = None


def get_object_detector() -> ObjectDetector:
    """
    Get or create the global object detector instance.

    Returns:
        ObjectDetector instance
    """
    global _detector
    if _detector is None:
        _detector = ObjectDetector()
    return _detector


def detect_objects(image_data: bytes) -> dict[str, Any]:
    """
    Detect objects in an image (convenience function).

    Args:
        image_data: Raw image bytes

    Returns:
        Detection result dict
    """
    return get_object_detector().detect(image_data)


def is_interesting_frame(image_data: bytes) -> bool:
    """
    Check if a frame contains interesting objects.

    Use this to filter frames before LLM processing.

    Args:
        image_data: Raw image bytes

    Returns:
        True if frame contains interesting objects
    """
    result = detect_objects(image_data)
    return result.get("has_interesting_objects", False)
