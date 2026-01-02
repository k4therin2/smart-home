"""
Unit Tests for Response Feedback Feature

Tests the database functions and feedback handler logic.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path


# =============================================================================
# Database Function Tests
# =============================================================================

class TestFeedbackDatabase:
    """Tests for feedback database operations."""

    def test_record_feedback_bug_filed(self, test_db):
        """Test recording feedback when a bug is filed."""
        from src.database import record_feedback, get_feedback_history

        # Record feedback
        feedback_id = record_feedback(
            original_command="turn off kitchen light",
            original_response="Done!",
            action_taken="bug_filed",
            bug_id="BUG-20260102120000",
        )

        assert feedback_id is not None
        assert feedback_id > 0

        # Verify it was stored
        history = get_feedback_history(limit=1)
        assert len(history) == 1
        assert history[0]["original_command"] == "turn off kitchen light"
        assert history[0]["original_response"] == "Done!"
        assert history[0]["action_taken"] == "bug_filed"
        assert history[0]["bug_id"] == "BUG-20260102120000"
        assert history[0]["feedback_text"] is None

    def test_record_feedback_with_retry(self, test_db):
        """Test recording feedback with retry context."""
        from src.database import record_feedback, get_feedback_history

        feedback_id = record_feedback(
            original_command="turn off kitchen light",
            original_response="Done!",
            action_taken="retry",
            feedback_text="light didn't actually turn off",
            retry_response="I've now turned off the kitchen light.",
            bug_id="BUG-20260102120001",
        )

        assert feedback_id is not None

        history = get_feedback_history(limit=1)
        assert history[0]["action_taken"] == "retry"
        assert history[0]["feedback_text"] == "light didn't actually turn off"
        assert history[0]["retry_response"] == "I've now turned off the kitchen light."

    def test_get_feedback_by_bug_id(self, test_db):
        """Test retrieving feedback by bug ID."""
        from src.database import record_feedback, get_feedback_by_bug_id

        record_feedback(
            original_command="test command",
            original_response="test response",
            action_taken="bug_filed",
            bug_id="BUG-UNIQUE123",
        )

        result = get_feedback_by_bug_id("BUG-UNIQUE123")
        assert result is not None
        assert result["bug_id"] == "BUG-UNIQUE123"
        assert result["original_command"] == "test command"

    def test_get_feedback_by_bug_id_not_found(self, test_db):
        """Test retrieving non-existent bug ID returns None."""
        from src.database import get_feedback_by_bug_id

        result = get_feedback_by_bug_id("BUG-NONEXISTENT")
        assert result is None

    def test_feedback_history_ordering(self, test_db):
        """Test that feedback history is returned newest first."""
        from src.database import record_feedback, get_feedback_history
        import time

        # Record multiple feedbacks
        record_feedback(
            original_command="first command",
            original_response="first response",
            action_taken="bug_filed",
        )
        time.sleep(0.1)  # Ensure different timestamps
        record_feedback(
            original_command="second command",
            original_response="second response",
            action_taken="bug_filed",
        )

        history = get_feedback_history(limit=10)
        assert len(history) == 2
        assert history[0]["original_command"] == "second command"  # Newest first
        assert history[1]["original_command"] == "first command"

    def test_feedback_history_pagination(self, test_db):
        """Test feedback history limit and offset."""
        from src.database import record_feedback, get_feedback_history

        # Record 5 feedbacks
        for i in range(5):
            record_feedback(
                original_command=f"command {i}",
                original_response=f"response {i}",
                action_taken="bug_filed",
            )

        # Get first 2
        page1 = get_feedback_history(limit=2, offset=0)
        assert len(page1) == 2

        # Get next 2
        page2 = get_feedback_history(limit=2, offset=2)
        assert len(page2) == 2

        # Ensure different records
        assert page1[0]["original_command"] != page2[0]["original_command"]


# =============================================================================
# Feedback Handler Tests
# =============================================================================

class TestFeedbackHandler:
    """Tests for feedback handler functions."""

    @patch("src.feedback_handler.get_vikunja_client")
    def test_file_bug_in_vikunja_success(self, mock_get_client):
        """Test successful bug filing in Vikunja."""
        from src.feedback_handler import file_bug_in_vikunja

        # Set up mock client
        mock_client = MagicMock()
        mock_client.find_project_by_title.return_value = {"id": 92, "title": "Smarthome"}
        mock_client.create_task.return_value = {"id": 123}
        mock_client.get_or_create_label.return_value = {"id": 1}
        mock_get_client.return_value = mock_client

        bug_id = file_bug_in_vikunja(
            command="turn off kitchen light",
            response="Done!",
        )

        assert bug_id is not None
        assert bug_id.startswith("BUG-")
        mock_client.create_task.assert_called_once()
        assert mock_client.add_label_to_task.call_count == 3  # bug, P2, source

    @patch("src.feedback_handler.get_vikunja_client")
    def test_file_bug_in_vikunja_no_project(self, mock_get_client):
        """Test bug filing when Smarthome project doesn't exist."""
        from src.feedback_handler import file_bug_in_vikunja

        mock_client = MagicMock()
        mock_client.find_project_by_title.return_value = None
        mock_get_client.return_value = mock_client

        bug_id = file_bug_in_vikunja(
            command="test command",
            response="test response",
        )

        assert bug_id is None

    @patch("src.feedback_handler.get_vikunja_client")
    def test_file_bug_in_vikunja_client_error(self, mock_get_client):
        """Test bug filing when Vikunja client fails."""
        from src.feedback_handler import file_bug_in_vikunja

        mock_get_client.return_value = None

        bug_id = file_bug_in_vikunja(
            command="test command",
            response="test response",
        )

        assert bug_id is None

    @patch("src.feedback_handler.asyncio.run")
    def test_alert_developers_via_nats(self, mock_asyncio_run):
        """Test NATS alert is attempted."""
        from src.feedback_handler import alert_developers_via_nats

        alert_developers_via_nats(
            bug_id="BUG-123",
            command="test command",
            response="test response",
        )

        mock_asyncio_run.assert_called_once()

    @patch("src.feedback_handler.asyncio.run")
    def test_alert_developers_via_nats_error_handled(self, mock_asyncio_run):
        """Test NATS alert failure is handled gracefully."""
        from src.feedback_handler import alert_developers_via_nats

        mock_asyncio_run.side_effect = Exception("Connection failed")

        # Should not raise
        alert_developers_via_nats(
            bug_id="BUG-123",
            command="test command",
            response="test response",
        )

    @patch("agent.run_agent")
    def test_retry_with_feedback_success(self, mock_run_agent):
        """Test successful retry with feedback context."""
        from src.feedback_handler import retry_with_feedback

        mock_run_agent.return_value = "Light turned off successfully."

        result = retry_with_feedback(
            original_command="turn off kitchen light",
            original_response="Done!",
            feedback_text="it didn't actually turn off",
        )

        assert result["success"] is True
        assert result["response"] == "Light turned off successfully."

        # Verify augmented prompt was passed
        call_args = mock_run_agent.call_args[0][0]
        assert "it didn't actually turn off" in call_args
        assert "turn off kitchen light" in call_args

    @patch("agent.run_agent")
    def test_retry_with_feedback_failure(self, mock_run_agent):
        """Test retry failure is handled."""
        from src.feedback_handler import retry_with_feedback

        mock_run_agent.side_effect = Exception("Agent error")

        result = retry_with_feedback(
            original_command="test command",
            original_response="test response",
            feedback_text="didn't work",
        )

        assert result["success"] is False
        assert "Agent error" in result["response"]
