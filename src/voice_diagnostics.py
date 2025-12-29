"""
Voice Pipeline Diagnostic Suite

Comprehensive diagnostic tool to test the entire voice pipeline from
voice puck to TTS response. Identifies failures and suggests fixes.

WP-9.2: Voice Pipeline Diagnostic Suite (Christmas Gift 2025)
Addresses: BUG-001 (Voice Puck not responding)

WP-10.17 Enhancements (2025-12-29):
- ESPHome version/firmware checker
- Pipeline configuration status helper
- Expanded troubleshooting guides
- STT/TTS quality testing helpers
"""

import socket
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import requests

from src.config import HA_TOKEN, HA_URL
from src.ha_client import get_ha_client
from src.utils import setup_logging


logger = setup_logging("voice_diagnostics")


class TestStatus(Enum):
    """Status of a diagnostic test."""

    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"


@dataclass
class DiagnosticResult:
    """Result of a single diagnostic test."""

    name: str
    status: TestStatus
    message: str
    details: dict = field(default_factory=dict)
    fix_suggestions: list = field(default_factory=list)
    duration_ms: float = 0.0


@dataclass
class DiagnosticSummary:
    """Summary of all diagnostic tests."""

    overall_status: TestStatus
    results: list[DiagnosticResult]
    timestamp: str
    total_duration_ms: float
    passed_count: int
    failed_count: int
    warning_count: int


