"""
Tests for the YOLO Object Detection Service

WP-11.1: YOLO Object Detection Integration
Tests for the object detection service that identifies objects
in camera snapshots before LLM processing.
"""

import io
import json
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_yolo_model():
    """Create a mock YOLO model."""
    mock = MagicMock()

    # Mock prediction result
    mock_result = MagicMock()
    mock_result.boxes = MagicMock()
    mock_result.boxes.xyxy = MagicMock()
    mock_result.boxes.xyxy.cpu.return_value.numpy.return_value = [
        [100, 100, 200, 200],  # person bounding box
        [300, 150, 400, 250],  # cat bounding box
    ]
    mock_result.boxes.conf = MagicMock()
    mock_result.boxes.conf.cpu.return_value.numpy.return_value = [0.95, 0.87]
    mock_result.boxes.cls = MagicMock()
    mock_result.boxes.cls.cpu.return_value.numpy.return_value = [0, 15]  # person=0, cat=15

    mock_result.names = {0: 'person', 15: 'cat', 16: 'dog', 2: 'car', 67: 'cell phone'}

    mock.return_value = [mock_result]
    mock.predict.return_value = [mock_result]

    return mock


@pytest.fixture
def sample_image_bytes():
    """Create sample image bytes for testing."""
    # Create a minimal valid JPEG header + data
    # This is a 1x1 pixel white JPEG
    jpeg_bytes = bytes([
        0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01,
        0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
        0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08, 0x07, 0x07, 0x07, 0x09,
        0x09, 0x08, 0x0A, 0x0C, 0x14, 0x0D, 0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12,
        0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D, 0x1A, 0x1C, 0x1C, 0x20,
        0x24, 0x2E, 0x27, 0x20, 0x22, 0x2C, 0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29,
        0x2C, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27, 0x39, 0x3D, 0x38, 0x32,
        0x3C, 0x2E, 0x33, 0x34, 0x32, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01,
        0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xFF, 0xC4, 0x00, 0x1F, 0x00, 0x00,
        0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
        0x09, 0x0A, 0x0B, 0xFF, 0xC4, 0x00, 0xB5, 0x10, 0x00, 0x02, 0x01, 0x03,
        0x03, 0x02, 0x04, 0x03, 0x05, 0x05, 0x04, 0x04, 0x00, 0x00, 0x01, 0x7D,
        0xFF, 0xD9
    ])
    return jpeg_bytes


@pytest.fixture
def object_detector_config():
    """Default object detector configuration."""
    return {
        "model_name": "yolov8n.pt",  # nano model for speed
        "confidence_threshold": 0.5,
        "interesting_classes": ["person", "cat", "dog", "car", "package", "bird"],
        "max_detections": 20,
    }


# =============================================================================
# ObjectDetector Class Tests
# =============================================================================


class TestObjectDetectorInit:
    """Tests for ObjectDetector initialization."""

    def test_init_with_default_config(self):
        """Test initialization with default configuration."""
        from src.object_detection import ObjectDetector, ObjectDetectorConfig

        detector = ObjectDetector()
        assert detector.config is not None
        assert detector.config.confidence_threshold == 0.5
        assert "person" in detector.config.interesting_classes

    def test_init_with_custom_config(self):
        """Test initialization with custom configuration."""
        from src.object_detection import ObjectDetector, ObjectDetectorConfig

        config = ObjectDetectorConfig(
            confidence_threshold=0.7,
            interesting_classes=["cat", "dog"],
        )
        detector = ObjectDetector(config=config)

        assert detector.config.confidence_threshold == 0.7
        assert detector.config.interesting_classes == ["cat", "dog"]

    def test_init_loads_model_lazily(self):
        """Test that model is loaded lazily on first use."""
        from src.object_detection import ObjectDetector

        detector = ObjectDetector()
        # Model should not be loaded until detect() is called
        assert detector._model is None

    def test_config_model_path_default(self):
        """Test default model path configuration."""
        from src.object_detection import ObjectDetectorConfig

        config = ObjectDetectorConfig()
        assert config.model_name == "yolov8n.pt"


