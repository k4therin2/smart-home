"""
Smart Home Assistant - Health Monitor

Centralized health monitoring system that aggregates health status from all
system components and triggers alerts/self-healing actions.
"""

import logging
import sqlite3
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import Any


logger = logging.getLogger("health_monitor")

# Data directory for databases
DATA_DIR = Path(__file__).parent.parent / "data"


class HealthStatus(Enum):
    """Health status levels for components."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"

    @property
    def severity(self) -> int:
        """Return severity level for comparison (higher = worse)."""
        severity_map = {
            HealthStatus.HEALTHY: 0,
            HealthStatus.DEGRADED: 1,
            HealthStatus.UNHEALTHY: 2,
        }
        return severity_map[self]


@dataclass
class ComponentHealth:
    """Health status for a single component."""

    name: str
    status: HealthStatus
    message: str
    last_check: datetime
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "last_check": self.last_check.isoformat(),
            "details": self.details,
        }


@dataclass
class ComponentChecker:
    """Configuration for a component health checker."""

    name: str
    check_fn: Callable[[], ComponentHealth]


class HealthMonitor:
    """
    Centralized health monitoring for all system components.

    Aggregates health status from:
    - Home Assistant connectivity
    - Cache performance
    - Database accessibility
    - Anthropic API usage/cost

    Features:
    - Periodic health checks
    - Status change alerting
    - Consecutive failure tracking
    - Health history for trending
    """

    # Thresholds
    CACHE_HIT_RATE_THRESHOLD = 0.5  # Below this = degraded
    CACHE_CAPACITY_THRESHOLD = 0.9  # Above this = degraded
    API_COST_WARNING_THRESHOLD = 4.0  # Daily cost USD
    API_COST_CRITICAL_THRESHOLD = 5.0  # Daily cost USD

    def __init__(
        self,
        check_interval: int = 60,
        max_history: int = 100,
        notifier: Any | None = None,
    ):
        """
        Initialize the health monitor.

        Args:
            check_interval: Seconds between automatic health checks
            max_history: Maximum health history entries per component
            notifier: SlackNotifier instance for alerts (optional)
        """
        self.check_interval = check_interval
        self.max_history = max_history
        self.notifier = notifier

        self._lock = Lock()
        self._health_history: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._consecutive_failures: dict[str, int] = defaultdict(int)
        self._last_status: dict[str, HealthStatus] = {}

        # Register default component checkers
        self._component_checkers: list[ComponentChecker] = [
            ComponentChecker("home_assistant", self.check_home_assistant),
            ComponentChecker("cache", self.check_cache),
            ComponentChecker("database", self.check_database),
            ComponentChecker("anthropic_api", self.check_anthropic_api),
        ]

    def check_home_assistant(self) -> ComponentHealth:
        """Check Home Assistant connectivity health."""
        try:
            from src.ha_client import HomeAssistantClient

            start_time = time.time()
            client = HomeAssistantClient()
            is_connected = client.check_connection()
            response_time_ms = int((time.time() - start_time) * 1000)

            if is_connected:
                return ComponentHealth(
                    name="home_assistant",
                    status=HealthStatus.HEALTHY,
                    message="Home Assistant connected and responding",
                    last_check=datetime.now(),
                    details={"response_time_ms": response_time_ms},
                )
            else:
                return ComponentHealth(
                    name="home_assistant",
                    status=HealthStatus.UNHEALTHY,
                    message="Home Assistant not responding or unavailable",
                    last_check=datetime.now(),
                    details={"response_time_ms": response_time_ms},
                )

        except Exception as error:
            logger.error(f"Error checking Home Assistant health: {error}")
            return ComponentHealth(
                name="home_assistant",
                status=HealthStatus.UNHEALTHY,
                message=f"Error checking Home Assistant: {error!s}",
                last_check=datetime.now(),
                details={"error": str(error)},
            )

    def check_cache(self) -> ComponentHealth:
        """Check cache health and performance."""
        try:
            from src.cache import get_cache

            cache = get_cache()
            stats = cache.get_stats()

            hit_rate = stats.get("hit_rate", 0.0)
            size = stats.get("size", 0)
            evictions = stats.get("evictions", 0)
            capacity_ratio = size / cache.max_size if cache.max_size > 0 else 0

            details = {
                "hit_rate": hit_rate,
                "size": size,
                "max_size": cache.max_size,
                "evictions": evictions,
                "capacity_ratio": capacity_ratio,
            }

            # Check for degraded conditions
            if capacity_ratio >= self.CACHE_CAPACITY_THRESHOLD:
                return ComponentHealth(
                    name="cache",
                    status=HealthStatus.DEGRADED,
                    message=f"Cache near capacity ({capacity_ratio:.0%}), high eviction rate",
                    last_check=datetime.now(),
                    details=details,
                )

            if (
                hit_rate < self.CACHE_HIT_RATE_THRESHOLD
                and stats.get("hits", 0) + stats.get("misses", 0) > 10
            ):
                return ComponentHealth(
                    name="cache",
                    status=HealthStatus.DEGRADED,
                    message=f"Low cache hit rate ({hit_rate:.0%})",
                    last_check=datetime.now(),
                    details=details,
                )

            return ComponentHealth(
                name="cache",
                status=HealthStatus.HEALTHY,
                message=f"Cache healthy (hit rate: {hit_rate:.0%})",
                last_check=datetime.now(),
                details=details,
            )

        except Exception as error:
            logger.error(f"Error checking cache health: {error}")
            return ComponentHealth(
                name="cache",
                status=HealthStatus.UNHEALTHY,
                message=f"Error checking cache: {error!s}",
                last_check=datetime.now(),
                details={"error": str(error)},
            )

    def check_database(self) -> ComponentHealth:
        """Check database accessibility and health."""
        try:
            db_names = ["timers.db", "reminders.db", "todos.db", "automations.db"]
            accessible_dbs = []
            failed_dbs = []

            for db_name in db_names:
                db_path = DATA_DIR / db_name
                if db_path.exists():
                    try:
                        # Try to connect and run integrity check
                        conn = sqlite3.connect(db_path, timeout=5)
                        cursor = conn.cursor()
                        cursor.execute("PRAGMA integrity_check")
                        result = cursor.fetchone()
                        conn.close()

                        if result and result[0] == "ok":
                            accessible_dbs.append(db_name)
                        else:
                            failed_dbs.append(db_name)
                    except Exception as db_error:
                        logger.warning(f"Database {db_name} check failed: {db_error}")
                        failed_dbs.append(db_name)

            details = {
                "accessible": accessible_dbs,
                "failed": failed_dbs,
                "total_checked": len(db_names),
            }

            if failed_dbs:
                return ComponentHealth(
                    name="database",
                    status=HealthStatus.UNHEALTHY,
                    message=f"Database errors: {', '.join(failed_dbs)}",
                    last_check=datetime.now(),
                    details=details,
                )

            if not accessible_dbs:
                return ComponentHealth(
                    name="database",
                    status=HealthStatus.HEALTHY,
                    message="No databases created yet (first run)",
                    last_check=datetime.now(),
                    details=details,
                )

            return ComponentHealth(
                name="database",
                status=HealthStatus.HEALTHY,
                message=f"All databases accessible ({len(accessible_dbs)}/{len(db_names)})",
                last_check=datetime.now(),
                details=details,
            )

        except Exception as error:
            logger.error(f"Error checking database health: {error}")
            return ComponentHealth(
                name="database",
                status=HealthStatus.UNHEALTHY,
                message=f"Error checking databases: {error!s}",
                last_check=datetime.now(),
                details={"error": str(error)},
            )

    def check_anthropic_api(self) -> ComponentHealth:
        """Check Anthropic API usage and cost health."""
        try:
            from src.utils import get_daily_usage

            usage = get_daily_usage()
            daily_cost = usage.get("cost_usd", 0.0)
            request_count = usage.get("requests", 0)

            details = {
                "daily_cost_usd": daily_cost,
                "request_count": request_count,
                "warning_threshold": self.API_COST_WARNING_THRESHOLD,
                "critical_threshold": self.API_COST_CRITICAL_THRESHOLD,
            }

            if daily_cost >= self.API_COST_CRITICAL_THRESHOLD:
                return ComponentHealth(
                    name="anthropic_api",
                    status=HealthStatus.UNHEALTHY,
                    message=f"Daily API cost exceeded threshold (${daily_cost:.2f} >= ${self.API_COST_CRITICAL_THRESHOLD})",
                    last_check=datetime.now(),
                    details=details,
                )

            if daily_cost >= self.API_COST_WARNING_THRESHOLD:
                return ComponentHealth(
                    name="anthropic_api",
                    status=HealthStatus.DEGRADED,
                    message=f"Daily API cost approaching threshold (${daily_cost:.2f})",
                    last_check=datetime.now(),
                    details=details,
                )

            return ComponentHealth(
                name="anthropic_api",
                status=HealthStatus.HEALTHY,
                message=f"API usage normal (${daily_cost:.2f} today, {request_count} requests)",
                last_check=datetime.now(),
                details=details,
            )

        except Exception as error:
            logger.error(f"Error checking Anthropic API health: {error}")
            return ComponentHealth(
                name="anthropic_api",
                status=HealthStatus.HEALTHY,  # Don't fail system if usage tracking fails
                message="Unable to check API usage (tracking may be disabled)",
                last_check=datetime.now(),
                details={"error": str(error)},
            )

    def get_system_health(self) -> dict[str, Any]:
        """
        Get aggregated system health status.

        Returns:
            Dictionary with overall status and component details
        """
        component_healths = []
        overall_status = HealthStatus.HEALTHY

        for checker in self._component_checkers:
            try:
                health = checker.check_fn()
                component_healths.append(health)

                # Track status changes and consecutive failures
                previous_status = self._last_status.get(checker.name)
                self._record_health_check(health)
                self._handle_status_change(health, previous_status)
                self._last_status[checker.name] = health.status

                # Determine overall status (worst wins)
                if health.status.severity > overall_status.severity:
                    overall_status = health.status

            except Exception as error:
                logger.error(f"Error running health check for {checker.name}: {error}")
                # Create an unhealthy status for the failed check
                health = ComponentHealth(
                    name=checker.name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Health check failed: {error!s}",
                    last_check=datetime.now(),
                    details={"error": str(error)},
                )
                component_healths.append(health)
                overall_status = HealthStatus.UNHEALTHY

        return {
            "timestamp": datetime.now().isoformat(),
            "status": overall_status.value,
            "components": [health.to_dict() for health in component_healths],
        }

    def _record_health_check(self, health: ComponentHealth) -> None:
        """Record a health check result in history."""
        with self._lock:
            # Update consecutive failures
            if health.status == HealthStatus.UNHEALTHY:
                self._consecutive_failures[health.name] += 1
            else:
                self._consecutive_failures[health.name] = 0

            # Add to history
            self._health_history[health.name].append(health.to_dict())

            # Enforce max history size
            if len(self._health_history[health.name]) > self.max_history:
                self._health_history[health.name] = self._health_history[health.name][
                    -self.max_history :
                ]

    def _handle_status_change(
        self, health: ComponentHealth, previous_status: HealthStatus | None
    ) -> None:
        """Handle status changes and send alerts if needed."""
        if previous_status is None:
            # First check, no alert needed
            return

        if health.status == previous_status:
            # No change, no alert
            return

        if self.notifier is None:
            return

        # Status changed - determine alert type
        if health.status == HealthStatus.UNHEALTHY:
            # Degradation alert
            self.notifier.send_alert(
                title=f"{health.name} Unhealthy",
                message=health.message,
                severity="critical",
                fields=[
                    {"title": "Component", "value": health.name},
                    {"title": "Previous Status", "value": previous_status.value},
                    {"title": "Current Status", "value": health.status.value},
                ],
            )
        elif health.status == HealthStatus.DEGRADED and previous_status == HealthStatus.HEALTHY:
            # Degradation warning
            self.notifier.send_alert(
                title=f"{health.name} Degraded",
                message=health.message,
                severity="warning",
                fields=[
                    {"title": "Component", "value": health.name},
                    {"title": "Previous Status", "value": previous_status.value},
                    {"title": "Current Status", "value": health.status.value},
                ],
            )
        elif health.status == HealthStatus.HEALTHY and previous_status in [
            HealthStatus.UNHEALTHY,
            HealthStatus.DEGRADED,
        ]:
            # Recovery alert
            self.notifier.send_alert(
                title=f"{health.name} Recovered",
                message=f"{health.name} has recovered and is now healthy",
                severity="info",
                fields=[
                    {"title": "Component", "value": health.name},
                    {"title": "Previous Status", "value": previous_status.value},
                    {"title": "Current Status", "value": health.status.value},
                ],
            )

    def get_health_history(self, component_name: str, limit: int = 10) -> list[dict[str, Any]]:
        """
        Get health history for a component.

        Args:
            component_name: Name of the component
            limit: Maximum number of entries to return

        Returns:
            List of health check results (most recent first)
        """
        with self._lock:
            history = self._health_history.get(component_name, [])
            return history[:limit]

    def get_consecutive_failures(self, component_name: str) -> int:
        """
        Get consecutive failure count for a component.

        Args:
            component_name: Name of the component

        Returns:
            Number of consecutive unhealthy checks
        """
        with self._lock:
            return self._consecutive_failures.get(component_name, 0)

    def register_component(self, name: str, check_fn: Callable[[], ComponentHealth]) -> None:
        """
        Register a custom component checker.

        Args:
            name: Component name
            check_fn: Function that returns ComponentHealth
        """
        self._component_checkers.append(ComponentChecker(name, check_fn))


# Singleton instance
_global_health_monitor: HealthMonitor | None = None


def get_health_monitor() -> HealthMonitor:
    """Get or create the global health monitor instance."""
    global _global_health_monitor
    if _global_health_monitor is None:
        _global_health_monitor = HealthMonitor()
    return _global_health_monitor
