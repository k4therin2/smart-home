"""
Tests for ConversationManager - Multi-turn conversation state for voice automation.

WP-9.1: Conversational Automation Setup via Voice

The ConversationManager handles:
1. Storing conversation context between voice commands
2. Tracking automation creation state (collecting required fields)
3. Managing clarification dialogs
4. Expiring stale conversations
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

# Will be implemented in src/conversation_manager.py
from src.conversation_manager import (
    ConversationManager,
    ConversationState,
    AutomationDraft,
)


class TestConversationState:
    """Test conversation state enum and transitions."""

    def test_initial_state_is_idle(self):
        """New conversations start in IDLE state."""
        manager = ConversationManager()
        state = manager.get_state("conv-123")
        assert state == ConversationState.IDLE

    def test_state_transitions(self):
        """Verify valid state transitions."""
        # IDLE -> COLLECTING (user requests automation)
        # COLLECTING -> CONFIRMING (all required fields collected)
        # CONFIRMING -> IDLE (user confirms or cancels)
        assert ConversationState.IDLE.can_transition_to(ConversationState.COLLECTING)
        assert ConversationState.COLLECTING.can_transition_to(ConversationState.CONFIRMING)
        assert ConversationState.CONFIRMING.can_transition_to(ConversationState.IDLE)
        assert ConversationState.COLLECTING.can_transition_to(ConversationState.IDLE)  # Cancel


class TestAutomationDraft:
    """Test automation draft data structure."""

    def test_create_empty_draft(self):
        """Create an empty draft with no fields."""
        draft = AutomationDraft()
        assert draft.name is None
        assert draft.trigger_type is None
        assert draft.trigger_config == {}
        assert draft.action_command is None
        assert not draft.is_complete()

    def test_draft_with_time_trigger(self):
        """Create a draft with time trigger."""
        draft = AutomationDraft(
            name="evening lights",
            trigger_type="time",
            trigger_config={"time": "20:00", "days": ["mon", "tue", "wed", "thu", "fri"]},
            action_command="turn on living room lights at 80%"
        )
        assert draft.is_complete()

    def test_draft_missing_action_is_incomplete(self):
        """Draft without action command is incomplete."""
        draft = AutomationDraft(
            name="evening lights",
            trigger_type="time",
            trigger_config={"time": "20:00"},
        )
        assert not draft.is_complete()
        assert "action_command" in draft.missing_fields()

    def test_draft_missing_time_is_incomplete(self):
        """Time trigger without time config is incomplete."""
        draft = AutomationDraft(
            name="evening lights",
            trigger_type="time",
            trigger_config={},  # Missing "time" key
            action_command="turn on living room lights"
        )
        assert not draft.is_complete()
        assert "trigger_time" in draft.missing_fields()

    def test_draft_missing_name_is_incomplete(self):
        """Draft without name is incomplete (name can be auto-generated)."""
        draft = AutomationDraft(
            trigger_type="time",
            trigger_config={"time": "20:00"},
            action_command="turn on lights"
        )
        # Name is optional - will be auto-generated if not provided
        # So this should be complete
        assert draft.is_complete()

    def test_draft_to_automation_params(self):
        """Convert draft to automation creation parameters."""
        draft = AutomationDraft(
            name="evening lights",
            trigger_type="time",
            trigger_config={"time": "20:00", "days": ["mon", "tue", "wed", "thu", "fri"]},
            action_command="turn on living room lights"
        )
        params = draft.to_automation_params()
        assert params["name"] == "evening lights"
        assert params["trigger_type"] == "time"
        assert params["trigger_time"] == "20:00"
        assert params["trigger_days"] == ["mon", "tue", "wed", "thu", "fri"]
        assert params["action_command"] == "turn on living room lights"


class TestConversationManager:
    """Test conversation state management."""

    def test_start_automation_conversation(self):
        """Start a new automation creation conversation."""
        manager = ConversationManager()
        manager.start_automation("conv-123")

        state = manager.get_state("conv-123")
        assert state == ConversationState.COLLECTING

    def test_update_draft(self):
        """Update fields on an automation draft."""
        manager = ConversationManager()
        manager.start_automation("conv-123")

        manager.update_draft("conv-123", trigger_type="time")
        draft = manager.get_draft("conv-123")
        assert draft.trigger_type == "time"

    def test_update_multiple_fields(self):
        """Update multiple fields at once."""
        manager = ConversationManager()
        manager.start_automation("conv-123")

        manager.update_draft(
            "conv-123",
            trigger_type="time",
            trigger_config={"time": "20:00"},
            action_command="turn on lights"
        )

        draft = manager.get_draft("conv-123")
        assert draft.trigger_type == "time"
        assert draft.trigger_config["time"] == "20:00"
        assert draft.action_command == "turn on lights"

    def test_get_next_question(self):
        """Get the next clarifying question based on missing fields."""
        manager = ConversationManager()
        manager.start_automation("conv-123")

        # Empty draft - ask about action first
        question = manager.get_next_question("conv-123")
        assert question is not None
        assert "what" in question.lower() or "which" in question.lower()

    def test_get_next_question_with_partial_draft(self):
        """Get question for partially complete draft."""
        manager = ConversationManager()
        manager.start_automation("conv-123")
        manager.update_draft(
            "conv-123",
            trigger_type="time",
            action_command="turn off all lights"
        )

        # Missing time - should ask about time
        question = manager.get_next_question("conv-123")
        assert question is not None
        assert "time" in question.lower() or "when" in question.lower()

    def test_no_question_when_complete(self):
        """No question when draft is complete."""
        manager = ConversationManager()
        manager.start_automation("conv-123")
        manager.update_draft(
            "conv-123",
            trigger_type="time",
            trigger_config={"time": "20:00"},
            action_command="turn off all lights"
        )

        question = manager.get_next_question("conv-123")
        assert question is None

    def test_complete_automation_returns_confirmation(self):
        """Complete draft triggers confirmation request."""
        manager = ConversationManager()
        manager.start_automation("conv-123")
        manager.update_draft(
            "conv-123",
            name="night lights",
            trigger_type="time",
            trigger_config={"time": "23:00"},
            action_command="turn off all lights"
        )

        # Check if ready for confirmation
        assert manager.is_ready_for_confirmation("conv-123")
        confirmation = manager.get_confirmation_text("conv-123")
        # Check for either 11pm, 11:00pm, or 23:00
        assert "11" in confirmation.lower() and "pm" in confirmation.lower()
        assert "turn off" in confirmation.lower()

    def test_confirm_creates_automation(self):
        """Confirming a complete draft creates the automation."""
        manager = ConversationManager()
        manager.start_automation("conv-123")
        manager.update_draft(
            "conv-123",
            name="night lights",
            trigger_type="time",
            trigger_config={"time": "23:00"},
            action_command="turn off all lights"
        )

        with patch("src.conversation_manager.create_automation") as mock_create:
            mock_create.return_value = {"success": True, "automation_id": 1}
            result = manager.confirm("conv-123")

            mock_create.assert_called_once()
            assert result["success"] is True

    def test_cancel_clears_state(self):
        """Canceling clears conversation state."""
        manager = ConversationManager()
        manager.start_automation("conv-123")
        manager.update_draft("conv-123", trigger_type="time")

        manager.cancel("conv-123")

        assert manager.get_state("conv-123") == ConversationState.IDLE
        assert manager.get_draft("conv-123") is None

    def test_conversation_expires(self):
        """Conversations expire after timeout."""
        manager = ConversationManager(timeout_minutes=5)
        manager.start_automation("conv-123")

        # Mock time passage
        with patch.object(manager, "_get_now") as mock_now:
            mock_now.return_value = datetime.now() + timedelta(minutes=10)

            state = manager.get_state("conv-123")
            assert state == ConversationState.IDLE  # Expired

    def test_get_context_for_agent(self):
        """Get conversation context to prepend to agent prompt."""
        manager = ConversationManager()
        manager.start_automation("conv-123")
        manager.update_draft(
            "conv-123",
            trigger_type="time",
            trigger_config={"time": "20:00"},
        )

        context = manager.get_context("conv-123")
        assert "automation" in context.lower()
        assert "20:00" in context or "8pm" in context.lower()


class TestConversationParsing:
    """Test parsing user responses in conversation context."""

    def test_parse_time_response(self):
        """Parse user's time response."""
        manager = ConversationManager()
        manager.start_automation("conv-123")
        manager.update_draft("conv-123", action_command="turn off lights")

        # User says "at 10pm every night"
        updates = manager.parse_response("conv-123", "at 10pm every night")
        assert updates.get("trigger_type") == "time"
        assert updates.get("trigger_config", {}).get("time") == "22:00"

    def test_parse_device_response(self):
        """Parse user's device/room response."""
        manager = ConversationManager()
        manager.start_automation("conv-123")

        # Context: We're building an automation with existing action
        manager.update_draft("conv-123", action_command="turn on lights")

        # User says "the living room lights" to specify which lights
        updates = manager.parse_response("conv-123", "the living room lights")
        # The action_command should be updated to include the room
        assert "living room" in updates.get("action_command", "").lower()

    def test_parse_confirmation_yes(self):
        """Parse yes/confirm responses."""
        manager = ConversationManager()
        manager.start_automation("conv-123")
        manager.update_draft(
            "conv-123",
            trigger_type="time",
            trigger_config={"time": "22:00"},
            action_command="turn off lights"
        )
        manager.transition_to_confirming("conv-123")

        assert manager.is_confirmation_response("yes")
        assert manager.is_confirmation_response("yes, that's right")
        assert manager.is_confirmation_response("confirm")
        assert manager.is_confirmation_response("sounds good")

    def test_parse_confirmation_no(self):
        """Parse no/cancel responses."""
        manager = ConversationManager()

        assert manager.is_cancel_response("no")
        assert manager.is_cancel_response("cancel")
        assert manager.is_cancel_response("never mind")
        assert manager.is_cancel_response("stop")

    def test_parse_generic_lights_command(self):
        """When user says 'the lights' without room, accept it as 'all lights'."""
        manager = ConversationManager()
        manager.start_automation("conv-123")

        # User says "turn on the lights" - interpret as "all lights"
        updates = manager.parse_response("conv-123", "turn on the lights")

        # Should capture the action command as-is (we can ask for clarification later)
        assert "turn on" in updates.get("action_command", "").lower()


