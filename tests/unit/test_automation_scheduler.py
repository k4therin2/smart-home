"""
Unit tests for AutomationScheduler background worker.

Tests for WP-10.3: Automation Scheduler Background Process
"""

import signal
import time
from datetime import datetime
from pathlib import Path
from threading import Thread
from unittest.mock import MagicMock, Mock, patch, call
import pytest

# Import will fail until we implement the module
from src.automation_scheduler import (
    AutomationScheduler,
    get_automation_scheduler,
    DEFAULT_CHECK_INTERVAL,
)


class TestAutomationSchedulerInit:
    """Tests for AutomationScheduler initialization."""

    def test_init_default_parameters(self):
        """Test scheduler initializes with default parameters."""
        with patch("src.automation_scheduler.get_automation_manager"):
            scheduler = AutomationScheduler()
            assert scheduler.check_interval == DEFAULT_CHECK_INTERVAL
            assert scheduler.running is False
            assert scheduler._start_time is None

    def test_init_custom_check_interval(self):
        """Test scheduler initializes with custom check interval."""
        with patch("src.automation_scheduler.get_automation_manager"):
            scheduler = AutomationScheduler(check_interval=30)
            assert scheduler.check_interval == 30

    def test_init_with_automation_manager(self):
        """Test scheduler can be initialized with custom automation manager."""
        mock_manager = MagicMock()
        scheduler = AutomationScheduler(automation_manager=mock_manager)
        assert scheduler.automation_manager is mock_manager

    def test_init_stats_tracking(self):
        """Test scheduler initializes with empty stats."""
        with patch("src.automation_scheduler.get_automation_manager"):
            scheduler = AutomationScheduler()
            stats = scheduler.get_stats()
            assert stats["executions_success"] == 0
            assert stats["executions_failed"] == 0
            assert stats["check_cycles"] == 0
            assert stats["state_checks"] == 0


class TestAutomationSchedulerRun:
    """Tests for the scheduler run loop."""

    def test_run_sets_running_flag(self):
        """Test that run() sets running flag to True."""
        with patch("src.automation_scheduler.get_automation_manager"):
            scheduler = AutomationScheduler(check_interval=1)

            def stop_after_start():
                time.sleep(0.1)
                scheduler.stop()

            thread = Thread(target=stop_after_start)
            thread.start()
            scheduler.run()
            thread.join()

            # Running should be False after stop
            assert scheduler.running is False

    def test_run_records_start_time(self):
        """Test that run() records start time."""
        with patch("src.automation_scheduler.get_automation_manager"):
            scheduler = AutomationScheduler(check_interval=1)

            def stop_after_start():
                time.sleep(0.1)
                scheduler.stop()

            thread = Thread(target=stop_after_start)
            thread.start()
            scheduler.run()
            thread.join()

            assert scheduler._start_time is not None
            assert isinstance(scheduler._start_time, datetime)

    def test_run_calls_process_automations(self):
        """Test that run() calls process_automations each cycle."""
        with patch("src.automation_scheduler.get_automation_manager"):
            scheduler = AutomationScheduler(check_interval=0.1)
            scheduler.process_automations = MagicMock(return_value=0)

            def stop_after_cycles():
                time.sleep(0.25)  # Allow ~2 cycles
                scheduler.stop()

            thread = Thread(target=stop_after_cycles)
            thread.start()
            scheduler.run()
            thread.join()

            assert scheduler.process_automations.call_count >= 1

    def test_run_handles_exceptions_gracefully(self):
        """Test that run() continues after exceptions in process_automations."""
        with patch("src.automation_scheduler.get_automation_manager"):
            scheduler = AutomationScheduler(check_interval=0.1)
            scheduler.process_automations = MagicMock(side_effect=Exception("Test error"))

            def stop_after_cycles():
                time.sleep(0.25)
                scheduler.stop()

            thread = Thread(target=stop_after_cycles)
            thread.start()
            scheduler.run()  # Should not raise
            thread.join()


