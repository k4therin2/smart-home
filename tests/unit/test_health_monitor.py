"""
Unit tests for HealthMonitor class.

Tests the centralized health monitoring system that aggregates health
status from all system components.
"""

import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest


class TestHealthStatus:
    """Tests for HealthStatus enum and constants."""

    def test_health_status_values(self):
        """Health status should have healthy, degraded, and unhealthy states."""
        from src.health_monitor import HealthStatus

        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"

    def test_health_status_ordering(self):
        """Health status should be comparable for severity ordering."""
        from src.health_monitor import HealthStatus

        # Unhealthy is worse than degraded, degraded worse than healthy
        assert HealthStatus.UNHEALTHY.severity > HealthStatus.DEGRADED.severity
        assert HealthStatus.DEGRADED.severity > HealthStatus.HEALTHY.severity


class TestComponentHealth:
    """Tests for ComponentHealth dataclass."""

    def test_component_health_creation(self):
        """Should create component health with all required fields."""
        from src.health_monitor import ComponentHealth, HealthStatus

        health = ComponentHealth(
            name="test_component",
            status=HealthStatus.HEALTHY,
            message="All good",
            last_check=datetime.now(),
            details={"foo": "bar"},
        )

        assert health.name == "test_component"
        assert health.status == HealthStatus.HEALTHY
        assert health.message == "All good"
        assert health.details == {"foo": "bar"}

    def test_component_health_to_dict(self):
        """Should convert to dictionary for JSON serialization."""
        from src.health_monitor import ComponentHealth, HealthStatus

        now = datetime.now()
        health = ComponentHealth(
            name="cache",
            status=HealthStatus.DEGRADED,
            message="High eviction rate",
            last_check=now,
            details={"evictions": 100},
        )

        result = health.to_dict()

        assert result["name"] == "cache"
        assert result["status"] == "degraded"
        assert result["message"] == "High eviction rate"
        assert result["details"]["evictions"] == 100
        assert "last_check" in result


class TestHealthMonitorInit:
    """Tests for HealthMonitor initialization."""

    def test_default_initialization(self):
        """Should initialize with default check intervals."""
        from src.health_monitor import HealthMonitor

        monitor = HealthMonitor()

        assert monitor.check_interval > 0
        assert len(monitor._component_checkers) > 0

    def test_custom_check_interval(self):
        """Should accept custom check interval."""
        from src.health_monitor import HealthMonitor

        monitor = HealthMonitor(check_interval=120)

        assert monitor.check_interval == 120

    def test_registers_default_components(self):
        """Should register default component checkers on init."""
        from src.health_monitor import HealthMonitor

        monitor = HealthMonitor()

        # Should have checkers for core components
        component_names = [checker.name for checker in monitor._component_checkers]
        assert "home_assistant" in component_names
        assert "cache" in component_names
        assert "database" in component_names


class TestHomeAssistantHealthCheck:
    """Tests for Home Assistant connectivity health check."""

    @patch("src.ha_client.HomeAssistantClient")
    def test_ha_healthy_when_connected(self, mock_ha_class):
        """HA should be healthy when check_connection returns True."""
        from src.health_monitor import HealthMonitor, HealthStatus

        mock_client = MagicMock()
        mock_client.check_connection.return_value = True
        mock_ha_class.return_value = mock_client

        monitor = HealthMonitor()
        health = monitor.check_home_assistant()

        assert health.status == HealthStatus.HEALTHY
        assert "connected" in health.message.lower()

    @patch("src.ha_client.HomeAssistantClient")
    def test_ha_unhealthy_when_disconnected(self, mock_ha_class):
        """HA should be unhealthy when check_connection returns False."""
        from src.health_monitor import HealthMonitor, HealthStatus

        mock_client = MagicMock()
        mock_client.check_connection.return_value = False
        mock_ha_class.return_value = mock_client

        monitor = HealthMonitor()
        health = monitor.check_home_assistant()

        assert health.status == HealthStatus.UNHEALTHY
        assert "not responding" in health.message.lower() or "unavailable" in health.message.lower()

    @patch("src.ha_client.HomeAssistantClient")
    def test_ha_unhealthy_on_exception(self, mock_ha_class):
        """HA should be unhealthy when check_connection raises exception."""
        from src.health_monitor import HealthMonitor, HealthStatus

        mock_client = MagicMock()
        mock_client.check_connection.side_effect = Exception("Connection timeout")
        mock_ha_class.return_value = mock_client

        monitor = HealthMonitor()
        health = monitor.check_home_assistant()

        assert health.status == HealthStatus.UNHEALTHY
        assert "error" in health.message.lower() or "timeout" in health.message.lower()

    @patch("src.ha_client.HomeAssistantClient")
    def test_ha_tracks_response_time(self, mock_ha_class):
        """HA health check should track response time."""
        from src.health_monitor import HealthMonitor

        mock_client = MagicMock()
        mock_client.check_connection.return_value = True
        mock_ha_class.return_value = mock_client

        monitor = HealthMonitor()
        health = monitor.check_home_assistant()

        assert "response_time_ms" in health.details


