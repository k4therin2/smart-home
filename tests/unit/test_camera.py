"""
Unit tests for Ring camera control tools.

Tests camera listing, snapshot capture, and status monitoring.
Part of WP-9.2: Ring Camera Integration.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Any
import base64


# =============================================================================
# Test Data
# =============================================================================

MOCK_CAMERA_LIVE_VIEW = {
    "entity_id": "camera.front_door_live_view",
    "state": "idle",
    "attributes": {
        "friendly_name": "Front Door Live View",
        "device_class": "doorbell",
        "model": "Doorbell Pro 2",
        "video_url": "rtsp://192.168.1.100:8554/front_door",
    },
}

MOCK_CAMERA_LAST_RECORDING = {
    "entity_id": "camera.front_door_last_recording",
    "state": "recording",
    "attributes": {
        "friendly_name": "Front Door Last Recording",
        "device_class": "doorbell",
        "video_url": "https://ring.com/api/recordings/12345",
    },
}

MOCK_INDOOR_CAMERA = {
    "entity_id": "camera.living_room_live_view",
    "state": "idle",
    "attributes": {
        "friendly_name": "Living Room Camera",
        "device_class": "camera",
        "model": "Indoor Cam",
    },
}

MOCK_MOTION_SENSOR = {
    "entity_id": "binary_sensor.front_door_motion",
    "state": "off",
    "attributes": {
        "friendly_name": "Front Door Motion",
        "device_class": "motion",
    },
}

MOCK_DING_SENSOR = {
    "entity_id": "binary_sensor.front_door_ding",
    "state": "off",
    "attributes": {
        "friendly_name": "Front Door Ding",
        "device_class": "doorbell",
    },
}

MOCK_BATTERY_SENSOR = {
    "entity_id": "sensor.front_door_battery",
    "state": "85",
    "attributes": {
        "friendly_name": "Front Door Battery",
        "device_class": "battery",
        "unit_of_measurement": "%",
    },
}

MOCK_WIFI_SENSOR = {
    "entity_id": "sensor.front_door_wifi_signal",
    "state": "-45",
    "attributes": {
        "friendly_name": "Front Door WiFi Signal",
        "unit_of_measurement": "dBm",
    },
}

MOCK_ALL_ENTITIES = [
    MOCK_CAMERA_LIVE_VIEW,
    MOCK_CAMERA_LAST_RECORDING,
    MOCK_INDOOR_CAMERA,
    MOCK_MOTION_SENSOR,
    MOCK_DING_SENSOR,
    MOCK_BATTERY_SENSOR,
    MOCK_WIFI_SENSOR,
]

# Mock snapshot image (tiny base64 PNG)
MOCK_SNAPSHOT_BASE64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
MOCK_SNAPSHOT_BYTES = base64.b64decode(MOCK_SNAPSHOT_BASE64)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_ha_client():
    """Create a mock Home Assistant client."""
    with patch("tools.camera.get_ha_client") as mock_get_client:
        client = Mock()
        mock_get_client.return_value = client
        yield client


@pytest.fixture
def mock_config():
    """Create mock camera configuration."""
    with patch("tools.camera.get_camera_entities") as mock_get_cameras:
        mock_get_cameras.return_value = [
            "camera.front_door_live_view",
            "camera.living_room_live_view",
        ]
        yield {
            "get_camera_entities": mock_get_cameras,
        }


@pytest.fixture
def mock_camera_registry():
    """Create mock camera registry."""
    with patch("tools.camera.CameraRegistry") as mock_registry_class:
        registry = Mock()
        registry.get_camera_location.return_value = None
        registry.list_cameras.return_value = []
        mock_registry_class.return_value = registry
        yield registry


# =============================================================================
# List Cameras Tests
# =============================================================================

class TestListCameras:
    """Tests for the list_cameras function."""

    def test_list_cameras_returns_all_cameras(self, mock_ha_client):
        """Lists all available cameras from Home Assistant."""
        mock_ha_client.get_states.return_value = MOCK_ALL_ENTITIES

        from tools.camera import list_cameras
        result = list_cameras()

        assert result["success"] is True
        # Should include 3 cameras: 2 live_view + 1 last_recording
        assert len(result["cameras"]) == 3
        camera_ids = [c["entity_id"] for c in result["cameras"]]
        assert "camera.front_door_live_view" in camera_ids
        assert "camera.living_room_live_view" in camera_ids
        assert "camera.front_door_last_recording" in camera_ids

    def test_list_cameras_includes_camera_details(self, mock_ha_client):
        """Camera list includes relevant details."""
        mock_ha_client.get_states.return_value = [MOCK_CAMERA_LIVE_VIEW]

        from tools.camera import list_cameras
        result = list_cameras()

        assert result["success"] is True
        camera = result["cameras"][0]
        assert camera["entity_id"] == "camera.front_door_live_view"
        assert camera["friendly_name"] == "Front Door Live View"
        assert camera["state"] == "idle"

    def test_list_cameras_filters_live_view_only(self, mock_ha_client):
        """Only returns live_view cameras, not last_recording."""
        mock_ha_client.get_states.return_value = MOCK_ALL_ENTITIES

        from tools.camera import list_cameras
        result = list_cameras(live_view_only=True)

        assert result["success"] is True
        for camera in result["cameras"]:
            assert "last_recording" not in camera["entity_id"]

    def test_list_cameras_empty_when_no_cameras(self, mock_ha_client):
        """Returns empty list when no cameras found."""
        mock_ha_client.get_states.return_value = [MOCK_MOTION_SENSOR]

        from tools.camera import list_cameras
        result = list_cameras()

        assert result["success"] is True
        assert result["cameras"] == []
        assert "message" in result

    def test_list_cameras_handles_error(self, mock_ha_client):
        """Handles errors gracefully."""
        mock_ha_client.get_states.side_effect = Exception("Connection failed")

        from tools.camera import list_cameras
        result = list_cameras()

        assert result["success"] is False
        assert "error" in result


# =============================================================================
# Get Camera Status Tests
# =============================================================================

class TestGetCameraStatus:
    """Tests for the get_camera_status function."""

    def test_get_camera_status_returns_state(self, mock_ha_client):
        """Returns camera state and attributes."""
        mock_ha_client.get_state.return_value = MOCK_CAMERA_LIVE_VIEW

        from tools.camera import get_camera_status
        result = get_camera_status(entity_id="camera.front_door_live_view")

        assert result["success"] is True
        assert result["state"] == "idle"
        assert result["friendly_name"] == "Front Door Live View"

    def test_get_camera_status_includes_related_sensors(self, mock_ha_client):
        """Includes related motion/battery sensors."""
        def mock_get_state(entity_id):
            states = {
                "camera.front_door_live_view": MOCK_CAMERA_LIVE_VIEW,
                "binary_sensor.front_door_motion": MOCK_MOTION_SENSOR,
                "sensor.front_door_battery": MOCK_BATTERY_SENSOR,
            }
            return states.get(entity_id)

        mock_ha_client.get_state.side_effect = mock_get_state
        mock_ha_client.get_states.return_value = MOCK_ALL_ENTITIES

        from tools.camera import get_camera_status
        result = get_camera_status(
            entity_id="camera.front_door_live_view",
            include_sensors=True
        )

        assert result["success"] is True
        assert "motion_detected" in result or "related_sensors" in result

    def test_get_camera_status_unknown_camera(self, mock_ha_client):
        """Returns error for unknown camera."""
        mock_ha_client.get_state.return_value = None

        from tools.camera import get_camera_status
        result = get_camera_status(entity_id="camera.unknown")

        assert result["success"] is False
        assert "error" in result

    def test_get_camera_status_handles_error(self, mock_ha_client):
        """Handles errors gracefully."""
        mock_ha_client.get_state.side_effect = Exception("API error")

        from tools.camera import get_camera_status
        result = get_camera_status(entity_id="camera.front_door_live_view")

        assert result["success"] is False
        assert "error" in result


# =============================================================================
# Get Camera Snapshot Tests
# =============================================================================

class TestGetCameraSnapshot:
    """Tests for the get_camera_snapshot function."""

    def test_get_snapshot_returns_image_data(self, mock_ha_client):
        """Returns snapshot image as base64."""
        mock_ha_client.get_state.return_value = MOCK_CAMERA_LIVE_VIEW
        mock_ha_client.get_camera_snapshot.return_value = MOCK_SNAPSHOT_BYTES

        from tools.camera import get_camera_snapshot
        result = get_camera_snapshot(entity_id="camera.front_door_live_view")

        assert result["success"] is True
        assert "image_base64" in result
        assert result["image_base64"] == MOCK_SNAPSHOT_BASE64

    def test_get_snapshot_saves_to_file(self, mock_ha_client, tmp_path):
        """Saves snapshot to file when path provided."""
        mock_ha_client.get_state.return_value = MOCK_CAMERA_LIVE_VIEW
        mock_ha_client.get_camera_snapshot.return_value = MOCK_SNAPSHOT_BYTES

        output_path = tmp_path / "snapshot.jpg"

        from tools.camera import get_camera_snapshot
        result = get_camera_snapshot(
            entity_id="camera.front_door_live_view",
            save_to=str(output_path)
        )

        assert result["success"] is True
        assert result["saved_to"] == str(output_path)
        assert output_path.exists()

    def test_get_snapshot_unknown_camera(self, mock_ha_client):
        """Returns error for unknown camera."""
        mock_ha_client.get_state.return_value = None

        from tools.camera import get_camera_snapshot
        result = get_camera_snapshot(entity_id="camera.unknown")

        assert result["success"] is False
        assert "error" in result

    def test_get_snapshot_camera_unavailable(self, mock_ha_client):
        """Returns error when camera is unavailable."""
        unavailable_camera = MOCK_CAMERA_LIVE_VIEW.copy()
        unavailable_camera["state"] = "unavailable"
        mock_ha_client.get_state.return_value = unavailable_camera

        from tools.camera import get_camera_snapshot
        result = get_camera_snapshot(entity_id="camera.front_door_live_view")

        assert result["success"] is False
        assert "unavailable" in result["error"].lower()

    def test_get_snapshot_handles_api_error(self, mock_ha_client):
        """Handles API errors gracefully."""
        mock_ha_client.get_state.return_value = MOCK_CAMERA_LIVE_VIEW
        mock_ha_client.get_camera_snapshot.side_effect = Exception("Camera busy")

        from tools.camera import get_camera_snapshot
        result = get_camera_snapshot(entity_id="camera.front_door_live_view")

        assert result["success"] is False
        assert "error" in result


# =============================================================================
# Camera Registry Tests
# =============================================================================

class TestCameraRegistry:
    """Tests for the CameraRegistry class."""

    def test_register_camera_location(self):
        """Registers camera with location."""
        from tools.camera import CameraRegistry

        with patch("tools.camera.DATA_DIR", "/tmp/test_data"):
            with patch("builtins.open", MagicMock()):
                with patch("json.dump"):
                    with patch("json.load", return_value={}):
                        with patch("pathlib.Path.exists", return_value=True):
                            registry = CameraRegistry()
                            result = registry.set_camera_location(
                                entity_id="camera.living_room_live_view",
                                location="living room",
                                description="Corner by the TV"
                            )

                            assert result["success"] is True

    def test_get_camera_location(self):
        """Gets registered camera location."""
        mock_data = {
            "camera.living_room_live_view": {
                "location": "living room",
                "description": "Corner by the TV",
                "updated_at": "2025-12-27T00:00:00"
            }
        }

        from tools.camera import CameraRegistry

        with patch("tools.camera.DATA_DIR", "/tmp/test_data"):
            with patch("pathlib.Path.exists", return_value=True):
                with patch("builtins.open", MagicMock()):
                    with patch("json.load", return_value=mock_data):
                        registry = CameraRegistry()
                        result = registry.get_camera_location("camera.living_room_live_view")

                        assert result is not None
                        assert result["location"] == "living room"

    def test_get_unregistered_camera_location(self):
        """Returns None for unregistered camera."""
        from tools.camera import CameraRegistry

        with patch("tools.camera.DATA_DIR", "/tmp/test_data"):
            with patch("pathlib.Path.exists", return_value=True):
                with patch("builtins.open", MagicMock()):
                    with patch("json.load", return_value={}):
                        registry = CameraRegistry()
                        result = registry.get_camera_location("camera.unknown")

                        assert result is None

    def test_list_registered_cameras(self):
        """Lists all registered cameras with locations."""
        mock_data = {
            "camera.living_room_live_view": {
                "location": "living room",
                "description": "Corner by the TV",
            },
            "camera.front_door_live_view": {
                "location": "front porch",
                "description": "Above the door",
            }
        }

        from tools.camera import CameraRegistry

        with patch("tools.camera.DATA_DIR", "/tmp/test_data"):
            with patch("pathlib.Path.exists", return_value=True):
                with patch("builtins.open", MagicMock()):
                    with patch("json.load", return_value=mock_data):
                        registry = CameraRegistry()
                        result = registry.list_cameras()

                        assert len(result) == 2


# =============================================================================
# Check House Status Tests
# =============================================================================

class TestCheckHouseStatus:
    """Tests for the check_house_status function."""

    def test_check_house_status_all_clear(self, mock_ha_client):
        """Returns all clear when no motion detected."""
        mock_ha_client.get_states.return_value = [
            MOCK_CAMERA_LIVE_VIEW,
            MOCK_INDOOR_CAMERA,
            {**MOCK_MOTION_SENSOR, "state": "off"},
        ]

        from tools.camera import check_house_status
        result = check_house_status()

        assert result["success"] is True
        assert result["status"] == "all_clear"
        assert result["cameras_online"] == 2

    def test_check_house_status_motion_detected(self, mock_ha_client):
        """Reports motion when detected."""
        motion_detected = {**MOCK_MOTION_SENSOR, "state": "on"}
        mock_ha_client.get_states.return_value = [
            MOCK_CAMERA_LIVE_VIEW,
            motion_detected,
        ]

        from tools.camera import check_house_status
        result = check_house_status()

        assert result["success"] is True
        assert result["status"] == "activity_detected"
        assert len(result["active_cameras"]) >= 1

    def test_check_house_status_camera_offline(self, mock_ha_client):
        """Reports when cameras are offline."""
        offline_camera = {**MOCK_CAMERA_LIVE_VIEW, "state": "unavailable"}
        mock_ha_client.get_states.return_value = [
            offline_camera,
            MOCK_INDOOR_CAMERA,
        ]

        from tools.camera import check_house_status
        result = check_house_status()

        assert result["success"] is True
        assert result["cameras_offline"] >= 1

    def test_check_house_status_handles_error(self, mock_ha_client):
        """Handles errors gracefully."""
        mock_ha_client.get_states.side_effect = Exception("Connection lost")

        from tools.camera import check_house_status
        result = check_house_status()

        assert result["success"] is False
        assert "error" in result


# =============================================================================
# Tool Execution Tests
# =============================================================================

class TestExecuteCameraTool:
    """Tests for the execute_camera_tool function."""

    def test_execute_list_cameras(self, mock_ha_client):
        """Executes list_cameras tool."""
        mock_ha_client.get_states.return_value = [MOCK_CAMERA_LIVE_VIEW]

        from tools.camera import execute_camera_tool
        result = execute_camera_tool("list_cameras", {})

        assert result["success"] is True
        assert "cameras" in result

    def test_execute_get_camera_status(self, mock_ha_client):
        """Executes get_camera_status tool."""
        mock_ha_client.get_state.return_value = MOCK_CAMERA_LIVE_VIEW
        mock_ha_client.get_states.return_value = MOCK_ALL_ENTITIES

        from tools.camera import execute_camera_tool
        result = execute_camera_tool(
            "get_camera_status",
            {"entity_id": "camera.front_door_live_view"}
        )

        assert result["success"] is True

    def test_execute_get_camera_snapshot(self, mock_ha_client):
        """Executes get_camera_snapshot tool."""
        mock_ha_client.get_state.return_value = MOCK_CAMERA_LIVE_VIEW
        mock_ha_client.get_camera_snapshot.return_value = MOCK_SNAPSHOT_BYTES

        from tools.camera import execute_camera_tool
        result = execute_camera_tool(
            "get_camera_snapshot",
            {"entity_id": "camera.front_door_live_view"}
        )

        assert result["success"] is True

    def test_execute_check_house_status(self, mock_ha_client):
        """Executes check_house_status tool."""
        mock_ha_client.get_states.return_value = MOCK_ALL_ENTITIES

        from tools.camera import execute_camera_tool
        result = execute_camera_tool("check_house_status", {})

        assert result["success"] is True

    def test_execute_unknown_tool(self, mock_ha_client):
        """Returns error for unknown tool."""
        from tools.camera import execute_camera_tool
        result = execute_camera_tool("unknown_tool", {})

        assert result["success"] is False
        assert "error" in result


# =============================================================================
# Tool Definitions Tests
# =============================================================================

class TestCameraToolDefinitions:
    """Tests for CAMERA_TOOLS definitions."""

    def test_tool_definitions_exist(self):
        """Camera tools are properly defined."""
        from tools.camera import CAMERA_TOOLS

        assert len(CAMERA_TOOLS) >= 4
        tool_names = [t["name"] for t in CAMERA_TOOLS]
        assert "list_cameras" in tool_names
        assert "get_camera_status" in tool_names
        assert "get_camera_snapshot" in tool_names
        assert "check_house_status" in tool_names

    def test_tool_definitions_have_required_fields(self):
        """Each tool has name, description, and input_schema."""
        from tools.camera import CAMERA_TOOLS

        for tool in CAMERA_TOOLS:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool
            assert "type" in tool["input_schema"]

    def test_list_cameras_tool_definition(self):
        """list_cameras tool is properly defined."""
        from tools.camera import CAMERA_TOOLS

        tool = next(t for t in CAMERA_TOOLS if t["name"] == "list_cameras")
        assert "camera" in tool["description"].lower()

    def test_get_snapshot_tool_definition(self):
        """get_camera_snapshot tool is properly defined."""
        from tools.camera import CAMERA_TOOLS

        tool = next(t for t in CAMERA_TOOLS if t["name"] == "get_camera_snapshot")
        assert "entity_id" in tool["input_schema"].get("properties", {})
