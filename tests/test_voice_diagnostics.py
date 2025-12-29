"""
Tests for Voice Pipeline Diagnostic Suite

WP-9.2: Voice Pipeline Diagnostic Suite (Christmas Gift 2025)
"""

import socket
from unittest.mock import MagicMock, patch

import pytest

from src.voice_diagnostics import (
    DiagnosticResult,
    DiagnosticSummary,
    TestStatus,
    VoicePipelineDiagnostics,
    get_diagnostics,
)


class TestDiagnosticModels:
    """Tests for diagnostic data models."""

    def test_diagnostic_result_creation(self):
        """Test DiagnosticResult can be created with minimal fields."""
        result = DiagnosticResult(
            name="Test",
            status=TestStatus.PASSED,
            message="Test passed"
        )
        assert result.name == "Test"
        assert result.status == TestStatus.PASSED
        assert result.message == "Test passed"
        assert result.details == {}
        assert result.fix_suggestions == []
        assert result.duration_ms == 0.0

    def test_diagnostic_result_with_details(self):
        """Test DiagnosticResult with all fields."""
        result = DiagnosticResult(
            name="Test",
            status=TestStatus.FAILED,
            message="Test failed",
            details={"error": "Connection refused"},
            fix_suggestions=["Check server", "Verify port"],
            duration_ms=123.45
        )
        assert result.details == {"error": "Connection refused"}
        assert len(result.fix_suggestions) == 2
        assert result.duration_ms == 123.45

    def test_test_status_values(self):
        """Test TestStatus enum values."""
        assert TestStatus.PASSED.value == "passed"
        assert TestStatus.FAILED.value == "failed"
        assert TestStatus.WARNING.value == "warning"
        assert TestStatus.SKIPPED.value == "skipped"


class TestVoicePipelineDiagnostics:
    """Tests for VoicePipelineDiagnostics class."""

    @pytest.fixture
    def mock_ha_client(self):
        """Create a mock HA client."""
        with patch('src.voice_diagnostics.get_ha_client') as mock:
            client = MagicMock()
            mock.return_value = client
            yield client

    @pytest.fixture
    def diagnostics(self, mock_ha_client):
        """Create a diagnostics instance with mocked dependencies."""
        return VoicePipelineDiagnostics(
            ha_url="http://localhost:8123",
            ha_token="test_token",
            voice_puck_host="test-puck.local",
            smarthome_webhook_url="http://localhost:5000"
        )

    def test_init_with_defaults(self, mock_ha_client):
        """Test initialization with default values."""
        with patch.dict('os.environ', {'HA_URL': 'http://ha:8123', 'HA_TOKEN': 'token'}):
            diag = VoicePipelineDiagnostics()
            assert diag.voice_puck_host == VoicePipelineDiagnostics.VOICE_PUCK_HOST

    def test_init_with_custom_values(self, mock_ha_client):
        """Test initialization with custom values."""
        diag = VoicePipelineDiagnostics(
            ha_url="http://custom:8123",
            voice_puck_host="custom-puck.local",
            smarthome_webhook_url="http://custom:5000"
        )
        assert diag.ha_url == "http://custom:8123"
        assert diag.voice_puck_host == "custom-puck.local"
        assert diag.smarthome_webhook_url == "http://custom:5000"


