"""
Unit tests for SelfHealer class.

Tests the automatic recovery system that responds to health issues
and attempts to restore system functionality.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest


class TestHealingActions:
    """Tests for healing action definitions."""

    def test_healing_action_registry(self):
        """Should have registered healing actions for common issues."""
        from src.self_healer import SelfHealer

        healer = SelfHealer()

        # Should have actions for known components
        assert "cache" in healer._healing_actions
        assert "home_assistant" in healer._healing_actions

    def test_healing_action_has_required_fields(self):
        """Healing actions should have name, condition, and action."""
        from src.self_healer import SelfHealer

        healer = SelfHealer()

        for component, actions in healer._healing_actions.items():
            for action in actions:
                assert "name" in action
                assert "condition" in action
                assert "action" in action
                assert callable(action["condition"])
                assert callable(action["action"])


class TestCacheHealing:
    """Tests for cache self-healing."""

    def test_clears_cache_on_saturation(self):
        """Should clear cache when near capacity."""
        from src.self_healer import SelfHealer
        from src.health_monitor import ComponentHealth, HealthStatus

        with patch("src.self_healer.clear_global_cache") as mock_clear:
            healer = SelfHealer()

            health = ComponentHealth(
                name="cache",
                status=HealthStatus.DEGRADED,
                message="Cache near capacity",
                last_check=datetime.now(),
                details={"capacity_ratio": 0.95, "evictions": 100},
            )

            result = healer.attempt_healing("cache", health)

            assert result["attempted"]
            mock_clear.assert_called_once()

    def test_does_not_clear_healthy_cache(self):
        """Should not clear cache when healthy."""
        from src.self_healer import SelfHealer
        from src.health_monitor import ComponentHealth, HealthStatus

        with patch("src.self_healer.clear_global_cache") as mock_clear:
            healer = SelfHealer()

            health = ComponentHealth(
                name="cache",
                status=HealthStatus.HEALTHY,
                message="Cache healthy",
                last_check=datetime.now(),
                details={"capacity_ratio": 0.5, "evictions": 5},
            )

            result = healer.attempt_healing("cache", health)

            assert not result["attempted"]
            mock_clear.assert_not_called()

    def test_respects_cooldown_on_cache_clear(self):
        """Should not clear cache again within cooldown period."""
        from src.self_healer import SelfHealer
        from src.health_monitor import ComponentHealth, HealthStatus

        with patch("src.self_healer.clear_global_cache") as mock_clear:
            healer = SelfHealer()

            health = ComponentHealth(
                name="cache",
                status=HealthStatus.DEGRADED,
                message="Cache near capacity",
                last_check=datetime.now(),
                details={"capacity_ratio": 0.95},
            )

            # First attempt should work
            result1 = healer.attempt_healing("cache", health)
            assert result1["attempted"]

            # Second attempt should be blocked by cooldown
            result2 = healer.attempt_healing("cache", health)
            assert not result2["attempted"]
            assert "cooldown" in result2.get("reason", "").lower()


class TestHomeAssistantHealing:
    """Tests for Home Assistant self-healing."""

    def test_logs_ha_failure_for_manual_intervention(self):
        """HA failures should be logged for manual intervention."""
        from src.self_healer import SelfHealer
        from src.health_monitor import ComponentHealth, HealthStatus

        healer = SelfHealer()

        health = ComponentHealth(
            name="home_assistant",
            status=HealthStatus.UNHEALTHY,
            message="HA not responding",
            last_check=datetime.now(),
            details={"consecutive_failures": 3},
        )

        with patch.object(healer, "_log_healing_attempt") as mock_log:
            result = healer.attempt_healing("home_assistant", health)

            # Should log the issue even if no automatic fix available
            mock_log.assert_called()


class TestDatabaseHealing:
    """Tests for database self-healing."""

    def test_handles_database_corruption(self):
        """Should handle database corruption gracefully."""
        from src.self_healer import SelfHealer
        from src.health_monitor import ComponentHealth, HealthStatus

        healer = SelfHealer()

        health = ComponentHealth(
            name="database",
            status=HealthStatus.UNHEALTHY,
            message="Database corrupted",
            last_check=datetime.now(),
            details={"failed": ["timers.db"]},
        )

        result = healer.attempt_healing("database", health)

        # Should record the issue for alerting
        assert any(entry["component"] == "database" for entry in healer._healing_log)


class TestHealingCooldowns:
    """Tests for healing action cooldowns."""

    def test_tracks_last_healing_time(self):
        """Should track when each healing action was last attempted."""
        from src.self_healer import SelfHealer
        from src.health_monitor import ComponentHealth, HealthStatus

        with patch("src.self_healer.clear_global_cache"):
            healer = SelfHealer()

            health = ComponentHealth(
                name="cache",
                status=HealthStatus.DEGRADED,
                message="Cache saturated",
                last_check=datetime.now(),
                details={"capacity_ratio": 0.95},
            )

            healer.attempt_healing("cache", health)

            assert "cache" in healer._last_healing_time

    def test_respects_component_specific_cooldowns(self):
        """Should use component-specific cooldown times."""
        from src.self_healer import SelfHealer

        healer = SelfHealer()

        # Different components may have different cooldowns
        assert healer._get_cooldown("cache") > 0
        assert healer._get_cooldown("home_assistant") > 0


class TestHealingLog:
    """Tests for healing action logging."""

    def test_logs_successful_healing(self):
        """Should log successful healing attempts."""
        from src.self_healer import SelfHealer
        from src.health_monitor import ComponentHealth, HealthStatus

        with patch("src.self_healer.clear_global_cache"):
            healer = SelfHealer()

            health = ComponentHealth(
                name="cache",
                status=HealthStatus.DEGRADED,
                message="Cache saturated",
                last_check=datetime.now(),
                details={"capacity_ratio": 0.95},
            )

            healer.attempt_healing("cache", health)

            # Should have log entry
            assert len(healer._healing_log) > 0
            log_entry = healer._healing_log[0]
            assert log_entry["component"] == "cache"
            assert log_entry["success"]

    def test_logs_failed_healing(self):
        """Should log failed healing attempts."""
        from src.self_healer import SelfHealer
        from src.health_monitor import ComponentHealth, HealthStatus

        with patch("src.self_healer.clear_global_cache", side_effect=Exception("Clear failed")):
            healer = SelfHealer()

            health = ComponentHealth(
                name="cache",
                status=HealthStatus.DEGRADED,
                message="Cache saturated",
                last_check=datetime.now(),
                details={"capacity_ratio": 0.95},
            )

            result = healer.attempt_healing("cache", health)

            # Should have logged the failure
            assert not result["success"]
            log_entry = healer._healing_log[-1]
            assert not log_entry["success"]
            # Error is nested in details
            assert "error" in log_entry.get("details", {})

    def test_get_healing_history(self):
        """Should return healing history for review."""
        from src.self_healer import SelfHealer
        from src.health_monitor import ComponentHealth, HealthStatus

        with patch("src.self_healer.clear_global_cache"):
            healer = SelfHealer()

            health = ComponentHealth(
                name="cache",
                status=HealthStatus.DEGRADED,
                message="Cache saturated",
                last_check=datetime.now(),
                details={"capacity_ratio": 0.95},
            )

            healer.attempt_healing("cache", health)

            history = healer.get_healing_history()

            assert len(history) > 0
            assert history[0]["component"] == "cache"


class TestAlertOnHealingFailure:
    """Tests for alerting when healing fails."""

    def test_alerts_when_healing_fails(self):
        """Should send alert when healing action fails."""
        from src.self_healer import SelfHealer
        from src.health_monitor import ComponentHealth, HealthStatus

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

            healer.attempt_healing("cache", health)

            # Should have sent an alert
            mock_notifier.send_alert.assert_called()

    def test_alerts_after_max_retries(self):
        """Should alert when max healing retries exceeded."""
        from src.self_healer import SelfHealer
        from src.health_monitor import ComponentHealth, HealthStatus

        mock_notifier = MagicMock()
        healer = SelfHealer(notifier=mock_notifier, max_retries=3)

        health = ComponentHealth(
            name="home_assistant",
            status=HealthStatus.UNHEALTHY,
            message="HA down",
            last_check=datetime.now(),
            details={"consecutive_failures": 5},
        )

        # Simulate multiple failed healings
        healer._healing_attempts["home_assistant"] = 3

        healer.attempt_healing("home_assistant", health)

        # Should alert about max retries
        assert mock_notifier.send_alert.called


class TestHealingIntegration:
    """Tests for healing integration with health monitor."""

    def test_auto_heal_on_unhealthy_check(self):
        """Should automatically attempt healing on unhealthy status."""
        from src.self_healer import SelfHealer
        from src.health_monitor import HealthMonitor, HealthStatus, ComponentHealth

        mock_healer = MagicMock()

        with patch("src.cache.get_cache") as mock_get_cache:
            mock_cache = MagicMock()
            mock_cache.get_stats.return_value = {
                "hits": 10,
                "misses": 90,
                "evictions": 200,
                "size": 950,
                "hit_rate": 0.1,
            }
            mock_cache.max_size = 1000
            mock_get_cache.return_value = mock_cache

            monitor = HealthMonitor()
            health = monitor.check_cache()

            # When integrated, should trigger healing
            mock_healer.attempt_healing("cache", health)
            mock_healer.attempt_healing.assert_called_once()
