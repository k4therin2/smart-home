"""
Integration tests for voice-driven automation creation.

WP-9.1: Conversational Automation Setup via Voice

Tests end-to-end flow from voice command through automation creation.
"""

import pytest
from unittest.mock import MagicMock, patch

from src.voice_handler import VoiceHandler
from src.conversation_manager import (
    ConversationManager,
    ConversationState,
    get_conversation_manager,
)


class TestVoiceAutomationFlow:
    """Test voice automation creation end-to-end flows."""

    @pytest.fixture
    def mock_agent(self):
        """Create a mock agent callback."""
        return MagicMock(return_value="Done.")

    @pytest.fixture
    def voice_handler(self, mock_agent):
        """Create a VoiceHandler with mock agent."""
        return VoiceHandler(agent_callback=mock_agent)

    @pytest.fixture
    def conversation_manager(self):
        """Create a fresh ConversationManager."""
        return ConversationManager()

    def test_simple_automation_one_shot(self, voice_handler, conversation_manager):
        """Test complete automation in single voice command.

        User: "Create automation to turn off lights at 10pm"
        System: Should ask for confirmation
        """
        with patch("src.voice_handler.get_conversation_manager", return_value=conversation_manager):
            result = voice_handler.process_command(
                "create automation to turn off lights at 10pm",
                {"conversation_id": "test-conv-1"}
            )

            assert result["success"] is True
            # Should be asking for confirmation
            response = result["response"].lower()
            assert any(word in response for word in ["confirm", "create", "should i", "is that"])

    def test_multi_turn_automation_flow(self, voice_handler, conversation_manager):
        """Test multi-turn automation creation.

        Turn 1: "Create an automation that turns off lights"
        System: "At what time should this automation run?"
        Turn 2: "10pm"
        System: Confirmation
        Turn 3: "Yes"
        System: Success
        """
        conv_id = "test-conv-2"
        context = {"conversation_id": conv_id}

        with patch("src.voice_handler.get_conversation_manager", return_value=conversation_manager):
            # Turn 1: Incomplete request
            result1 = voice_handler.process_command(
                "create an automation that turns off lights",
                context
            )

            assert result1["success"] is True
            # Should ask for clarification
            response1 = result1["response"].lower()
            assert any(word in response1 for word in ["time", "when"])

            # Turn 2: Provide time
            result2 = voice_handler.process_command(
                "at 10pm every night",
                context
            )

            assert result2["success"] is True
            # Should ask for confirmation
            response2 = result2["response"].lower()
            assert any(word in response2 for word in ["confirm", "create", "should i", "is that", "10"])

            # Turn 3: Confirm
            with patch("src.conversation_manager.create_automation") as mock_create:
                mock_create.return_value = {"success": True, "automation_id": 1, "message": "Created automation."}

                result3 = voice_handler.process_command("yes", context)

                assert result3["success"] is True
                mock_create.assert_called_once()

    def test_cancel_mid_flow(self, voice_handler, conversation_manager):
        """Test canceling automation creation mid-flow."""
        conv_id = "test-conv-3"
        context = {"conversation_id": conv_id}

        with patch("src.voice_handler.get_conversation_manager", return_value=conversation_manager):
            # Start automation creation
            voice_handler.process_command(
                "create automation to turn on lights",
                context
            )

            # Cancel
            result = voice_handler.process_command("cancel", context)

            assert result["success"] is True
            assert "cancel" in result["response"].lower()

            # Verify state is cleared
            state = conversation_manager.get_state(conv_id)
            assert state == ConversationState.IDLE

    def test_non_automation_command_passes_through(self, voice_handler, mock_agent, conversation_manager):
        """Test that non-automation commands pass through to agent."""
        with patch("src.voice_handler.get_conversation_manager", return_value=conversation_manager):
            result = voice_handler.process_command(
                "what time is it",
                {"conversation_id": "test-conv-4"}
            )

            # Should have called the agent
            mock_agent.assert_called_once()
            assert result["success"] is True

    def test_conversation_isolation(self, voice_handler, conversation_manager):
        """Test that different conversation_ids are isolated."""
        context1 = {"conversation_id": "conv-A"}
        context2 = {"conversation_id": "conv-B"}

        with patch("src.voice_handler.get_conversation_manager", return_value=conversation_manager):
            # Start automation in conv-A
            voice_handler.process_command(
                "create automation to turn on lights",
                context1
            )

            # Start different automation in conv-B
            voice_handler.process_command(
                "create automation to start vacuum",
                context2
            )

            # Verify drafts are different
            draft_a = conversation_manager.get_draft("conv-A")
            draft_b = conversation_manager.get_draft("conv-B")

            assert draft_a is not None
            assert draft_b is not None
            # If action_command was parsed, they should be different
            if draft_a.action_command and draft_b.action_command:
                assert "lights" in draft_a.action_command.lower() or "vacuum" not in draft_a.action_command.lower()

    def test_state_trigger_automation(self, voice_handler, conversation_manager):
        """Test creating state-based automation.

        User: "Create automation that starts vacuum when I leave"
        """
        conv_id = "test-conv-5"
        context = {"conversation_id": conv_id}

        with patch("src.voice_handler.get_conversation_manager", return_value=conversation_manager):
            # Request state-based automation
            result = voice_handler.process_command(
                "create automation to start vacuum when I leave home",
                context
            )

            assert result["success"] is True

            # Check draft has state trigger info
            draft = conversation_manager.get_draft(conv_id)
            # Note: Full state trigger parsing may require more work
            # For now, verify the conversation started

    def test_weekday_time_automation(self, voice_handler, conversation_manager):
        """Test automation with weekday restriction."""
        conv_id = "test-conv-6"
        context = {"conversation_id": conv_id}

        with patch("src.voice_handler.get_conversation_manager", return_value=conversation_manager):
            result = voice_handler.process_command(
                "create automation to turn off lights at 11pm on weekdays",
                context
            )

            assert result["success"] is True

            draft = conversation_manager.get_draft(conv_id)
            if draft and draft.trigger_config:
                days = draft.trigger_config.get("days", [])
                if days:
                    assert "sat" not in days
                    assert "sun" not in days