class VoicePipelineDiagnostics:
    """
    Diagnostic suite for the voice pipeline.

    Tests the full path from voice puck to TTS response:
    1. Voice Puck connectivity (ping, ESPHome status)
    2. HA Assist pipeline check (STT, TTS, conversation agent config)
    3. SmartHome webhook reachability from HA
    4. SmartHome voice endpoint functionality
    5. TTS output verification
    """

    # Default configuration - can be overridden
    VOICE_PUCK_HOST = "esphome-voice.local"  # ESPHome voice device
    VOICE_PUCK_IP = None  # Set if mDNS doesn't work
    VOICE_PUCK_API_PORT = 6053  # ESPHome native API port
    SMARTHOME_WEBHOOK_PORT = 5000  # SmartHome server port

    def __init__(
        self,
        ha_url: str | None = None,
        ha_token: str | None = None,
        voice_puck_host: str | None = None,
        smarthome_webhook_url: str | None = None,
    ):
        """
        Initialize the diagnostic suite.

        Args:
            ha_url: Home Assistant URL (defaults to config)
            ha_token: Home Assistant token (defaults to config)
            voice_puck_host: Voice puck hostname or IP
            smarthome_webhook_url: SmartHome webhook URL
        """
        self.ha_url = (ha_url or HA_URL).rstrip("/")
        self.ha_token = ha_token or HA_TOKEN
        self.ha_headers = {
            "Authorization": f"Bearer {self.ha_token}",
            "Content-Type": "application/json",
        }

        self.voice_puck_host = voice_puck_host or self.VOICE_PUCK_HOST
        self.smarthome_webhook_url = (
            smarthome_webhook_url or f"http://localhost:{self.SMARTHOME_WEBHOOK_PORT}"
        )

        self.ha_client = get_ha_client()

    def run_all_diagnostics(self) -> DiagnosticSummary:
        """
        Run all diagnostic tests in sequence.

        Returns:
            DiagnosticSummary with all test results
        """
        start_time = datetime.now()
        results = []

        # Test 1: Voice Puck Connectivity
        results.append(self.test_voice_puck_connectivity())

        # Test 2: HA Assist Pipeline Check
        results.append(self.test_ha_assist_pipeline())

        # Test 3: SmartHome Webhook Reachability
        results.append(self.test_smarthome_webhook())

        # Test 4: SmartHome Voice Endpoint
        results.append(self.test_smarthome_voice_endpoint())

        # Test 5: TTS Output Verification
        results.append(self.test_tts_output())

        end_time = datetime.now()
        total_duration = (end_time - start_time).total_seconds() * 1000

        # Calculate summary stats
        passed = sum(1 for r in results if r.status == TestStatus.PASSED)
        failed = sum(1 for r in results if r.status == TestStatus.FAILED)
        warnings = sum(1 for r in results if r.status == TestStatus.WARNING)

        # Determine overall status
        if failed > 0:
            overall = TestStatus.FAILED
        elif warnings > 0:
            overall = TestStatus.WARNING
        else:
            overall = TestStatus.PASSED

        return DiagnosticSummary(
            overall_status=overall,
            results=results,
            timestamp=datetime.now().isoformat(),
            total_duration_ms=total_duration,
            passed_count=passed,
            failed_count=failed,
            warning_count=warnings,
        )

    def test_voice_puck_connectivity(self) -> DiagnosticResult:
        """
        Test 1: Voice Puck Connectivity

        Checks:
        - Network reachability (ping or socket)
        - ESPHome API availability
        """
        start_time = datetime.now()
        details = {}
        fix_suggestions = []

        # Try to resolve and connect to the voice puck
        try:
            # First try to resolve the hostname
            ip_address = self._resolve_host(self.voice_puck_host)
            if ip_address:
                details["resolved_ip"] = ip_address
                details["hostname"] = self.voice_puck_host

                # Check if ESPHome API port is reachable
                is_reachable = self._check_port(ip_address, self.VOICE_PUCK_API_PORT)

                if is_reachable:
                    details["esphome_api_port"] = self.VOICE_PUCK_API_PORT
                    details["esphome_api_status"] = "reachable"

                    duration = (datetime.now() - start_time).total_seconds() * 1000
                    return DiagnosticResult(
                        name="Voice Puck Connectivity",
                        status=TestStatus.PASSED,
                        message=f"Voice puck is reachable at {ip_address}",
                        details=details,
                        duration_ms=duration,
                    )
                else:
                    details["esphome_api_status"] = "port_closed"
                    fix_suggestions = [
                        "Check if ESPHome is running on the voice puck",
                        "Verify the voice puck is powered on",
                        f"Ensure ESPHome API is enabled (port {self.VOICE_PUCK_API_PORT})",
                        "Check firewall rules on the voice puck device",
                    ]

                    duration = (datetime.now() - start_time).total_seconds() * 1000
                    return DiagnosticResult(
                        name="Voice Puck Connectivity",
                        status=TestStatus.FAILED,
                        message=f"Voice puck at {ip_address} has ESPHome API port closed",
                        details=details,
                        fix_suggestions=fix_suggestions,
                        duration_ms=duration,
                    )
            else:
                fix_suggestions = [
                    f"Verify the voice puck hostname '{self.voice_puck_host}' is correct",
                    "Check if mDNS/Avahi is running on your network",
                    "Try using the IP address directly instead of hostname",
                    "Verify the voice puck is on the same network/VLAN",
                ]

                duration = (datetime.now() - start_time).total_seconds() * 1000
                return DiagnosticResult(
                    name="Voice Puck Connectivity",
                    status=TestStatus.FAILED,
                    message=f"Cannot resolve hostname '{self.voice_puck_host}'",
                    details={"hostname": self.voice_puck_host, "error": "DNS resolution failed"},
                    fix_suggestions=fix_suggestions,
                    duration_ms=duration,
                )

        except Exception as error:
            fix_suggestions = [
                "Check network connectivity",
                "Verify the voice puck is powered on",
                "Check if the voice puck is on the same network",
            ]

            duration = (datetime.now() - start_time).total_seconds() * 1000
            return DiagnosticResult(
                name="Voice Puck Connectivity",
                status=TestStatus.FAILED,
                message=f"Error checking voice puck: {error}",
                details={"error": str(error)},
                fix_suggestions=fix_suggestions,
                duration_ms=duration,
            )

    def test_ha_assist_pipeline(self) -> DiagnosticResult:
        """
        Test 2: HA Assist Pipeline Check

        Checks:
        - Home Assistant is reachable
        - Assist pipelines are configured
        - STT (speech-to-text) is configured
        - TTS (text-to-speech) is configured
        - Conversation agent is configured
        """
        start_time = datetime.now()
        details = {}
        fix_suggestions = []

        try:
            # Check HA connection
            ha_ok = self.ha_client.check_connection()
            details["ha_connected"] = ha_ok

            if not ha_ok:
                fix_suggestions = [
                    "Verify Home Assistant is running",
                    f"Check HA_URL is correct: {self.ha_url}",
                    "Verify your HA access token is valid",
                    "Check network connectivity to Home Assistant",
                ]

                duration = (datetime.now() - start_time).total_seconds() * 1000
                return DiagnosticResult(
                    name="HA Assist Pipeline",
                    status=TestStatus.FAILED,
                    message="Cannot connect to Home Assistant",
                    details=details,
                    fix_suggestions=fix_suggestions,
                    duration_ms=duration,
                )

            # Check for Assist pipelines via API
            pipelines_info = self._get_assist_pipelines()
            details["pipelines"] = pipelines_info

            if not pipelines_info.get("pipelines"):
                fix_suggestions = [
                    "Go to Home Assistant Settings > Voice assistants",
                    "Create a new Assist pipeline",
                    "Configure STT (e.g., Whisper) and TTS (e.g., Piper)",
                    "Set up a conversation agent (e.g., Home Assistant default)",
                ]

                duration = (datetime.now() - start_time).total_seconds() * 1000
                return DiagnosticResult(
                    name="HA Assist Pipeline",
                    status=TestStatus.FAILED,
                    message="No Assist pipelines configured",
                    details=details,
                    fix_suggestions=fix_suggestions,
                    duration_ms=duration,
                )

            # Check STT and TTS configuration
            default_pipeline = pipelines_info.get("preferred_pipeline")
            has_stt = any(p.get("stt_engine") for p in pipelines_info.get("pipelines", []))
            has_tts = any(p.get("tts_engine") for p in pipelines_info.get("pipelines", []))

            details["has_stt"] = has_stt
            details["has_tts"] = has_tts
            details["default_pipeline"] = default_pipeline

            if not has_stt:
                fix_suggestions.append(
                    "Configure Speech-to-Text in your Assist pipeline (e.g., Whisper)"
                )

            if not has_tts:
                fix_suggestions.append(
                    "Configure Text-to-Speech in your Assist pipeline (e.g., Piper)"
                )

            if fix_suggestions:
                duration = (datetime.now() - start_time).total_seconds() * 1000
                return DiagnosticResult(
                    name="HA Assist Pipeline",
                    status=TestStatus.WARNING,
                    message="Assist pipeline has incomplete configuration",
                    details=details,
                    fix_suggestions=fix_suggestions,
                    duration_ms=duration,
                )

            duration = (datetime.now() - start_time).total_seconds() * 1000
            return DiagnosticResult(
                name="HA Assist Pipeline",
                status=TestStatus.PASSED,
                message="HA Assist pipeline is properly configured",
                details=details,
                duration_ms=duration,
            )

        except Exception as error:
            fix_suggestions = [
                "Verify Home Assistant is running",
                "Check API connectivity",
                "Review Home Assistant logs for errors",
            ]

            duration = (datetime.now() - start_time).total_seconds() * 1000
            return DiagnosticResult(
                name="HA Assist Pipeline",
                status=TestStatus.FAILED,
                message=f"Error checking HA Assist pipeline: {error}",
                details={"error": str(error)},
                fix_suggestions=fix_suggestions,
                duration_ms=duration,
            )

    def test_smarthome_webhook(self) -> DiagnosticResult:
        """
        Test 3: SmartHome Webhook Reachability

        Checks if the SmartHome server webhook is reachable from where
        Home Assistant would call it.
        """
        start_time = datetime.now()
        details = {"webhook_url": self.smarthome_webhook_url}
        fix_suggestions = []

        try:
            # Check if the SmartHome server is reachable
            response = requests.get(f"{self.smarthome_webhook_url}/api/health", timeout=5)

            details["status_code"] = response.status_code
            details["response"] = (
                response.json()
                if response.headers.get("content-type", "").startswith("application/json")
                else response.text[:200]
            )

            if response.status_code == 200:
                duration = (datetime.now() - start_time).total_seconds() * 1000
                return DiagnosticResult(
                    name="SmartHome Webhook",
                    status=TestStatus.PASSED,
                    message="SmartHome webhook is reachable",
                    details=details,
                    duration_ms=duration,
                )
            else:
                fix_suggestions = [
                    "Check if SmartHome server is running",
                    "Verify the webhook URL is correct",
                    f"Check server logs at {self.smarthome_webhook_url}",
                ]

                duration = (datetime.now() - start_time).total_seconds() * 1000
                return DiagnosticResult(
                    name="SmartHome Webhook",
                    status=TestStatus.WARNING,
                    message=f"SmartHome webhook returned status {response.status_code}",
                    details=details,
                    fix_suggestions=fix_suggestions,
                    duration_ms=duration,
                )

        except requests.exceptions.ConnectionError:
            fix_suggestions = [
                "Check if SmartHome server is running",
                "Start the server: python -m src.server",
                "Verify the port number is correct",
                "Check firewall rules",
            ]

            duration = (datetime.now() - start_time).total_seconds() * 1000
            return DiagnosticResult(
                name="SmartHome Webhook",
                status=TestStatus.FAILED,
                message=f"Cannot connect to SmartHome webhook at {self.smarthome_webhook_url}",
                details=details,
                fix_suggestions=fix_suggestions,
                duration_ms=duration,
            )

        except Exception as error:
            fix_suggestions = ["Check server logs for errors", "Verify network configuration"]

            duration = (datetime.now() - start_time).total_seconds() * 1000
            return DiagnosticResult(
                name="SmartHome Webhook",
                status=TestStatus.FAILED,
                message=f"Error checking SmartHome webhook: {error}",
                details={"error": str(error)},
                fix_suggestions=fix_suggestions,
                duration_ms=duration,
            )

    def test_smarthome_voice_endpoint(self) -> DiagnosticResult:
        """
        Test 4: SmartHome Voice Endpoint Functionality

        Tests the /api/voice endpoint with a simple command.
        """
        start_time = datetime.now()
        details = {"endpoint": f"{self.smarthome_webhook_url}/api/voice"}
        fix_suggestions = []

        try:
            # Send a test voice command
            test_payload = {
                "text": "what time is it",
                "language": "en",
                "device_id": "diagnostic_test",
            }

            response = requests.post(
                f"{self.smarthome_webhook_url}/api/voice",
                json=test_payload,
                timeout=30,  # Voice processing can take time
            )

            details["status_code"] = response.status_code

            if response.headers.get("content-type", "").startswith("application/json"):
                response_data = response.json()
                details["response"] = response_data

                if response.status_code == 200 and response_data.get("success"):
                    duration = (datetime.now() - start_time).total_seconds() * 1000
                    return DiagnosticResult(
                        name="SmartHome Voice Endpoint",
                        status=TestStatus.PASSED,
                        message="Voice endpoint is functional",
                        details=details,
                        duration_ms=duration,
                    )
                else:
                    error_msg = response_data.get("error", "Unknown error")
                    fix_suggestions = [
                        f"Voice endpoint error: {error_msg}",
                        "Check SmartHome server logs for details",
                        "Verify LLM API key is configured correctly",
                        "Check agent initialization in server.py",
                    ]

                    duration = (datetime.now() - start_time).total_seconds() * 1000
                    return DiagnosticResult(
                        name="SmartHome Voice Endpoint",
                        status=TestStatus.FAILED,
                        message=f"Voice endpoint returned error: {error_msg}",
                        details=details,
                        fix_suggestions=fix_suggestions,
                        duration_ms=duration,
                    )
            else:
                details["response_text"] = response.text[:500]
                fix_suggestions = [
                    "Voice endpoint returned non-JSON response",
                    "Check server logs for errors",
                    "Verify endpoint route is correctly defined",
                ]

                duration = (datetime.now() - start_time).total_seconds() * 1000
                return DiagnosticResult(
                    name="SmartHome Voice Endpoint",
                    status=TestStatus.FAILED,
                    message="Unexpected response format from voice endpoint",
                    details=details,
                    fix_suggestions=fix_suggestions,
                    duration_ms=duration,
                )

        except requests.exceptions.Timeout:
            fix_suggestions = [
                "Voice processing timed out",
                "Check if LLM service is responding",
                "Review agent timeout configuration",
                "Check network connectivity to LLM provider",
            ]

            duration = (datetime.now() - start_time).total_seconds() * 1000
            return DiagnosticResult(
                name="SmartHome Voice Endpoint",
                status=TestStatus.FAILED,
                message="Voice endpoint request timed out",
                details=details,
                fix_suggestions=fix_suggestions,
                duration_ms=duration,
            )

        except requests.exceptions.ConnectionError:
            fix_suggestions = [
                "Cannot connect to SmartHome server",
                "Check if server is running",
                "Verify port and URL",
            ]

            duration = (datetime.now() - start_time).total_seconds() * 1000
            return DiagnosticResult(
                name="SmartHome Voice Endpoint",
                status=TestStatus.FAILED,
                message="Cannot connect to voice endpoint",
                details=details,
                fix_suggestions=fix_suggestions,
                duration_ms=duration,
            )

        except Exception as error:
            fix_suggestions = ["Check server logs for errors", "Verify endpoint configuration"]

            duration = (datetime.now() - start_time).total_seconds() * 1000
            return DiagnosticResult(
                name="SmartHome Voice Endpoint",
                status=TestStatus.FAILED,
                message=f"Error testing voice endpoint: {error}",
                details={"error": str(error)},
                fix_suggestions=fix_suggestions,
                duration_ms=duration,
            )

    def test_tts_output(self) -> DiagnosticResult:
        """
        Test 5: TTS Output Verification

        Checks TTS entities in Home Assistant are available.
        """
        start_time = datetime.now()
        details = {}
        fix_suggestions = []

        try:
            # Get all TTS entities
            all_states = self.ha_client.get_all_states()

            # Find TTS entities
            tts_entities = [s for s in all_states if s.get("entity_id", "").startswith("tts.")]

            # Find media players that could be TTS targets
            media_players = [
                s
                for s in all_states
                if s.get("entity_id", "").startswith("media_player.")
                and s.get("state") not in ["unavailable", "unknown"]
            ]

            details["tts_entities"] = [e.get("entity_id") for e in tts_entities]
            details["available_media_players"] = len(media_players)
            details["media_player_samples"] = [
                {
                    "entity_id": m.get("entity_id"),
                    "state": m.get("state"),
                    "friendly_name": m.get("attributes", {}).get("friendly_name"),
                }
                for m in media_players[:5]  # Show first 5
            ]

            if not tts_entities:
                fix_suggestions = [
                    "No TTS entities found in Home Assistant",
                    "Install a TTS integration (e.g., Piper, Google TTS)",
                    "Configure TTS in your Assist pipeline",
                    "Check Settings > Devices & Services for TTS options",
                ]

                duration = (datetime.now() - start_time).total_seconds() * 1000
                return DiagnosticResult(
                    name="TTS Output",
                    status=TestStatus.FAILED,
                    message="No TTS entities configured",
                    details=details,
                    fix_suggestions=fix_suggestions,
                    duration_ms=duration,
                )

            if not media_players:
                fix_suggestions = [
                    "No available media players found",
                    "Check voice puck is registered as a media player",
                    "Verify speaker/media player is online",
                ]

                duration = (datetime.now() - start_time).total_seconds() * 1000
                return DiagnosticResult(
                    name="TTS Output",
                    status=TestStatus.WARNING,
                    message="TTS configured but no available media players",
                    details=details,
                    fix_suggestions=fix_suggestions,
                    duration_ms=duration,
                )

            duration = (datetime.now() - start_time).total_seconds() * 1000
            return DiagnosticResult(
                name="TTS Output",
                status=TestStatus.PASSED,
                message=f"TTS configured with {len(tts_entities)} engine(s) and {len(media_players)} media player(s)",
                details=details,
                duration_ms=duration,
            )

        except Exception as error:
            fix_suggestions = [
                "Error checking TTS configuration",
                "Verify Home Assistant connection",
            ]

            duration = (datetime.now() - start_time).total_seconds() * 1000
            return DiagnosticResult(
                name="TTS Output",
                status=TestStatus.FAILED,
                message=f"Error checking TTS: {error}",
                details={"error": str(error)},
                fix_suggestions=fix_suggestions,
                duration_ms=duration,
            )

    def _resolve_host(self, hostname: str) -> str | None:
        """Resolve hostname to IP address."""
        try:
            return socket.gethostbyname(hostname)
        except socket.gaierror:
            logger.warning(f"Cannot resolve hostname: {hostname}")
            return None

    def _check_port(self, host: str, port: int, timeout: float = 2.0) -> bool:
        """Check if a port is open on a host."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except Exception as error:
            logger.warning(f"Error checking port {port} on {host}: {error}")
            return False

    def _get_assist_pipelines(self) -> dict[str, Any]:
        """Get Assist pipelines from Home Assistant via WebSocket API fallback."""
        # Try REST API first (may not be available in all HA versions)
        try:
            response = requests.get(f"{self.ha_url}/api/config", headers=self.ha_headers, timeout=5)

            if response.status_code == 200:
                config = response.json()
                # Check for conversation integration
                if "conversation" in config.get("components", []):
                    # Pipelines may be available via assist_pipeline component
                    all_states = self.ha_client.get_all_states()

                    # Look for assist_pipeline and conversation entities
                    assist_entities = [
                        s
                        for s in all_states
                        if "assist" in s.get("entity_id", "").lower()
                        or s.get("entity_id", "").startswith("conversation.")
                    ]

                    stt_entities = [
                        s for s in all_states if s.get("entity_id", "").startswith("stt.")
                    ]

                    tts_entities = [
                        s for s in all_states if s.get("entity_id", "").startswith("tts.")
                    ]

                    # Build pipeline info from what we can discover
                    return {
                        "pipelines": [
                            {
                                "name": "discovered",
                                "stt_engine": bool(stt_entities),
                                "tts_engine": bool(tts_entities),
                                "conversation": "conversation" in config.get("components", []),
                            }
                        ],
                        "preferred_pipeline": "discovered"
                        if (stt_entities or tts_entities)
                        else None,
                        "stt_entities": [s.get("entity_id") for s in stt_entities],
                        "tts_entities": [s.get("entity_id") for s in tts_entities],
                        "assist_entities": [s.get("entity_id") for s in assist_entities],
                    }

        except Exception as error:
            logger.warning(f"Error getting assist pipelines: {error}")

        return {"pipelines": [], "preferred_pipeline": None}

    # ========== WP-10.17: Voice Pipeline Diagnostic Enhancements ==========

    def get_esphome_version(self) -> dict[str, Any] | None:
        """
        Get ESPHome device version information (WP-10.17).

        Returns:
            Dictionary with version info or None if unavailable
        """
        try:
            # ESPHome web server API endpoint for device info
            ip = self._resolve_host(self.voice_puck_host)
            if not ip:
                logger.warning(f"Cannot resolve host: {self.voice_puck_host}")
                return None

            # Try ESPHome web server (common port 80) first
            response = requests.get(f"http://{ip}/", timeout=5)
            if response.status_code == 200:
                # Try to parse version from response or headers
                # ESPHome devices typically expose info via different endpoints
                try:
                    # Try JSON endpoint
                    info_response = requests.get(f"http://{ip}/text_sensor/esphome_version", timeout=5)
                    if info_response.status_code == 200:
                        return {
                            "name": self.voice_puck_host,
                            "version": info_response.json().get("value", "unknown"),
                            "ip": ip,
                        }
                except Exception:
                    pass

                # Fallback: return basic info
                return {
                    "name": self.voice_puck_host,
                    "version": "detected (version not exposed)",
                    "ip": ip,
                    "reachable": True,
                }

            return None

        except requests.exceptions.ConnectionError:
            logger.warning(f"Cannot connect to ESPHome device: {self.voice_puck_host}")
            return None
        except Exception as error:
            logger.warning(f"Error getting ESPHome version: {error}")
            return None

    def get_latest_esphome_version(self) -> str | None:
        """
        Get the latest ESPHome version from GitHub (WP-10.17).

        Returns:
            Latest version string or None if unavailable
        """
        try:
            # ESPHome releases API
            response = requests.get(
                "https://api.github.com/repos/esphome/esphome/releases/latest",
                timeout=10,
            )
            if response.status_code == 200:
                return response.json().get("tag_name", "").lstrip("v")
            return None
        except Exception as error:
            logger.warning(f"Error getting latest ESPHome version: {error}")
            return None

    def check_firmware_update(self) -> dict[str, Any]:
        """
        Check if firmware update is available (WP-10.17).

        Returns:
            Dictionary with update status
        """
        current = self.get_esphome_version()
        latest = self.get_latest_esphome_version()

        if current is None:
            return {
                "update_available": False,
                "error": "Cannot connect to ESPHome device",
                "current_version": None,
                "latest_version": latest,
            }

        current_version = current.get("version", "")

        # If version couldn't be determined, can't compare
        if "unknown" in current_version.lower() or "detected" in current_version.lower():
            return {
                "update_available": False,
                "error": "Cannot determine current version",
                "current_version": current_version,
                "latest_version": latest,
            }

        if latest is None:
            return {
                "update_available": False,
                "error": "Cannot fetch latest version",
                "current_version": current_version,
                "latest_version": None,
            }

        # Simple version comparison
        update_available = current_version != latest

        return {
            "update_available": update_available,
            "current_version": current_version,
            "latest_version": latest,
        }

    def get_pipeline_status(self) -> dict[str, Any]:
        """
        Get HA Assist pipeline configuration status (WP-10.17).

        Returns:
            Dictionary with pipeline component status
        """
        try:
            all_states = self.ha_client.get_all_states()

            has_stt = any(s.get("entity_id", "").startswith("stt.") for s in all_states)
            has_tts = any(s.get("entity_id", "").startswith("tts.") for s in all_states)
            has_conversation = any(
                s.get("entity_id", "").startswith("conversation.") for s in all_states
            )

            is_complete = has_stt and has_tts and has_conversation

            return {
                "has_stt": has_stt,
                "has_tts": has_tts,
                "has_conversation": has_conversation,
                "is_complete": is_complete,
                "stt_entities": [s.get("entity_id") for s in all_states if s.get("entity_id", "").startswith("stt.")],
                "tts_entities": [s.get("entity_id") for s in all_states if s.get("entity_id", "").startswith("tts.")],
            }
        except Exception as error:
            logger.error(f"Error getting pipeline status: {error}")
            return {
                "has_stt": False,
                "has_tts": False,
                "has_conversation": False,
                "is_complete": False,
                "error": str(error),
            }

    def get_pipeline_setup_steps(self) -> list[str]:
        """
        Get setup steps based on current pipeline status (WP-10.17).

        Returns:
            List of setup steps needed
        """
        status = self.get_pipeline_status()
        steps = []

        if not status.get("has_stt"):
            steps.extend([
                "Install Whisper STT: Go to Settings > Devices & Services > Add Integration > Whisper",
                "Configure Whisper: Choose model (tiny/base/small) based on hardware",
                "Verify STT entity: Check Settings > Voice assistants for stt.whisper",
            ])

        if not status.get("has_tts"):
            steps.extend([
                "Install Piper TTS: Go to Settings > Devices & Services > Add Integration > Piper",
                "Select voice: Choose a voice pack for your language",
                "Verify TTS entity: Check Settings > Voice assistants for tts.piper",
            ])

        if not status.get("has_conversation"):
            steps.extend([
                "Configure Assist: Go to Settings > Voice assistants",
                "Create a new Assist pipeline or edit the default",
                "Set conversation agent (Home Assistant or custom)",
            ])

        if not steps:
            steps.append("Pipeline is fully configured! Test with: 'Hey Jarvis, what time is it?'")

        return steps

    def get_troubleshooting_guide(self, issue_type: str) -> dict[str, Any]:
        """
        Get troubleshooting guide for a specific issue (WP-10.17).

        Args:
            issue_type: Type of issue (e.g., 'voice_puck_not_responding')

        Returns:
            Dictionary with symptoms, causes, and solutions
        """
        guides = {
            "voice_puck_not_responding": {
                "type": "voice_puck_not_responding",
                "symptoms": [
                    "Voice puck LED not lighting up",
                    "No audio response after speaking",
                    "Cannot find device on network",
                ],
                "causes": [
                    "Power issue (cable, adapter)",
                    "WiFi connectivity problem",
                    "ESPHome firmware crash",
                    "mDNS resolution failure",
                ],
                "solutions": [
                    "Check power connection and LED indicators",
                    "Verify WiFi credentials in ESPHome config",
                    "Restart the voice puck (power cycle)",
                    "Check router DHCP leases for device IP",
                    "Try accessing ESPHome web interface: http://esphome-voice.local/",
                    "Reflash ESPHome firmware if device is unresponsive",
                ],
                "docs_link": "https://esphome.io/components/voice_assistant.html",
            },
            "stt_not_working": {
                "type": "stt_not_working",
                "symptoms": [
                    "Voice recognized but not converted to text",
                    "Empty transcription results",
                    "STT entity shows error state",
                ],
                "causes": [
                    "Whisper model not loaded",
                    "Insufficient memory for model",
                    "Microphone audio quality issues",
                    "Sample rate mismatch",
                ],
                "solutions": [
                    "Restart Home Assistant to reload Whisper",
                    "Use a smaller model (tiny instead of small)",
                    "Check system memory: free -h",
                    "Verify microphone is not muted",
                    "Test microphone with: arecord -d 5 test.wav",
                ],
                "docs_link": "https://www.home-assistant.io/integrations/whisper/",
            },
            "tts_not_working": {
                "type": "tts_not_working",
                "symptoms": [
                    "No audio output from speakers",
                    "TTS entity shows error",
                    "Voice response text but no speech",
                ],
                "causes": [
                    "Piper voice pack not installed",
                    "Audio output device misconfigured",
                    "Volume set to zero",
                    "Media player unavailable",
                ],
                "solutions": [
                    "Install Piper voice pack for your language",
                    "Check media player entity state",
                    "Verify volume level on target device",
                    "Test TTS directly: Developer Tools > Services > tts.speak",
                ],
                "docs_link": "https://www.home-assistant.io/integrations/piper/",
            },
            "pipeline_not_responding": {
                "type": "pipeline_not_responding",
                "symptoms": [
                    "Wake word detected but no processing",
                    "Timeout errors in logs",
                    "Pipeline stuck in processing state",
                ],
                "causes": [
                    "Conversation agent not configured",
                    "SmartHome webhook unreachable",
                    "LLM API rate limit or error",
                ],
                "solutions": [
                    "Check Assist pipeline configuration",
                    "Verify SmartHome server is running",
                    "Check LLM API key and quota",
                    "Review Home Assistant logs for errors",
                ],
                "docs_link": "https://www.home-assistant.io/voice_control/",
            },
        }

        if issue_type in guides:
            return guides[issue_type]

        # Return general troubleshooting for unknown issues
        return {
            "type": "general",
            "symptoms": ["Unspecified voice pipeline issue"],
            "causes": ["Multiple possible causes"],
            "solutions": [
                "Run full diagnostic: /api/voice-diagnostics",
                "Check Home Assistant logs: docker logs homeassistant",
                "Verify all services are running",
                "Check network connectivity between components",
                "Review SmartHome server logs",
            ],
            "docs_link": "https://www.home-assistant.io/voice_control/troubleshooting/",
        }

    def test_stt_quality(self) -> DiagnosticResult:
        """
        Test STT quality by checking configuration (WP-10.17).

        Note: Actual audio quality testing requires hardware.
        This checks configuration and availability.

        Returns:
            DiagnosticResult with STT status
        """
        start_time = datetime.now()
        details = {}

        try:
            all_states = self.ha_client.get_all_states()
            stt_entities = [s for s in all_states if s.get("entity_id", "").startswith("stt.")]

            details["stt_entities"] = [e.get("entity_id") for e in stt_entities]
            details["stt_count"] = len(stt_entities)

            if not stt_entities:
                duration = (datetime.now() - start_time).total_seconds() * 1000
                return DiagnosticResult(
                    name="STT Quality",
                    status=TestStatus.FAILED,
                    message="No STT entities found",
                    details=details,
                    fix_suggestions=self.get_troubleshooting_guide("stt_not_working")["solutions"],
                    duration_ms=duration,
                )

            # Check if any STT entities have error states
            error_entities = [
                e for e in stt_entities
                if e.get("state") in ["unavailable", "unknown", "error"]
            ]

            if error_entities:
                details["error_entities"] = [e.get("entity_id") for e in error_entities]
                duration = (datetime.now() - start_time).total_seconds() * 1000
                return DiagnosticResult(
                    name="STT Quality",
                    status=TestStatus.WARNING,
                    message=f"STT entity in error state: {error_entities[0].get('entity_id')}",
                    details=details,
                    fix_suggestions=["Restart Home Assistant", "Check STT integration logs"],
                    duration_ms=duration,
                )

            duration = (datetime.now() - start_time).total_seconds() * 1000
            return DiagnosticResult(
                name="STT Quality",
                status=TestStatus.PASSED,
                message=f"STT configured with {len(stt_entities)} engine(s)",
                details=details,
                duration_ms=duration,
            )

        except Exception as error:
            duration = (datetime.now() - start_time).total_seconds() * 1000
            return DiagnosticResult(
                name="STT Quality",
                status=TestStatus.FAILED,
                message=f"Error checking STT: {error}",
                details={"error": str(error)},
                fix_suggestions=["Verify Home Assistant connection"],
                duration_ms=duration,
            )

    def test_tts_quality(self) -> DiagnosticResult:
        """
        Test TTS quality by checking configuration (WP-10.17).

        Note: Actual audio quality testing requires hardware.
        This checks configuration and availability.

        Returns:
            DiagnosticResult with TTS status
        """
        start_time = datetime.now()
        details = {}

        try:
            all_states = self.ha_client.get_all_states()
            tts_entities = [s for s in all_states if s.get("entity_id", "").startswith("tts.")]

            details["tts_entities"] = [e.get("entity_id") for e in tts_entities]
            details["tts_count"] = len(tts_entities)

            if not tts_entities:
                duration = (datetime.now() - start_time).total_seconds() * 1000
                return DiagnosticResult(
                    name="TTS Quality",
                    status=TestStatus.FAILED,
                    message="No TTS entities found",
                    details=details,
                    fix_suggestions=self.get_troubleshooting_guide("tts_not_working")["solutions"],
                    duration_ms=duration,
                )

            # Check if any TTS entities have error states
            error_entities = [
                e for e in tts_entities
                if e.get("state") in ["unavailable", "unknown", "error"]
            ]

            if error_entities:
                details["error_entities"] = [e.get("entity_id") for e in error_entities]
                duration = (datetime.now() - start_time).total_seconds() * 1000
                return DiagnosticResult(
                    name="TTS Quality",
                    status=TestStatus.WARNING,
                    message=f"TTS entity in error state: {error_entities[0].get('entity_id')}",
                    details=details,
                    fix_suggestions=["Restart Home Assistant", "Check TTS integration logs"],
                    duration_ms=duration,
                )

            duration = (datetime.now() - start_time).total_seconds() * 1000
            return DiagnosticResult(
                name="TTS Quality",
                status=TestStatus.PASSED,
                message=f"TTS configured with {len(tts_entities)} engine(s)",
                details=details,
                duration_ms=duration,
            )

        except Exception as error:
            duration = (datetime.now() - start_time).total_seconds() * 1000
            return DiagnosticResult(
                name="TTS Quality",
                status=TestStatus.FAILED,
                message=f"Error checking TTS: {error}",
                details={"error": str(error)},
                fix_suggestions=["Verify Home Assistant connection"],
                duration_ms=duration,
            )

    def to_dict(self, summary: DiagnosticSummary) -> dict[str, Any]:
        """
        Convert DiagnosticSummary to a JSON-serializable dictionary.

        Args:
            summary: DiagnosticSummary to convert

        Returns:
            Dictionary representation
        """
        return {
            "overall_status": summary.overall_status.value,
            "timestamp": summary.timestamp,
            "total_duration_ms": round(summary.total_duration_ms, 2),
            "summary": {
                "passed": summary.passed_count,
                "failed": summary.failed_count,
                "warnings": summary.warning_count,
                "total": len(summary.results),
            },
            "results": [
                {
                    "name": r.name,
                    "status": r.status.value,
                    "message": r.message,
                    "details": r.details,
                    "fix_suggestions": r.fix_suggestions,
                    "duration_ms": round(r.duration_ms, 2),
                }
                for r in summary.results
            ],
        }


# Singleton instance for convenience
_diagnostics: VoicePipelineDiagnostics | None = None


def get_diagnostics() -> VoicePipelineDiagnostics:
    """Get or create the diagnostics singleton."""
    global _diagnostics
    if _diagnostics is None:
        _diagnostics = VoicePipelineDiagnostics()
    return _diagnostics