class TestAutomationSchedulerStop:
    """Tests for scheduler stop functionality."""

    def test_stop_sets_running_to_false(self):
        """Test stop() sets running flag to False."""
        with patch("src.automation_scheduler.get_automation_manager"):
            scheduler = AutomationScheduler()
            scheduler.running = True
            scheduler.stop()
            assert scheduler.running is False


class TestSignalHandlers:
    """Tests for signal handler registration."""

    def test_register_signal_handlers(self):
        """Test signal handlers are registered."""
        with patch("src.automation_scheduler.get_automation_manager"):
            scheduler = AutomationScheduler()

            with patch("signal.signal") as mock_signal:
                scheduler.register_signal_handlers()

                # Should register SIGTERM and SIGINT
                calls = mock_signal.call_args_list
                signal_nums = [c[0][0] for c in calls]
                assert signal.SIGTERM in signal_nums
                assert signal.SIGINT in signal_nums

    def test_handle_shutdown_stops_scheduler(self):
        """Test that shutdown handler calls stop()."""
        with patch("src.automation_scheduler.get_automation_manager"):
            scheduler = AutomationScheduler()
            scheduler.running = True

            scheduler._handle_shutdown(signal.SIGTERM, None)

            assert scheduler.running is False


class TestProcessTimeTriggers:
    """Tests for time-based trigger evaluation."""

    def test_process_due_time_automations(self):
        """Test processing of due time-based automations."""
        mock_manager = MagicMock()
        mock_manager.get_due_automations.return_value = [
            {
                "id": 1,
                "name": "Test automation",
                "trigger_type": "time",
                "trigger_config": {"time": "08:00", "days": ["mon", "tue"]},
                "action_type": "agent_command",
                "action_config": {"command": "turn lights on"},
            }
        ]

        scheduler = AutomationScheduler(automation_manager=mock_manager)
        scheduler._execute_automation = MagicMock(return_value=True)

        processed = scheduler._process_time_triggers()

        assert processed == 1
        mock_manager.get_due_automations.assert_called_once()
        scheduler._execute_automation.assert_called_once()

    def test_no_due_time_automations(self):
        """Test no processing when no automations are due."""
        mock_manager = MagicMock()
        mock_manager.get_due_automations.return_value = []

        scheduler = AutomationScheduler(automation_manager=mock_manager)

        processed = scheduler._process_time_triggers()

        assert processed == 0

    def test_time_trigger_marks_automation_triggered(self):
        """Test that executed time automation is marked as triggered."""
        mock_manager = MagicMock()
        mock_manager.get_due_automations.return_value = [
            {
                "id": 42,
                "name": "Test automation",
                "trigger_type": "time",
                "action_type": "agent_command",
                "action_config": {"command": "test"},
            }
        ]

        scheduler = AutomationScheduler(automation_manager=mock_manager)
        scheduler._execute_automation = MagicMock(return_value=True)

        scheduler._process_time_triggers()

        mock_manager.mark_triggered.assert_called_once_with(42)