class TestConversationIntegration:
    """Test end-to-end conversation flows."""

    def test_simple_automation_flow(self):
        """Test simple automation creation flow.

        User: "Make a new automation to turn off lights at 10pm"
        System: "I'll turn off all lights at 10pm every day. Is that right?"
        User: "Yes"
        System: "Created automation 'Evening lights off'."
        """
        manager = ConversationManager()

        # First message starts the flow
        result = manager.process_message(
            "conv-123",
            "make a new automation to turn off lights at 10pm"
        )

        # Should ask for confirmation
        assert "confirm" in result["type"] or "clarify" in result["type"]

        if result["type"] == "confirm":
            # Confirm
            result = manager.process_message("conv-123", "yes")
            assert result["type"] == "success"
        else:
            # Need more info, then confirm
            pass

    def test_clarification_flow(self):
        """Test flow with clarification questions.

        User: "Create an automation that turns off lights"
        System: "At what time should I turn off the lights?"
        User: "10pm"
        System: "Which lights? You have Living Room, Bedroom, Kitchen."
        User: "All of them"
        System: "I'll turn off all lights at 10pm. Confirm?"
        User: "Yes"
        """
        manager = ConversationManager()

        # Incomplete request
        result = manager.process_message(
            "conv-123",
            "create an automation that turns off lights"
        )

        assert result["type"] == "clarify"
        assert "question" in result

    def test_multi_turn_state_persists(self):
        """Conversation state persists across multiple calls."""
        manager = ConversationManager()

        # Turn 1: Start
        manager.process_message("conv-123", "create automation to turn off lights")
        state_1 = manager.get_state("conv-123")

        # Turn 2: Add time
        manager.process_message("conv-123", "at 10pm")
        state_2 = manager.get_state("conv-123")

        # State should still be COLLECTING or CONFIRMING
        assert state_2 != ConversationState.IDLE

        # Draft should have accumulated info
        draft = manager.get_draft("conv-123")
        assert draft.trigger_config.get("time") == "22:00"

    def test_different_conversations_isolated(self):
        """Different conversation IDs have separate state."""
        manager = ConversationManager()

        manager.start_automation("conv-1")
        manager.update_draft("conv-1", action_command="turn on lights")

        manager.start_automation("conv-2")
        manager.update_draft("conv-2", action_command="start vacuum")

        draft_1 = manager.get_draft("conv-1")
        draft_2 = manager.get_draft("conv-2")

        assert "lights" in draft_1.action_command
        assert "vacuum" in draft_2.action_command