class TestCacheHealthCheck:
    """Tests for cache health check."""

    def test_cache_healthy_with_good_stats(self):
        """Cache should be healthy with normal hit rate and no saturation."""
        from src.health_monitor import HealthMonitor, HealthStatus

        with patch("src.cache.get_cache") as mock_get_cache:
            mock_cache = MagicMock()
            mock_cache.get_stats.return_value = {
                "hits": 100,
                "misses": 10,
                "evictions": 5,
                "size": 500,
                "hit_rate": 0.91,
            }
            mock_cache.max_size = 1000
            mock_get_cache.return_value = mock_cache

            monitor = HealthMonitor()
            health = monitor.check_cache()

            assert health.status == HealthStatus.HEALTHY
            assert health.details["hit_rate"] == 0.91

    def test_cache_degraded_with_low_hit_rate(self):
        """Cache should be degraded with low hit rate."""
        from src.health_monitor import HealthMonitor, HealthStatus

        with patch("src.cache.get_cache") as mock_get_cache:
            mock_cache = MagicMock()
            mock_cache.get_stats.return_value = {
                "hits": 20,
                "misses": 80,
                "evictions": 50,
                "size": 500,
                "hit_rate": 0.2,
            }
            mock_cache.max_size = 1000
            mock_get_cache.return_value = mock_cache

            monitor = HealthMonitor()
            health = monitor.check_cache()

            assert health.status == HealthStatus.DEGRADED
            assert "hit rate" in health.message.lower()

    def test_cache_degraded_when_near_capacity(self):
        """Cache should be degraded when near max capacity."""
        from src.health_monitor import HealthMonitor, HealthStatus

        with patch("src.cache.get_cache") as mock_get_cache:
            mock_cache = MagicMock()
            mock_cache.get_stats.return_value = {
                "hits": 100,
                "misses": 10,
                "evictions": 200,
                "size": 950,
                "hit_rate": 0.91,
            }
            mock_cache.max_size = 1000
            mock_get_cache.return_value = mock_cache

            monitor = HealthMonitor()
            health = monitor.check_cache()

            assert health.status == HealthStatus.DEGRADED
            assert "capacity" in health.message.lower() or "eviction" in health.message.lower()

    def test_cache_unhealthy_on_exception(self):
        """Cache should be unhealthy when stats retrieval fails."""
        from src.health_monitor import HealthMonitor, HealthStatus

        with patch("src.cache.get_cache") as mock_get_cache:
            mock_get_cache.side_effect = Exception("Cache error")

            monitor = HealthMonitor()
            health = monitor.check_cache()

            assert health.status == HealthStatus.UNHEALTHY


class TestDatabaseHealthCheck:
    """Tests for database health check."""

    def test_database_healthy_when_accessible(self, tmp_path):
        """Database should be healthy when all DBs are accessible."""
        from src.health_monitor import HealthMonitor, HealthStatus

        # Create test database files
        for db_name in ["timers.db", "reminders.db", "todos.db", "automations.db"]:
            db_path = tmp_path / db_name
            conn = sqlite3.connect(db_path)
            conn.execute("CREATE TABLE test (id INTEGER)")
            conn.close()

        with patch("src.health_monitor.DATA_DIR", tmp_path):
            monitor = HealthMonitor()
            health = monitor.check_database()

            assert health.status == HealthStatus.HEALTHY
            assert "accessible" in health.message.lower()

    def test_database_degraded_when_some_missing(self, tmp_path):
        """Database should be degraded when some DBs are missing."""
        from src.health_monitor import HealthMonitor, HealthStatus

        # Create only some database files
        db_path = tmp_path / "timers.db"
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE test (id INTEGER)")
        conn.close()

        with patch("src.health_monitor.DATA_DIR", tmp_path):
            monitor = HealthMonitor()
            health = monitor.check_database()

            assert health.status in [HealthStatus.DEGRADED, HealthStatus.HEALTHY]

    def test_database_unhealthy_when_corrupted(self, tmp_path):
        """Database should be unhealthy when DB is corrupted."""
        from src.health_monitor import HealthMonitor, HealthStatus

        # Create a corrupted database file
        db_path = tmp_path / "timers.db"
        with open(db_path, "w") as file:
            file.write("not a valid sqlite database")

        with patch("src.health_monitor.DATA_DIR", tmp_path):
            monitor = HealthMonitor()
            health = monitor.check_database()

            # Should detect corruption
            assert health.status == HealthStatus.UNHEALTHY or "error" in health.message.lower()


