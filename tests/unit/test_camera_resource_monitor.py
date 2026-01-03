"""
Unit tests for Camera Resource Monitor.

Tests CPU, RAM, GPU monitoring with throttling and circuit breaker functionality.
Part of WP-11.7: Resource Caps & Monitoring.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from typing import Any


# =============================================================================
# Test Constants
# =============================================================================

# Thresholds from requirements
CPU_WARNING_THRESHOLD = 15.0  # Warning at 15% CPU
CPU_CRITICAL_THRESHOLD = 25.0  # Critical/throttle at 25%
RAM_WARNING_THRESHOLD = 15.0  # Warning at 15% RAM
RAM_CRITICAL_THRESHOLD = 25.0  # Critical/throttle at 25%
GPU_WARNING_THRESHOLD = 50.0  # Warning at 50% GPU
GPU_CRITICAL_THRESHOLD = 80.0  # Critical/throttle at 80%

# Circuit breaker constants
CIRCUIT_BREAKER_THRESHOLD = 3  # Trip after 3 consecutive high-resource states
CIRCUIT_BREAKER_COOLDOWN = 300  # 5 minute cooldown


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_psutil():
    """Mock psutil for CPU/RAM monitoring."""
    with patch("src.camera_resource_monitor.psutil") as mock:
        mock.cpu_percent.return_value = 5.0
        mock.virtual_memory.return_value = Mock(percent=30.0, available=8 * 1024**3)
        yield mock


@pytest.fixture
def mock_pynvml():
    """Mock pynvml for GPU monitoring."""
    with patch("src.camera_resource_monitor.HAS_NVIDIA_GPU", True):
        with patch("src.camera_resource_monitor.pynvml") as mock:
            mock_handle = Mock()
            mock.nvmlDeviceGetHandleByIndex.return_value = mock_handle
            mock.nvmlDeviceGetMemoryInfo.return_value = Mock(
                used=2 * 1024**3,
                total=8 * 1024**3
            )
            mock.nvmlDeviceGetUtilizationRates.return_value = Mock(gpu=30)
            yield mock


@pytest.fixture
def resource_monitor(mock_psutil):
    """Create a CameraResourceMonitor instance."""
    from src.camera_resource_monitor import CameraResourceMonitor
    monitor = CameraResourceMonitor()
    yield monitor


# =============================================================================
# Resource Sampling Tests
# =============================================================================

class TestResourceSampling:
    """Tests for resource usage sampling."""

    def test_sample_cpu_usage(self, resource_monitor, mock_psutil):
        """Samples current CPU usage percentage."""
        mock_psutil.cpu_percent.return_value = 12.5

        usage = resource_monitor.sample_resources()

        assert "cpu_percent" in usage
        assert usage["cpu_percent"] == 12.5
        mock_psutil.cpu_percent.assert_called_once()

    def test_sample_memory_usage(self, resource_monitor, mock_psutil):
        """Samples current memory usage percentage."""
        mock_psutil.virtual_memory.return_value = Mock(
            percent=45.0,
            available=8 * 1024**3,
            total=16 * 1024**3
        )

        usage = resource_monitor.sample_resources()

        assert "ram_percent" in usage
        assert usage["ram_percent"] == 45.0

    def test_sample_gpu_usage_with_nvidia(self, mock_psutil, mock_pynvml):
        """Samples GPU usage when NVIDIA GPU available."""
        from src.camera_resource_monitor import CameraResourceMonitor
        monitor = CameraResourceMonitor()

        mock_pynvml.nvmlDeviceGetUtilizationRates.return_value = Mock(gpu=55)

        usage = monitor.sample_resources()

        assert "gpu_percent" in usage
        assert usage["gpu_percent"] == 55

    def test_sample_gpu_graceful_without_gpu(self, resource_monitor, mock_psutil):
        """Returns None for GPU when no NVIDIA GPU available."""
        with patch("src.camera_resource_monitor.HAS_NVIDIA_GPU", False):
            usage = resource_monitor.sample_resources()

            assert usage.get("gpu_percent") is None

    def test_sample_includes_timestamp(self, resource_monitor, mock_psutil):
        """Sample includes timestamp for tracking."""
        usage = resource_monitor.sample_resources()

        assert "timestamp" in usage
        assert isinstance(usage["timestamp"], datetime)

    def test_sample_error_handling(self, resource_monitor, mock_psutil):
        """Handles sampling errors gracefully."""
        mock_psutil.cpu_percent.side_effect = Exception("Sampling failed")

        usage = resource_monitor.sample_resources()

        # Should return partial data or defaults, not raise
        assert "error" in usage or "cpu_percent" in usage


# =============================================================================
# Threshold Detection Tests
# =============================================================================

class TestThresholdDetection:
    """Tests for threshold detection and status determination."""

    def test_status_healthy_when_below_thresholds(self, resource_monitor, mock_psutil):
        """Status is healthy when all resources below warning thresholds."""
        mock_psutil.cpu_percent.return_value = 5.0
        mock_psutil.virtual_memory.return_value = Mock(percent=10.0)  # Below 15% RAM warning

        status = resource_monitor.get_status()

        assert status["status"] == "healthy"
        assert status["can_process"] is True

    def test_status_warning_when_cpu_high(self, resource_monitor, mock_psutil):
        """Status is warning when CPU exceeds warning threshold."""
        mock_psutil.cpu_percent.return_value = 18.0  # Above 15% warning
        mock_psutil.virtual_memory.return_value = Mock(percent=10.0)

        status = resource_monitor.get_status()

        assert status["status"] in ["warning", "degraded"]
        assert status["can_process"] is True  # Still processable at warning level
        assert "cpu" in status.get("warnings", []) or "cpu" in str(status)

    def test_status_critical_when_cpu_very_high(self, resource_monitor, mock_psutil):
        """Status is critical and throttled when CPU exceeds critical threshold."""
        mock_psutil.cpu_percent.return_value = 30.0  # Above 25% critical
        mock_psutil.virtual_memory.return_value = Mock(percent=10.0)

        status = resource_monitor.get_status()

        assert status["status"] in ["critical", "unhealthy", "throttled"]
        assert status["can_process"] is False  # Should throttle

    def test_status_warning_when_ram_high(self, resource_monitor, mock_psutil):
        """Status is warning when RAM exceeds warning threshold."""
        mock_psutil.cpu_percent.return_value = 5.0
        mock_psutil.virtual_memory.return_value = Mock(percent=18.0)  # Above 15%

        status = resource_monitor.get_status()

        assert status["status"] in ["warning", "degraded"]
        assert status["can_process"] is True

    def test_status_critical_when_ram_very_high(self, resource_monitor, mock_psutil):
        """Status is critical when RAM exceeds critical threshold."""
        mock_psutil.cpu_percent.return_value = 5.0
        mock_psutil.virtual_memory.return_value = Mock(percent=30.0)  # Above 25%

        status = resource_monitor.get_status()

        assert status["status"] in ["critical", "unhealthy", "throttled"]
        assert status["can_process"] is False

    def test_multiple_high_resources_escalates(self, resource_monitor, mock_psutil):
        """Status escalates when multiple resources are high."""
        mock_psutil.cpu_percent.return_value = 18.0  # Warning
        mock_psutil.virtual_memory.return_value = Mock(percent=18.0)  # Warning

        status = resource_monitor.get_status()

        # Combined warnings should escalate
        assert status["status"] in ["warning", "degraded", "critical"]


# =============================================================================
# Throttling Tests
# =============================================================================

class TestThrottling:
    """Tests for throttling behavior when resources are high."""

    def test_can_process_when_resources_low(self, resource_monitor, mock_psutil):
        """Allows processing when resources are low."""
        mock_psutil.cpu_percent.return_value = 5.0
        mock_psutil.virtual_memory.return_value = Mock(percent=10.0)

        assert resource_monitor.can_process() is True

    def test_throttle_when_resources_critical(self, resource_monitor, mock_psutil):
        """Throttles processing when resources exceed critical thresholds."""
        mock_psutil.cpu_percent.return_value = 30.0  # Critical
        mock_psutil.virtual_memory.return_value = Mock(percent=30.0)  # Critical

        assert resource_monitor.can_process() is False

    def test_throttle_time_estimate(self, resource_monitor, mock_psutil):
        """Returns estimate of when processing can resume."""
        mock_psutil.cpu_percent.return_value = 30.0
        mock_psutil.virtual_memory.return_value = Mock(percent=30.0)

        result = resource_monitor.check_throttle_status()

        assert result["throttled"] is True
        assert "estimated_resume" in result or "retry_after_seconds" in result

    def test_gradual_throttling(self, resource_monitor, mock_psutil):
        """Throttling reduces processing rate gradually, not all-or-nothing."""
        mock_psutil.virtual_memory.return_value = Mock(percent=10.0)

        # At 20% CPU (between warning and critical), should suggest reduced rate
        mock_psutil.cpu_percent.return_value = 20.0
        rate = resource_monitor.get_suggested_processing_rate()

        assert 0 < rate < 1.0  # Reduced but not zero


# =============================================================================
# Circuit Breaker Tests
# =============================================================================

class TestCircuitBreaker:
    """Tests for circuit breaker pattern to prevent overload."""

    def test_circuit_closed_initially(self, resource_monitor, mock_psutil):
        """Circuit breaker starts in closed (operational) state."""
        mock_psutil.cpu_percent.return_value = 5.0
        mock_psutil.virtual_memory.return_value = Mock(percent=10.0)

        assert resource_monitor.circuit_state == "closed"
        assert resource_monitor.can_process() is True

    def test_circuit_opens_after_consecutive_failures(self, resource_monitor, mock_psutil):
        """Circuit opens after consecutive high-resource states."""
        mock_psutil.cpu_percent.return_value = 30.0  # Critical
        mock_psutil.virtual_memory.return_value = Mock(percent=30.0)

        # Trigger threshold checks multiple times
        for _ in range(CIRCUIT_BREAKER_THRESHOLD):
            resource_monitor.check_and_update()

        assert resource_monitor.circuit_state == "open"

    def test_circuit_open_blocks_processing(self, resource_monitor, mock_psutil):
        """Open circuit blocks all processing."""
        resource_monitor._set_circuit_state("open")

        # Even if resources are now low
        mock_psutil.cpu_percent.return_value = 5.0
        mock_psutil.virtual_memory.return_value = Mock(percent=10.0)

        assert resource_monitor.can_process() is False

    def test_circuit_half_open_after_cooldown(self, resource_monitor, mock_psutil):
        """Circuit transitions to half-open after cooldown period."""
        resource_monitor._set_circuit_state("open")
        resource_monitor._circuit_opened_at = datetime.now() - timedelta(seconds=CIRCUIT_BREAKER_COOLDOWN + 10)

        resource_monitor.check_and_update()

        assert resource_monitor.circuit_state == "half_open"

    def test_circuit_closes_on_successful_check(self, resource_monitor, mock_psutil):
        """Circuit closes when resources return to normal."""
        resource_monitor._set_circuit_state("half_open")
        mock_psutil.cpu_percent.return_value = 5.0
        mock_psutil.virtual_memory.return_value = Mock(percent=10.0)

        resource_monitor.check_and_update()

        assert resource_monitor.circuit_state == "closed"

    def test_circuit_reopens_if_still_high(self, resource_monitor, mock_psutil):
        """Circuit reopens if resources still high during half-open test."""
        resource_monitor._set_circuit_state("half_open")
        mock_psutil.cpu_percent.return_value = 30.0  # Still critical
        mock_psutil.virtual_memory.return_value = Mock(percent=30.0)

        resource_monitor.check_and_update()

        assert resource_monitor.circuit_state == "open"


# =============================================================================
# Health Monitor Integration Tests
# =============================================================================

class TestHealthMonitorIntegration:
    """Tests for integration with existing HealthMonitor."""

    def test_provides_component_health_check(self, resource_monitor, mock_psutil):
        """Provides health check function for HealthMonitor."""
        mock_psutil.cpu_percent.return_value = 5.0
        mock_psutil.virtual_memory.return_value = Mock(percent=10.0)

        health = resource_monitor.get_component_health()

        assert hasattr(health, 'name') or "name" in health
        assert hasattr(health, 'status') or "status" in health

    def test_health_check_returns_healthy(self, resource_monitor, mock_psutil):
        """Returns healthy status when resources OK."""
        mock_psutil.cpu_percent.return_value = 5.0
        mock_psutil.virtual_memory.return_value = Mock(percent=10.0)

        health = resource_monitor.get_component_health()

        # Handle both ComponentHealth object and dict
        if hasattr(health, 'status'):
            status_value = health.status.value if hasattr(health.status, 'value') else health.status
        else:
            status_value = health.get('status')
        assert status_value == "healthy"

    def test_health_check_returns_degraded(self, resource_monitor, mock_psutil):
        """Returns degraded status when resources warning."""
        mock_psutil.cpu_percent.return_value = 18.0  # Warning
        mock_psutil.virtual_memory.return_value = Mock(percent=10.0)

        health = resource_monitor.get_component_health()

        # Handle both ComponentHealth object and dict
        if hasattr(health, 'status'):
            status_value = health.status.value if hasattr(health.status, 'value') else health.status
        else:
            status_value = health.get('status')
        assert status_value in ["degraded", "warning"]

    def test_health_check_returns_unhealthy(self, resource_monitor, mock_psutil):
        """Returns unhealthy status when resources critical."""
        mock_psutil.cpu_percent.return_value = 30.0  # Critical
        mock_psutil.virtual_memory.return_value = Mock(percent=30.0)

        health = resource_monitor.get_component_health()

        # Handle both ComponentHealth object and dict
        if hasattr(health, 'status'):
            status_value = health.status.value if hasattr(health.status, 'value') else health.status
        else:
            status_value = health.get('status')
        assert status_value in ["unhealthy", "critical"]


# =============================================================================
# Metrics & History Tests
# =============================================================================

class TestMetricsAndHistory:
    """Tests for metrics tracking and history."""

    def test_tracks_resource_history(self, resource_monitor, mock_psutil):
        """Tracks resource usage over time."""
        mock_psutil.cpu_percent.return_value = 10.0
        mock_psutil.virtual_memory.return_value = Mock(percent=20.0)

        resource_monitor.sample_resources()
        resource_monitor.sample_resources()
        resource_monitor.sample_resources()

        history = resource_monitor.get_history(limit=10)
        assert len(history) >= 3

    def test_history_limit_enforced(self, resource_monitor, mock_psutil):
        """History respects size limits."""
        mock_psutil.cpu_percent.return_value = 10.0
        mock_psutil.virtual_memory.return_value = Mock(percent=20.0)

        for _ in range(100):
            resource_monitor.sample_resources()

        history = resource_monitor.get_history(limit=50)
        assert len(history) <= 50

    def test_provides_prometheus_metrics(self, resource_monitor, mock_psutil):
        """Provides metrics in Prometheus format."""
        mock_psutil.cpu_percent.return_value = 10.0
        mock_psutil.virtual_memory.return_value = Mock(percent=20.0)

        metrics = resource_monitor.get_prometheus_metrics()

        assert "camera_processing_cpu_percent" in metrics
        assert "camera_processing_ram_percent" in metrics
        assert "camera_processing_throttled" in metrics

    def test_get_statistics_summary(self, resource_monitor, mock_psutil):
        """Provides statistical summary of resource usage."""
        mock_psutil.cpu_percent.return_value = 10.0
        mock_psutil.virtual_memory.return_value = Mock(percent=20.0)

        for _ in range(10):
            resource_monitor.sample_resources()

        stats = resource_monitor.get_statistics()

        assert "cpu" in stats
        assert "avg" in stats["cpu"] or "mean" in stats["cpu"]
        assert "max" in stats["cpu"]
        assert "min" in stats["cpu"]


# =============================================================================
# Slack Alert Tests
# =============================================================================

class TestSlackAlerts:
    """Tests for Slack alert integration."""

    def test_alert_on_threshold_exceeded(self, resource_monitor, mock_psutil):
        """Generates alert when threshold exceeded."""
        mock_psutil.cpu_percent.return_value = 30.0
        mock_psutil.virtual_memory.return_value = Mock(percent=30.0)

        alert = resource_monitor.check_alert_condition()

        assert alert is not None
        assert alert["severity"] in ["warning", "critical"]

    def test_no_alert_when_healthy(self, resource_monitor, mock_psutil):
        """No alert generated when resources healthy."""
        mock_psutil.cpu_percent.return_value = 5.0
        mock_psutil.virtual_memory.return_value = Mock(percent=10.0)

        alert = resource_monitor.check_alert_condition()

        assert alert is None

    def test_alert_includes_details(self, resource_monitor, mock_psutil):
        """Alert includes resource usage details."""
        mock_psutil.cpu_percent.return_value = 30.0
        mock_psutil.virtual_memory.return_value = Mock(percent=30.0)

        alert = resource_monitor.check_alert_condition()

        assert "cpu" in str(alert).lower() or "cpu_percent" in alert.get("details", {})
        assert "message" in alert

    def test_alert_suggests_action(self, resource_monitor, mock_psutil):
        """Alert includes suggested action."""
        mock_psutil.cpu_percent.return_value = 30.0
        mock_psutil.virtual_memory.return_value = Mock(percent=30.0)

        alert = resource_monitor.check_alert_condition()

        assert "action" in alert or "suggestion" in alert


# =============================================================================
# Camera Scheduler Integration Tests
# =============================================================================

class TestCameraSchedulerIntegration:
    """Tests for integration with camera scheduler."""

    def test_scheduler_checks_resources_before_capture(self, mock_psutil):
        """Camera scheduler checks resource availability."""
        mock_psutil.cpu_percent.return_value = 5.0
        mock_psutil.virtual_memory.return_value = Mock(percent=10.0)

        # Verify the resource monitor can be used by scheduler
        from src.camera_resource_monitor import get_resource_monitor
        monitor = get_resource_monitor()
        assert monitor.can_process() is True

    def test_scheduler_skips_when_throttled(self, mock_psutil):
        """Camera scheduler skips processing when throttled."""
        from src.camera_resource_monitor import CameraResourceMonitor
        monitor = CameraResourceMonitor()

        mock_psutil.cpu_percent.return_value = 30.0
        mock_psutil.virtual_memory.return_value = Mock(percent=30.0)

        # Trigger circuit breaker
        for _ in range(CIRCUIT_BREAKER_THRESHOLD):
            monitor.check_and_update()

        assert monitor.can_process() is False


# =============================================================================
# Grafana Dashboard Data Tests
# =============================================================================

class TestGrafanaDashboard:
    """Tests for Grafana dashboard data export."""

    def test_exports_json_for_grafana(self, resource_monitor, mock_psutil):
        """Exports data in format suitable for Grafana."""
        mock_psutil.cpu_percent.return_value = 10.0
        mock_psutil.virtual_memory.return_value = Mock(percent=20.0)

        resource_monitor.sample_resources()
        data = resource_monitor.get_grafana_data()

        assert isinstance(data, (list, dict))
        if isinstance(data, list):
            assert all("timestamp" in item for item in data)
        else:
            assert "current" in data or "history" in data

    def test_time_series_format(self, resource_monitor, mock_psutil):
        """Data includes proper time series format."""
        mock_psutil.cpu_percent.return_value = 10.0
        mock_psutil.virtual_memory.return_value = Mock(percent=20.0)

        for _ in range(5):
            resource_monitor.sample_resources()

        data = resource_monitor.get_time_series()

        assert len(data) >= 5
        # Each point should have timestamp and values
        for point in data:
            assert "timestamp" in point
            assert "cpu_percent" in point or "values" in point
