"""
Tests for agent.py - Agent Loop Integration Tests

Test Strategy:
- Integration tests exercising the complete agent loop
- Mock OpenAI API at the boundary (external service)
- Mock Home Assistant API at the boundary (external service)
- Test real agent.py logic without mocking internal components
- Use in-memory database for usage tracking tests
- Verify multi-turn conversations, tool execution, and error handling
"""

import json
from unittest.mock import MagicMock, patch
import pytest
import responses
from datetime import datetime


class TestAgentSimpleResponses:
    """Test agent simple text responses without tool use."""

    def test_agent_simple_command(self, mock_openai, mock_ha_api):
        """Agent should handle simple text responses without tools."""
        from agent import run_agent

        # Configure mock to return simple text response (OpenAI format)
        mock_message = MagicMock()
        mock_message.content = "Hello! How can I help with your smart home?"
        mock_message.tool_calls = None

        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_choice.finish_reason = "stop"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = MagicMock(prompt_tokens=50, completion_tokens=20)

        mock_openai.chat.completions.create.return_value = mock_response

        # Patch the OpenAI client
        with patch("agent.openai.OpenAI", return_value=mock_openai):
            result = run_agent("hello")

        assert "Hello!" in result
        assert mock_openai.chat.completions.create.called


class TestAgentToolExecution:
    """Test agent tool selection and execution."""

    def test_agent_tool_use_single_turn(self, mock_openai, mock_ha_api):
        """Agent should execute tool in single turn and return result."""
        from agent import run_agent

        # First response: tool use (OpenAI format)
        tool_call = MagicMock()
        tool_call.id = "tool_1"
        tool_call.function = MagicMock()
        tool_call.function.name = "get_current_time"
        tool_call.function.arguments = "{}"

        mock_message_1 = MagicMock()
        mock_message_1.content = None
        mock_message_1.tool_calls = [tool_call]

        mock_choice_1 = MagicMock()
        mock_choice_1.message = mock_message_1
        mock_choice_1.finish_reason = "tool_calls"

        response_1 = MagicMock()
        response_1.choices = [mock_choice_1]
        response_1.usage = MagicMock(prompt_tokens=100, completion_tokens=30)

        # Second response: final answer after tool result
        mock_message_2 = MagicMock()
        mock_message_2.content = "It's currently 2:30 PM."
        mock_message_2.tool_calls = None

        mock_choice_2 = MagicMock()
        mock_choice_2.message = mock_message_2
        mock_choice_2.finish_reason = "stop"

        response_2 = MagicMock()
        response_2.choices = [mock_choice_2]
        response_2.usage = MagicMock(prompt_tokens=120, completion_tokens=15)

        mock_openai.chat.completions.create.side_effect = [response_1, response_2]

        with patch("agent.openai.OpenAI", return_value=mock_openai):
            result = run_agent("what time is it?")

        assert "2:30 PM" in result
        # Should have called API twice (initial + after tool)
        assert mock_openai.chat.completions.create.call_count == 2

    def test_agent_tool_use_multi_turn(self, mock_openai, mock_ha_api):
        """Agent should handle multiple tool uses across turns."""
        from agent import run_agent

        # Turn 1: Use get_system_status tool
        tool_1 = MagicMock()
        tool_1.id = "tool_1"
        tool_1.function = MagicMock()
        tool_1.function.name = "get_system_status"
        tool_1.function.arguments = "{}"

        msg_1 = MagicMock()
        msg_1.content = None
        msg_1.tool_calls = [tool_1]

        choice_1 = MagicMock()
        choice_1.message = msg_1
        choice_1.finish_reason = "tool_calls"

        response_1 = MagicMock()
        response_1.choices = [choice_1]
        response_1.usage = MagicMock(prompt_tokens=100, completion_tokens=30)

        # Turn 2: Use get_current_time tool
        tool_2 = MagicMock()
        tool_2.id = "tool_2"
        tool_2.function = MagicMock()
        tool_2.function.name = "get_current_time"
        tool_2.function.arguments = "{}"

        msg_2 = MagicMock()
        msg_2.content = None
        msg_2.tool_calls = [tool_2]

        choice_2 = MagicMock()
        choice_2.message = msg_2
        choice_2.finish_reason = "tool_calls"

        response_2 = MagicMock()
        response_2.choices = [choice_2]
        response_2.usage = MagicMock(prompt_tokens=150, completion_tokens=25)

        # Turn 3: Final response
        msg_3 = MagicMock()
        msg_3.content = "System is operational and it's currently morning."
        msg_3.tool_calls = None

        choice_3 = MagicMock()
        choice_3.message = msg_3
        choice_3.finish_reason = "stop"

        response_3 = MagicMock()
        response_3.choices = [choice_3]
        response_3.usage = MagicMock(prompt_tokens=180, completion_tokens=20)

        mock_openai.chat.completions.create.side_effect = [response_1, response_2, response_3]

        with patch("agent.openai.OpenAI", return_value=mock_openai):
            result = run_agent("how is the system doing?")

        assert "operational" in result.lower()
        assert mock_openai.chat.completions.create.call_count == 3

    def test_agent_max_iterations_reached(self, mock_openai):
        """Agent should stop at max iterations and return appropriate message."""
        from agent import run_agent
        from src.config import MAX_AGENT_ITERATIONS

        # Mock endless tool use (never returns stop)
        tool_call = MagicMock()
        tool_call.id = "tool_loop"
        tool_call.function = MagicMock()
        tool_call.function.name = "get_current_time"
        tool_call.function.arguments = "{}"

        msg = MagicMock()
        msg.content = None
        msg.tool_calls = [tool_call]

        choice = MagicMock()
        choice.message = msg
        choice.finish_reason = "tool_calls"

        endless_response = MagicMock()
        endless_response.choices = [choice]
        endless_response.usage = MagicMock(prompt_tokens=100, completion_tokens=30)

        # Return same response every time (infinite loop)
        mock_openai.chat.completions.create.return_value = endless_response

        with patch("agent.openai.OpenAI", return_value=mock_openai):
            result = run_agent("cause infinite loop")

        assert "processing limit" in result.lower()
        # Should have called exactly MAX_AGENT_ITERATIONS times
        assert mock_openai.chat.completions.create.call_count == MAX_AGENT_ITERATIONS


