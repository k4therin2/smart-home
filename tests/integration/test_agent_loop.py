"""
Tests for agent.py - Agent Loop Integration Tests

Test Strategy:
- Integration tests exercising the complete agent loop
- Mock Anthropic API at the boundary (external service)
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

    def test_agent_simple_command(self, mock_anthropic, mock_ha_api):
        """Agent should handle simple text responses without tools."""
        from agent import run_agent

        # Configure mock to return simple text response
        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="text", text="Hello! How can I help with your smart home?")]
        mock_response.stop_reason = "end_turn"
        mock_response.usage = MagicMock(input_tokens=50, output_tokens=20)
        mock_anthropic.messages.create.return_value = mock_response

        # Patch the anthropic client
        with patch("agent.anthropic.Anthropic", return_value=mock_anthropic):
            result = run_agent("hello")

        assert "Hello!" in result
        assert mock_anthropic.messages.create.called


class TestAgentToolExecution:
    """Test agent tool selection and execution."""

    def test_agent_tool_use_single_turn(self, mock_anthropic, mock_ha_api):
        """Agent should execute tool in single turn and return result."""
        from agent import run_agent

        # First response: tool use
        tool_use_block = MagicMock()
        tool_use_block.type = "tool_use"
        tool_use_block.name = "get_current_time"
        tool_use_block.input = {}
        tool_use_block.id = "tool_1"

        response_1 = MagicMock()
        response_1.content = [tool_use_block]
        response_1.stop_reason = "tool_use"
        response_1.usage = MagicMock(input_tokens=100, output_tokens=30)

        # Second response: final answer after tool result
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "It's currently 2:30 PM."

        response_2 = MagicMock()
        response_2.content = [text_block]
        response_2.stop_reason = "end_turn"
        response_2.usage = MagicMock(input_tokens=120, output_tokens=15)

        mock_anthropic.messages.create.side_effect = [response_1, response_2]

        with patch("agent.anthropic.Anthropic", return_value=mock_anthropic):
            result = run_agent("what time is it?")

        assert "2:30 PM" in result
        # Should have called API twice (initial + after tool)
        assert mock_anthropic.messages.create.call_count == 2

    def test_agent_tool_use_multi_turn(self, mock_anthropic, mock_ha_api):
        """Agent should handle multiple tool uses across turns."""
        from agent import run_agent

        # Turn 1: Use get_system_status tool
        tool_1 = MagicMock()
        tool_1.type = "tool_use"
        tool_1.name = "get_system_status"
        tool_1.input = {}
        tool_1.id = "tool_1"

        response_1 = MagicMock()
        response_1.content = [tool_1]
        response_1.stop_reason = "tool_use"
        response_1.usage = MagicMock(input_tokens=100, output_tokens=30)

        # Turn 2: Use get_current_time tool
        tool_2 = MagicMock()
        tool_2.type = "tool_use"
        tool_2.name = "get_current_time"
        tool_2.input = {}
        tool_2.id = "tool_2"

        response_2 = MagicMock()
        response_2.content = [tool_2]
        response_2.stop_reason = "tool_use"
        response_2.usage = MagicMock(input_tokens=150, output_tokens=25)

        # Turn 3: Final response
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "System is operational and it's currently morning."

        response_3 = MagicMock()
        response_3.content = [text_block]
        response_3.stop_reason = "end_turn"
        response_3.usage = MagicMock(input_tokens=180, output_tokens=20)

        mock_anthropic.messages.create.side_effect = [response_1, response_2, response_3]

        with patch("agent.anthropic.Anthropic", return_value=mock_anthropic):
            result = run_agent("how is the system doing?")

        assert "operational" in result.lower()
        assert mock_anthropic.messages.create.call_count == 3

    def test_agent_max_iterations_reached(self, mock_anthropic):
        """Agent should stop at max iterations and return appropriate message."""
        from agent import run_agent, MAX_AGENT_ITERATIONS

        # Mock endless tool use (never returns end_turn)
        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.name = "get_current_time"
        tool_block.input = {}
        tool_block.id = "tool_loop"

        endless_response = MagicMock()
        endless_response.content = [tool_block]
        endless_response.stop_reason = "tool_use"
        endless_response.usage = MagicMock(input_tokens=100, output_tokens=30)

        # Return same response every time (infinite loop)
        mock_anthropic.messages.create.return_value = endless_response

        with patch("agent.anthropic.Anthropic", return_value=mock_anthropic):
            result = run_agent("cause infinite loop")

        assert "processing limit" in result.lower()
        # Should have called exactly MAX_AGENT_ITERATIONS times
        assert mock_anthropic.messages.create.call_count == MAX_AGENT_ITERATIONS


class TestAgentSystemTools:
    """Test system tool execution."""

    def test_agent_system_tool_get_time(self, mock_anthropic):
        """Agent should execute get_current_time tool correctly."""
        from agent import run_agent

        # Tool use response
        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.name = "get_current_time"
        tool_block.input = {}
        tool_block.id = "time_tool"

        response_1 = MagicMock()
        response_1.content = [tool_block]
        response_1.stop_reason = "tool_use"
        response_1.usage = MagicMock(input_tokens=80, output_tokens=25)

        # Final response
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "The current time is displayed above."

        response_2 = MagicMock()
        response_2.content = [text_block]
        response_2.stop_reason = "end_turn"
        response_2.usage = MagicMock(input_tokens=100, output_tokens=10)

        mock_anthropic.messages.create.side_effect = [response_1, response_2]

        with patch("agent.anthropic.Anthropic", return_value=mock_anthropic):
            result = run_agent("what time is it?")

        # Should have successful response
        assert result is not None
        assert mock_anthropic.messages.create.call_count == 2

    def test_agent_system_tool_get_status(self, mock_anthropic, mock_ha_api):
        """Agent should execute get_system_status tool correctly."""
        from agent import run_agent

        # Tool use response
        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.name = "get_system_status"
        tool_block.input = {}
        tool_block.id = "status_tool"

        response_1 = MagicMock()
        response_1.content = [tool_block]
        response_1.stop_reason = "tool_use"
        response_1.usage = MagicMock(input_tokens=80, output_tokens=30)

        # Final response
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "System is operational, Home Assistant is connected."

        response_2 = MagicMock()
        response_2.content = [text_block]
        response_2.stop_reason = "end_turn"
        response_2.usage = MagicMock(input_tokens=150, output_tokens=15)

        mock_anthropic.messages.create.side_effect = [response_1, response_2]

        with patch("agent.anthropic.Anthropic", return_value=mock_anthropic):
            result = run_agent("how is the system?")

        assert "operational" in result.lower() or "connected" in result.lower()
        assert mock_anthropic.messages.create.call_count == 2


class TestAgentLightTools:
    """Test light control tool execution."""

    def test_agent_light_tool_execution(self, mock_anthropic, mock_ha_api):
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
        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.name = "set_room_ambiance"
        tool_block.input = {"room": "living_room", "state": "on", "brightness": 80}
        tool_block.id = "light_tool"

        response_1 = MagicMock()
        response_1.content = [tool_block]
        response_1.stop_reason = "tool_use"
        response_1.usage = MagicMock(input_tokens=120, output_tokens=40)

        # Final response
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "I've turned on the living room lights to 80% brightness."

        response_2 = MagicMock()
        response_2.content = [text_block]
        response_2.stop_reason = "end_turn"
        response_2.usage = MagicMock(input_tokens=160, output_tokens=20)

        mock_anthropic.messages.create.side_effect = [response_1, response_2]

        with patch("agent.anthropic.Anthropic", return_value=mock_anthropic):
            result = run_agent("turn on living room lights")

        assert "living room" in result.lower() or "light" in result.lower()
        assert mock_anthropic.messages.create.call_count == 2


class TestAgentErrorHandling:
    """Test agent error handling and recovery."""

    def test_agent_error_handling_api_failure(self, mock_anthropic):
        """Agent should handle Anthropic API errors gracefully."""
        from agent import run_agent
        import anthropic

        # Mock API error
        mock_anthropic.messages.create.side_effect = anthropic.APIError("Rate limit exceeded")

        with patch("agent.anthropic.Anthropic", return_value=mock_anthropic):
            result = run_agent("test command")

        assert "API Error" in result or "error" in result.lower()


class TestAgentCostTracking:
    """Test API usage and cost tracking."""

    def test_agent_cost_tracking(self, mock_anthropic, test_db):
        """Agent should track API usage and costs in database."""
        from agent import run_agent
        from src.utils import get_daily_usage
        import sqlite3

        # Simple response
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "Test response"

        response = MagicMock()
        response.content = [text_block]
        response.stop_reason = "end_turn"
        response.usage = MagicMock(input_tokens=1000, output_tokens=500)

        mock_anthropic.messages.create.return_value = response

        # Get initial cost
        initial_cost = get_daily_usage()

        with patch("agent.anthropic.Anthropic", return_value=mock_anthropic):
            run_agent("test command")

        # Cost should have increased
        final_cost = get_daily_usage()
        assert final_cost > initial_cost

        # Verify cost calculation (1000 input tokens at $3/M + 500 output at $15/M)
        expected_cost = (1000 / 1_000_000) * 3.00 + (500 / 1_000_000) * 15.00
        cost_delta = final_cost - initial_cost
        assert abs(cost_delta - expected_cost) < 0.0001  # Allow for floating point error


class TestAgentCommandLogging:
    """Test command and tool call logging."""

    def test_agent_command_logging(self, test_db):
        """Agent should log commands and tool calls."""
        from agent import run_agent
        from src.utils import log_command, log_tool_call
        import logging

        # Create a simple mock
        mock_anthropic = MagicMock()
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "Logged successfully"

        response = MagicMock()
        response.content = [text_block]
        response.stop_reason = "end_turn"
        response.usage = MagicMock(input_tokens=50, output_tokens=20)

        mock_anthropic.messages.create.return_value = response

        # Capture logs
        with patch("agent.anthropic.Anthropic", return_value=mock_anthropic):
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
        monkeypatch.setenv("ANTHROPIC_API_KEY", "")

        # Force config reload by patching the module-level constant
        with patch("agent.ANTHROPIC_API_KEY", None):
            result = run_agent("test command")

        assert "ANTHROPIC_API_KEY" in result or "not configured" in result.lower()