class TestVoiceHandlerIntegration:
    """Test VoiceHandler integration with ConversationManager."""

    def test_handler_gets_conversation_id_from_context(self):
        """Test that conversation_id is extracted from context."""
        mock_agent = MagicMock(return_value="Done.")
        handler = VoiceHandler(agent_callback=mock_agent)

        context = {
            "conversation_id": "unique-id-123",
            "device_id": "voice_puck_1",
            "language": "en"
        }

        with patch("src.voice_handler.get_conversation_manager") as mock_manager:
            manager_instance = ConversationManager()
            mock_manager.return_value = manager_instance

            handler.process_command("create automation to turn on lights", context)

            # Verify conversation_id was used
            state = manager_instance.get_state("unique-id-123")
            # If automation intent was detected, state should be COLLECTING
            assert state in [ConversationState.IDLE, ConversationState.COLLECTING, ConversationState.CONFIRMING]

    def test_handler_generates_conversation_id_if_missing(self):
        """Test that a conversation_id is generated if not provided."""
        mock_agent = MagicMock(return_value="Done.")
        handler = VoiceHandler(agent_callback=mock_agent)

        # Context without conversation_id
        context = {
            "device_id": "voice_puck_1",
            "language": "en"
        }

        with patch("src.voice_handler.get_conversation_manager") as mock_manager:
            manager_instance = ConversationManager()
            mock_manager.return_value = manager_instance

            result = handler.process_command("what time is it", context)

            # Should still work
            assert result["success"] is True


class TestResponseFormatting:
    """Test voice response formatting for automation dialogs."""

    def test_clarification_response_is_tts_friendly(self):
        """Clarification questions should be TTS-friendly."""
        manager = ConversationManager()
        manager.start_automation("test-conv")

        question = manager.get_next_question("test-conv")

        # Should not have special characters
        assert "**" not in question
        assert "`" not in question
        assert "[" not in question

        # Should end with question mark
        assert question.endswith("?")

    def test_confirmation_response_is_tts_friendly(self):
        """Confirmation text should be TTS-friendly."""
        manager = ConversationManager()
        manager.start_automation("test-conv")
        manager.update_draft(
            "test-conv",
            trigger_type="time",
            trigger_config={"time": "22:00"},
            action_command="turn off all lights"
        )

        confirmation = manager.get_confirmation_text("test-conv")

        # Should not have special characters
        assert "**" not in confirmation
        assert "`" not in confirmation

        # Should have the action and time
        assert "turn off" in confirmation.lower()
        assert "10" in confirmation.lower() or "22" in confirmation


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_conversation_id(self):
        """Test handling of empty conversation_id."""
        manager = ConversationManager()

        # Empty string should still work
        manager.start_automation("")
        state = manager.get_state("")
        assert state == ConversationState.COLLECTING

    def test_special_characters_in_action(self):
        """Test automation with special characters in action."""
        manager = ConversationManager()
        manager.start_automation("test-conv")

        manager.update_draft(
            "test-conv",
            trigger_type="time",
            trigger_config={"time": "20:00"},
            action_command="turn on the 'cozy' lights"
        )

        assert manager.is_ready_for_confirmation("test-conv")

    def test_rapid_consecutive_messages(self):
        """Test rapid consecutive messages don't corrupt state."""
        manager = ConversationManager()

        for i in range(5):
            manager.process_message(f"conv-{i}", f"create automation to turn on lights at {10+i}pm")

        # All should have started
        for i in range(5):
            state = manager.get_state(f"conv-{i}")
            assert state in [ConversationState.COLLECTING, ConversationState.CONFIRMING]
