"""
Tests for Camera Query REST API (WP-11.6)

API endpoints for cross-system camera data access:
- GET /api/camera/events - Query camera events with filters
- GET /api/camera/summary - Get activity summary for time range

Tests cover:
- Endpoint functionality
- Query parameter parsing
- Authentication (Tailscale-based)
- Response formatting
- Error handling
"""

import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from src.camera_store import CameraObservationStore


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def app():
    """Create Flask test app."""
    from src.server import app
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def mock_camera_store(tmp_path):
    """Create a mock camera store with test data."""
    db_path = tmp_path / "camera_test.db"
    images_dir = tmp_path / "images"
    store = CameraObservationStore(
        db_path=db_path, images_dir=images_dir, retention_days=14
    )

    # Initialize database schema
    with store._get_cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS camera_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                camera_id TEXT NOT NULL,
                image_path TEXT,
                objects_detected TEXT,
                llm_description TEXT,
                confidence REAL,
                motion_triggered BOOLEAN DEFAULT FALSE,
                processing_time_ms INTEGER,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    # Add test observations
    now = datetime.now()

    store.add_observation(
        camera_id="camera.living_room",
        timestamp=now - timedelta(hours=2),
        objects_detected=["cat"],
        llm_description="Cat on the couch",
        motion_triggered=True,
    )

    store.add_observation(
        camera_id="camera.front_door",
        timestamp=now - timedelta(hours=3),
        objects_detected=["person", "package"],
        llm_description="Delivery at front door",
        motion_triggered=True,
    )

    store.add_observation(
        camera_id="camera.backyard",
        timestamp=now - timedelta(hours=4),
        objects_detected=["dog"],
        llm_description="Dog playing outside",
        motion_triggered=True,
    )

    return store


@pytest.fixture
def auth_headers():
    """Create authentication headers for Tailscale-based auth."""
    return {
        "X-Forwarded-For": "100.75.232.36",  # Tailscale IP
        "X-API-Key": "test-api-key",
    }


# =============================================================================
# Events Endpoint Tests
# =============================================================================


class TestCameraEventsEndpoint:
    """Tests for GET /api/camera/events endpoint."""

    def test_events_endpoint_exists(self, client, auth_headers):
        """Events endpoint exists and responds."""
        with patch("src.server.verify_camera_api_auth", return_value=True):
            response = client.get("/api/camera/events", headers=auth_headers)
            # Should not be 404
            assert response.status_code != 404

    def test_events_returns_json(self, client, auth_headers, mock_camera_store):
        """Events endpoint returns JSON."""
        with patch("src.server.verify_camera_api_auth", return_value=True):
            with patch("src.server.get_camera_store", return_value=mock_camera_store):
                response = client.get("/api/camera/events", headers=auth_headers)
                assert response.content_type == "application/json"

    def test_events_with_object_filter(self, client, auth_headers, mock_camera_store):
        """Filter events by object type."""
        with patch("src.server.verify_camera_api_auth", return_value=True):
            with patch("src.server.get_camera_store", return_value=mock_camera_store):
                response = client.get(
                    "/api/camera/events?object=cat",
                    headers=auth_headers,
                )
                assert response.status_code == 200
                data = json.loads(response.data)
                assert "events" in data
                # All events should contain cat
                for event in data["events"]:
                    assert "cat" in event.get("objects_detected", [])

    def test_events_with_time_range(self, client, auth_headers, mock_camera_store):
        """Filter events by time range."""
        with patch("src.server.verify_camera_api_auth", return_value=True):
            with patch("src.server.get_camera_store", return_value=mock_camera_store):
                response = client.get(
                    "/api/camera/events?time_range=today",
                    headers=auth_headers,
                )
                assert response.status_code == 200
                data = json.loads(response.data)
                assert "events" in data

    def test_events_with_camera_filter(self, client, auth_headers, mock_camera_store):
        """Filter events by camera."""
        with patch("src.server.verify_camera_api_auth", return_value=True):
            with patch("src.server.get_camera_store", return_value=mock_camera_store):
                response = client.get(
                    "/api/camera/events?camera=front_door",
                    headers=auth_headers,
                )
                assert response.status_code == 200
                data = json.loads(response.data)
                assert "events" in data
                for event in data["events"]:
                    assert "front_door" in event.get("camera_id", "")

    def test_events_with_limit(self, client, auth_headers, mock_camera_store):
        """Limit number of results."""
        with patch("src.server.verify_camera_api_auth", return_value=True):
            with patch("src.server.get_camera_store", return_value=mock_camera_store):
                response = client.get(
                    "/api/camera/events?limit=1",
                    headers=auth_headers,
                )
                assert response.status_code == 200
                data = json.loads(response.data)
                assert len(data.get("events", [])) <= 1

    def test_events_includes_count(self, client, auth_headers, mock_camera_store):
        """Response includes event count."""
        with patch("src.server.verify_camera_api_auth", return_value=True):
            with patch("src.server.get_camera_store", return_value=mock_camera_store):
                response = client.get("/api/camera/events", headers=auth_headers)
                assert response.status_code == 200
                data = json.loads(response.data)
                assert "count" in data
                assert data["count"] == len(data.get("events", []))

    def test_events_unauthorized_without_auth(self, client):
        """Events endpoint requires authentication."""
        with patch("src.server.verify_camera_api_auth", return_value=False):
            response = client.get("/api/camera/events")
            assert response.status_code in [401, 403]