class TestAgentSystemTools:
    """Test system tool execution."""

    def test_agent_system_tool_get_time(self, mock_openai):
        """Agent should execute get_current_time tool correctly."""
        from agent import run_agent

        # Tool use response
        tool_call = MagicMock()
        tool_call.id = "time_tool"
        tool_call.function = MagicMock()
        tool_call.function.name = "get_current_time"
        tool_call.function.arguments = "{}"

        msg_1 = MagicMock()
        msg_1.content = None
        msg_1.tool_calls = [tool_call]

        choice_1 = MagicMock()
        choice_1.message = msg_1
        choice_1.finish_reason = "tool_calls"

        response_1 = MagicMock()
        response_1.choices = [choice_1]
        response_1.usage = MagicMock(prompt_tokens=80, completion_tokens=25)

        # Final response
        msg_2 = MagicMock()
        msg_2.content = "The current time is displayed above."
        msg_2.tool_calls = None

        choice_2 = MagicMock()
        choice_2.message = msg_2
        choice_2.finish_reason = "stop"

        response_2 = MagicMock()
        response_2.choices = [choice_2]
        response_2.usage = MagicMock(prompt_tokens=100, completion_tokens=10)

        mock_openai.chat.completions.create.side_effect = [response_1, response_2]

        with patch("agent.openai.OpenAI", return_value=mock_openai):
            result = run_agent("what time is it?")

        # Should have successful response
        assert result is not None
        assert mock_openai.chat.completions.create.call_count == 2

    def test_agent_system_tool_get_status(self, mock_openai, mock_ha_api):
        """Agent should execute get_system_status tool correctly."""
        from agent import run_agent

        # Tool use response
        tool_call = MagicMock()
        tool_call.id = "status_tool"
        tool_call.function = MagicMock()
        tool_call.function.name = "get_system_status"
        tool_call.function.arguments = "{}"

        msg_1 = MagicMock()
        msg_1.content = None
        msg_1.tool_calls = [tool_call]

        choice_1 = MagicMock()
        choice_1.message = msg_1
        choice_1.finish_reason = "tool_calls"

        response_1 = MagicMock()
        response_1.choices = [choice_1]
        response_1.usage = MagicMock(prompt_tokens=80, completion_tokens=30)

        # Final response
        msg_2 = MagicMock()
        msg_2.content = "System is operational, Home Assistant is connected."
        msg_2.tool_calls = None

        choice_2 = MagicMock()
        choice_2.message = msg_2
        choice_2.finish_reason = "stop"

        response_2 = MagicMock()
        response_2.choices = [choice_2]
        response_2.usage = MagicMock(prompt_tokens=150, completion_tokens=15)

        mock_openai.chat.completions.create.side_effect = [response_1, response_2]

        with patch("agent.openai.OpenAI", return_value=mock_openai):
            result = run_agent("how is the system?")

        assert "operational" in result.lower() or "connected" in result.lower()
        assert mock_openai.chat.completions.create.call_count == 2