class TestAnthropicAPIHealthCheck:
    """Tests for Anthropic API health check."""

    def test_api_healthy_with_low_cost(self):
        """API should be healthy when daily cost is under threshold."""
        from src.health_monitor import HealthMonitor, HealthStatus

        with patch("src.utils.get_daily_usage") as mock_usage:
            mock_usage.return_value = {"cost_usd": 1.50, "requests": 50}

            monitor = HealthMonitor()
            health = monitor.check_anthropic_api()

            assert health.status == HealthStatus.HEALTHY
            assert health.details["daily_cost_usd"] == 1.50

    def test_api_degraded_approaching_threshold(self):
        """API should be degraded when approaching cost threshold."""
        from src.health_monitor import HealthMonitor, HealthStatus

        with patch("src.utils.get_daily_usage") as mock_usage:
            mock_usage.return_value = {"cost_usd": 4.50, "requests": 150}

            monitor = HealthMonitor()
            health = monitor.check_anthropic_api()

            assert health.status == HealthStatus.DEGRADED
            assert "cost" in health.message.lower()

    def test_api_unhealthy_over_threshold(self):
        """API should be unhealthy when over cost threshold."""
        from src.health_monitor import HealthMonitor, HealthStatus

        with patch("src.utils.get_daily_usage") as mock_usage:
            mock_usage.return_value = {"cost_usd": 6.00, "requests": 200}

            monitor = HealthMonitor()
            health = monitor.check_anthropic_api()

            assert health.status == HealthStatus.UNHEALTHY
            assert "exceeded" in health.message.lower() or "over" in health.message.lower()


class TestAggregatedHealth:
    """Tests for aggregated system health."""

    def _setup_mocked_monitor(self, health_configs):
        """
        Create a monitor with mocked component checkers.

        Args:
            health_configs: Dict mapping component names to (status, message, details) tuples
        """
        from src.health_monitor import HealthMonitor, HealthStatus, ComponentHealth, ComponentChecker

        monitor = HealthMonitor()
        now = datetime.now()

        # Replace component checkers with mocks that return configured health
        mock_checkers = []
        for name, (status, message, details) in health_configs.items():
            health = ComponentHealth(name, status, message, now, details or {})
            mock_fn = Mock(return_value=health)
            mock_checkers.append(ComponentChecker(name, mock_fn))

        monitor._component_checkers = mock_checkers
        return monitor

    def test_system_healthy_when_all_healthy(self):
        """System should be healthy when all components are healthy."""
        from src.health_monitor import HealthStatus

        monitor = self._setup_mocked_monitor({
            "home_assistant": (HealthStatus.HEALTHY, "OK", {}),
            "cache": (HealthStatus.HEALTHY, "OK", {}),
            "database": (HealthStatus.HEALTHY, "OK", {}),
            "anthropic_api": (HealthStatus.HEALTHY, "OK", {}),
        })

        result = monitor.get_system_health()

        assert result["status"] == "healthy"
        assert len(result["components"]) == 4

    def test_system_degraded_when_one_degraded(self):
        """System should be degraded when any component is degraded."""
        from src.health_monitor import HealthStatus

        monitor = self._setup_mocked_monitor({
            "home_assistant": (HealthStatus.HEALTHY, "OK", {}),
            "cache": (HealthStatus.DEGRADED, "Low hit rate", {}),
            "database": (HealthStatus.HEALTHY, "OK", {}),
            "anthropic_api": (HealthStatus.HEALTHY, "OK", {}),
        })

        result = monitor.get_system_health()

        assert result["status"] == "degraded"

    def test_system_unhealthy_when_one_unhealthy(self):
        """System should be unhealthy when any component is unhealthy."""
        from src.health_monitor import HealthStatus

        monitor = self._setup_mocked_monitor({
            "home_assistant": (HealthStatus.UNHEALTHY, "Down", {}),
            "cache": (HealthStatus.HEALTHY, "OK", {}),
            "database": (HealthStatus.HEALTHY, "OK", {}),
            "anthropic_api": (HealthStatus.HEALTHY, "OK", {}),
        })

        result = monitor.get_system_health()

        assert result["status"] == "unhealthy"

    def test_get_system_health_returns_all_details(self):
        """System health should include timestamp and all component details."""
        from src.health_monitor import HealthStatus

        monitor = self._setup_mocked_monitor({
            "home_assistant": (HealthStatus.HEALTHY, "OK", {"response_time_ms": 50}),
            "cache": (HealthStatus.HEALTHY, "OK", {"hit_rate": 0.95}),
            "database": (HealthStatus.HEALTHY, "OK", {}),
            "anthropic_api": (HealthStatus.HEALTHY, "OK", {"daily_cost_usd": 1.0}),
        })

        result = monitor.get_system_health()

        assert "timestamp" in result
        assert "status" in result
        assert "components" in result
        assert len(result["components"]) == 4

        # Check component details are included
        ha_component = next(c for c in result["components"] if c["name"] == "home_assistant")
        assert ha_component["details"]["response_time_ms"] == 50