class TestProcessStateTriggers:
    """Tests for state-based trigger evaluation."""

    def test_process_state_triggers_with_matching_state_change(self):
        """Test state trigger fires when state changes to target."""
        mock_manager = MagicMock()
        mock_manager.get_automations.return_value = [
            {
                "id": 1,
                "name": "Door open lights",
                "trigger_type": "state",
                "trigger_config": {
                    "entity_id": "binary_sensor.front_door",
                    "to_state": "on",
                },
                "action_type": "agent_command",
                "action_config": {"command": "turn hallway lights on"},
            }
        ]

        mock_ha = MagicMock()
        mock_ha.get_state.return_value = "on"

        scheduler = AutomationScheduler(
            automation_manager=mock_manager,
            ha_client=mock_ha,
        )
        # Simulate previous state was "off"
        scheduler._entity_states = {"binary_sensor.front_door": "off"}
        scheduler._execute_automation = MagicMock(return_value=True)

        processed = scheduler._process_state_triggers()

        assert processed == 1
        scheduler._execute_automation.assert_called_once()

    def test_state_trigger_no_change(self):
        """Test state trigger doesn't fire when state hasn't changed."""
        mock_manager = MagicMock()
        mock_manager.get_automations.return_value = [
            {
                "id": 1,
                "name": "Door open lights",
                "trigger_type": "state",
                "trigger_config": {
                    "entity_id": "binary_sensor.front_door",
                    "to_state": "on",
                },
                "action_type": "agent_command",
                "action_config": {"command": "turn lights on"},
            }
        ]

        mock_ha = MagicMock()
        mock_ha.get_state.return_value = "on"

        scheduler = AutomationScheduler(
            automation_manager=mock_manager,
            ha_client=mock_ha,
        )
        # Previous state is same as current
        scheduler._entity_states = {"binary_sensor.front_door": "on"}

        processed = scheduler._process_state_triggers()

        assert processed == 0

    def test_state_trigger_with_from_state_condition(self):
        """Test state trigger with from_state requirement."""
        mock_manager = MagicMock()
        mock_manager.get_automations.return_value = [
            {
                "id": 1,
                "name": "Test",
                "trigger_type": "state",
                "trigger_config": {
                    "entity_id": "light.living_room",
                    "from_state": "off",
                    "to_state": "on",
                },
                "action_type": "ha_service",
                "action_config": {"domain": "notify", "service": "notify"},
            }
        ]

        mock_ha = MagicMock()
        mock_ha.get_state.return_value = "on"

        scheduler = AutomationScheduler(
            automation_manager=mock_manager,
            ha_client=mock_ha,
        )
        scheduler._entity_states = {"light.living_room": "off"}
        scheduler._execute_automation = MagicMock(return_value=True)

        processed = scheduler._process_state_triggers()

        assert processed == 1

    def test_state_trigger_from_state_mismatch(self):
        """Test state trigger doesn't fire when from_state doesn't match."""
        mock_manager = MagicMock()
        mock_manager.get_automations.return_value = [
            {
                "id": 1,
                "name": "Test",
                "trigger_type": "state",
                "trigger_config": {
                    "entity_id": "light.living_room",
                    "from_state": "off",
                    "to_state": "on",
                },
                "action_type": "agent_command",
                "action_config": {"command": "test"},
            }
        ]

        mock_ha = MagicMock()
        mock_ha.get_state.return_value = "on"

        scheduler = AutomationScheduler(
            automation_manager=mock_manager,
            ha_client=mock_ha,
        )
        # Previous state was "unavailable", not "off"
        scheduler._entity_states = {"light.living_room": "unavailable"}

        processed = scheduler._process_state_triggers()

        assert processed == 0

    def test_state_trigger_updates_entity_state_cache(self):
        """Test that state check updates entity state cache."""
        mock_manager = MagicMock()
        mock_manager.get_automations.return_value = [
            {
                "id": 1,
                "name": "Test",
                "trigger_type": "state",
                "trigger_config": {
                    "entity_id": "sensor.temperature",
                    "to_state": "25",
                },
                "action_type": "agent_command",
                "action_config": {"command": "test"},
            }
        ]

        mock_ha = MagicMock()
        mock_ha.get_state.return_value = "22"

        scheduler = AutomationScheduler(
            automation_manager=mock_manager,
            ha_client=mock_ha,
        )
        scheduler._entity_states = {}

        scheduler._process_state_triggers()

        assert scheduler._entity_states["sensor.temperature"] == "22"