class TestAgentLightTools:
    """Test light control tool execution."""

    def test_agent_light_tool_execution(self, mock_openai, mock_ha_api):
        """Agent should execute light control tools correctly."""
        from agent import run_agent

        # Mock HA API for light control
        mock_ha_api.add(
            responses.POST,
            "http://test-ha.local:8123/api/services/light/turn_on",
            json=[{"entity_id": "light.living_room"}],
            status=200,
        )

        # Tool use response
        tool_call = MagicMock()
        tool_call.id = "light_tool"
        tool_call.function = MagicMock()
        tool_call.function.name = "set_room_ambiance"
        tool_call.function.arguments = '{"room": "living_room", "state": "on", "brightness": 80}'

        msg_1 = MagicMock()
        msg_1.content = None
        msg_1.tool_calls = [tool_call]

        choice_1 = MagicMock()
        choice_1.message = msg_1
        choice_1.finish_reason = "tool_calls"

        response_1 = MagicMock()
        response_1.choices = [choice_1]
        response_1.usage = MagicMock(prompt_tokens=120, completion_tokens=40)

        # Final response
        msg_2 = MagicMock()
        msg_2.content = "I've turned on the living room lights to 80% brightness."
        msg_2.tool_calls = None

        choice_2 = MagicMock()
        choice_2.message = msg_2
        choice_2.finish_reason = "stop"

        response_2 = MagicMock()
        response_2.choices = [choice_2]
        response_2.usage = MagicMock(prompt_tokens=160, completion_tokens=20)

        mock_openai.chat.completions.create.side_effect = [response_1, response_2]

        with patch("agent.openai.OpenAI", return_value=mock_openai):
            result = run_agent("turn on living room lights")

        assert "living room" in result.lower() or "light" in result.lower()
        assert mock_openai.chat.completions.create.call_count == 2


class TestAgentErrorHandling:
    """Test agent error handling and recovery."""

    def test_agent_error_handling_api_failure(self, mock_openai):
        """Agent should handle OpenAI API errors gracefully."""
        from agent import run_agent
        import openai

        # Mock API error - OpenAI APIError takes message and request
        mock_openai.chat.completions.create.side_effect = openai.APIConnectionError(
            request=MagicMock()
        )

        with patch("agent.openai.OpenAI", return_value=mock_openai):
            result = run_agent("test command")

        assert "API Error" in result or "error" in result.lower()


class TestAgentCostTracking:
    """Test API usage and cost tracking."""

    def test_agent_cost_tracking(self, mock_openai, test_db):
        """Agent should track API usage and costs in database."""
        from agent import run_agent
        from src.utils import get_daily_usage

        # Simple response
        msg = MagicMock()
        msg.content = "Test response"
        msg.tool_calls = None

        choice = MagicMock()
        choice.message = msg
        choice.finish_reason = "stop"

        response = MagicMock()
        response.choices = [choice]
        response.usage = MagicMock(prompt_tokens=1000, completion_tokens=500)

        mock_openai.chat.completions.create.return_value = response

        # Get initial cost
        initial_cost = get_daily_usage()

        with patch("agent.openai.OpenAI", return_value=mock_openai):
            run_agent("test command")

        # Cost should have increased
        final_cost = get_daily_usage()
        assert final_cost > initial_cost

        # Verify cost calculation (1000 input at $0.15/M + 500 output at $0.60/M)
        expected_cost = (1000 / 1_000_000) * 0.15 + (500 / 1_000_000) * 0.60
        cost_delta = final_cost - initial_cost
        assert abs(cost_delta - expected_cost) < 0.0001  # Allow for floating point error


class TestAgentCommandLogging:
    """Test command and tool call logging."""

    def test_agent_command_logging(self, test_db):
        """Agent should log commands and tool calls."""
        from agent import run_agent

        # Create a simple mock
        mock_openai = MagicMock()

        msg = MagicMock()
        msg.content = "Logged successfully"
        msg.tool_calls = None

        choice = MagicMock()
        choice.message = msg
        choice.finish_reason = "stop"

        response = MagicMock()
        response.choices = [choice]
        response.usage = MagicMock(prompt_tokens=50, completion_tokens=20)

        mock_openai.chat.completions.create.return_value = response

        # Capture logs
        with patch("agent.openai.OpenAI", return_value=mock_openai):
            with patch("agent.logger") as mock_logger:
                run_agent("test logging")

                # Verify logger was called
                assert mock_logger.info.called or mock_logger.debug.called


class TestAgentConfiguration:
    """Test agent configuration and setup."""

    def test_agent_no_api_key(self, monkeypatch):
        """Agent should return error message when API key is missing."""
        from agent import run_agent

        # Remove API key
        monkeypatch.setenv("OPENAI_API_KEY", "")

        # Force config reload by patching the module-level constant
        with patch("agent.OPENAI_API_KEY", None):
            result = run_agent("test command")

        assert "OPENAI_API_KEY" in result or "not configured" in result.lower()
