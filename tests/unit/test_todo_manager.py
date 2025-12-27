"""
Unit tests for TodoManager - Todo List & Reminders (WP-4.1)

Tests cover all CRUD operations for todos and todo lists.
Written TDD-style before implementation.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import sqlite3
import tempfile
import os


class TestTodoManagerInitialization:
    """Tests for TodoManager initialization and database setup."""

    def test_creates_todos_table(self, todo_manager):
        """TodoManager should create the todos table on initialization."""
        with todo_manager._get_cursor() as cursor:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='todos'"
            )
            result = cursor.fetchone()
        assert result is not None
        assert result[0] == "todos"

    def test_creates_todo_lists_table(self, todo_manager):
        """TodoManager should create the todo_lists table on initialization."""
        with todo_manager._get_cursor() as cursor:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='todo_lists'"
            )
            result = cursor.fetchone()
        assert result is not None
        assert result[0] == "todo_lists"

    def test_creates_default_lists(self, todo_manager):
        """TodoManager should create default lists on initialization."""
        lists = todo_manager.get_lists()
        list_names = [lst["name"] for lst in lists]

        assert "default" in list_names
        assert "shopping" in list_names


class TestAddTodo:
    """Tests for adding todo items."""

    def test_add_todo_returns_id(self, todo_manager):
        """Adding a todo should return a positive integer ID."""
        todo_id = todo_manager.add_todo("Buy milk")
        assert isinstance(todo_id, int)
        assert todo_id > 0

    def test_add_todo_with_content_only(self, todo_manager):
        """Should add a todo with just content to default list."""
        todo_id = todo_manager.add_todo("Test todo item")
        todo = todo_manager.get_todo(todo_id)

        assert todo["content"] == "Test todo item"
        assert todo["list_name"] == "default"
        assert todo["status"] == "pending"
        assert todo["priority"] == 0

    def test_add_todo_to_specific_list(self, todo_manager):
        """Should add a todo to a specific list."""
        todo_id = todo_manager.add_todo("Buy eggs", list_name="shopping")
        todo = todo_manager.get_todo(todo_id)

        assert todo["content"] == "Buy eggs"
        assert todo["list_name"] == "shopping"

    def test_add_todo_with_priority(self, todo_manager):
        """Should set todo priority."""
        todo_id = todo_manager.add_todo("Urgent task", priority=2)
        todo = todo_manager.get_todo(todo_id)

        assert todo["priority"] == 2

    def test_add_todo_with_due_date(self, todo_manager):
        """Should set todo due date."""
        due_date = datetime.now() + timedelta(days=7)
        todo_id = todo_manager.add_todo("Future task", due_date=due_date)
        todo = todo_manager.get_todo(todo_id)

        assert todo["due_date"] is not None
        # Check it's within a minute of what we set
        stored_due = datetime.fromisoformat(todo["due_date"])
        assert abs((stored_due - due_date).total_seconds()) < 60

    def test_add_todo_with_tags(self, todo_manager):
        """Should set todo tags as JSON array."""
        todo_id = todo_manager.add_todo("Tagged task", tags=["urgent", "work"])
        todo = todo_manager.get_todo(todo_id)

        assert todo["tags"] == ["urgent", "work"]

    def test_add_todo_empty_content_raises(self, todo_manager):
        """Adding a todo with empty content should raise ValueError."""
        with pytest.raises(ValueError, match="content cannot be empty"):
            todo_manager.add_todo("")

    def test_add_todo_creates_new_list_if_not_exists(self, todo_manager):
        """Should create a new list if it doesn't exist."""
        todo_id = todo_manager.add_todo("Custom list item", list_name="custom")
        lists = todo_manager.get_lists()
        list_names = [lst["name"] for lst in lists]

        assert "custom" in list_names


class TestGetTodo:
    """Tests for retrieving individual todo items."""

    def test_get_existing_todo(self, todo_manager):
        """Should retrieve a todo by ID."""
        todo_id = todo_manager.add_todo("Test item")
        todo = todo_manager.get_todo(todo_id)

        assert todo is not None
        assert todo["id"] == todo_id
        assert todo["content"] == "Test item"

    def test_get_nonexistent_todo_returns_none(self, todo_manager):
        """Should return None for non-existent todo ID."""
        todo = todo_manager.get_todo(99999)
        assert todo is None

    def test_get_todo_includes_all_fields(self, todo_manager):
        """Retrieved todo should include all expected fields."""
        todo_id = todo_manager.add_todo("Complete item", priority=1, tags=["test"])
        todo = todo_manager.get_todo(todo_id)

        expected_fields = [
            "id", "list_name", "content", "priority", "status",
            "created_at", "updated_at", "completed_at", "due_date", "tags"
        ]
        for field in expected_fields:
            assert field in todo