class TestObjectDetection:
    """Tests for object detection functionality."""

    @patch("PIL.Image.open")
    @patch("ultralytics.YOLO")
    def test_detect_objects_in_image(self, mock_yolo_class, mock_pil_open, mock_yolo_model, sample_image_bytes):
        """Test detecting objects in an image."""
        from src.object_detection import ObjectDetector

        mock_pil_open.return_value = MagicMock()  # Mock image
        mock_yolo_class.return_value = mock_yolo_model

        detector = ObjectDetector()
        result = detector.detect(sample_image_bytes)

        assert result["success"] is True
        assert len(result["detections"]) == 2
        assert result["detections"][0]["class_name"] == "person"
        assert result["detections"][1]["class_name"] == "cat"

    @patch("PIL.Image.open")
    @patch("ultralytics.YOLO")
    def test_detect_returns_confidence_scores(self, mock_yolo_class, mock_pil_open, mock_yolo_model, sample_image_bytes):
        """Test that confidence scores are returned."""
        from src.object_detection import ObjectDetector

        mock_pil_open.return_value = MagicMock()
        mock_yolo_class.return_value = mock_yolo_model

        detector = ObjectDetector()
        result = detector.detect(sample_image_bytes)

        assert result["detections"][0]["confidence"] == pytest.approx(0.95, rel=0.01)
        assert result["detections"][1]["confidence"] == pytest.approx(0.87, rel=0.01)

    @patch("PIL.Image.open")
    @patch("ultralytics.YOLO")
    def test_detect_returns_bounding_boxes(self, mock_yolo_class, mock_pil_open, mock_yolo_model, sample_image_bytes):
        """Test that bounding boxes are returned."""
        from src.object_detection import ObjectDetector

        mock_pil_open.return_value = MagicMock()
        mock_yolo_class.return_value = mock_yolo_model

        detector = ObjectDetector()
        result = detector.detect(sample_image_bytes)

        bbox = result["detections"][0]["bbox"]
        assert bbox == {"x1": 100, "y1": 100, "x2": 200, "y2": 200}

    @patch("PIL.Image.open")
    @patch("ultralytics.YOLO")
    def test_detect_filters_by_confidence(self, mock_yolo_class, mock_pil_open, sample_image_bytes):
        """Test filtering by confidence threshold."""
        from src.object_detection import ObjectDetector, ObjectDetectorConfig

        mock_pil_open.return_value = MagicMock()

        # Create mock with low confidence detection
        mock_model = MagicMock()
        mock_result = MagicMock()
        mock_result.boxes.xyxy.cpu.return_value.numpy.return_value = [
            [100, 100, 200, 200],
        ]
        mock_result.boxes.conf.cpu.return_value.numpy.return_value = [0.3]  # Below threshold
        mock_result.boxes.cls.cpu.return_value.numpy.return_value = [0]
        mock_result.names = {0: 'person'}
        mock_model.return_value = [mock_result]
        mock_model.predict.return_value = [mock_result]
        mock_yolo_class.return_value = mock_model

        config = ObjectDetectorConfig(confidence_threshold=0.5)
        detector = ObjectDetector(config=config)
        result = detector.detect(sample_image_bytes)

        assert result["success"] is True
        assert len(result["detections"]) == 0

    @patch("PIL.Image.open")
    @patch("ultralytics.YOLO")
    def test_detect_filters_interesting_classes_only(self, mock_yolo_class, mock_pil_open, sample_image_bytes):
        """Test filtering to only interesting classes."""
        from src.object_detection import ObjectDetector, ObjectDetectorConfig

        mock_pil_open.return_value = MagicMock()

        # Create mock with uninteresting class (cell phone)
        mock_model = MagicMock()
        mock_result = MagicMock()
        mock_result.boxes.xyxy.cpu.return_value.numpy.return_value = [
            [100, 100, 200, 200],
        ]
        mock_result.boxes.conf.cpu.return_value.numpy.return_value = [0.9]
        mock_result.boxes.cls.cpu.return_value.numpy.return_value = [67]  # cell phone
        mock_result.names = {67: 'cell phone'}
        mock_model.return_value = [mock_result]
        mock_model.predict.return_value = [mock_result]
        mock_yolo_class.return_value = mock_model

        config = ObjectDetectorConfig(interesting_classes=["person", "cat", "dog"])
        detector = ObjectDetector(config=config)
        result = detector.detect(sample_image_bytes)

        # Cell phone should be filtered out (not interesting for smart home)
        assert result["success"] is True
        assert len(result["detections"]) == 0

    @patch("PIL.Image.open")
    @patch("ultralytics.YOLO")
    def test_detect_empty_image(self, mock_yolo_class, mock_pil_open, sample_image_bytes):
        """Test detection on image with no objects."""
        from src.object_detection import ObjectDetector

        mock_pil_open.return_value = MagicMock()

        # Create mock with empty results
        mock_model = MagicMock()
        mock_result = MagicMock()
        mock_result.boxes.xyxy.cpu.return_value.numpy.return_value = []
        mock_result.boxes.conf.cpu.return_value.numpy.return_value = []
        mock_result.boxes.cls.cpu.return_value.numpy.return_value = []
        mock_result.names = {}
        mock_model.return_value = [mock_result]
        mock_model.predict.return_value = [mock_result]
        mock_yolo_class.return_value = mock_model

        detector = ObjectDetector()
        result = detector.detect(sample_image_bytes)

        assert result["success"] is True
        assert len(result["detections"]) == 0
        assert result["has_interesting_objects"] is False

    @patch("ultralytics.YOLO")
    def test_detect_handles_invalid_image(self, mock_yolo_class):
        """Test handling of invalid image data."""
        from src.object_detection import ObjectDetector

        mock_model = MagicMock()
        mock_model.predict.side_effect = Exception("Invalid image format")
        mock_yolo_class.return_value = mock_model

        detector = ObjectDetector()
        result = detector.detect(b"not an image")

        assert result["success"] is False
        assert "error" in result