class TestHealthHistory:
    """Tests for health check history tracking."""

    def test_stores_health_history(self):
        """Should store recent health check results."""
        from src.health_monitor import HealthMonitor, HealthStatus, ComponentHealth

        monitor = HealthMonitor()

        # Record some health checks
        monitor._record_health_check(
            ComponentHealth("test", HealthStatus.HEALTHY, "OK", datetime.now())
        )
        monitor._record_health_check(
            ComponentHealth("test", HealthStatus.DEGRADED, "Slow", datetime.now())
        )

        history = monitor.get_health_history("test", limit=10)

        assert len(history) == 2
        assert history[0]["status"] == "healthy"
        assert history[1]["status"] == "degraded"

    def test_limits_history_size(self):
        """Should limit history to prevent memory growth."""
        from src.health_monitor import HealthMonitor, HealthStatus, ComponentHealth

        monitor = HealthMonitor(max_history=5)

        # Record more than max history
        for i in range(10):
            monitor._record_health_check(
                ComponentHealth("test", HealthStatus.HEALTHY, f"Check {i}", datetime.now())
            )

        history = monitor.get_health_history("test")

        assert len(history) <= 5


class TestHealthAlerts:
    """Tests for health-based alerting."""

    def test_alerts_on_status_change(self):
        """Should send alert when status changes to unhealthy."""
        from src.health_monitor import HealthMonitor, HealthStatus, ComponentHealth

        mock_notifier = MagicMock()
        monitor = HealthMonitor(notifier=mock_notifier)

        # First check - healthy
        monitor._handle_status_change(
            ComponentHealth("test", HealthStatus.HEALTHY, "OK", datetime.now()),
            previous_status=None
        )

        # Second check - unhealthy
        monitor._handle_status_change(
            ComponentHealth("test", HealthStatus.UNHEALTHY, "Down", datetime.now()),
            previous_status=HealthStatus.HEALTHY
        )

        # Should have sent an alert
        assert mock_notifier.send_alert.called

    def test_no_alert_for_same_status(self):
        """Should not send alert when status remains the same."""
        from src.health_monitor import HealthMonitor, HealthStatus, ComponentHealth

        mock_notifier = MagicMock()
        monitor = HealthMonitor(notifier=mock_notifier)

        # Multiple healthy checks
        monitor._handle_status_change(
            ComponentHealth("test", HealthStatus.HEALTHY, "OK", datetime.now()),
            previous_status=HealthStatus.HEALTHY
        )

        # Should not send alert
        assert not mock_notifier.send_alert.called

    def test_recovery_alert(self):
        """Should send recovery alert when status improves."""
        from src.health_monitor import HealthMonitor, HealthStatus, ComponentHealth

        mock_notifier = MagicMock()
        monitor = HealthMonitor(notifier=mock_notifier)

        # Recovery from unhealthy to healthy
        monitor._handle_status_change(
            ComponentHealth("test", HealthStatus.HEALTHY, "Recovered", datetime.now()),
            previous_status=HealthStatus.UNHEALTHY
        )

        # Should have sent a recovery alert
        assert mock_notifier.send_alert.called
        call_args = mock_notifier.send_alert.call_args
        assert "recover" in call_args.kwargs.get("title", "").lower() or \
               "recover" in call_args.kwargs.get("message", "").lower()