class TestGetTodos:
    """Tests for retrieving multiple todos."""

    def test_get_todos_from_default_list(self, todo_manager):
        """Should get todos from default list."""
        todo_manager.add_todo("Item 1")
        todo_manager.add_todo("Item 2")

        todos = todo_manager.get_todos()
        assert len(todos) >= 2

    def test_get_todos_from_specific_list(self, todo_manager):
        """Should get todos from a specific list only."""
        todo_manager.add_todo("Shopping item", list_name="shopping")
        todo_manager.add_todo("Default item", list_name="default")

        shopping_todos = todo_manager.get_todos(list_name="shopping")
        default_todos = todo_manager.get_todos(list_name="default")

        assert all(todo["list_name"] == "shopping" for todo in shopping_todos)
        assert all(todo["list_name"] == "default" for todo in default_todos)

    def test_get_todos_excludes_completed_by_default(self, todo_manager):
        """Should exclude completed todos by default."""
        todo_id = todo_manager.add_todo("To complete")
        todo_manager.complete_todo(todo_id)
        todo_manager.add_todo("Still pending")

        todos = todo_manager.get_todos()
        statuses = [todo["status"] for todo in todos]

        assert "completed" not in statuses

    def test_get_todos_includes_completed_when_requested(self, todo_manager):
        """Should include completed todos when include_completed=True."""
        todo_id = todo_manager.add_todo("To complete")
        todo_manager.complete_todo(todo_id)

        todos = todo_manager.get_todos(include_completed=True)
        statuses = [todo["status"] for todo in todos]

        assert "completed" in statuses

    def test_get_todos_ordered_by_priority_and_created(self, todo_manager):
        """Should order by priority (desc) then created_at (asc)."""
        todo_manager.add_todo("Low priority", priority=0)
        todo_manager.add_todo("High priority", priority=2)
        todo_manager.add_todo("Medium priority", priority=1)

        todos = todo_manager.get_todos()
        priorities = [todo["priority"] for todo in todos]

        # Higher priority should come first
        assert priorities == sorted(priorities, reverse=True)


class TestUpdateTodo:
    """Tests for updating todo items."""

    def test_update_todo_content(self, todo_manager):
        """Should update todo content."""
        todo_id = todo_manager.add_todo("Original content")
        success = todo_manager.update_todo(todo_id, content="Updated content")

        assert success is True
        todo = todo_manager.get_todo(todo_id)
        assert todo["content"] == "Updated content"

    def test_update_todo_priority(self, todo_manager):
        """Should update todo priority."""
        todo_id = todo_manager.add_todo("Task")
        success = todo_manager.update_todo(todo_id, priority=2)

        assert success is True
        todo = todo_manager.get_todo(todo_id)
        assert todo["priority"] == 2

    def test_update_todo_due_date(self, todo_manager):
        """Should update todo due date."""
        todo_id = todo_manager.add_todo("Task")
        new_due_date = datetime.now() + timedelta(days=3)
        success = todo_manager.update_todo(todo_id, due_date=new_due_date)

        assert success is True
        todo = todo_manager.get_todo(todo_id)
        assert todo["due_date"] is not None

    def test_update_todo_updates_timestamp(self, todo_manager):
        """Should update the updated_at timestamp."""
        todo_id = todo_manager.add_todo("Task")
        original = todo_manager.get_todo(todo_id)

        # Small delay to ensure timestamp difference
        import time
        time.sleep(0.1)

        todo_manager.update_todo(todo_id, content="New content")
        updated = todo_manager.get_todo(todo_id)

        assert updated["updated_at"] >= original["updated_at"]

    def test_update_nonexistent_todo_returns_false(self, todo_manager):
        """Should return False for non-existent todo."""
        success = todo_manager.update_todo(99999, content="New content")
        assert success is False


class TestCompleteTodo:
    """Tests for completing todo items."""

    def test_complete_todo(self, todo_manager):
        """Should mark todo as completed."""
        todo_id = todo_manager.add_todo("Task to complete")
        success = todo_manager.complete_todo(todo_id)

        assert success is True
        todo = todo_manager.get_todo(todo_id)
        assert todo["status"] == "completed"

    def test_complete_todo_sets_completed_at(self, todo_manager):
        """Should set completed_at timestamp."""
        todo_id = todo_manager.add_todo("Task to complete")
        todo_manager.complete_todo(todo_id)

        todo = todo_manager.get_todo(todo_id)
        assert todo["completed_at"] is not None

    def test_complete_nonexistent_todo_returns_false(self, todo_manager):
        """Should return False for non-existent todo."""
        success = todo_manager.complete_todo(99999)
        assert success is False

    def test_complete_todo_by_content_match(self, todo_manager):
        """Should complete todo by fuzzy content match."""
        todo_manager.add_todo("Buy milk from store")
        success = todo_manager.complete_todo_by_match("buy milk")

        assert success is True