# =============================================================================
# Summary Endpoint Tests
# =============================================================================


class TestCameraSummaryEndpoint:
    """Tests for GET /api/camera/summary endpoint."""

    def test_summary_endpoint_exists(self, client, auth_headers):
        """Summary endpoint exists and responds."""
        with patch("src.server.verify_camera_api_auth", return_value=True):
            response = client.get("/api/camera/summary", headers=auth_headers)
            assert response.status_code != 404

    def test_summary_returns_json(self, client, auth_headers, mock_camera_store):
        """Summary endpoint returns JSON."""
        with patch("src.server.verify_camera_api_auth", return_value=True):
            with patch("src.server.get_camera_store", return_value=mock_camera_store):
                response = client.get("/api/camera/summary", headers=auth_headers)
                assert response.content_type == "application/json"

    def test_summary_includes_total_events(self, client, auth_headers, mock_camera_store):
        """Summary includes total event count."""
        with patch("src.server.verify_camera_api_auth", return_value=True):
            with patch("src.server.get_camera_store", return_value=mock_camera_store):
                response = client.get("/api/camera/summary", headers=auth_headers)
                assert response.status_code == 200
                data = json.loads(response.data)
                assert "total_events" in data

    def test_summary_includes_objects_breakdown(self, client, auth_headers, mock_camera_store):
        """Summary includes object type breakdown."""
        with patch("src.server.verify_camera_api_auth", return_value=True):
            with patch("src.server.get_camera_store", return_value=mock_camera_store):
                response = client.get("/api/camera/summary", headers=auth_headers)
                assert response.status_code == 200
                data = json.loads(response.data)
                assert "objects_detected" in data

    def test_summary_with_time_range(self, client, auth_headers, mock_camera_store):
        """Summary respects time range filter."""
        with patch("src.server.verify_camera_api_auth", return_value=True):
            with patch("src.server.get_camera_store", return_value=mock_camera_store):
                response = client.get(
                    "/api/camera/summary?time_range=today",
                    headers=auth_headers,
                )
                assert response.status_code == 200
                data = json.loads(response.data)
                assert "period_start" in data
                assert "period_end" in data

    def test_summary_unauthorized_without_auth(self, client):
        """Summary endpoint requires authentication."""
        with patch("src.server.verify_camera_api_auth", return_value=False):
            response = client.get("/api/camera/summary")
            assert response.status_code in [401, 403]


# =============================================================================
# Authentication Tests
# =============================================================================


