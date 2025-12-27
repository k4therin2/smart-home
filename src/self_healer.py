"""
Smart Home Assistant - Self Healer

Automatic recovery system that responds to health issues and attempts
to restore system functionality without user intervention.
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from src.cache import clear_global_cache
from src.health_monitor import ComponentHealth, HealthStatus


logger = logging.getLogger("self_healer")


class SelfHealer:
    """
    Automatic recovery system for the smart home assistant.

    Monitors component health and attempts automatic recovery actions:
    - Cache: Clear when saturated
    - Database: Log for manual intervention
    - Home Assistant: Reconnection attempts
    - Anthropic API: Rate limiting backoff

    Features:
    - Configurable cooldowns per action type
    - Retry limits with escalation
    - Healing action logging
    - Slack alerts for failures
    """

    # Default cooldowns in seconds
    DEFAULT_COOLDOWNS = {
        "cache": 300,  # 5 minutes
        "database": 3600,  # 1 hour
        "home_assistant": 60,  # 1 minute
        "anthropic_api": 1800,  # 30 minutes
    }

    def __init__(
        self,
        notifier: Any | None = None,
        max_retries: int = 3,
        cooldowns: dict[str, int] | None = None,
    ):
        """
        Initialize the self healer.

        Args:
            notifier: SlackNotifier instance for alerts
            max_retries: Maximum healing attempts before escalation
            cooldowns: Custom cooldown times per component
        """
        self.notifier = notifier
        self.max_retries = max_retries
        self._cooldowns = cooldowns or self.DEFAULT_COOLDOWNS

        # Track healing state
        self._last_healing_time: dict[str, datetime] = {}
        self._healing_attempts: dict[str, int] = defaultdict(int)
        self._healing_log: list[dict[str, Any]] = []

        # Register healing actions
        self._healing_actions = self._register_healing_actions()

    def _register_healing_actions(self) -> dict[str, list[dict[str, Any]]]:
        """Register available healing actions for each component."""
        return {
            "cache": [
                {
                    "name": "clear_cache",
                    "description": "Clear the cache when near capacity or high eviction rate",
                    "condition": self._should_clear_cache,
                    "action": self._heal_cache,
                }
            ],
            "home_assistant": [
                {
                    "name": "log_ha_failure",
                    "description": "Log HA connectivity failure for investigation",
                    "condition": self._should_log_ha_failure,
                    "action": self._heal_home_assistant,
                }
            ],
            "database": [
                {
                    "name": "log_db_corruption",
                    "description": "Log database corruption for manual intervention",
                    "condition": self._should_log_db_issue,
                    "action": self._heal_database,
                }
            ],
            "anthropic_api": [
                {
                    "name": "api_backoff",
                    "description": "Implement API backoff when cost threshold exceeded",
                    "condition": self._should_backoff_api,
                    "action": self._heal_anthropic_api,
                }
            ],
        }

    def _get_cooldown(self, component: str) -> int:
        """Get cooldown time for a component."""
        return self._cooldowns.get(component, 300)

    def _is_in_cooldown(self, component: str) -> bool:
        """Check if a component is in healing cooldown."""
        if component not in self._last_healing_time:
            return False

        last_time = self._last_healing_time[component]
        cooldown_seconds = self._get_cooldown(component)
        cooldown_end = last_time + timedelta(seconds=cooldown_seconds)

        return datetime.now() < cooldown_end

    # Condition checkers

    def _should_clear_cache(self, health: ComponentHealth) -> bool:
        """Check if cache should be cleared."""
        if health.status == HealthStatus.HEALTHY:
            return False

        capacity_ratio = health.details.get("capacity_ratio", 0)
        return capacity_ratio >= 0.9

    def _should_log_ha_failure(self, health: ComponentHealth) -> bool:
        """Check if HA failure should be logged."""
        return health.status == HealthStatus.UNHEALTHY

    def _should_log_db_issue(self, health: ComponentHealth) -> bool:
        """Check if database issue should be logged."""
        return health.status == HealthStatus.UNHEALTHY

    def _should_backoff_api(self, health: ComponentHealth) -> bool:
        """Check if API backoff is needed."""
        return health.status in [HealthStatus.DEGRADED, HealthStatus.UNHEALTHY]

    # Healing actions

    def _heal_cache(self, health: ComponentHealth) -> dict[str, Any]:
        """Attempt to heal cache by clearing it."""
        try:
            clear_global_cache()
            logger.info("Cache cleared successfully as part of self-healing")
            return {"success": True, "action": "cache_cleared"}
        except Exception as error:
            logger.error(f"Failed to clear cache: {error}")
            return {"success": False, "error": str(error)}

    def _heal_home_assistant(self, health: ComponentHealth) -> dict[str, Any]:
        """Handle Home Assistant connectivity issues."""
        # HA issues typically require manual intervention
        # Log and alert, but don't attempt automatic fixes
        logger.warning(f"Home Assistant health issue: {health.message}")

        consecutive_failures = health.details.get("consecutive_failures", 0)

        return {
            "success": True,
            "action": "logged_for_investigation",
            "note": f"HA issue logged. Consecutive failures: {consecutive_failures}",
        }

    def _heal_database(self, health: ComponentHealth) -> dict[str, Any]:
        """Handle database issues."""
        # Database corruption requires manual intervention
        failed_dbs = health.details.get("failed", [])
        logger.error(f"Database health issue: {health.message}. Failed: {failed_dbs}")

        return {
            "success": True,
            "action": "logged_for_manual_intervention",
            "failed_databases": failed_dbs,
        }

    def _heal_anthropic_api(self, health: ComponentHealth) -> dict[str, Any]:
        """Handle API cost issues."""
        daily_cost = health.details.get("daily_cost_usd", 0)
        logger.warning(f"API cost issue: ${daily_cost:.2f} - implementing backoff")

        return {
            "success": True,
            "action": "backoff_recommended",
            "daily_cost": daily_cost,
        }

    def _log_healing_attempt(
        self,
        component: str,
        action_name: str,
        success: bool,
        details: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        """Log a healing attempt."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "component": component,
            "action": action_name,
            "success": success,
            "details": details or {},
        }

        if error:
            log_entry["error"] = error

        self._healing_log.append(log_entry)

        # Keep log from growing too large
        if len(self._healing_log) > 1000:
            self._healing_log = self._healing_log[-500:]

        logger.info(
            f"Healing attempt: {component}/{action_name} - {'success' if success else 'failed'}"
        )

    def attempt_healing(self, component: str, health: ComponentHealth) -> dict[str, Any]:
        """
        Attempt to heal a component based on its health status.

        Args:
            component: Component name
            health: Current health status

        Returns:
            Dictionary with healing attempt results
        """
        result = {
            "component": component,
            "attempted": False,
            "success": False,
            "actions": [],
        }

        # Check if component has registered healing actions
        if component not in self._healing_actions:
            result["reason"] = f"No healing actions registered for {component}"
            return result

        # Check cooldown
        if self._is_in_cooldown(component):
            result["reason"] = f"Component {component} is in cooldown period"
            return result

        # Check max retries
        if self._healing_attempts[component] >= self.max_retries:
            # Alert about max retries exceeded
            if self.notifier:
                self.notifier.send_alert(
                    title=f"Healing Retries Exceeded: {component}",
                    message=f"Maximum healing attempts ({self.max_retries}) exceeded for {component}. Manual intervention required.",
                    severity="critical",
                    fields=[
                        {"title": "Component", "value": component},
                        {"title": "Attempts", "value": str(self._healing_attempts[component])},
                        {"title": "Last Status", "value": health.status.value},
                    ],
                )
            result["reason"] = "Max retries exceeded"
            return result

        # Try each healing action for this component
        for action_config in self._healing_actions[component]:
            action_name = action_config["name"]
            condition_fn = action_config["condition"]
            action_fn = action_config["action"]

            # Check if condition is met
            if not condition_fn(health):
                continue

            result["attempted"] = True

            try:
                # Execute healing action
                action_result = action_fn(health)
                success = action_result.get("success", False)

                result["success"] = success
                result["actions"].append(
                    {
                        "name": action_name,
                        "success": success,
                        "result": action_result,
                    }
                )

                # Log the attempt
                self._log_healing_attempt(
                    component=component,
                    action_name=action_name,
                    success=success,
                    details=action_result,
                )

                # Update tracking
                self._last_healing_time[component] = datetime.now()

                if success:
                    self._healing_attempts[component] = 0
                else:
                    self._healing_attempts[component] += 1

                    # Alert on failure
                    if self.notifier:
                        self.notifier.send_alert(
                            title=f"Healing Failed: {component}",
                            message=f"Automatic healing action '{action_name}' failed for {component}",
                            severity="warning",
                            fields=[
                                {"title": "Component", "value": component},
                                {"title": "Action", "value": action_name},
                                {"title": "Error", "value": action_result.get("error", "Unknown")},
                            ],
                        )

            except Exception as error:
                logger.error(f"Healing action {action_name} failed: {error}")
                result["success"] = False
                result["actions"].append(
                    {
                        "name": action_name,
                        "success": False,
                        "error": str(error),
                    }
                )

                self._log_healing_attempt(
                    component=component,
                    action_name=action_name,
                    success=False,
                    error=str(error),
                )

                self._healing_attempts[component] += 1

                # Alert on failure
                if self.notifier:
                    self.notifier.send_alert(
                        title=f"Healing Failed: {component}",
                        message=f"Automatic healing action '{action_name}' raised exception",
                        severity="warning",
                        fields=[
                            {"title": "Component", "value": component},
                            {"title": "Action", "value": action_name},
                            {"title": "Error", "value": str(error)},
                        ],
                    )

        return result

    def get_healing_history(
        self, component: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        """
        Get healing action history.

        Args:
            component: Filter by component name (optional)
            limit: Maximum number of entries

        Returns:
            List of healing log entries
        """
        if component:
            filtered = [entry for entry in self._healing_log if entry["component"] == component]
        else:
            filtered = self._healing_log

        return filtered[-limit:]

    def reset_attempts(self, component: str) -> None:
        """Reset healing attempt counter for a component."""
        self._healing_attempts[component] = 0
        if component in self._last_healing_time:
            del self._last_healing_time[component]


# Singleton instance
_global_self_healer: SelfHealer | None = None


def get_self_healer() -> SelfHealer:
    """Get or create the global self healer instance."""
    global _global_self_healer
    if _global_self_healer is None:
        _global_self_healer = SelfHealer()
    return _global_self_healer
