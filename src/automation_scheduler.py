"""
Smart Home Assistant - Automation Scheduler Background Worker

Runs as a background process to evaluate automation triggers
and execute automation actions.

Part of WP-10.3: Automation Scheduler Background Process
"""

import logging
import signal
import time
from datetime import datetime
from typing import Any

from src.automation_manager import AutomationManager, get_automation_manager
from src.ha_client import HomeAssistantClient, get_ha_client
from src.utils import send_health_alert


logger = logging.getLogger(__name__)

# Default check interval (seconds)
DEFAULT_CHECK_INTERVAL = 60

# State check interval for more responsive state triggers
STATE_CHECK_INTERVAL = 10


class AutomationScheduler:
    """
    Background worker for evaluating automation triggers and executing actions.

    Supports:
    - Time-based triggers (evaluated every minute)
    - State-based triggers (evaluated more frequently via polling)
    - Agent command actions (natural language via run_agent)
    - Home Assistant service call actions (direct API calls)

    Follows the same pattern as NotificationWorker for consistency.
    """

    def __init__(
        self,
        automation_manager: AutomationManager | None = None,
        ha_client: HomeAssistantClient | None = None,
        check_interval: int = DEFAULT_CHECK_INTERVAL,
    ):
        """
        Initialize AutomationScheduler.

        Args:
            automation_manager: AutomationManager instance (uses singleton if None)
            ha_client: HAClient instance (uses singleton if None)
            check_interval: Seconds between automation checks
        """
        self.automation_manager = automation_manager or get_automation_manager()
        self.ha_client = ha_client or get_ha_client()
        self.check_interval = check_interval
        self.running = False
        self._start_time: datetime | None = None

        # Entity state cache for detecting state changes
        self._entity_states: dict[str, str] = {}

        # Statistics tracking
        self._stats = {
            "executions_success": 0,
            "executions_failed": 0,
            "check_cycles": 0,
            "state_checks": 0,
        }

        logger.info(f"AutomationScheduler initialized (check_interval={check_interval}s)")

    def _execute_automation(self, automation: dict[str, Any]) -> bool:
        """
        Execute an automation action.

        Args:
            automation: Automation dict with action_type and action_config

        Returns:
            True if action executed successfully
        """
        automation_id = automation.get("id", "unknown")
        automation_name = automation.get("name", "unnamed")
        trigger_type = automation.get("trigger_type", "unknown")
        action_type = automation.get("action_type")
        action_config = automation.get("action_config", {})

        logger.info(f"Executing automation {automation_id}: {automation_name} ({action_type})")

        try:
            if action_type == "agent_command":
                success = self._execute_agent_command(action_config)
            elif action_type == "ha_service":
                success = self._execute_ha_service(action_config)
            else:
                logger.error(f"Unknown action type: {action_type}")
                self._stats["executions_failed"] += 1
                self._send_automation_alert(
                    automation_id,
                    automation_name,
                    trigger_type,
                    action_type,
                    success=False,
                    error=f"Unknown action type: {action_type}",
                )
                return False

            # Send alert for execution result (WP-10.5)
            if success:
                self._send_automation_alert(
                    automation_id, automation_name, trigger_type, action_type, success=True
                )
            else:
                self._send_automation_alert(
                    automation_id,
                    automation_name,
                    trigger_type,
                    action_type,
                    success=False,
                    error="Action execution returned failure",
                )
            return success

        except Exception as error:
            logger.error(f"Error executing automation {automation_id}: {error}")
            self._stats["executions_failed"] += 1
            self._send_automation_alert(
                automation_id,
                automation_name,
                trigger_type,
                action_type,
                success=False,
                error=str(error),
            )
            return False

    def _send_automation_alert(
        self,
        automation_id: Any,
        automation_name: str,
        trigger_type: str,
        action_type: str,
        success: bool,
        error: str | None = None,
    ) -> None:
        """
        Send Slack alert for automation execution.

        Args:
            automation_id: ID of the automation
            automation_name: Name of the automation
            trigger_type: Type of trigger (time, state, presence)
            action_type: Type of action (agent_command, ha_service)
            success: Whether execution was successful
            error: Error message if failed
        """
        try:
            if success:
                send_health_alert(
                    title=f"Automation Executed: {automation_name}",
                    message=f"Successfully executed automation '{automation_name}'",
                    severity="info",
                    component="automation",
                    details={
                        "automation_id": automation_id,
                        "trigger_type": trigger_type,
                        "action_type": action_type,
                    },
                )
            else:
                send_health_alert(
                    title=f"Automation Failed: {automation_name}",
                    message=f"Failed to execute automation '{automation_name}': {error}",
                    severity="warning",
                    component="automation",
                    details={
                        "automation_id": automation_id,
                        "trigger_type": trigger_type,
                        "action_type": action_type,
                        "error": error,
                    },
                )
        except Exception as alert_error:
            logger.error(f"Failed to send automation alert: {alert_error}")

    def _execute_agent_command(self, action_config: dict[str, Any]) -> bool:
        """
        Execute an agent command action.

        Args:
            action_config: Config with 'command' key

        Returns:
            True if command executed successfully
        """
        command = action_config.get("command")
        if not command:
            logger.error("Agent command action missing 'command' key")
            self._stats["executions_failed"] += 1
            return False

        logger.info(f"Executing agent command: {command}")

        try:
            # Import here to avoid circular imports
            from agent import run_agent

            response = run_agent(command)
            logger.info(
                f"Agent command completed: {response[:100] if response else 'No response'}..."
            )
            self._stats["executions_success"] += 1
            return True
        except Exception as error:
            logger.error(f"Agent command failed: {error}")
            self._stats["executions_failed"] += 1
            return False

    def _execute_ha_service(self, action_config: dict[str, Any]) -> bool:
        """
        Execute a Home Assistant service call action.

        Args:
            action_config: Config with 'domain', 'service', and optional 'service_data'

        Returns:
            True if service call succeeded
        """
        domain = action_config.get("domain")
        service = action_config.get("service")
        service_data = action_config.get("service_data")

        if not domain or not service:
            logger.error("HA service action missing 'domain' or 'service' key")
            self._stats["executions_failed"] += 1
            return False

        logger.info(f"Calling HA service: {domain}.{service}")

        try:
            success = self.ha_client.call_service(
                domain=domain,
                service=service,
                service_data=service_data,
            )

            if success:
                logger.info(f"HA service call succeeded: {domain}.{service}")
                self._stats["executions_success"] += 1
            else:
                logger.error(f"HA service call failed: {domain}.{service}")
                self._stats["executions_failed"] += 1

            return success
        except Exception as error:
            logger.error(f"HA service call error: {error}")
            self._stats["executions_failed"] += 1
            return False

    def _process_time_triggers(self) -> int:
        """
        Process all due time-based automations.

        Returns:
            Number of automations processed successfully
        """
        processed = 0

        try:
            due_automations = self.automation_manager.get_due_automations()
        except Exception as error:
            logger.error(f"Error getting due automations: {error}")
            return 0

        for automation in due_automations:
            automation_id = automation.get("id")

            if self._execute_automation(automation):
                # Mark as triggered if execution succeeded
                self.automation_manager.mark_triggered(automation_id)
                processed += 1
            else:
                logger.warning(
                    f"Automation {automation_id} execution failed, will retry next cycle"
                )

        return processed

    def _process_state_triggers(self) -> int:
        """
        Process state-based automations by polling entity states.

        Compares current entity states to cached states and triggers
        automations when state changes match trigger conditions.

        Returns:
            Number of automations processed successfully
        """
        processed = 0
        self._stats["state_checks"] += 1

        try:
            # Get all enabled state and presence automations
            state_automations = self.automation_manager.get_automations(
                enabled_only=True, trigger_type="state"
            )
            presence_automations = self.automation_manager.get_automations(
                enabled_only=True, trigger_type="presence"
            )
            all_automations = state_automations + presence_automations
        except Exception as error:
            logger.error(f"Error getting state automations: {error}")
            return 0

        for automation in all_automations:
            trigger_config = automation.get("trigger_config", {})
            entity_id = trigger_config.get("entity_id")

            if not entity_id:
                continue

            # Get current state from HA
            try:
                current_state = self.ha_client.get_state(entity_id)
            except Exception as error:
                logger.warning(f"Error getting state for {entity_id}: {error}")
                continue

            # Get previous state from cache
            previous_state = self._entity_states.get(entity_id)

            # Update cache with current state
            self._entity_states[entity_id] = current_state

            # Skip if no previous state (first check)
            if previous_state is None:
                continue

            # Check if state changed
            if current_state == previous_state:
                continue

            # Check trigger conditions
            to_state = trigger_config.get("to_state")
            from_state = trigger_config.get("from_state")

            # Must match to_state if specified
            if to_state and current_state != to_state:
                continue

            # Must match from_state if specified
            if from_state and previous_state != from_state:
                continue

            # Trigger matches! Execute the automation
            logger.info(
                f"State trigger matched for automation {automation.get('id')}: "
                f"{entity_id} changed from {previous_state} to {current_state}"
            )

            if self._execute_automation(automation):
                self.automation_manager.mark_triggered(automation.get("id"))
                processed += 1

        return processed

    def process_automations(self) -> int:
        """
        Process all automation types.

        Returns:
            Total number of automations processed
        """
        total_processed = 0

        # Process time-based triggers
        time_processed = self._process_time_triggers()
        total_processed += time_processed

        if time_processed > 0:
            logger.info(f"Processed {time_processed} time-based automation(s)")

        # Process state-based triggers
        state_processed = self._process_state_triggers()
        total_processed += state_processed

        if state_processed > 0:
            logger.info(f"Processed {state_processed} state-based automation(s)")

        self._stats["check_cycles"] += 1
        return total_processed

    def run(self) -> None:
        """
        Start the scheduler loop.

        Runs until stopped via stop() or signal.
        """
        self.running = True
        self._start_time = datetime.now()
        logger.info("AutomationScheduler started")

        while self.running:
            try:
                processed = self.process_automations()
                if processed > 0:
                    logger.info(f"Processed {processed} automation(s) this cycle")
            except Exception as error:
                logger.error(f"Error processing automations: {error}")

            # Sleep in short intervals to allow for quick shutdown
            sleep_remaining = self.check_interval
            while sleep_remaining > 0 and self.running:
                sleep_time = min(sleep_remaining, 1.0)
                time.sleep(sleep_time)
                sleep_remaining -= sleep_time

        logger.info("AutomationScheduler stopped")

    def stop(self) -> None:
        """Stop the scheduler gracefully."""
        logger.info("Stopping AutomationScheduler...")
        self.running = False

    def register_signal_handlers(self) -> None:
        """Register signal handlers for graceful shutdown."""
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)
        logger.debug("Signal handlers registered (SIGTERM, SIGINT)")

    def _handle_shutdown(self, signum: int, frame: Any) -> None:
        """Handle shutdown signals."""
        sig_name = signal.Signals(signum).name
        logger.info(f"Received {sig_name}, initiating graceful shutdown")
        self.stop()

    def get_stats(self) -> dict[str, Any]:
        """
        Get scheduler statistics.

        Returns:
            Dictionary with execution and uptime stats
        """
        uptime_seconds = 0
        if self._start_time:
            uptime_seconds = (datetime.now() - self._start_time).total_seconds()

        return {
            "executions_success": self._stats["executions_success"],
            "executions_failed": self._stats["executions_failed"],
            "check_cycles": self._stats["check_cycles"],
            "state_checks": self._stats["state_checks"],
            "uptime_seconds": uptime_seconds,
            "running": self.running,
        }


# Singleton instance
_automation_scheduler: AutomationScheduler | None = None


def get_automation_scheduler() -> AutomationScheduler:
    """Get the singleton AutomationScheduler instance."""
    global _automation_scheduler
    if _automation_scheduler is None:
        _automation_scheduler = AutomationScheduler()
    return _automation_scheduler


def main() -> None:
    """Entry point for running the automation scheduler as a script."""
    from src.utils import setup_logging

    # Setup logging
    setup_logging("automation_scheduler")

    # Create and run scheduler
    scheduler = get_automation_scheduler()
    scheduler.register_signal_handlers()

    logger.info("Starting automation scheduler...")
    try:
        scheduler.run()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        scheduler.stop()
        logger.info("Automation scheduler shutdown complete")


if __name__ == "__main__":
    main()