class TestInterestingObjectsFilter:
    """Tests for the interesting objects filtering logic."""

    @patch("PIL.Image.open")
    @patch("ultralytics.YOLO")
    def test_person_is_interesting(self, mock_yolo_class, mock_pil_open, mock_yolo_model, sample_image_bytes):
        """Test that person detection marks as interesting."""
        from src.object_detection import ObjectDetector

        mock_pil_open.return_value = MagicMock()
        mock_yolo_class.return_value = mock_yolo_model

        detector = ObjectDetector()
        result = detector.detect(sample_image_bytes)

        assert result["has_interesting_objects"] is True
        assert "person" in result["interesting_classes"]

    @patch("PIL.Image.open")
    @patch("ultralytics.YOLO")
    def test_pet_is_interesting(self, mock_yolo_class, mock_pil_open, mock_yolo_model, sample_image_bytes):
        """Test that pet detection marks as interesting."""
        from src.object_detection import ObjectDetector

        mock_pil_open.return_value = MagicMock()
        mock_yolo_class.return_value = mock_yolo_model

        detector = ObjectDetector()
        result = detector.detect(sample_image_bytes)

        assert "cat" in result["interesting_classes"]

    def test_package_detection_label_mapping(self):
        """Test that package-related classes are mapped correctly."""
        from src.object_detection import PACKAGE_CLASS_MAPPINGS

        # YOLO doesn't have "package" directly, so we map related classes
        assert "suitcase" in PACKAGE_CLASS_MAPPINGS or "backpack" in PACKAGE_CLASS_MAPPINGS

    @patch("PIL.Image.open")
    @patch("ultralytics.YOLO")
    def test_vehicle_is_interesting(self, mock_yolo_class, mock_pil_open, sample_image_bytes):
        """Test that vehicle detection marks as interesting."""
        from src.object_detection import ObjectDetector, ObjectDetectorConfig

        mock_pil_open.return_value = MagicMock()

        mock_model = MagicMock()
        mock_result = MagicMock()
        mock_result.boxes.xyxy.cpu.return_value.numpy.return_value = [[50, 50, 400, 300]]
        mock_result.boxes.conf.cpu.return_value.numpy.return_value = [0.85]
        mock_result.boxes.cls.cpu.return_value.numpy.return_value = [2]  # car
        mock_result.names = {2: 'car'}
        mock_model.return_value = [mock_result]
        mock_model.predict.return_value = [mock_result]
        mock_yolo_class.return_value = mock_model

        config = ObjectDetectorConfig(interesting_classes=["car", "truck", "person"])
        detector = ObjectDetector(config=config)
        result = detector.detect(sample_image_bytes)

        assert result["has_interesting_objects"] is True
        assert "car" in result["interesting_classes"]