class TestCameraAPIAuthentication:
    """Tests for camera API authentication."""

    def test_tailscale_ip_allowed(self, client, mock_camera_store):
        """Requests from Tailscale IPs are allowed."""
        headers = {"X-Forwarded-For": "100.75.232.36"}
        with patch("src.server.get_camera_store", return_value=mock_camera_store):
            response = client.get("/api/camera/events", headers=headers)
            # Should not be 401/403
            assert response.status_code not in [401, 403]

    def test_api_key_allowed(self, client, mock_camera_store):
        """Requests with valid API key are allowed."""
        # This requires API key to be configured
        headers = {"X-API-Key": "valid-test-key"}
        with patch("src.server.verify_camera_api_key", return_value=True):
            with patch("src.server.get_camera_store", return_value=mock_camera_store):
                response = client.get("/api/camera/events", headers=headers)
                # Should not be 401/403
                assert response.status_code not in [401, 403]

    def test_invalid_api_key_rejected(self, client):
        """Invalid API key is rejected."""
        headers = {"X-API-Key": "invalid-key"}
        with patch("src.server.verify_camera_api_key", return_value=False):
            with patch("src.server.is_tailscale_ip", return_value=False):
                response = client.get("/api/camera/events", headers=headers)
                assert response.status_code in [401, 403]

    def test_external_ip_rejected(self, client):
        """External IPs without API key are rejected."""
        headers = {"X-Forwarded-For": "8.8.8.8"}
        with patch("src.server.is_tailscale_ip", return_value=False):
            response = client.get("/api/camera/events", headers=headers)
            assert response.status_code in [401, 403]


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestCameraAPIErrorHandling:
    """Tests for camera API error handling."""

    def test_invalid_time_range(self, client, auth_headers):
        """Invalid time range returns error."""
        with patch("src.server.verify_camera_api_auth", return_value=True):
            response = client.get(
                "/api/camera/events?time_range=invalid_time",
                headers=auth_headers,
            )
            # Should return 200 with empty results or 400 with error
            assert response.status_code in [200, 400]

    def test_invalid_limit(self, client, auth_headers):
        """Invalid limit parameter is handled."""
        with patch("src.server.verify_camera_api_auth", return_value=True):
            response = client.get(
                "/api/camera/events?limit=not_a_number",
                headers=auth_headers,
            )
            assert response.status_code in [200, 400]

    def test_database_error_handled(self, client, auth_headers):
        """Database errors return 500."""
        with patch("src.server.verify_camera_api_auth", return_value=True):
            with patch("src.server.get_camera_store", side_effect=Exception("DB Error")):
                response = client.get("/api/camera/events", headers=auth_headers)
                assert response.status_code == 500


# =============================================================================
# Response Format Tests
# =============================================================================


class TestCameraAPIResponseFormat:
    """Tests for camera API response format."""

    def test_events_response_structure(self, client, auth_headers, mock_camera_store):
        """Events response has correct structure."""
        with patch("src.server.verify_camera_api_auth", return_value=True):
            with patch("src.server.get_camera_store", return_value=mock_camera_store):
                response = client.get("/api/camera/events", headers=auth_headers)
                assert response.status_code == 200
                data = json.loads(response.data)

                # Required top-level fields
                assert "success" in data
                assert "events" in data
                assert "count" in data

                # Event structure (if events exist)
                if data["events"]:
                    event = data["events"][0]
                    assert "id" in event
                    assert "timestamp" in event
                    assert "camera_id" in event
                    assert "objects_detected" in event

    def test_summary_response_structure(self, client, auth_headers, mock_camera_store):
        """Summary response has correct structure."""
        with patch("src.server.verify_camera_api_auth", return_value=True):
            with patch("src.server.get_camera_store", return_value=mock_camera_store):
                response = client.get("/api/camera/summary", headers=auth_headers)
                assert response.status_code == 200
                data = json.loads(response.data)

                # Required top-level fields
                assert "success" in data
                assert "total_events" in data
                assert "period_start" in data
                assert "period_end" in data
                assert "objects_detected" in data

    def test_events_timestamps_are_iso_format(self, client, auth_headers, mock_camera_store):
        """Event timestamps are in ISO format."""
        with patch("src.server.verify_camera_api_auth", return_value=True):
            with patch("src.server.get_camera_store", return_value=mock_camera_store):
                response = client.get("/api/camera/events", headers=auth_headers)
                data = json.loads(response.data)

                if data["events"]:
                    timestamp = data["events"][0]["timestamp"]
                    # Should parse as ISO format
                    try:
                        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    except ValueError:
                        pytest.fail(f"Timestamp not in ISO format: {timestamp}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
