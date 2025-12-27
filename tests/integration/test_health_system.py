"""
Integration tests for the health monitoring and self-healing system.

Tests the complete flow from health check to healing action to alerting.
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestHealthMonitoringFlow:
    """Integration tests for the health monitoring flow."""

    def test_full_health_check_flow(self):
        """Test complete health check across all components."""
        from src.health_monitor import HealthMonitor, HealthStatus

        with patch("src.ha_client.HomeAssistantClient") as mock_ha_class, \
             patch("src.cache.get_cache") as mock_get_cache, \
             patch("src.utils.get_daily_usage") as mock_usage:

            # Setup mocks
            mock_client = MagicMock()
            mock_client.check_connection.return_value = True
            mock_ha_class.return_value = mock_client

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

            mock_usage.return_value = {"cost_usd": 1.50, "requests": 50}

            # Run health check
            monitor = HealthMonitor()
            result = monitor.get_system_health()

            # Verify result structure
            assert "status" in result
            assert "timestamp" in result
            assert "components" in result
            assert len(result["components"]) >= 3

    def test_health_check_with_degraded_cache(self):
        """Test health check when cache is degraded."""
        from src.health_monitor import HealthMonitor, HealthStatus

        with patch("src.ha_client.HomeAssistantClient") as mock_ha_class, \
             patch("src.cache.get_cache") as mock_get_cache, \
             patch("src.utils.get_daily_usage") as mock_usage:

            mock_client = MagicMock()
            mock_client.check_connection.return_value = True
            mock_ha_class.return_value = mock_client

            # Degraded cache - low hit rate
            mock_cache = MagicMock()
            mock_cache.get_stats.return_value = {
                "hits": 10,
                "misses": 90,
                "evictions": 50,
                "size": 500,
                "hit_rate": 0.1,
            }
            mock_cache.max_size = 1000
            mock_get_cache.return_value = mock_cache

            mock_usage.return_value = {"cost_usd": 1.0, "requests": 30}

            monitor = HealthMonitor()
            result = monitor.get_system_health()

            # System should be degraded
            assert result["status"] == "degraded"

            # Find cache component
            cache_health = next(c for c in result["components"] if c["name"] == "cache")
            assert cache_health["status"] == "degraded"

    def test_health_check_records_history(self):
        """Test that health checks are recorded in history."""
        from src.health_monitor import HealthMonitor

        with patch("src.ha_client.HomeAssistantClient") as mock_ha_class, \
             patch("src.cache.get_cache") as mock_get_cache, \
             patch("src.utils.get_daily_usage") as mock_usage:

            mock_client = MagicMock()
            mock_client.check_connection.return_value = True
            mock_ha_class.return_value = mock_client

            mock_cache = MagicMock()
            mock_cache.get_stats.return_value = {
                "hits": 100, "misses": 10, "evictions": 5, "size": 500, "hit_rate": 0.91
            }
            mock_cache.max_size = 1000
            mock_get_cache.return_value = mock_cache

            mock_usage.return_value = {"cost_usd": 1.0, "requests": 30}

            monitor = HealthMonitor()

            # Run multiple health checks
            monitor.get_system_health()
            monitor.get_system_health()
            monitor.get_system_health()

            # Check history
            history = monitor.get_health_history("home_assistant")
            assert len(history) >= 3


class TestSelfHealingFlow:
    """Integration tests for the self-healing flow."""

    def test_cache_healing_on_saturation(self):
        """Test that saturated cache triggers clearing."""
        from src.health_monitor import HealthMonitor, HealthStatus, ComponentHealth
        from src.self_healer import SelfHealer

        with patch("src.self_healer.clear_global_cache") as mock_clear:
            healer = SelfHealer()

            # Create a degraded cache health status
            health = ComponentHealth(
                name="cache",
                status=HealthStatus.DEGRADED,
                message="Cache near capacity",
                last_check=datetime.now(),
                details={"capacity_ratio": 0.95, "evictions": 200},
            )

            result = healer.attempt_healing("cache", health)

            assert result["attempted"]
            assert result["success"]
            mock_clear.assert_called_once()

    def test_healing_respects_cooldowns(self):
        """Test that healing actions respect cooldown periods."""
        from src.health_monitor import ComponentHealth, HealthStatus
        from src.self_healer import SelfHealer

        with patch("src.self_healer.clear_global_cache") as mock_clear:
            healer = SelfHealer()

            health = ComponentHealth(
                name="cache",
                status=HealthStatus.DEGRADED,
                message="Cache saturated",
                last_check=datetime.now(),
                details={"capacity_ratio": 0.95},
            )

            # First healing attempt
            result1 = healer.attempt_healing("cache", health)
            assert result1["attempted"]

            # Second attempt should be blocked by cooldown
            result2 = healer.attempt_healing("cache", health)
            assert not result2["attempted"]

            # Should only have called clear once
            assert mock_clear.call_count == 1

    def test_healing_alerts_on_failure(self):
        """Test that failed healing sends alert."""
        from src.health_monitor import ComponentHealth, HealthStatus
        from src.self_healer import SelfHealer

        mock_notifier = MagicMock()

        with patch("src.self_healer.clear_global_cache", side_effect=Exception("Clear failed")):
            healer = SelfHealer(notifier=mock_notifier)

            health = ComponentHealth(
                name="cache",
                status=HealthStatus.DEGRADED,
                message="Cache saturated",
                last_check=datetime.now(),
                details={"capacity_ratio": 0.95},
            )

            result = healer.attempt_healing("cache", health)

            assert result["attempted"]
            assert not result["success"]
            mock_notifier.send_alert.assert_called()


class TestHealthAndHealingIntegration:
    """Tests for health monitoring and self-healing working together."""

    def test_monitor_triggers_healer(self):
        """Test that unhealthy status triggers healing action."""
        from src.health_monitor import HealthMonitor, HealthStatus
        from src.self_healer import SelfHealer

        with patch("src.ha_client.HomeAssistantClient") as mock_ha_class, \
             patch("src.cache.get_cache") as mock_get_cache, \
             patch("src.utils.get_daily_usage") as mock_usage, \
             patch("src.self_healer.clear_global_cache") as mock_clear:

            mock_client = MagicMock()
            mock_client.check_connection.return_value = True
            mock_ha_class.return_value = mock_client

            # Degraded cache with high capacity
            mock_cache = MagicMock()
            mock_cache.get_stats.return_value = {
                "hits": 10,
                "misses": 90,
                "evictions": 500,
                "size": 950,
                "hit_rate": 0.1,
            }
            mock_cache.max_size = 1000
            mock_get_cache.return_value = mock_cache

            mock_usage.return_value = {"cost_usd": 1.0, "requests": 30}

            # Create monitor and healer
            monitor = HealthMonitor()
            healer = SelfHealer()

            # Get health status
            health_data = monitor.get_system_health()

            # Find degraded component and attempt healing
            for component in health_data["components"]:
                if component["status"] in ["degraded", "unhealthy"]:
                    from src.health_monitor import ComponentHealth

                    status_map = {
                        "healthy": HealthStatus.HEALTHY,
                        "degraded": HealthStatus.DEGRADED,
                        "unhealthy": HealthStatus.UNHEALTHY,
                    }
                    component_health = ComponentHealth(
                        name=component["name"],
                        status=status_map[component["status"]],
                        message=component["message"],
                        last_check=datetime.now(),
                        details=component.get("details", {}),
                    )
                    healer.attempt_healing(component["name"], component_health)

            # Cache should have been cleared
            mock_clear.assert_called()


class TestAlertingIntegration:
    """Tests for alerting integration with health monitoring."""

    def test_status_change_sends_alert(self):
        """Test that status changes trigger alerts."""
        from src.health_monitor import HealthMonitor, HealthStatus, ComponentHealth

        mock_notifier = MagicMock()
        monitor = HealthMonitor(notifier=mock_notifier)

        # Simulate status change from healthy to unhealthy
        monitor._last_status["test"] = HealthStatus.HEALTHY

        monitor._handle_status_change(
            ComponentHealth(
                name="test",
                status=HealthStatus.UNHEALTHY,
                message="Component failed",
                last_check=datetime.now(),
            ),
            previous_status=HealthStatus.HEALTHY
        )

        # Should have sent an alert
        mock_notifier.send_alert.assert_called()

        # Check alert content
        call_args = mock_notifier.send_alert.call_args
        assert "unhealthy" in call_args.kwargs.get("title", "").lower()

    def test_recovery_sends_alert(self):
        """Test that recovery sends informational alert."""
        from src.health_monitor import HealthMonitor, HealthStatus, ComponentHealth

        mock_notifier = MagicMock()
        monitor = HealthMonitor(notifier=mock_notifier)

        # Simulate recovery from unhealthy to healthy
        monitor._last_status["test"] = HealthStatus.UNHEALTHY

        monitor._handle_status_change(
            ComponentHealth(
                name="test",
                status=HealthStatus.HEALTHY,
                message="Component recovered",
                last_check=datetime.now(),
            ),
            previous_status=HealthStatus.UNHEALTHY
        )

        # Should have sent a recovery alert
        mock_notifier.send_alert.assert_called()

        call_args = mock_notifier.send_alert.call_args
        assert "recover" in call_args.kwargs.get("title", "").lower() or \
               "recover" in call_args.kwargs.get("message", "").lower()


class TestDatabaseHealthIntegration:
    """Tests for database health monitoring integration."""

    def test_database_health_check_with_real_db(self, tmp_path):
        """Test database health check with actual SQLite database."""
        from src.health_monitor import HealthMonitor, HealthStatus

        # Create a test database
        db_path = tmp_path / "timers.db"
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE timers (id INTEGER PRIMARY KEY)")
        conn.execute("INSERT INTO timers (id) VALUES (1)")
        conn.commit()
        conn.close()

        with patch("src.health_monitor.DATA_DIR", tmp_path):
            monitor = HealthMonitor()
            health = monitor.check_database()

            # Should be healthy with accessible DB
            assert health.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]
            assert "timers.db" in health.details.get("accessible", [])


class TestConsecutiveFailureTracking:
    """Tests for consecutive failure tracking."""

    def test_tracks_consecutive_failures(self):
        """Test that consecutive failures are tracked correctly."""
        from src.health_monitor import HealthMonitor, HealthStatus, ComponentHealth

        monitor = HealthMonitor()

        # Record multiple failures
        for i in range(5):
            monitor._record_health_check(
                ComponentHealth(
                    name="test",
                    status=HealthStatus.UNHEALTHY,
                    message=f"Failure {i}",
                    last_check=datetime.now(),
                )
            )

        assert monitor.get_consecutive_failures("test") == 5

    def test_resets_on_success(self):
        """Test that consecutive failures reset on success."""
        from src.health_monitor import HealthMonitor, HealthStatus, ComponentHealth

        monitor = HealthMonitor()

        # Record failures
        for _ in range(3):
            monitor._record_health_check(
                ComponentHealth(
                    name="test",
                    status=HealthStatus.UNHEALTHY,
                    message="Failure",
                    last_check=datetime.now(),
                )
            )

        assert monitor.get_consecutive_failures("test") == 3

        # Record success
        monitor._record_health_check(
            ComponentHealth(
                name="test",
                status=HealthStatus.HEALTHY,
                message="Success",
                last_check=datetime.now(),
            )
        )

        assert monitor.get_consecutive_failures("test") == 0


class TestHealthAPIEndpoints:
    """Tests for health API endpoints (mock Flask app)."""

    def test_health_endpoint_returns_status(self):
        """Test that /api/health returns proper status structure."""
        # This would normally use Flask test client
        # For now, test the underlying functions

        from src.health_monitor import HealthMonitor

        with patch("src.ha_client.HomeAssistantClient") as mock_ha_class, \
             patch("src.cache.get_cache") as mock_get_cache, \
             patch("src.utils.get_daily_usage") as mock_usage:

            mock_client = MagicMock()
            mock_client.check_connection.return_value = True
            mock_ha_class.return_value = mock_client

            mock_cache = MagicMock()
            mock_cache.get_stats.return_value = {
                "hits": 100, "misses": 10, "evictions": 5, "size": 500, "hit_rate": 0.91
            }
            mock_cache.max_size = 1000
            mock_get_cache.return_value = mock_cache

            mock_usage.return_value = {"cost_usd": 1.0, "requests": 30}

            monitor = HealthMonitor()
            result = monitor.get_system_health()

            # Verify structure matches API response
            assert "status" in result
            assert "timestamp" in result
            assert "components" in result
            assert all("name" in c for c in result["components"])
            assert all("status" in c for c in result["components"])
            assert all("message" in c for c in result["components"])