class TestConsecutiveFailures:
    """Tests for consecutive failure tracking."""

    def test_tracks_consecutive_failures(self):
        """Should track consecutive failures per component."""
        from src.health_monitor import HealthMonitor, HealthStatus, ComponentHealth

        monitor = HealthMonitor()

        # Record failures
        for _ in range(3):
            monitor._record_health_check(
                ComponentHealth("ha", HealthStatus.UNHEALTHY, "Down", datetime.now())
            )

        assert monitor.get_consecutive_failures("ha") == 3

    def test_resets_failures_on_success(self):
        """Should reset consecutive failures on successful check."""
        from src.health_monitor import HealthMonitor, HealthStatus, ComponentHealth

        monitor = HealthMonitor()

        # Record failures then success
        for _ in range(3):
            monitor._record_health_check(
                ComponentHealth("ha", HealthStatus.UNHEALTHY, "Down", datetime.now())
            )

        monitor._record_health_check(
            ComponentHealth("ha", HealthStatus.HEALTHY, "OK", datetime.now())
        )

        assert monitor.get_consecutive_failures("ha") == 0


class TestLLMProviderHealthCheck:
    """Tests for LLM provider health check (WP-10.21)."""

    def test_llm_healthy_when_api_reachable(self):
        """LLM should be healthy when provider API is reachable."""
        from src.health_monitor import HealthMonitor, HealthStatus

        with patch("src.llm_client.get_llm_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.provider = "openai"
            mock_client.model = "gpt-4o-mini"
            # Mock a successful API check
            mock_client.complete.return_value = MagicMock(content="test", input_tokens=5, output_tokens=5)
            mock_get_client.return_value = mock_client

            monitor = HealthMonitor()
            health = monitor.check_llm_provider()

            assert health.status == HealthStatus.HEALTHY
            assert "llm" in health.name.lower() or "provider" in health.name.lower()

    def test_llm_unhealthy_when_api_fails(self):
        """LLM should be unhealthy when provider API fails."""
        from src.health_monitor import HealthMonitor, HealthStatus

        with patch("src.llm_client.get_llm_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.provider = "openai"
            mock_client.complete.side_effect = Exception("API rate limit exceeded")
            mock_get_client.return_value = mock_client

            monitor = HealthMonitor()
            health = monitor.check_llm_provider()

            assert health.status == HealthStatus.UNHEALTHY
            assert "error" in health.message.lower() or "fail" in health.message.lower()

    def test_llm_includes_provider_details(self):
        """LLM health check should include provider details."""
        from src.health_monitor import HealthMonitor

        with patch("src.llm_client.get_llm_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.provider = "anthropic"
            mock_client.model = "claude-sonnet-4"
            mock_client.complete.return_value = MagicMock(content="test", input_tokens=5, output_tokens=5)
            mock_get_client.return_value = mock_client

            monitor = HealthMonitor()
            health = monitor.check_llm_provider()

            assert "provider" in health.details
            assert health.details["provider"] == "anthropic"


class TestLivenessReadinessEndpoints:
    """Tests for /healthz and /readyz endpoint functionality (WP-10.21)."""

    def test_liveness_check_basic(self):
        """Liveness check should verify process is alive."""
        from src.health_monitor import HealthMonitor, HealthStatus

        monitor = HealthMonitor()
        liveness = monitor.get_liveness()

        # Should always be healthy if the process is running
        assert liveness["status"] == "ok"
        assert "timestamp" in liveness

    def test_readiness_check_all_healthy(self):
        """Readiness check should return ready when all critical deps are healthy."""
        from src.health_monitor import HealthMonitor, HealthStatus, ComponentHealth, ComponentChecker
        from unittest.mock import Mock

        monitor = HealthMonitor()
        # Replace checkers with healthy mocks
        mock_checkers = []
        for name in ["home_assistant", "database"]:
            health = ComponentHealth(name, HealthStatus.HEALTHY, "OK", datetime.now())
            mock_fn = Mock(return_value=health)
            mock_checkers.append(ComponentChecker(name, mock_fn))
        monitor._component_checkers = mock_checkers

        readiness = monitor.get_readiness()

        assert readiness["ready"] is True

    def test_readiness_check_unhealthy_critical_dep(self):
        """Readiness check should return not ready when critical dep unhealthy."""
        from src.health_monitor import HealthMonitor, HealthStatus, ComponentHealth, ComponentChecker
        from unittest.mock import Mock

        monitor = HealthMonitor()
        # Replace checkers with one unhealthy mock
        mock_checkers = []
        for name, status in [("home_assistant", HealthStatus.UNHEALTHY), ("database", HealthStatus.HEALTHY)]:
            health = ComponentHealth(name, status, "msg", datetime.now())
            mock_fn = Mock(return_value=health)
            mock_checkers.append(ComponentChecker(name, mock_fn))
        monitor._component_checkers = mock_checkers

        readiness = monitor.get_readiness()

        assert readiness["ready"] is False
        assert "home_assistant" in readiness.get("failing", [])


class TestHealthHistoryRetention:
    """Tests for health check history retention policies (WP-10.21)."""

    def test_history_retention_default_policy(self):
        """Should retain history according to default policy."""
        from src.health_monitor import HealthMonitor, HealthStatus, ComponentHealth

        monitor = HealthMonitor(max_history=100, history_retention_days=7)

        # Record health checks
        for i in range(5):
            monitor._record_health_check(
                ComponentHealth("test", HealthStatus.HEALTHY, f"Check {i}", datetime.now())
            )

        history = monitor.get_health_history("test")
        assert len(history) == 5

    def test_history_cleanup_old_entries(self):
        """Should clean up old entries beyond retention period."""
        from src.health_monitor import HealthMonitor, HealthStatus, ComponentHealth

        monitor = HealthMonitor(max_history=100, history_retention_days=1)

        # Record old health check (beyond retention)
        old_time = datetime.now() - timedelta(days=2)
        monitor._health_history["test"].append(
            ComponentHealth("test", HealthStatus.HEALTHY, "Old check", old_time).to_dict()
        )

        # Record new health check
        monitor._record_health_check(
            ComponentHealth("test", HealthStatus.HEALTHY, "New check", datetime.now())
        )

        # Cleanup should remove old entries
        monitor.cleanup_old_history()
        history = monitor.get_health_history("test")

        # Only the new entry should remain
        assert len(history) == 1
        assert "New check" in history[0]["message"]


class TestManualHealingTriggers:
    """Tests for manual healing triggers (WP-10.21)."""

    def test_trigger_healing_for_component(self):
        """Should be able to manually trigger healing for a component."""
        from src.health_monitor import HealthMonitor, HealthStatus

        mock_healer = MagicMock()
        mock_healer.attempt_healing.return_value = {"attempted": True, "success": True, "action": "restart"}

        monitor = HealthMonitor()
        monitor.set_healer(mock_healer)

        result = monitor.trigger_healing("home_assistant")

        assert result["attempted"] is True
        mock_healer.attempt_healing.assert_called_once()

    def test_trigger_healing_returns_result(self):
        """Manual healing trigger should return healing result."""
        from src.health_monitor import HealthMonitor

        mock_healer = MagicMock()
        mock_healer.attempt_healing.return_value = {
            "attempted": True,
            "success": False,
            "action": "restart",
            "error": "Service restart failed"
        }

        monitor = HealthMonitor()
        monitor.set_healer(mock_healer)

        result = monitor.trigger_healing("database")

        assert result["attempted"] is True
        assert result["success"] is False
        assert "error" in result


class TestImprovedHealingLogging:
    """Tests for improved healing action logging (WP-10.21)."""

    def test_healing_action_logged_with_details(self):
        """Healing actions should be logged with full details."""
        from src.health_monitor import HealthMonitor, HealthStatus, ComponentHealth, HealingLogEntry

        monitor = HealthMonitor()

        healing_entry = HealingLogEntry(
            component="home_assistant",
            action="restart_service",
            success=True,
            timestamp=datetime.now(),
            details={"service": "ha-supervisor", "duration_ms": 1500}
        )

        monitor.log_healing_action(healing_entry)

        logs = monitor.get_healing_log(limit=10)
        assert len(logs) >= 1
        assert logs[0]["component"] == "home_assistant"
        assert logs[0]["action"] == "restart_service"
        assert logs[0]["success"] is True

    def test_healing_log_stores_failures(self):
        """Healing log should store failure details."""
        from src.health_monitor import HealthMonitor, HealingLogEntry

        monitor = HealthMonitor()

        healing_entry = HealingLogEntry(
            component="database",
            action="repair_tables",
            success=False,
            timestamp=datetime.now(),
            details={"error": "Permission denied", "tables_attempted": 3}
        )

        monitor.log_healing_action(healing_entry)

        logs = monitor.get_healing_log(limit=10)
        assert logs[0]["success"] is False
        assert "error" in logs[0]["details"]