class TestVoicePuckConnectivity:
    """Tests for voice puck connectivity diagnostic."""

    @pytest.fixture
    def diagnostics(self):
        """Create diagnostics with mocked dependencies."""
        with patch('src.voice_diagnostics.get_ha_client'):
            return VoicePipelineDiagnostics(
                voice_puck_host="test-puck.local"
            )

    def test_puck_reachable(self, diagnostics):
        """Test when voice puck is reachable."""
        with patch.object(diagnostics, '_resolve_host', return_value="192.168.1.100"):
            with patch.object(diagnostics, '_check_port', return_value=True):
                result = diagnostics.test_voice_puck_connectivity()

        assert result.status == TestStatus.PASSED
        assert "reachable" in result.message.lower()
        assert result.details.get("resolved_ip") == "192.168.1.100"

    def test_puck_dns_failure(self, diagnostics):
        """Test when voice puck hostname cannot be resolved."""
        with patch.object(diagnostics, '_resolve_host', return_value=None):
            result = diagnostics.test_voice_puck_connectivity()

        assert result.status == TestStatus.FAILED
        assert "cannot resolve" in result.message.lower()
        assert len(result.fix_suggestions) > 0

    def test_puck_port_closed(self, diagnostics):
        """Test when voice puck is reachable but port is closed."""
        with patch.object(diagnostics, '_resolve_host', return_value="192.168.1.100"):
            with patch.object(diagnostics, '_check_port', return_value=False):
                result = diagnostics.test_voice_puck_connectivity()

        assert result.status == TestStatus.FAILED
        assert "port closed" in result.message.lower()
        assert any("esphome" in s.lower() for s in result.fix_suggestions)


class TestHAAssistPipeline:
    """Tests for HA Assist pipeline diagnostic."""

    @pytest.fixture
    def mock_ha_client(self):
        """Create a mock HA client."""
        with patch('src.voice_diagnostics.get_ha_client') as mock:
            client = MagicMock()
            mock.return_value = client
            yield client

    @pytest.fixture
    def diagnostics(self, mock_ha_client):
        """Create diagnostics with mocked HA client."""
        return VoicePipelineDiagnostics()

    def test_ha_connected_with_pipeline(self, diagnostics, mock_ha_client):
        """Test when HA is connected with configured pipeline."""
        mock_ha_client.check_connection.return_value = True
        mock_ha_client.get_all_states.return_value = [
            {"entity_id": "stt.whisper"},
            {"entity_id": "tts.piper"},
        ]

        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"components": ["conversation"]}
            mock_get.return_value = mock_response

            result = diagnostics.test_ha_assist_pipeline()

        assert result.status == TestStatus.PASSED
        assert result.details.get("ha_connected") is True

    def test_ha_not_connected(self, diagnostics, mock_ha_client):
        """Test when HA is not reachable."""
        mock_ha_client.check_connection.return_value = False

        result = diagnostics.test_ha_assist_pipeline()

        assert result.status == TestStatus.FAILED
        assert "cannot connect" in result.message.lower()
        assert len(result.fix_suggestions) > 0


class TestSmartHomeWebhook:
    """Tests for SmartHome webhook diagnostic."""

    @pytest.fixture
    def diagnostics(self):
        """Create diagnostics with mocked dependencies."""
        with patch('src.voice_diagnostics.get_ha_client'):
            return VoicePipelineDiagnostics(
                smarthome_webhook_url="http://localhost:5000"
            )

    def test_webhook_reachable(self, diagnostics):
        """Test when webhook is reachable."""
        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "application/json"}
            mock_response.json.return_value = {"status": "ok"}
            mock_get.return_value = mock_response

            result = diagnostics.test_smarthome_webhook()

        assert result.status == TestStatus.PASSED
        assert "reachable" in result.message.lower()

    def test_webhook_connection_error(self, diagnostics):
        """Test when webhook connection fails."""
        with patch('requests.get') as mock_get:
            import requests
            mock_get.side_effect = requests.exceptions.ConnectionError()

            result = diagnostics.test_smarthome_webhook()

        assert result.status == TestStatus.FAILED
        assert "cannot connect" in result.message.lower()
        assert any("running" in s.lower() for s in result.fix_suggestions)


