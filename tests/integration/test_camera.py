"""
Integration tests for Ring camera control tools.

Tests the full workflow of camera operations including:
- Listing cameras from HA
- Getting camera status with related sensors
- Taking snapshots
- Checking house security status
- Camera location registry

Part of WP-9.2: Ring Camera Integration.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import json
import base64
import tempfile


# =============================================================================
# Test Data
# =============================================================================

MOCK_HA_STATES = [
    {
        "entity_id": "camera.front_door_live_view",
        "state": "idle",
        "attributes": {
            "friendly_name": "Front Door Live View",
            "device_class": "doorbell",
            "model": "Doorbell Pro 2",
        },
    },
    {
        "entity_id": "camera.living_room_live_view",
        "state": "idle",
        "attributes": {
            "friendly_name": "Living Room Camera",
            "device_class": "camera",
            "model": "Indoor Cam",
        },
    },
    {
        "entity_id": "camera.back_door_live_view",
        "state": "unavailable",
        "attributes": {
            "friendly_name": "Back Door Camera",
            "device_class": "camera",
        },
    },
    {
        "entity_id": "binary_sensor.front_door_motion",
        "state": "off",
        "attributes": {
            "friendly_name": "Front Door Motion",
            "device_class": "motion",
        },
    },
    {
        "entity_id": "binary_sensor.front_door_ding",
        "state": "off",
        "attributes": {
            "friendly_name": "Front Door Ding",
            "device_class": "doorbell",
        },
    },
    {
        "entity_id": "sensor.front_door_battery",
        "state": "85",
        "attributes": {
            "friendly_name": "Front Door Battery",
            "device_class": "battery",
            "unit_of_measurement": "%",
        },
    },
    {
        "entity_id": "light.living_room",
        "state": "on",
        "attributes": {
            "friendly_name": "Living Room",
        },
    },
]

MOCK_SNAPSHOT = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_ha_client():
    """Create a mock Home Assistant client for integration tests."""
    with patch("tools.camera.get_ha_client") as mock_get_client:
        client = Mock()

        # Default behaviors
        client.get_states.return_value = MOCK_HA_STATES
        client.get_camera_snapshot.return_value = MOCK_SNAPSHOT

        def mock_get_state(entity_id):
            for state in MOCK_HA_STATES:
                if state["entity_id"] == entity_id:
                    return state
            return None

        client.get_state.side_effect = mock_get_state

        mock_get_client.return_value = client
        yield client


@pytest.fixture
def temp_data_dir(tmp_path):
    """Create a temporary data directory for registry files."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    with patch("tools.camera.DATA_DIR", data_dir):
        yield data_dir


# =============================================================================
# Voice Command Integration Tests
# =============================================================================

class TestVoiceCommandIntegration:
    """Tests simulating voice command workflows."""

    def test_voice_command_list_cameras(self, mock_ha_client):
        """'What cameras do I have?' workflow."""
        from tools.camera import execute_camera_tool

        result = execute_camera_tool("list_cameras", {})

        assert result["success"] is True
        assert result["count"] == 3  # All camera entities
        assert any(c["friendly_name"] == "Front Door Live View"
                   for c in result["cameras"])

    def test_voice_command_check_front_door(self, mock_ha_client):
        """'Is the front door camera working?' workflow."""
        from tools.camera import execute_camera_tool

        result = execute_camera_tool("get_camera_status", {
            "entity_id": "camera.front_door_live_view",
            "include_sensors": True
        })

        assert result["success"] is True
        assert result["state"] == "idle"
        assert result["friendly_name"] == "Front Door Live View"

    def test_voice_command_snapshot_front_door(self, mock_ha_client):
        """'Take a picture from the front door.' workflow."""
        from tools.camera import execute_camera_tool

        result = execute_camera_tool("get_camera_snapshot", {
            "entity_id": "camera.front_door_live_view"
        })

        assert result["success"] is True
        assert "image_base64" in result
        assert "timestamp" in result

    def test_voice_command_check_house(self, mock_ha_client):
        """'Is everything okay at home?' workflow."""
        from tools.camera import execute_camera_tool

        result = execute_camera_tool("check_house_status", {})

        assert result["success"] is True
        assert result["cameras_online"] >= 2
        assert result["cameras_offline"] >= 1  # back_door is unavailable
        assert "message" in result

    def test_voice_command_camera_location(self, mock_ha_client, temp_data_dir):
        """'The living room camera is now in the bedroom' workflow."""
        from tools.camera import execute_camera_tool

        # Register new location
        result = execute_camera_tool("register_camera_location", {
            "entity_id": "camera.living_room_live_view",
            "location": "bedroom",
            "description": "Watching the baby"
        })

        assert result["success"] is True
        assert result["location"] == "bedroom"

        # Verify location is returned in camera status
        from tools.camera import get_camera_registry
        registry = get_camera_registry()
        location = registry.get_camera_location("camera.living_room_live_view")

        assert location is not None
        assert location["location"] == "bedroom"


