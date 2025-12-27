"""
Integration tests for Productivity Tools - Todo List & Reminders (WP-4.1)

Tests the full flow from tool functions through manager classes.
"""

import pytest
from datetime import datetime, timedelta
import tempfile
import os


class TestAddTodoIntegration:
    """Integration tests for adding todos via tools."""

    def test_add_todo_basic(self, productivity_setup):
        """Should add a todo via tool function."""
        from tools.productivity import add_todo

        result = add_todo("Buy groceries")

        assert result["success"] is True
        assert result["todo_id"] > 0
        assert "groceries" in result["message"].lower()

    def test_add_todo_to_shopping_list(self, productivity_setup):
        """Should add to shopping list."""
        from tools.productivity import add_todo, list_todos

        add_todo("Milk", list_name="shopping")
        add_todo("Eggs", list_name="shopping")

        result = list_todos(list_name="shopping")

        assert result["success"] is True
        assert result["count"] >= 2
        assert any("milk" in t["content"].lower() for t in result["todos"])

    def test_add_todo_with_priority(self, productivity_setup):
        """Should set priority correctly."""
        from tools.productivity import add_todo

        result = add_todo("Urgent task", priority="urgent")

        assert result["success"] is True
        # Priority 2 = urgent

    def test_add_todo_empty_content_fails(self, productivity_setup):
        """Should fail with empty content."""
        from tools.productivity import add_todo

        result = add_todo("")

        assert result["success"] is False
        assert "empty" in result["error"].lower()


class TestListTodosIntegration:
    """Integration tests for listing todos."""

    def test_list_todos_default_list(self, productivity_setup):
        """Should list todos from default list."""
        from tools.productivity import add_todo, list_todos

        add_todo("Item 1")
        add_todo("Item 2")

        result = list_todos()

        assert result["success"] is True
        assert result["count"] >= 2

    def test_list_todos_excludes_completed(self, productivity_setup):
        """Should exclude completed by default."""
        from tools.productivity import add_todo, complete_todo, list_todos

        add_todo("To complete")
        result = add_todo("To keep")
        complete_todo(content_match="complete")

        result = list_todos()

        # Should not include completed item
        for todo in result["todos"]:
            assert todo["status"] != "completed"

    def test_list_todos_includes_completed_when_requested(self, productivity_setup):
        """Should include completed when show_completed=True."""
        from tools.productivity import add_todo, complete_todo, list_todos

        add_todo("To complete")
        complete_todo(content_match="complete")

        result = list_todos(show_completed=True)

        statuses = [t["status"] for t in result["todos"]]
        assert "completed" in statuses


class TestCompleteTodoIntegration:
    """Integration tests for completing todos."""

    def test_complete_todo_by_match(self, productivity_setup):
        """Should complete by content match."""
        from tools.productivity import add_todo, complete_todo

        add_todo("Buy milk from store")

        result = complete_todo(content_match="buy milk")

        assert result["success"] is True
        assert "milk" in result["message"].lower()

    def test_complete_todo_by_id(self, productivity_setup):
        """Should complete by ID."""
        from tools.productivity import add_todo, complete_todo

        add_result = add_todo("Task to complete")
        todo_id = add_result["todo_id"]

        result = complete_todo(todo_id=todo_id)

        assert result["success"] is True

    def test_complete_nonexistent_fails(self, productivity_setup):
        """Should fail for non-matching content."""
        from tools.productivity import complete_todo

        result = complete_todo(content_match="nonexistent xyz abc")

        assert result["success"] is False


class TestSetReminderIntegration:
    """Integration tests for setting reminders."""

    def test_set_reminder_basic(self, productivity_setup):
        """Should set a reminder via tool function."""
        from tools.productivity import set_reminder

        result = set_reminder("Call mom", "in 2 hours")

        assert result["success"] is True
        assert result["reminder_id"] > 0
        assert "mom" in result["response_message"].lower()

    def test_set_reminder_absolute_time(self, productivity_setup):
        """Should parse absolute time like '3pm'."""
        from tools.productivity import set_reminder

        result = set_reminder("Take meds", "3pm")

        assert result["success"] is True

    def test_set_reminder_tomorrow(self, productivity_setup):
        """Should parse 'tomorrow at 9am'."""
        from tools.productivity import set_reminder

        result = set_reminder("Morning meeting", "tomorrow at 9am")

        assert result["success"] is True
        remind_at = datetime.fromisoformat(result["remind_at"])
        tomorrow = datetime.now() + timedelta(days=1)
        assert remind_at.date() == tomorrow.date()

    def test_set_reminder_repeating(self, productivity_setup):
        """Should set repeating reminder."""
        from tools.productivity import set_reminder

        result = set_reminder("Take vitamins", "9am", repeat="daily")

        assert result["success"] is True
        assert "daily" in result["response_message"]

    def test_set_reminder_invalid_time_fails(self, productivity_setup):
        """Should fail for unparseable time."""
        from tools.productivity import set_reminder

        result = set_reminder("Test", "gibberish time")

        assert result["success"] is False
        assert "understand" in result["error"].lower()


class TestListRemindersIntegration:
    """Integration tests for listing reminders."""

    def test_list_reminders(self, productivity_setup):
        """Should list pending reminders."""
        from tools.productivity import set_reminder, list_reminders

        set_reminder("Reminder 1", "in 1 hour")
        set_reminder("Reminder 2", "in 2 hours")

        result = list_reminders()

        assert result["success"] is True
        assert result["count"] >= 2