class TestPerformanceMetrics:
    """Tests for performance tracking and benchmarking."""

    @patch("PIL.Image.open")
    @patch("ultralytics.YOLO")
    def test_detect_returns_processing_time(self, mock_yolo_class, mock_pil_open, mock_yolo_model, sample_image_bytes):
        """Test that processing time is tracked."""
        from src.object_detection import ObjectDetector

        mock_pil_open.return_value = MagicMock()
        mock_yolo_class.return_value = mock_yolo_model

        detector = ObjectDetector()
        result = detector.detect(sample_image_bytes)

        assert "processing_time_ms" in result
        assert result["processing_time_ms"] >= 0

    @patch("PIL.Image.open")
    @patch("ultralytics.YOLO")
    def test_get_metrics_tracks_calls(self, mock_yolo_class, mock_pil_open, mock_yolo_model, sample_image_bytes):
        """Test that metrics track detection calls."""
        from src.object_detection import ObjectDetector

        mock_pil_open.return_value = MagicMock()
        mock_yolo_class.return_value = mock_yolo_model

        detector = ObjectDetector()

        # Make some detections
        detector.detect(sample_image_bytes)
        detector.detect(sample_image_bytes)
        detector.detect(sample_image_bytes)

        metrics = detector.get_metrics()

        assert metrics["total_detections"] == 3
        assert "avg_processing_time_ms" in metrics

    @patch("PIL.Image.open")
    @patch("ultralytics.YOLO")
    def test_detect_under_200ms_target(self, mock_yolo_class, mock_pil_open, mock_yolo_model, sample_image_bytes):
        """Test that detection completes within 200ms target (acceptance criteria)."""
        from src.object_detection import ObjectDetector

        mock_pil_open.return_value = MagicMock()
        mock_yolo_class.return_value = mock_yolo_model

        detector = ObjectDetector()
        result = detector.detect(sample_image_bytes)

        # With mocked model, should be very fast
        assert result["processing_time_ms"] < 200


class TestResourceUsage:
    """Tests for resource usage monitoring."""

    @patch("ultralytics.YOLO")
    def test_detector_has_resource_tracking(self, mock_yolo_class, mock_yolo_model):
        """Test that resource tracking is available."""
        from src.object_detection import ObjectDetector

        mock_yolo_class.return_value = mock_yolo_model

        detector = ObjectDetector()
        resources = detector.get_resource_usage()

        assert "model_loaded" in resources
        assert "model_memory_mb" in resources or resources["model_loaded"] is False

    @patch("PIL.Image.open")
    @patch("ultralytics.YOLO")
    def test_model_can_be_unloaded(self, mock_yolo_class, mock_pil_open, mock_yolo_model, sample_image_bytes):
        """Test that model can be unloaded to free memory."""
        from src.object_detection import ObjectDetector

        mock_pil_open.return_value = MagicMock()
        mock_yolo_class.return_value = mock_yolo_model

        detector = ObjectDetector()
        detector.detect(sample_image_bytes)  # Load model

        detector.unload_model()

        assert detector._model is None


class TestConfigurationOptions:
    """Tests for configuration options."""

    def test_config_confidence_threshold_validation(self):
        """Test confidence threshold validation."""
        from src.object_detection import ObjectDetectorConfig

        # Valid thresholds
        config = ObjectDetectorConfig(confidence_threshold=0.5)
        assert config.confidence_threshold == 0.5

        config = ObjectDetectorConfig(confidence_threshold=0.0)
        assert config.confidence_threshold == 0.0

        config = ObjectDetectorConfig(confidence_threshold=1.0)
        assert config.confidence_threshold == 1.0

    def test_config_max_detections(self):
        """Test max detections configuration."""
        from src.object_detection import ObjectDetectorConfig

        config = ObjectDetectorConfig(max_detections=10)
        assert config.max_detections == 10

    def test_config_from_dict(self):
        """Test creating config from dictionary."""
        from src.object_detection import ObjectDetectorConfig

        config_dict = {
            "confidence_threshold": 0.7,
            "interesting_classes": ["person", "cat"],
            "max_detections": 15,
        }

        config = ObjectDetectorConfig.from_dict(config_dict)

        assert config.confidence_threshold == 0.7
        assert config.interesting_classes == ["person", "cat"]
        assert config.max_detections == 15


class TestIntegrationWithCameraStore:
    """Tests for integration with camera observation store."""

    @patch("PIL.Image.open")
    @patch("ultralytics.YOLO")
    def test_detection_result_compatible_with_store(self, mock_yolo_class, mock_pil_open, mock_yolo_model, sample_image_bytes):
        """Test that detection results are compatible with camera store."""
        from src.object_detection import ObjectDetector

        mock_pil_open.return_value = MagicMock()
        mock_yolo_class.return_value = mock_yolo_model

        detector = ObjectDetector()
        result = detector.detect(sample_image_bytes)

        # Result should have fields that camera_store expects
        assert "interesting_classes" in result
        assert isinstance(result["interesting_classes"], list)

    @patch("PIL.Image.open")
    @patch("ultralytics.YOLO")
    def test_detection_can_serialize_to_json(self, mock_yolo_class, mock_pil_open, mock_yolo_model, sample_image_bytes):
        """Test that detection results can be serialized to JSON."""
        from src.object_detection import ObjectDetector

        mock_pil_open.return_value = MagicMock()
        mock_yolo_class.return_value = mock_yolo_model

        detector = ObjectDetector()
        result = detector.detect(sample_image_bytes)

        # Should not raise
        json_str = json.dumps(result)
        assert json_str is not None