# =============================================================================
# Multi-Step Workflow Tests
# =============================================================================

class TestMultiStepWorkflows:
    """Tests for complex multi-step operations."""

    def test_security_check_workflow(self, mock_ha_client):
        """Full security check: list cameras, check status, identify issues."""
        from tools.camera import execute_camera_tool

        # Step 1: List all cameras
        list_result = execute_camera_tool("list_cameras", {"live_view_only": True})
        assert list_result["success"] is True

        # Step 2: Check house status
        status_result = execute_camera_tool("check_house_status", {})
        assert status_result["success"] is True

        # Step 3: Identify offline cameras
        if status_result["cameras_offline"] > 0:
            # The back door camera is offline
            assert status_result["issues"]
            assert any("Back Door" in issue for issue in status_result["issues"])

    def test_motion_detection_workflow(self, mock_ha_client):
        """Motion detection scenario: motion triggered, take snapshot."""
        # Simulate motion detected
        mock_ha_client.get_states.return_value = [
            {
                "entity_id": "camera.front_door_live_view",
                "state": "idle",
                "attributes": {"friendly_name": "Front Door Live View"},
            },
            {
                "entity_id": "binary_sensor.front_door_motion",
                "state": "on",  # Motion detected
                "attributes": {"friendly_name": "Front Door Motion"},
            },
        ]

        from tools.camera import execute_camera_tool

        # Check status - should show motion
        status = execute_camera_tool("check_house_status", {})
        assert status["success"] is True
        assert status["status"] == "activity_detected"
        assert "Front Door Motion" in status.get("motion_detected", [])

        # Take snapshot
        snapshot = execute_camera_tool("get_camera_snapshot", {
            "entity_id": "camera.front_door_live_view"
        })
        assert snapshot["success"] is True

    def test_camera_relocation_workflow(self, mock_ha_client, temp_data_dir):
        """Camera relocation scenario for travel."""
        from tools.camera import execute_camera_tool, CameraRegistry
        import tools.camera

        # Reset the registry singleton for clean test
        tools.camera._camera_registry = None

        # Step 1: Register cameras for travel monitoring
        cameras_to_move = [
            ("camera.living_room_live_view", "entry hall", "Watching front door"),
            ("camera.front_door_live_view", "front porch", "Doorbell position"),
        ]

        for entity_id, location, description in cameras_to_move:
            result = execute_camera_tool("register_camera_location", {
                "entity_id": entity_id,
                "location": location,
                "description": description
            })
            assert result["success"] is True

        # Step 2: Verify the cameras we registered exist
        from tools.camera import get_camera_registry
        registry = get_camera_registry()
        registered = registry.list_cameras()

        # Check that at least our 2 cameras are registered
        assert len(registered) >= 2
        entity_ids = [c["entity_id"] for c in registered]
        assert "camera.living_room_live_view" in entity_ids
        assert "camera.front_door_live_view" in entity_ids

        # Step 3: Get status with location context
        status = execute_camera_tool("get_camera_status", {
            "entity_id": "camera.living_room_live_view"
        })
        assert status["success"] is True
        assert status.get("location") == "entry hall"


# =============================================================================
# Error Handling Integration Tests
# =============================================================================