class TestDeleteTodoIntegration:
    """Integration tests for deleting todos."""

    def test_delete_todo_by_match(self, productivity_setup):
        """Should delete by content match."""
        from tools.productivity import add_todo, delete_todo, list_todos

        add_todo("Item to delete")
        delete_todo(content_match="delete")

        result = list_todos()
        contents = [t["content"].lower() for t in result["todos"]]
        assert not any("delete" in c for c in contents)


class TestDismissReminderIntegration:
    """Integration tests for dismissing reminders."""

    def test_dismiss_reminder_by_match(self, productivity_setup):
        """Should dismiss by message match."""
        from tools.productivity import set_reminder, dismiss_reminder, list_reminders

        set_reminder("Meeting reminder", "in 1 hour")

        result = dismiss_reminder(match="meeting")

        assert result["success"] is True

        # Should not appear in pending list
        reminders = list_reminders()
        messages = [r["message"].lower() for r in reminders["reminders"]]
        assert not any("meeting" in m for m in messages)


class TestExecuteProductivityTool:
    """Integration tests for the tool dispatcher."""

    def test_execute_add_todo(self, productivity_setup):
        """Should dispatch add_todo correctly."""
        from tools.productivity import execute_productivity_tool

        result = execute_productivity_tool("add_todo", {
            "content": "Test item",
            "list_name": "default",
            "priority": "normal"
        })

        assert result["success"] is True

    def test_execute_list_todos(self, productivity_setup):
        """Should dispatch list_todos correctly."""
        from tools.productivity import execute_productivity_tool

        execute_productivity_tool("add_todo", {"content": "Test item"})

        result = execute_productivity_tool("list_todos", {})

        assert result["success"] is True
        assert result["count"] >= 1

    def test_execute_set_reminder(self, productivity_setup):
        """Should dispatch set_reminder correctly."""
        from tools.productivity import execute_productivity_tool

        result = execute_productivity_tool("set_reminder", {
            "message": "Test reminder",
            "remind_at": "in 30 minutes"
        })

        assert result["success"] is True

    def test_execute_unknown_tool(self, productivity_setup):
        """Should return error for unknown tool."""
        from tools.productivity import execute_productivity_tool

        result = execute_productivity_tool("unknown_tool", {})

        assert result["success"] is False
        assert "unknown" in result["error"].lower()


class TestVoiceCommandScenarios:
    """Test realistic voice command scenarios."""

    def test_voice_add_to_shopping(self, productivity_setup):
        """Simulate: 'add milk to shopping list'"""
        from tools.productivity import add_todo

        result = add_todo("milk", list_name="shopping")

        assert result["success"] is True
        assert result["list_name"] == "shopping"

    def test_voice_show_shopping_list(self, productivity_setup):
        """Simulate: 'show my shopping list'"""
        from tools.productivity import add_todo, list_todos

        add_todo("bread", list_name="shopping")
        add_todo("butter", list_name="shopping")

        result = list_todos(list_name="shopping")

        assert result["success"] is True
        assert "shopping" in result["message"].lower()

    def test_voice_mark_done(self, productivity_setup):
        """Simulate: 'mark eggs as done'"""
        from tools.productivity import add_todo, complete_todo

        add_todo("buy eggs")

        result = complete_todo(content_match="eggs")

        assert result["success"] is True

    def test_voice_remind_me(self, productivity_setup):
        """Simulate: 'remind me to take meds at 9pm'"""
        from tools.productivity import set_reminder

        result = set_reminder("take meds", "9pm")

        assert result["success"] is True
        assert "9" in result["response_message"]

    def test_voice_remind_in_minutes(self, productivity_setup):
        """Simulate: 'remind me in 30 minutes to check laundry'"""
        from tools.productivity import set_reminder

        result = set_reminder("check laundry", "in 30 minutes")

        assert result["success"] is True


# Pytest fixtures
@pytest.fixture
def productivity_setup(monkeypatch):
    """Set up isolated test environment for productivity tools."""
    # Create temporary databases
    fd_todo, todo_db_path = tempfile.mkstemp(suffix='_todo.db')
    os.close(fd_todo)

    fd_reminder, reminder_db_path = tempfile.mkstemp(suffix='_reminder.db')
    os.close(fd_reminder)

    # Patch the managers to use temp databases
    from src import todo_manager, reminder_manager
    import tools.productivity as productivity_tools

    # Reset singletons
    todo_manager._todo_manager = None
    reminder_manager._reminder_manager = None

    # Create managers with temp paths
    temp_todo_mgr = todo_manager.TodoManager(database_path=todo_db_path)
    temp_reminder_mgr = reminder_manager.ReminderManager(database_path=reminder_db_path)

    # Patch get functions in BOTH the source module and the tools module
    # (tools.productivity imports get_todo_manager at module load time)
    monkeypatch.setattr(todo_manager, "get_todo_manager", lambda: temp_todo_mgr)
    monkeypatch.setattr(reminder_manager, "get_reminder_manager", lambda: temp_reminder_mgr)
    monkeypatch.setattr(productivity_tools, "get_todo_manager", lambda: temp_todo_mgr)
    monkeypatch.setattr(productivity_tools, "get_reminder_manager", lambda: temp_reminder_mgr)

    yield {
        "todo_manager": temp_todo_mgr,
        "reminder_manager": temp_reminder_mgr,
    }

    # Cleanup
    todo_manager._todo_manager = None
    reminder_manager._reminder_manager = None

    if os.path.exists(todo_db_path):
        os.remove(todo_db_path)
    if os.path.exists(reminder_db_path):
        os.remove(reminder_db_path)