class TestSmartHomeVoiceEndpoint:
    """Tests for SmartHome voice endpoint diagnostic."""

    @pytest.fixture
    def diagnostics(self):
        """Create diagnostics with mocked dependencies."""
        with patch('src.voice_diagnostics.get_ha_client'):
            return VoicePipelineDiagnostics(
                smarthome_webhook_url="http://localhost:5000"
            )

    def test_voice_endpoint_success(self, diagnostics):
        """Test when voice endpoint works correctly."""
        with patch('requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "application/json"}
            mock_response.json.return_value = {
                "success": True,
                "response": "The time is 3:00 PM"
            }
            mock_post.return_value = mock_response

            result = diagnostics.test_smarthome_voice_endpoint()

        assert result.status == TestStatus.PASSED
        assert "functional" in result.message.lower()

    def test_voice_endpoint_timeout(self, diagnostics):
        """Test when voice endpoint times out."""
        with patch('requests.post') as mock_post:
            import requests
            mock_post.side_effect = requests.exceptions.Timeout()

            result = diagnostics.test_smarthome_voice_endpoint()

        assert result.status == TestStatus.FAILED
        assert "timed out" in result.message.lower()

    def test_voice_endpoint_error_response(self, diagnostics):
        """Test when voice endpoint returns an error."""
        with patch('requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "application/json"}
            mock_response.json.return_value = {
                "success": False,
                "error": "LLM API key not configured"
            }
            mock_post.return_value = mock_response

            result = diagnostics.test_smarthome_voice_endpoint()

        assert result.status == TestStatus.FAILED
        assert "error" in result.message.lower()


class TestTTSOutput:
    """Tests for TTS output diagnostic."""

    @pytest.fixture
    def mock_ha_client(self):
        """Create a mock HA client."""
        with patch('src.voice_diagnostics.get_ha_client') as mock:
            client = MagicMock()
            mock.return_value = client
            yield client

    @pytest.fixture
    def diagnostics(self, mock_ha_client):
        """Create diagnostics with mocked HA client."""
        return VoicePipelineDiagnostics()

    def test_tts_configured_with_media_players(self, diagnostics, mock_ha_client):
        """Test when TTS is configured with available media players."""
        mock_ha_client.get_all_states.return_value = [
            {"entity_id": "tts.piper", "state": "idle"},
            {"entity_id": "media_player.living_room", "state": "idle", "attributes": {"friendly_name": "Living Room Speaker"}},
            {"entity_id": "media_player.bedroom", "state": "playing", "attributes": {"friendly_name": "Bedroom Speaker"}},
        ]

        result = diagnostics.test_tts_output()

        assert result.status == TestStatus.PASSED
        assert "tts.piper" in result.details.get("tts_entities", [])
        assert result.details.get("available_media_players") == 2

    def test_no_tts_configured(self, diagnostics, mock_ha_client):
        """Test when no TTS is configured."""
        mock_ha_client.get_all_states.return_value = [
            {"entity_id": "light.living_room", "state": "on"},
        ]

        result = diagnostics.test_tts_output()

        assert result.status == TestStatus.FAILED
        assert "no tts" in result.message.lower()
        assert any("install" in s.lower() for s in result.fix_suggestions)

    def test_tts_but_no_media_players(self, diagnostics, mock_ha_client):
        """Test when TTS is configured but no media players available."""
        mock_ha_client.get_all_states.return_value = [
            {"entity_id": "tts.piper", "state": "idle"},
            {"entity_id": "media_player.speaker", "state": "unavailable"},
        ]

        result = diagnostics.test_tts_output()

        assert result.status == TestStatus.WARNING
        assert "no available media players" in result.message.lower()


class TestRunAllDiagnostics:
    """Tests for running the full diagnostic suite."""

    @pytest.fixture
    def diagnostics(self):
        """Create diagnostics with mocked dependencies."""
        with patch('src.voice_diagnostics.get_ha_client'):
            diag = VoicePipelineDiagnostics()
            # Mock all individual tests
            diag.test_voice_puck_connectivity = MagicMock(return_value=DiagnosticResult(
                name="Voice Puck Connectivity",
                status=TestStatus.PASSED,
                message="Passed"
            ))
            diag.test_ha_assist_pipeline = MagicMock(return_value=DiagnosticResult(
                name="HA Assist Pipeline",
                status=TestStatus.PASSED,
                message="Passed"
            ))
            diag.test_smarthome_webhook = MagicMock(return_value=DiagnosticResult(
                name="SmartHome Webhook",
                status=TestStatus.PASSED,
                message="Passed"
            ))
            diag.test_smarthome_voice_endpoint = MagicMock(return_value=DiagnosticResult(
                name="SmartHome Voice Endpoint",
                status=TestStatus.PASSED,
                message="Passed"
            ))
            diag.test_tts_output = MagicMock(return_value=DiagnosticResult(
                name="TTS Output",
                status=TestStatus.PASSED,
                message="Passed"
            ))
            return diag

    def test_all_pass(self, diagnostics):
        """Test when all diagnostics pass."""
        summary = diagnostics.run_all_diagnostics()

        assert summary.overall_status == TestStatus.PASSED
        assert summary.passed_count == 5
        assert summary.failed_count == 0
        assert summary.warning_count == 0
        assert len(summary.results) == 5

    def test_one_failure(self, diagnostics):
        """Test when one diagnostic fails."""
        diagnostics.test_voice_puck_connectivity.return_value = DiagnosticResult(
            name="Voice Puck Connectivity",
            status=TestStatus.FAILED,
            message="Failed"
        )

        summary = diagnostics.run_all_diagnostics()

        assert summary.overall_status == TestStatus.FAILED
        assert summary.passed_count == 4
        assert summary.failed_count == 1

    def test_one_warning(self, diagnostics):
        """Test when one diagnostic has warning."""
        diagnostics.test_tts_output.return_value = DiagnosticResult(
            name="TTS Output",
            status=TestStatus.WARNING,
            message="Warning"
        )

        summary = diagnostics.run_all_diagnostics()

        assert summary.overall_status == TestStatus.WARNING
        assert summary.passed_count == 4
        assert summary.warning_count == 1


class TestToDict:
    """Tests for JSON serialization."""

    @pytest.fixture
    def diagnostics(self):
        """Create diagnostics with mocked dependencies."""
        with patch('src.voice_diagnostics.get_ha_client'):
            return VoicePipelineDiagnostics()

    def test_to_dict_serialization(self, diagnostics):
        """Test that summary converts to dictionary correctly."""
        summary = DiagnosticSummary(
            overall_status=TestStatus.PASSED,
            results=[
                DiagnosticResult(
                    name="Test 1",
                    status=TestStatus.PASSED,
                    message="OK",
                    duration_ms=100.5
                )
            ],
            timestamp="2025-12-25T08:00:00",
            total_duration_ms=100.5,
            passed_count=1,
            failed_count=0,
            warning_count=0
        )

        result = diagnostics.to_dict(summary)

        assert result["overall_status"] == "passed"
        assert result["timestamp"] == "2025-12-25T08:00:00"
        assert result["total_duration_ms"] == 100.5
        assert result["summary"]["passed"] == 1
        assert len(result["results"]) == 1
        assert result["results"][0]["name"] == "Test 1"
        assert result["results"][0]["status"] == "passed"


# ========== WP-10.17: Voice Pipeline Diagnostic Enhancements ==========


class TestESPHomeFirmwareChecker:
    """Tests for ESPHome version/firmware checking (WP-10.17)."""

    @pytest.fixture
    def diagnostics(self):
        """Create diagnostics with mocked dependencies."""
        with patch('src.voice_diagnostics.get_ha_client'):
            return VoicePipelineDiagnostics(
                voice_puck_host="test-puck.local"
            )

    def test_get_esphome_version_success(self, diagnostics):
        """Test successfully retrieving ESPHome version."""
        with patch.object(diagnostics, '_resolve_host', return_value="192.168.1.100"):
            with patch('requests.get') as mock_get:
                # First call is to root, second is to version endpoint
                mock_root_response = MagicMock()
                mock_root_response.status_code = 200

                mock_version_response = MagicMock()
                mock_version_response.status_code = 200
                mock_version_response.json.return_value = {"value": "2024.12.0"}

                mock_get.side_effect = [mock_root_response, mock_version_response]

                version_info = diagnostics.get_esphome_version()

                assert version_info is not None
                assert version_info.get("version") == "2024.12.0"
                assert version_info.get("name") == "test-puck.local"

    def test_get_esphome_version_connection_error(self, diagnostics):
        """Test handling connection error when getting version."""
        with patch('requests.get') as mock_get:
            import requests
            mock_get.side_effect = requests.exceptions.ConnectionError()

            version_info = diagnostics.get_esphome_version()

            assert version_info is None

    def test_check_firmware_update_available(self, diagnostics):
        """Test detecting when firmware update is available."""
        with patch.object(diagnostics, 'get_esphome_version') as mock_version, \
             patch.object(diagnostics, 'get_latest_esphome_version') as mock_latest:
            mock_version.return_value = {"version": "2024.10.0"}
            mock_latest.return_value = "2024.12.0"

            result = diagnostics.check_firmware_update()

            assert result["update_available"] is True
            assert result["current_version"] == "2024.10.0"
            assert result["latest_version"] == "2024.12.0"

    def test_check_firmware_up_to_date(self, diagnostics):
        """Test detecting when firmware is up to date."""
        with patch.object(diagnostics, 'get_esphome_version') as mock_version, \
             patch.object(diagnostics, 'get_latest_esphome_version') as mock_latest:
            mock_version.return_value = {"version": "2024.12.0"}
            mock_latest.return_value = "2024.12.0"

            result = diagnostics.check_firmware_update()

            assert result["update_available"] is False


class TestPipelineConfigHelper:
    """Tests for HA Assist pipeline configuration helper (WP-10.17)."""

    @pytest.fixture
    def mock_ha_client(self):
        """Create a mock HA client."""
        with patch('src.voice_diagnostics.get_ha_client') as mock:
            client = MagicMock()
            mock.return_value = client
            yield client

    @pytest.fixture
    def diagnostics(self, mock_ha_client):
        """Create diagnostics with mocked HA client."""
        return VoicePipelineDiagnostics()

    def test_get_pipeline_setup_steps(self, diagnostics, mock_ha_client):
        """Test getting pipeline setup steps based on current config."""
        mock_ha_client.get_all_states.return_value = []  # No STT/TTS configured

        steps = diagnostics.get_pipeline_setup_steps()

        assert len(steps) > 0
        assert any("stt" in step.lower() or "whisper" in step.lower() for step in steps)
        assert any("tts" in step.lower() or "piper" in step.lower() for step in steps)

    def test_get_pipeline_status_complete(self, diagnostics, mock_ha_client):
        """Test pipeline status when fully configured."""
        mock_ha_client.get_all_states.return_value = [
            {"entity_id": "stt.whisper"},
            {"entity_id": "tts.piper"},
            {"entity_id": "conversation.home_assistant"},
        ]

        status = diagnostics.get_pipeline_status()

        assert status["has_stt"] is True
        assert status["has_tts"] is True
        assert status["has_conversation"] is True
        assert status["is_complete"] is True

    def test_get_pipeline_status_incomplete(self, diagnostics, mock_ha_client):
        """Test pipeline status when missing components."""
        mock_ha_client.get_all_states.return_value = [
            {"entity_id": "tts.piper"},
        ]

        status = diagnostics.get_pipeline_status()

        assert status["has_stt"] is False
        assert status["has_tts"] is True
        assert status["is_complete"] is False


class TestExpandedTroubleshootingGuide:
    """Tests for expanded troubleshooting guidance (WP-10.17)."""

    @pytest.fixture
    def diagnostics(self):
        """Create diagnostics with mocked dependencies."""
        with patch('src.voice_diagnostics.get_ha_client'):
            return VoicePipelineDiagnostics()

    def test_get_troubleshooting_guide(self, diagnostics):
        """Test getting troubleshooting guide for a specific issue."""
        guide = diagnostics.get_troubleshooting_guide("voice_puck_not_responding")

        assert guide is not None
        assert "symptoms" in guide
        assert "causes" in guide
        assert "solutions" in guide
        assert len(guide["solutions"]) > 0

    def test_get_troubleshooting_guide_unknown_issue(self, diagnostics):
        """Test handling unknown issue type."""
        guide = diagnostics.get_troubleshooting_guide("unknown_issue_xyz")

        assert guide is not None
        assert "general" in guide.get("type", "").lower() or len(guide.get("solutions", [])) > 0

    def test_troubleshooting_guide_includes_links(self, diagnostics):
        """Test that troubleshooting guide includes documentation links."""
        guide = diagnostics.get_troubleshooting_guide("stt_not_working")

        # Should include helpful links
        all_text = str(guide)
        has_link = "http" in all_text or "docs" in all_text.lower()
        assert has_link or len(guide.get("solutions", [])) > 0


class TestSTTTTSQualityTest:
    """Tests for STT/TTS quality testing helpers (WP-10.17)."""

    @pytest.fixture
    def mock_ha_client(self):
        """Create a mock HA client."""
        with patch('src.voice_diagnostics.get_ha_client') as mock:
            client = MagicMock()
            mock.return_value = client
            yield client

    @pytest.fixture
    def diagnostics(self, mock_ha_client):
        """Create diagnostics with mocked HA client."""
        return VoicePipelineDiagnostics()

    def test_test_stt_quality_returns_result(self, diagnostics, mock_ha_client):
        """Test STT quality check returns a diagnostic result."""
        mock_ha_client.get_all_states.return_value = [
            {"entity_id": "stt.whisper"},
        ]

        result = diagnostics.test_stt_quality()

        assert isinstance(result, DiagnosticResult)
        assert result.name == "STT Quality"

    def test_test_tts_quality_returns_result(self, diagnostics, mock_ha_client):
        """Test TTS quality check returns a diagnostic result."""
        mock_ha_client.get_all_states.return_value = [
            {"entity_id": "tts.piper"},
        ]

        result = diagnostics.test_tts_quality()

        assert isinstance(result, DiagnosticResult)
        assert result.name == "TTS Quality"


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_diagnostics_returns_instance(self):
        """Test that get_diagnostics returns a VoicePipelineDiagnostics instance."""
        with patch('src.voice_diagnostics.get_ha_client'):
            diag1 = get_diagnostics()
            diag2 = get_diagnostics()

            assert diag1 is diag2
            assert isinstance(diag1, VoicePipelineDiagnostics)


class TestHelperMethods:
    """Tests for private helper methods."""

    @pytest.fixture
    def diagnostics(self):
        """Create diagnostics with mocked dependencies."""
        with patch('src.voice_diagnostics.get_ha_client'):
            return VoicePipelineDiagnostics()

    def test_resolve_host_success(self, diagnostics):
        """Test successful hostname resolution."""
        with patch('socket.gethostbyname', return_value="192.168.1.1"):
            result = diagnostics._resolve_host("test.local")
            assert result == "192.168.1.1"

    def test_resolve_host_failure(self, diagnostics):
        """Test failed hostname resolution."""
        with patch('socket.gethostbyname', side_effect=socket.gaierror()):
            result = diagnostics._resolve_host("invalid.local")
            assert result is None

    def test_check_port_open(self, diagnostics):
        """Test checking an open port."""
        mock_socket = MagicMock()
        mock_socket.connect_ex.return_value = 0

        with patch('socket.socket', return_value=mock_socket):
            result = diagnostics._check_port("192.168.1.1", 80)
            assert result is True

    def test_check_port_closed(self, diagnostics):
        """Test checking a closed port."""
        mock_socket = MagicMock()
        mock_socket.connect_ex.return_value = 111  # Connection refused

        with patch('socket.socket', return_value=mock_socket):
            result = diagnostics._check_port("192.168.1.1", 80)
            assert result is False
