"""
Unit tests for Shopping List features (WP-4.4)

Extends the todo system with shopping-specific features:
- Item categorization (groceries, household, produce, etc.)
- Auto-categorization based on common items
- Category-based filtering and grouping

Written TDD-style before implementation.
"""

import pytest
from datetime import datetime
import tempfile
import os


class TestShoppingItemCategories:
    """Tests for shopping item categorization."""

    def test_add_shopping_item_with_category(self, todo_manager):
        """Should add a shopping item with explicit category."""
        todo_id = todo_manager.add_todo(
            "milk",
            list_name="shopping",
            category="dairy"
        )
        todo = todo_manager.get_todo(todo_id)

        assert todo["category"] == "dairy"

    def test_add_shopping_item_without_category(self, todo_manager):
        """Shopping items without category should default to 'other'."""
        todo_id = todo_manager.add_todo(
            "random item",
            list_name="shopping"
        )
        todo = todo_manager.get_todo(todo_id)

        assert todo["category"] == "other"

    def test_update_item_category(self, todo_manager):
        """Should update an item's category."""
        todo_id = todo_manager.add_todo(
            "cheese",
            list_name="shopping",
            category="other"
        )

        success = todo_manager.update_todo(todo_id, category="dairy")
        todo = todo_manager.get_todo(todo_id)

        assert success is True
        assert todo["category"] == "dairy"


class TestAutoCategorization:
    """Tests for automatic item categorization."""

    def test_auto_categorize_dairy_items(self, todo_manager):
        """Should auto-categorize common dairy items."""
        items = ["milk", "cheese", "yogurt", "butter", "cream"]

        for item in items:
            todo_id = todo_manager.add_todo(item, list_name="shopping")
            todo = todo_manager.get_todo(todo_id)
            assert todo["category"] == "dairy", f"{item} should be categorized as dairy"

    def test_auto_categorize_produce_items(self, todo_manager):
        """Should auto-categorize common produce items."""
        items = ["apples", "bananas", "lettuce", "tomatoes", "onions", "carrots"]

        for item in items:
            todo_id = todo_manager.add_todo(item, list_name="shopping")
            todo = todo_manager.get_todo(todo_id)
            assert todo["category"] == "produce", f"{item} should be categorized as produce"

    def test_auto_categorize_meat_items(self, todo_manager):
        """Should auto-categorize common meat items."""
        items = ["chicken", "beef", "pork", "bacon", "sausage", "ground beef"]

        for item in items:
            todo_id = todo_manager.add_todo(item, list_name="shopping")
            todo = todo_manager.get_todo(todo_id)
            assert todo["category"] == "meat", f"{item} should be categorized as meat"

    def test_auto_categorize_bread_items(self, todo_manager):
        """Should auto-categorize bread and bakery items."""
        items = ["bread", "bagels", "rolls", "croissants", "muffins"]

        for item in items:
            todo_id = todo_manager.add_todo(item, list_name="shopping")
            todo = todo_manager.get_todo(todo_id)
            assert todo["category"] == "bakery", f"{item} should be categorized as bakery"

    def test_auto_categorize_frozen_items(self, todo_manager):
        """Should auto-categorize frozen items."""
        items = ["ice cream", "frozen pizza", "frozen vegetables", "frozen waffles"]

        for item in items:
            todo_id = todo_manager.add_todo(item, list_name="shopping")
            todo = todo_manager.get_todo(todo_id)
            assert todo["category"] == "frozen", f"{item} should be categorized as frozen"

    def test_auto_categorize_household_items(self, todo_manager):
        """Should auto-categorize household items."""
        items = ["paper towels", "dish soap", "laundry detergent", "trash bags", "toilet paper"]

        for item in items:
            todo_id = todo_manager.add_todo(item, list_name="shopping")
            todo = todo_manager.get_todo(todo_id)
            assert todo["category"] == "household", f"{item} should be categorized as household"

    def test_auto_categorize_beverages(self, todo_manager):
        """Should auto-categorize beverages."""
        items = ["soda", "juice", "water", "coffee", "tea"]

        for item in items:
            todo_id = todo_manager.add_todo(item, list_name="shopping")
            todo = todo_manager.get_todo(todo_id)
            assert todo["category"] == "beverages", f"{item} should be categorized as beverages"

    def test_explicit_category_overrides_auto(self, todo_manager):
        """Explicit category should override auto-categorization."""
        todo_id = todo_manager.add_todo(
            "milk",  # Would auto-categorize as dairy
            list_name="shopping",
            category="baby"  # But user specified baby
        )
        todo = todo_manager.get_todo(todo_id)

        assert todo["category"] == "baby"

    def test_unknown_item_gets_other_category(self, todo_manager):
        """Unknown items should get 'other' category."""
        todo_id = todo_manager.add_todo(
            "xyz random thing 12345",
            list_name="shopping"
        )
        todo = todo_manager.get_todo(todo_id)

        assert todo["category"] == "other"

    def test_auto_categorize_only_for_shopping_list(self, todo_manager):
        """Auto-categorization should only apply to shopping list."""
        todo_id = todo_manager.add_todo(
            "milk",  # Would be dairy in shopping list
            list_name="default"
        )
        todo = todo_manager.get_todo(todo_id)

        # Non-shopping lists should have None or no category
        assert todo.get("category") is None or todo.get("category") == "other"


