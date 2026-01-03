"""
Smart Home Assistant - Camera Resource Monitor

Monitors CPU, RAM, and GPU usage for camera processing operations.
Implements throttling and circuit breaker patterns to prevent server overload.

WP-11.7: Resource Caps & Monitoring
- Monitor CPU, RAM, GPU usage
- Alert if usage > 15% for 5+ minutes
- Throttle snapshot processing if limits approached
- Circuit breaker for overload protection
"""

import json
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

import psutil

# Try to import NVIDIA monitoring
try:
    import pynvml
    pynvml.nvmlInit()
    HAS_NVIDIA_GPU = True
except (ImportError, Exception):
    pynvml = None
    HAS_NVIDIA_GPU = False


logger = logging.getLogger("camera_resource_monitor")

# Data directory
DATA_DIR = Path(__file__).parent.parent / "data"


# =============================================================================
# Configuration
# =============================================================================

# Thresholds (camera processing should stay under 15% for normal operation)
CPU_WARNING_THRESHOLD = 15.0
CPU_CRITICAL_THRESHOLD = 25.0
RAM_WARNING_THRESHOLD = 15.0
RAM_CRITICAL_THRESHOLD = 25.0
GPU_WARNING_THRESHOLD = 50.0
GPU_CRITICAL_THRESHOLD = 80.0

# Circuit breaker
CIRCUIT_BREAKER_THRESHOLD = 3  # Trip after 3 consecutive critical states
CIRCUIT_BREAKER_COOLDOWN = 300  # 5 minute cooldown

# History
MAX_HISTORY_SIZE = 1000


# =============================================================================
# Data Classes
# =============================================================================

class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Blocked, waiting for cooldown
    HALF_OPEN = "half_open"  # Testing if resources recovered