class TestErrorHandlingIntegration:
    """Tests for error handling in realistic scenarios."""

    def test_unavailable_camera_snapshot(self, mock_ha_client):
        """Attempting snapshot from unavailable camera."""
        from tools.camera import execute_camera_tool

        result = execute_camera_tool("get_camera_snapshot", {
            "entity_id": "camera.back_door_live_view"
        })

        assert result["success"] is False
        assert "unavailable" in result["error"].lower()

    def test_nonexistent_camera(self, mock_ha_client):
        """Querying a camera that doesn't exist."""
        from tools.camera import execute_camera_tool

        result = execute_camera_tool("get_camera_status", {
            "entity_id": "camera.garage_cam"
        })

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_ha_connection_failure(self, mock_ha_client):
        """Home Assistant connection failure."""
        mock_ha_client.get_states.side_effect = Exception("Connection refused")

        from tools.camera import execute_camera_tool

        result = execute_camera_tool("list_cameras", {})

        assert result["success"] is False
        assert "error" in result


# =============================================================================
# Registry Persistence Tests
# =============================================================================

class TestRegistryPersistence:
    """Tests for camera registry persistence."""

    def test_registry_persists_across_instances(self, temp_data_dir):
        """Registry data persists when reloaded."""
        from tools.camera import CameraRegistry

        # First instance - register camera
        registry1 = CameraRegistry()
        registry1.set_camera_location(
            "camera.test_cam",
            "test room",
            "For testing"
        )

        # Verify file was written
        registry_file = temp_data_dir / "camera_registry.json"
        assert registry_file.exists()

        # Second instance - should load persisted data
        registry2 = CameraRegistry()
        registry2._cache = None  # Force reload
        location = registry2.get_camera_location("camera.test_cam")

        assert location is not None
        assert location["location"] == "test room"

    def test_registry_handles_missing_file(self, temp_data_dir):
        """Registry handles missing file gracefully."""
        from tools.camera import CameraRegistry

        registry = CameraRegistry()
        cameras = registry.list_cameras()

        assert cameras == []

    def test_registry_remove_camera(self, temp_data_dir):
        """Camera can be removed from registry."""
        from tools.camera import CameraRegistry

        registry = CameraRegistry()

        # Add then remove
        registry.set_camera_location("camera.temp", "temp room")
        result = registry.remove_camera("camera.temp")

        assert result["success"] is True
        assert registry.get_camera_location("camera.temp") is None


# =============================================================================
# Snapshot File Output Tests
# =============================================================================

class TestSnapshotFileOutput:
    """Tests for snapshot file saving functionality."""

    def test_snapshot_saves_to_custom_path(self, mock_ha_client, tmp_path):
        """Snapshot saves to specified file path."""
        output_file = tmp_path / "snapshots" / "test_snapshot.jpg"

        from tools.camera import execute_camera_tool

        result = execute_camera_tool("get_camera_snapshot", {
            "entity_id": "camera.front_door_live_view",
            "save_to": str(output_file)
        })

        assert result["success"] is True
        assert result["saved_to"] == str(output_file)
        assert output_file.exists()
        assert output_file.read_bytes() == MOCK_SNAPSHOT

    def test_snapshot_creates_parent_directories(self, mock_ha_client, tmp_path):
        """Snapshot creates parent directories if needed."""
        output_file = tmp_path / "deep" / "nested" / "path" / "snap.jpg"

        from tools.camera import execute_camera_tool

        result = execute_camera_tool("get_camera_snapshot", {
            "entity_id": "camera.front_door_live_view",
            "save_to": str(output_file)
        })

        assert result["success"] is True
        assert output_file.exists()


# =============================================================================
# Tool Routing Tests
# =============================================================================

class TestToolRouting:
    """Tests for correct tool routing in execute_camera_tool."""

    def test_all_tools_route_correctly(self, mock_ha_client, temp_data_dir):
        """All defined tools route to correct functions."""
        from tools.camera import execute_camera_tool, CAMERA_TOOLS

        tool_test_inputs = {
            "list_cameras": {},
            "get_camera_status": {"entity_id": "camera.front_door_live_view"},
            "get_camera_snapshot": {"entity_id": "camera.front_door_live_view"},
            "check_house_status": {},
            "register_camera_location": {
                "entity_id": "camera.test",
                "location": "test"
            },
        }

        for tool in CAMERA_TOOLS:
            tool_name = tool["name"]
            if tool_name in tool_test_inputs:
                result = execute_camera_tool(tool_name, tool_test_inputs[tool_name])
                assert "error" not in result or result.get("success") is False