class TestDeleteTodo:
    """Tests for deleting todo items."""

    def test_delete_todo(self, todo_manager):
        """Should delete a todo."""
        todo_id = todo_manager.add_todo("To delete")
        success = todo_manager.delete_todo(todo_id)

        assert success is True
        assert todo_manager.get_todo(todo_id) is None

    def test_delete_nonexistent_todo_returns_false(self, todo_manager):
        """Should return False for non-existent todo."""
        success = todo_manager.delete_todo(99999)
        assert success is False


class TestTodoLists:
    """Tests for managing todo lists."""

    def test_create_list(self, todo_manager):
        """Should create a new list."""
        # Use a custom list name since "work" is a default list
        success = todo_manager.create_list("my_projects", description="Project tasks")
        assert success is True

        lists = todo_manager.get_lists()
        list_names = [lst["name"] for lst in lists]
        assert "my_projects" in list_names

    def test_create_duplicate_list_returns_false(self, todo_manager):
        """Should return False when creating duplicate list."""
        todo_manager.create_list("unique")
        success = todo_manager.create_list("unique")
        assert success is False

    def test_get_lists(self, todo_manager):
        """Should return all lists."""
        todo_manager.create_list("list1")
        todo_manager.create_list("list2")

        lists = todo_manager.get_lists()
        assert len(lists) >= 2

    def test_delete_list(self, todo_manager):
        """Should delete a list."""
        todo_manager.create_list("to_delete")
        success = todo_manager.delete_list("to_delete")

        assert success is True
        lists = todo_manager.get_lists()
        list_names = [lst["name"] for lst in lists]
        assert "to_delete" not in list_names

    def test_cannot_delete_default_list(self, todo_manager):
        """Should not allow deleting the default list."""
        success = todo_manager.delete_list("default")
        assert success is False

    def test_deleting_list_moves_todos_to_default(self, todo_manager):
        """Should move todos to default list when deleting a list."""
        todo_manager.create_list("temp_list")
        todo_id = todo_manager.add_todo("Item in temp list", list_name="temp_list")

        todo_manager.delete_list("temp_list")

        todo = todo_manager.get_todo(todo_id)
        assert todo["list_name"] == "default"


class TestSearchTodos:
    """Tests for searching todos."""

    def test_search_by_content(self, todo_manager):
        """Should find todos by content match."""
        todo_manager.add_todo("Buy milk")
        todo_manager.add_todo("Buy eggs")
        todo_manager.add_todo("Call mom")

        results = todo_manager.search_todos("buy")
        assert len(results) == 2

    def test_search_case_insensitive(self, todo_manager):
        """Search should be case insensitive."""
        todo_manager.add_todo("IMPORTANT task")

        results = todo_manager.search_todos("important")
        assert len(results) >= 1

    def test_search_no_results(self, todo_manager):
        """Should return empty list when no matches."""
        results = todo_manager.search_todos("nonexistent query xyz")
        assert results == []


class TestTodoStats:
    """Tests for todo statistics."""

    def test_get_stats(self, todo_manager):
        """Should return statistics about todos."""
        todo_manager.add_todo("Item 1")
        todo_manager.add_todo("Item 2")
        todo_id = todo_manager.add_todo("Item 3")
        todo_manager.complete_todo(todo_id)

        stats = todo_manager.get_stats()

        assert "total" in stats
        assert "pending" in stats
        assert "completed" in stats
        assert stats["total"] >= 3
        assert stats["completed"] >= 1

    def test_get_stats_by_list(self, todo_manager):
        """Should return statistics for a specific list."""
        todo_manager.add_todo("Shopping 1", list_name="shopping")
        todo_manager.add_todo("Shopping 2", list_name="shopping")

        stats = todo_manager.get_stats(list_name="shopping")
        assert stats["total"] >= 2


# Pytest fixture for todo manager with test database
@pytest.fixture
def todo_manager():
    """Create TodoManager with a temporary test database."""
    # Import here to avoid circular imports during collection
    from src.todo_manager import TodoManager

    # Create a temporary database file
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    try:
        manager = TodoManager(database_path=db_path)
        yield manager
    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.remove(db_path)