class ResourceStatus(Enum):
    """Resource status levels."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class ResourceSample:
    """A single resource usage sample."""
    timestamp: datetime
    cpu_percent: float
    ram_percent: float
    gpu_percent: float | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "cpu_percent": self.cpu_percent,
            "ram_percent": self.ram_percent,
            "gpu_percent": self.gpu_percent,
            "error": self.error,
        }


# =============================================================================
# Camera Resource Monitor
# =============================================================================

class CameraResourceMonitor:
    """
    Monitors system resources and implements throttling/circuit breaker
    for camera processing operations.
    """

    def __init__(
        self,
        cpu_warning: float = CPU_WARNING_THRESHOLD,
        cpu_critical: float = CPU_CRITICAL_THRESHOLD,
        ram_warning: float = RAM_WARNING_THRESHOLD,
        ram_critical: float = RAM_CRITICAL_THRESHOLD,
        gpu_warning: float = GPU_WARNING_THRESHOLD,
        gpu_critical: float = GPU_CRITICAL_THRESHOLD,
    ):
        """Initialize the resource monitor."""
        self.cpu_warning = cpu_warning
        self.cpu_critical = cpu_critical
        self.ram_warning = ram_warning
        self.ram_critical = ram_critical
        self.gpu_warning = gpu_warning
        self.gpu_critical = gpu_critical

        # State
        self._lock = threading.Lock()
        self._history: deque[ResourceSample] = deque(maxlen=MAX_HISTORY_SIZE)
        self._circuit_state = CircuitState.CLOSED
        self._circuit_opened_at: datetime | None = None
        self._consecutive_critical = 0

        # GPU handle
        self._gpu_handle = None
        if HAS_NVIDIA_GPU:
            try:
                self._gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            except Exception as e:
                logger.warning(f"Failed to get GPU handle: {e}")

    @property
    def circuit_state(self) -> str:
        """Get current circuit state as string."""
        return self._circuit_state.value

    def _set_circuit_state(self, state: str) -> None:
        """Set circuit state (for testing)."""
        with self._lock:
            self._circuit_state = CircuitState(state)
            if state == "open":
                self._circuit_opened_at = datetime.now()

    # =========================================================================
    # Resource Sampling
    # =========================================================================

    def sample_resources(self) -> dict[str, Any]:
        """
        Sample current resource usage.

        Returns:
            Dictionary with cpu_percent, ram_percent, gpu_percent, timestamp
        """
        timestamp = datetime.now()
        cpu_percent = 0.0
        ram_percent = 0.0
        gpu_percent = None
        error = None

        try:
            # CPU - sample over 0.1 second interval for accuracy
            cpu_percent = psutil.cpu_percent(interval=0.1)
        except Exception as e:
            error = f"CPU sampling failed: {e}"
            logger.warning(error)

        try:
            # RAM
            mem = psutil.virtual_memory()
            ram_percent = mem.percent
        except Exception as e:
            if error:
                error += f"; RAM: {e}"
            else:
                error = f"RAM sampling failed: {e}"
            logger.warning(f"RAM sampling failed: {e}")

        # GPU (optional)
        if HAS_NVIDIA_GPU and self._gpu_handle:
            try:
                utilization = pynvml.nvmlDeviceGetUtilizationRates(self._gpu_handle)
                gpu_percent = utilization.gpu
            except Exception as e:
                logger.debug(f"GPU sampling failed: {e}")

        sample = ResourceSample(
            timestamp=timestamp,
            cpu_percent=cpu_percent,
            ram_percent=ram_percent,
            gpu_percent=gpu_percent,
            error=error,
        )

        with self._lock:
            self._history.append(sample)

        result = sample.to_dict()
        result["timestamp"] = timestamp  # Keep as datetime for callers
        return result

    def _get_resource_status(self, cpu: float, ram: float, gpu: float | None) -> ResourceStatus:
        """Determine overall resource status."""
        # Check critical thresholds
        if cpu >= self.cpu_critical or ram >= self.ram_critical:
            return ResourceStatus.CRITICAL
        if gpu is not None and gpu >= self.gpu_critical:
            return ResourceStatus.CRITICAL

        # Check warning thresholds
        if cpu >= self.cpu_warning or ram >= self.ram_warning:
            return ResourceStatus.WARNING
        if gpu is not None and gpu >= self.gpu_warning:
            return ResourceStatus.WARNING

        return ResourceStatus.HEALTHY

    # =========================================================================
    # Status & Throttling
    # =========================================================================

    def get_status(self) -> dict[str, Any]:
        """
        Get current resource status with throttling decision.

        Returns:
            Dictionary with status, can_process, and resource details
        """
        sample = self.sample_resources()
        cpu = sample["cpu_percent"]
        ram = sample["ram_percent"]
        gpu = sample.get("gpu_percent")

        status = self._get_resource_status(cpu, ram, gpu)

        # Build warnings list
        warnings = []
        if cpu >= self.cpu_warning:
            warnings.append(f"cpu: {cpu:.1f}% >= {self.cpu_warning}%")
        if ram >= self.ram_warning:
            warnings.append(f"ram: {ram:.1f}% >= {self.ram_warning}%")
        if gpu is not None and gpu >= self.gpu_warning:
            warnings.append(f"gpu: {gpu:.1f}% >= {self.gpu_warning}%")

        # Determine if processing is allowed
        can_process = (
            self._circuit_state != CircuitState.OPEN and
            status != ResourceStatus.CRITICAL
        )

        return {
            "status": status.value,
            "can_process": can_process,
            "cpu_percent": cpu,
            "ram_percent": ram,
            "gpu_percent": gpu,
            "warnings": warnings,
            "circuit_state": self._circuit_state.value,
            "timestamp": sample["timestamp"],
        }

    def can_process(self) -> bool:
        """
        Check if camera processing is allowed.

        Returns:
            True if processing is allowed, False if throttled
        """
        # Check circuit breaker first
        if self._circuit_state == CircuitState.OPEN:
            return False

        # Sample current resources
        sample = self.sample_resources()
        status = self._get_resource_status(
            sample["cpu_percent"],
            sample["ram_percent"],
            sample.get("gpu_percent")
        )

        return status != ResourceStatus.CRITICAL

    def check_throttle_status(self) -> dict[str, Any]:
        """
        Check throttling status with time estimate.

        Returns:
            Dictionary with throttled status and estimated resume time
        """
        status = self.get_status()
        throttled = not status["can_process"]

        result = {
            "throttled": throttled,
            "reason": None,
            "estimated_resume": None,
            "retry_after_seconds": None,
        }

        if throttled:
            if self._circuit_state == CircuitState.OPEN:
                result["reason"] = "circuit_breaker_open"
                if self._circuit_opened_at:
                    resume_at = self._circuit_opened_at + timedelta(seconds=CIRCUIT_BREAKER_COOLDOWN)
                    result["estimated_resume"] = resume_at.isoformat()
                    result["retry_after_seconds"] = max(0, (resume_at - datetime.now()).total_seconds())
            else:
                result["reason"] = "resources_critical"
                result["retry_after_seconds"] = 60  # Check again in 1 minute

        return result

    def get_suggested_processing_rate(self) -> float:
        """
        Get suggested processing rate based on resource availability.

        Returns:
            Rate from 0.0 (stop) to 1.0 (full speed)
        """
        sample = self.sample_resources()
        cpu = sample["cpu_percent"]
        ram = sample["ram_percent"]

        if self._circuit_state == CircuitState.OPEN:
            return 0.0

        # Critical = stop
        if cpu >= self.cpu_critical or ram >= self.ram_critical:
            return 0.0

        # Calculate rate based on headroom
        # At warning threshold: 0.5 rate
        # Below warning: 1.0 rate
        # Between warning and critical: linear interpolation

        cpu_rate = 1.0
        if cpu >= self.cpu_warning:
            cpu_rate = max(0.0, 1.0 - (cpu - self.cpu_warning) / (self.cpu_critical - self.cpu_warning))

        ram_rate = 1.0
        if ram >= self.ram_warning:
            ram_rate = max(0.0, 1.0 - (ram - self.ram_warning) / (self.ram_critical - self.ram_warning))

        # Use minimum of CPU and RAM rates
        return min(cpu_rate, ram_rate)

    # =========================================================================
    # Circuit Breaker
    # =========================================================================

    def check_and_update(self) -> dict[str, Any]:
        """
        Check resources and update circuit breaker state.

        Returns:
            Current status after update
        """
        sample = self.sample_resources()
        status = self._get_resource_status(
            sample["cpu_percent"],
            sample["ram_percent"],
            sample.get("gpu_percent")
        )

        with self._lock:
            if status == ResourceStatus.CRITICAL:
                self._consecutive_critical += 1
            else:
                self._consecutive_critical = 0

            # Handle circuit state transitions
            if self._circuit_state == CircuitState.CLOSED:
                if self._consecutive_critical >= CIRCUIT_BREAKER_THRESHOLD:
                    self._circuit_state = CircuitState.OPEN
                    self._circuit_opened_at = datetime.now()
                    logger.warning(
                        f"Circuit breaker OPEN: {self._consecutive_critical} consecutive critical states"
                    )

            elif self._circuit_state == CircuitState.OPEN:
                if self._circuit_opened_at:
                    elapsed = (datetime.now() - self._circuit_opened_at).total_seconds()
                    if elapsed >= CIRCUIT_BREAKER_COOLDOWN:
                        self._circuit_state = CircuitState.HALF_OPEN
                        logger.info("Circuit breaker HALF_OPEN: testing recovery")

            elif self._circuit_state == CircuitState.HALF_OPEN:
                if status == ResourceStatus.CRITICAL:
                    self._circuit_state = CircuitState.OPEN
                    self._circuit_opened_at = datetime.now()
                    logger.warning("Circuit breaker OPEN: still critical during half-open test")
                else:
                    self._circuit_state = CircuitState.CLOSED
                    self._consecutive_critical = 0
                    logger.info("Circuit breaker CLOSED: resources recovered")

        return self.get_status()

    # =========================================================================
    # Health Monitor Integration
    # =========================================================================

    def get_component_health(self):
        """
        Get health check result for HealthMonitor integration.

        Returns:
            ComponentHealth object or dict with health status
        """
        try:
            from src.health_monitor import ComponentHealth, HealthStatus
        except ImportError:
            # Return dict if ComponentHealth not available
            status = self.get_status()
            return {
                "name": "camera_processing",
                "status": status["status"],
                "message": self._get_health_message(status),
                "details": status,
            }

        status = self.get_status()

        if status["status"] == "critical":
            health_status = HealthStatus.UNHEALTHY
        elif status["status"] == "warning":
            health_status = HealthStatus.DEGRADED
        else:
            health_status = HealthStatus.HEALTHY

        return ComponentHealth(
            name="camera_processing",
            status=health_status,
            message=self._get_health_message(status),
            last_check=datetime.now(),
            details={
                "cpu_percent": status["cpu_percent"],
                "ram_percent": status["ram_percent"],
                "gpu_percent": status["gpu_percent"],
                "circuit_state": status["circuit_state"],
                "can_process": status["can_process"],
            },
        )

    def _get_health_message(self, status: dict) -> str:
        """Generate health message from status."""
        if status["status"] == "critical":
            return f"Camera processing throttled: CPU={status['cpu_percent']:.1f}%, RAM={status['ram_percent']:.1f}%"
        elif status["status"] == "warning":
            return f"Camera processing warning: {', '.join(status['warnings'])}"
        else:
            return f"Camera processing healthy: CPU={status['cpu_percent']:.1f}%, RAM={status['ram_percent']:.1f}%"

    # =========================================================================
    # Metrics & History
    # =========================================================================

    def get_history(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get resource usage history."""
        with self._lock:
            samples = list(self._history)[-limit:]
            return [s.to_dict() for s in samples]

    def get_statistics(self) -> dict[str, Any]:
        """Get statistical summary of resource usage."""
        with self._lock:
            if not self._history:
                return {
                    "cpu": {"avg": 0, "max": 0, "min": 0},
                    "ram": {"avg": 0, "max": 0, "min": 0},
                    "sample_count": 0,
                }

            cpu_values = [s.cpu_percent for s in self._history]
            ram_values = [s.ram_percent for s in self._history]

            return {
                "cpu": {
                    "avg": sum(cpu_values) / len(cpu_values),
                    "max": max(cpu_values),
                    "min": min(cpu_values),
                },
                "ram": {
                    "avg": sum(ram_values) / len(ram_values),
                    "max": max(ram_values),
                    "min": min(ram_values),
                },
                "sample_count": len(self._history),
            }

    def get_prometheus_metrics(self) -> str:
        """
        Get metrics in Prometheus exposition format.

        Returns:
            String in Prometheus text format
        """
        sample = self.sample_resources()
        status = self.get_status()

        lines = [
            "# HELP camera_processing_cpu_percent CPU usage for camera processing",
            "# TYPE camera_processing_cpu_percent gauge",
            f"camera_processing_cpu_percent {sample['cpu_percent']}",
            "",
            "# HELP camera_processing_ram_percent RAM usage for camera processing",
            "# TYPE camera_processing_ram_percent gauge",
            f"camera_processing_ram_percent {sample['ram_percent']}",
            "",
            "# HELP camera_processing_throttled Whether processing is throttled (1=yes, 0=no)",
            "# TYPE camera_processing_throttled gauge",
            f"camera_processing_throttled {0 if status['can_process'] else 1}",
            "",
            "# HELP camera_processing_circuit_state Circuit breaker state (0=closed, 1=open, 2=half_open)",
            "# TYPE camera_processing_circuit_state gauge",
            f"camera_processing_circuit_state {self._get_circuit_state_value(status['circuit_state'])}",
        ]

        if sample.get("gpu_percent") is not None:
            lines.extend([
                "",
                "# HELP camera_processing_gpu_percent GPU usage for camera processing",
                "# TYPE camera_processing_gpu_percent gauge",
                f"camera_processing_gpu_percent {sample['gpu_percent']}",
            ])

        return "\n".join(lines)

    def get_grafana_data(self) -> dict[str, Any]:
        """Get data formatted for Grafana JSON datasource."""
        current = self.sample_resources()
        stats = self.get_statistics()

        return {
            "current": {
                "cpu_percent": current["cpu_percent"],
                "ram_percent": current["ram_percent"],
                "gpu_percent": current.get("gpu_percent"),
                "timestamp": current["timestamp"].isoformat() if isinstance(current["timestamp"], datetime) else current["timestamp"],
            },
            "statistics": stats,
            "thresholds": {
                "cpu_warning": self.cpu_warning,
                "cpu_critical": self.cpu_critical,
                "ram_warning": self.ram_warning,
                "ram_critical": self.ram_critical,
            },
            "status": self.get_status()["status"],
        }

    def get_time_series(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get time series data for charting."""
        return self.get_history(limit)

    # =========================================================================
    # Alerting
    # =========================================================================

    def _get_circuit_state_value(self, state: str) -> int:
        """Convert circuit state to numeric value for Prometheus."""
        state_map = {"closed": 0, "open": 1, "half_open": 2}
        return state_map.get(state, 0)

    def check_alert_condition(self) -> dict[str, Any] | None:
        """
        Check if an alert should be sent.

        Returns:
            Alert dict if threshold exceeded, None otherwise
        """
        status = self.get_status()

        if status["status"] == "healthy":
            return None

        severity = "warning" if status["status"] == "warning" else "critical"

        return {
            "severity": severity,
            "message": self._get_health_message(status),
            "action": self._get_suggested_action(status),
            "details": {
                "cpu_percent": status["cpu_percent"],
                "ram_percent": status["ram_percent"],
                "gpu_percent": status["gpu_percent"],
                "circuit_state": status["circuit_state"],
            },
        }

    def _get_suggested_action(self, status: dict) -> str:
        """Get suggested action based on status."""
        if status["circuit_state"] == "open":
            return "Circuit breaker is open. Processing will resume automatically after cooldown."
        elif status["status"] == "critical":
            return "Reduce camera processing load or check for runaway processes."
        else:
            return "Monitor resource usage. Consider reducing processing rate if sustained."


# =============================================================================
# Module-Level Convenience Functions
# =============================================================================

_monitor: CameraResourceMonitor | None = None


def get_resource_monitor() -> CameraResourceMonitor:
    """Get or create the global resource monitor."""
    global _monitor
    if _monitor is None:
        _monitor = CameraResourceMonitor()
    return _monitor


def can_process_camera() -> bool:
    """Check if camera processing is allowed (convenience function)."""
    return get_resource_monitor().can_process()


def get_resource_status() -> dict[str, Any]:
    """Get current resource status (convenience function)."""
    return get_resource_monitor().get_status()


def check_resources_and_update() -> dict[str, Any]:
    """Check and update circuit breaker (convenience function)."""
    return get_resource_monitor().check_and_update()