# =============================================================================
# Module-Level Function Tests
# =============================================================================


class TestModuleFunctions:
    """Tests for module-level convenience functions."""

    @patch("PIL.Image.open")
    @patch("ultralytics.YOLO")
    def test_detect_objects_convenience_function(self, mock_yolo_class, mock_pil_open, mock_yolo_model, sample_image_bytes):
        """Test the module-level detect_objects function."""
        # Reset global detector
        import src.object_detection
        src.object_detection._detector = None

        mock_pil_open.return_value = MagicMock()
        mock_yolo_class.return_value = mock_yolo_model

        from src.object_detection import detect_objects

        result = detect_objects(sample_image_bytes)

        assert result["success"] is True

    @patch("PIL.Image.open")
    @patch("ultralytics.YOLO")
    def test_is_interesting_frame_function(self, mock_yolo_class, mock_pil_open, mock_yolo_model, sample_image_bytes):
        """Test the is_interesting_frame convenience function."""
        # Reset global detector
        import src.object_detection
        src.object_detection._detector = None

        mock_pil_open.return_value = MagicMock()
        mock_yolo_class.return_value = mock_yolo_model

        from src.object_detection import is_interesting_frame

        result = is_interesting_frame(sample_image_bytes)

        assert result is True  # Has person and cat

    @patch("ultralytics.YOLO")
    def test_get_global_detector(self, mock_yolo_class, mock_yolo_model):
        """Test global detector instance."""
        # Reset global detector
        import src.object_detection
        src.object_detection._detector = None

        mock_yolo_class.return_value = mock_yolo_model

        from src.object_detection import get_object_detector

        detector1 = get_object_detector()
        detector2 = get_object_detector()

        assert detector1 is detector2  # Same instance


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @patch("ultralytics.YOLO")
    def test_handles_model_load_failure(self, mock_yolo_class):
        """Test handling of model load failure."""
        from src.object_detection import ObjectDetector

        mock_yolo_class.side_effect = Exception("Failed to load model")

        detector = ObjectDetector()
        result = detector.detect(b"some image data")

        assert result["success"] is False
        assert "error" in result

    @patch("ultralytics.YOLO")
    def test_handles_empty_bytes(self, mock_yolo_class, mock_yolo_model):
        """Test handling of empty image bytes."""
        from src.object_detection import ObjectDetector

        mock_yolo_class.return_value = mock_yolo_model

        detector = ObjectDetector()
        result = detector.detect(b"")

        assert result["success"] is False

    @patch("ultralytics.YOLO")
    def test_handles_none_input(self, mock_yolo_class, mock_yolo_model):
        """Test handling of None input."""
        from src.object_detection import ObjectDetector

        mock_yolo_class.return_value = mock_yolo_model

        detector = ObjectDetector()
        result = detector.detect(None)

        assert result["success"] is False
        assert "error" in result

    @patch("PIL.Image.open")
    @patch("ultralytics.YOLO")
    def test_max_detections_limit(self, mock_yolo_class, mock_pil_open, sample_image_bytes):
        """Test that max_detections limit is enforced."""
        from src.object_detection import ObjectDetector, ObjectDetectorConfig

        mock_pil_open.return_value = MagicMock()

        # Create mock with many detections
        mock_model = MagicMock()
        mock_result = MagicMock()
        mock_result.boxes.xyxy.cpu.return_value.numpy.return_value = [
            [i*10, i*10, i*10+50, i*10+50] for i in range(30)
        ]
        mock_result.boxes.conf.cpu.return_value.numpy.return_value = [0.9] * 30
        mock_result.boxes.cls.cpu.return_value.numpy.return_value = [0] * 30  # all persons
        mock_result.names = {0: 'person'}
        mock_model.return_value = [mock_result]
        mock_model.predict.return_value = [mock_result]
        mock_yolo_class.return_value = mock_model

        config = ObjectDetectorConfig(max_detections=5)
        detector = ObjectDetector(config=config)
        result = detector.detect(sample_image_bytes)

        assert len(result["detections"]) <= 5