class TestCategoryFiltering:
    """Tests for filtering shopping items by category."""

    def test_get_shopping_items_by_category(self, todo_manager):
        """Should filter shopping items by category."""
        todo_manager.add_todo("milk", list_name="shopping", category="dairy")
        todo_manager.add_todo("cheese", list_name="shopping", category="dairy")
        todo_manager.add_todo("bread", list_name="shopping", category="bakery")

        dairy_items = todo_manager.get_todos(list_name="shopping", category="dairy")

        assert len(dairy_items) == 2
        assert all(item["category"] == "dairy" for item in dairy_items)

    def test_get_all_categories_with_counts(self, todo_manager):
        """Should return all categories with item counts."""
        todo_manager.add_todo("milk", list_name="shopping", category="dairy")
        todo_manager.add_todo("cheese", list_name="shopping", category="dairy")
        todo_manager.add_todo("bread", list_name="shopping", category="bakery")
        todo_manager.add_todo("soap", list_name="shopping", category="household")

        categories = todo_manager.get_shopping_categories()

        assert "dairy" in categories
        assert categories["dairy"] == 2
        assert "bakery" in categories
        assert categories["bakery"] == 1
        assert "household" in categories
        assert categories["household"] == 1


class TestCategoryConstants:
    """Tests for category constants and validation."""

    def test_valid_categories(self, todo_manager):
        """Should accept all valid categories."""
        valid_categories = [
            "produce", "dairy", "meat", "seafood", "bakery",
            "frozen", "canned", "beverages", "snacks", "condiments",
            "household", "personal", "baby", "pet", "other"
        ]

        for category in valid_categories:
            todo_id = todo_manager.add_todo(
                f"test item {category}",
                list_name="shopping",
                category=category
            )
            todo = todo_manager.get_todo(todo_id)
            assert todo["category"] == category


class TestShoppingListStats:
    """Tests for shopping list statistics."""

    def test_shopping_stats_include_categories(self, todo_manager):
        """Stats should include category breakdown."""
        todo_manager.add_todo("milk", list_name="shopping", category="dairy")
        todo_manager.add_todo("bread", list_name="shopping", category="bakery")
        todo_manager.add_todo("soap", list_name="shopping", category="household")

        stats = todo_manager.get_stats(list_name="shopping")

        assert "categories" in stats
        assert stats["categories"]["dairy"] == 1
        assert stats["categories"]["bakery"] == 1
        assert stats["categories"]["household"] == 1


# Pytest fixture
@pytest.fixture
def todo_manager():
    """Create TodoManager with a temporary test database."""
    from src.todo_manager import TodoManager

    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    try:
        manager = TodoManager(database_path=db_path)
        yield manager
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)