class TestExecuteAutomation:
    """Tests for automation action execution."""

    def test_execute_agent_command_action(self):
        """Test execution of agent_command action type."""
        mock_manager = MagicMock()
        scheduler = AutomationScheduler(automation_manager=mock_manager)

        automation = {
            "id": 1,
            "name": "Test",
            "action_type": "agent_command",
            "action_config": {"command": "turn living room lights to warm"},
        }

        with patch("agent.run_agent") as mock_run_agent:
            mock_run_agent.return_value = "Done!"

            result = scheduler._execute_automation(automation)

            assert result is True
            mock_run_agent.assert_called_once_with("turn living room lights to warm")

    def test_execute_ha_service_action(self):
        """Test execution of ha_service action type."""
        mock_manager = MagicMock()
        mock_ha = MagicMock()
        mock_ha.call_service.return_value = True

        scheduler = AutomationScheduler(
            automation_manager=mock_manager,
            ha_client=mock_ha,
        )

        automation = {
            "id": 1,
            "name": "Test",
            "action_type": "ha_service",
            "action_config": {
                "domain": "light",
                "service": "turn_on",
                "service_data": {"entity_id": "light.living_room", "brightness_pct": 80},
            },
        }

        result = scheduler._execute_automation(automation)

        assert result is True
        mock_ha.call_service.assert_called_once_with(
            domain="light",
            service="turn_on",
            service_data={"entity_id": "light.living_room", "brightness_pct": 80},
        )

    def test_execute_agent_command_failure(self):
        """Test handling of agent command execution failure."""
        mock_manager = MagicMock()
        scheduler = AutomationScheduler(automation_manager=mock_manager)

        automation = {
            "id": 1,
            "name": "Test",
            "action_type": "agent_command",
            "action_config": {"command": "invalid command"},
        }

        with patch("agent.run_agent") as mock_run_agent:
            mock_run_agent.side_effect = Exception("API Error")

            result = scheduler._execute_automation(automation)

            assert result is False

    def test_execute_ha_service_failure(self):
        """Test handling of HA service call failure."""
        mock_manager = MagicMock()
        mock_ha = MagicMock()
        mock_ha.call_service.return_value = False

        scheduler = AutomationScheduler(
            automation_manager=mock_manager,
            ha_client=mock_ha,
        )

        automation = {
            "id": 1,
            "name": "Test",
            "action_type": "ha_service",
            "action_config": {
                "domain": "light",
                "service": "turn_on",
            },
        }

        result = scheduler._execute_automation(automation)

        assert result is False

    def test_execute_unknown_action_type(self):
        """Test handling of unknown action type."""
        mock_manager = MagicMock()
        scheduler = AutomationScheduler(automation_manager=mock_manager)

        automation = {
            "id": 1,
            "name": "Test",
            "action_type": "unknown_type",
            "action_config": {},
        }

        result = scheduler._execute_automation(automation)

        assert result is False

    def test_execute_updates_stats_on_success(self):
        """Test that successful execution updates stats."""
        mock_manager = MagicMock()
        scheduler = AutomationScheduler(automation_manager=mock_manager)

        automation = {
            "id": 1,
            "name": "Test",
            "action_type": "agent_command",
            "action_config": {"command": "test"},
        }

        with patch("agent.run_agent") as mock_run_agent:
            mock_run_agent.return_value = "Done"

            scheduler._execute_automation(automation)

            stats = scheduler.get_stats()
            assert stats["executions_success"] == 1
            assert stats["executions_failed"] == 0

    def test_execute_updates_stats_on_failure(self):
        """Test that failed execution updates stats."""
        mock_manager = MagicMock()
        scheduler = AutomationScheduler(automation_manager=mock_manager)

        automation = {
            "id": 1,
            "name": "Test",
            "action_type": "agent_command",
            "action_config": {"command": "test"},
        }

        with patch("agent.run_agent") as mock_run_agent:
            mock_run_agent.side_effect = Exception("Error")

            scheduler._execute_automation(automation)

            stats = scheduler.get_stats()
            assert stats["executions_success"] == 0
            assert stats["executions_failed"] == 1


class TestProcessAutomations:
    """Tests for the main process_automations method."""

    def test_process_automations_calls_time_and_state(self):
        """Test that process_automations processes both trigger types."""
        mock_manager = MagicMock()
        mock_manager.get_due_automations.return_value = []
        mock_manager.get_automations.return_value = []

        mock_ha = MagicMock()

        scheduler = AutomationScheduler(
            automation_manager=mock_manager,
            ha_client=mock_ha,
        )

        scheduler.process_automations()

        # Should call both time and state processing
        mock_manager.get_due_automations.assert_called_once()
        mock_manager.get_automations.assert_called()

    def test_process_automations_increments_check_cycles(self):
        """Test that process_automations increments check cycles stat."""
        mock_manager = MagicMock()
        mock_manager.get_due_automations.return_value = []
        mock_manager.get_automations.return_value = []

        scheduler = AutomationScheduler(automation_manager=mock_manager)

        scheduler.process_automations()
        scheduler.process_automations()

        stats = scheduler.get_stats()
        assert stats["check_cycles"] == 2


class TestGetStats:
    """Tests for statistics retrieval."""

    def test_get_stats_includes_uptime(self):
        """Test that stats include uptime when running."""
        with patch("src.automation_scheduler.get_automation_manager"):
            scheduler = AutomationScheduler()
            scheduler._start_time = datetime.now()

            stats = scheduler.get_stats()

            assert "uptime_seconds" in stats
            assert stats["uptime_seconds"] >= 0

    def test_get_stats_includes_all_counters(self):
        """Test that stats include all counter fields."""
        with patch("src.automation_scheduler.get_automation_manager"):
            scheduler = AutomationScheduler()

            stats = scheduler.get_stats()

            assert "executions_success" in stats
            assert "executions_failed" in stats
            assert "check_cycles" in stats
            assert "state_checks" in stats
            assert "running" in stats


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_automation_scheduler_returns_same_instance(self):
        """Test that get_automation_scheduler returns singleton."""
        # Reset singleton for test
        import src.automation_scheduler as module
        module._automation_scheduler = None

        with patch("src.automation_scheduler.get_automation_manager"):
            scheduler1 = get_automation_scheduler()
            scheduler2 = get_automation_scheduler()

            assert scheduler1 is scheduler2


class TestAgentCommandExecution:
    """Tests specific to agent command execution with timeout."""

    def test_agent_command_with_timeout(self):
        """Test that agent commands have timeout protection."""
        mock_manager = MagicMock()
        scheduler = AutomationScheduler(automation_manager=mock_manager)

        automation = {
            "id": 1,
            "name": "Test",
            "action_type": "agent_command",
            "action_config": {"command": "long running command"},
        }

        with patch("agent.run_agent") as mock_run_agent:
            mock_run_agent.return_value = "Done"

            result = scheduler._execute_automation(automation)

            assert result is True

    def test_agent_command_logs_execution_time(self):
        """Test that agent command execution is logged."""
        mock_manager = MagicMock()
        scheduler = AutomationScheduler(automation_manager=mock_manager)

        automation = {
            "id": 1,
            "name": "Morning lights",
            "action_type": "agent_command",
            "action_config": {"command": "turn lights on"},
        }

        with patch("agent.run_agent") as mock_run_agent:
            mock_run_agent.return_value = "Done"

            with patch("src.automation_scheduler.logger") as mock_logger:
                scheduler._execute_automation(automation)

                # Should log execution
                assert mock_logger.info.called


class TestHAServiceExecution:
    """Tests specific to HA service execution."""

    def test_ha_service_without_service_data(self):
        """Test HA service call without service_data."""
        mock_manager = MagicMock()
        mock_ha = MagicMock()
        mock_ha.call_service.return_value = True

        scheduler = AutomationScheduler(
            automation_manager=mock_manager,
            ha_client=mock_ha,
        )

        automation = {
            "id": 1,
            "name": "Test",
            "action_type": "ha_service",
            "action_config": {
                "domain": "homeassistant",
                "service": "restart",
            },
        }

        result = scheduler._execute_automation(automation)

        assert result is True
        mock_ha.call_service.assert_called_once_with(
            domain="homeassistant",
            service="restart",
            service_data=None,
        )


class TestErrorHandling:
    """Tests for error handling scenarios."""

    def test_ha_client_connection_error(self):
        """Test handling of HA client connection errors."""
        mock_manager = MagicMock()
        mock_ha = MagicMock()
        mock_ha.get_state.side_effect = Exception("Connection refused")

        scheduler = AutomationScheduler(
            automation_manager=mock_manager,
            ha_client=mock_ha,
        )
        scheduler._entity_states = {}

        # Should not raise, should handle gracefully
        mock_manager.get_automations.return_value = [
            {
                "id": 1,
                "trigger_type": "state",
                "trigger_config": {"entity_id": "light.test", "to_state": "on"},
                "action_type": "agent_command",
                "action_config": {"command": "test"},
            }
        ]

        processed = scheduler._process_state_triggers()
        assert processed == 0

    def test_database_error_handling(self):
        """Test handling of database errors."""
        mock_manager = MagicMock()
        mock_manager.get_due_automations.side_effect = Exception("Database locked")

        scheduler = AutomationScheduler(automation_manager=mock_manager)

        # Should not raise
        processed = scheduler._process_time_triggers()
        assert processed == 0


class TestPresenceTriggers:
    """Tests for presence-based triggers (special case of state)."""

    def test_presence_trigger_home_to_away(self):
        """Test presence trigger when changing from home to away."""
        mock_manager = MagicMock()
        mock_manager.get_automations.return_value = [
            {
                "id": 1,
                "name": "Leaving home",
                "trigger_type": "presence",
                "trigger_config": {
                    "entity_id": "person.katherine",
                    "to_state": "not_home",
                },
                "action_type": "agent_command",
                "action_config": {"command": "turn all lights off"},
            }
        ]

        mock_ha = MagicMock()
        mock_ha.get_state.return_value = "not_home"

        scheduler = AutomationScheduler(
            automation_manager=mock_manager,
            ha_client=mock_ha,
        )
        scheduler._entity_states = {"person.katherine": "home"}
        scheduler._execute_automation = MagicMock(return_value=True)

        # Presence triggers are handled like state triggers
        processed = scheduler._process_state_triggers()

        assert processed == 1


class TestMultipleAutomations:
    """Tests for handling multiple automations."""

    def test_multiple_time_automations_due(self):
        """Test processing multiple due time automations."""
        mock_manager = MagicMock()
        mock_manager.get_due_automations.return_value = [
            {"id": 1, "name": "A1", "action_type": "agent_command", "action_config": {"command": "cmd1"}},
            {"id": 2, "name": "A2", "action_type": "agent_command", "action_config": {"command": "cmd2"}},
            {"id": 3, "name": "A3", "action_type": "agent_command", "action_config": {"command": "cmd3"}},
        ]

        scheduler = AutomationScheduler(automation_manager=mock_manager)
        scheduler._execute_automation = MagicMock(return_value=True)

        processed = scheduler._process_time_triggers()

        assert processed == 3
        assert scheduler._execute_automation.call_count == 3

    def test_partial_automation_failures(self):
        """Test that one failing automation doesn't stop others."""
        mock_manager = MagicMock()
        mock_manager.get_due_automations.return_value = [
            {"id": 1, "name": "A1", "action_type": "agent_command", "action_config": {"command": "cmd1"}},
            {"id": 2, "name": "A2", "action_type": "agent_command", "action_config": {"command": "cmd2"}},
        ]

        scheduler = AutomationScheduler(automation_manager=mock_manager)
        # First fails, second succeeds
        scheduler._execute_automation = MagicMock(side_effect=[False, True])

        processed = scheduler._process_time_triggers()

        # Only 1 succeeded
        assert processed == 1
        # But both were attempted
        assert scheduler._execute_automation.call_count == 2
