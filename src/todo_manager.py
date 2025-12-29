"""
Smart Home Assistant - Todo List Manager

Manages todo items and lists with SQLite persistence.
Part of WP-4.1: Todo List & Reminders feature.
"""

import json
import logging
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from src.config import DATA_DIR


logger = logging.getLogger(__name__)

# Default database path
DEFAULT_DATABASE_PATH = DATA_DIR / "todos.db"

# Default lists that should always exist
DEFAULT_LISTS = [
    {"name": "default", "description": "General todo items"},
    {"name": "shopping", "description": "Shopping list"},
    {"name": "work", "description": "Work-related tasks"},
    {"name": "home", "description": "Home and household tasks"},
]

# Valid shopping categories
SHOPPING_CATEGORIES = [
    "produce",
    "dairy",
    "meat",
    "seafood",
    "bakery",
    "frozen",
    "canned",
    "beverages",
    "snacks",
    "condiments",
    "household",
    "personal",
    "baby",
    "pet",
    "other",
]

# Auto-categorization mappings (lowercase keywords -> category)
CATEGORY_KEYWORDS = {
    "dairy": [
        "milk",
        "cheese",
        "yogurt",
        "butter",
        "cream",
        "sour cream",
        "cottage cheese",
        "half and half",
        "creamer",
        "eggs",
    ],
    "produce": [
        "apple",
        "banana",
        "orange",
        "lettuce",
        "tomato",
        "onion",
        "carrot",
        "potato",
        "broccoli",
        "spinach",
        "cucumber",
        "pepper",
        "celery",
        "garlic",
        "lemon",
        "lime",
        "avocado",
        "mushroom",
        "corn",
        "beans",
        "peas",
        "squash",
        "zucchini",
        "cabbage",
        "kale",
        "grape",
        "berry",
        "strawberry",
        "blueberry",
        "raspberry",
        "melon",
        "watermelon",
        "peach",
        "pear",
        "plum",
        "mango",
        "pineapple",
        "fruit",
        "vegetable",
    ],
    "meat": [
        "chicken",
        "beef",
        "pork",
        "bacon",
        "sausage",
        "ham",
        "turkey",
        "ground beef",
        "steak",
        "ribs",
        "lamb",
        "veal",
        "hot dog",
        "deli meat",
        "lunch meat",
        "meatball",
    ],
    "seafood": [
        "fish",
        "salmon",
        "tuna",
        "shrimp",
        "crab",
        "lobster",
        "cod",
        "tilapia",
        "halibut",
        "scallop",
        "clam",
        "mussel",
        "oyster",
    ],
    "bakery": [
        "bread",
        "bagel",
        "roll",
        "croissant",
        "muffin",
        "donut",
        "cake",
        "pie",
        "cookie",
        "pastry",
        "bun",
        "tortilla",
        "pita",
    ],
    "frozen": [
        "frozen",
        "ice cream",
        "frozen pizza",
        "frozen vegetable",
        "frozen waffle",
        "frozen dinner",
        "popsicle",
        "frozen fruit",
    ],
    "canned": ["canned", "soup", "beans", "tomato sauce", "pasta sauce", "tuna can", "corn can"],
    "beverages": [
        "soda",
        "juice",
        "water",
        "coffee",
        "tea",
        "drink",
        "beer",
        "wine",
        "sparkling",
        "lemonade",
        "gatorade",
        "energy drink",
    ],
    "snacks": [
        "chips",
        "crackers",
        "popcorn",
        "pretzel",
        "nuts",
        "granola",
        "candy",
        "chocolate",
        "gum",
    ],
    "condiments": [
        "ketchup",
        "mustard",
        "mayo",
        "mayonnaise",
        "salsa",
        "sauce",
        "dressing",
        "vinegar",
        "oil",
        "spice",
        "seasoning",
        "salt",
        "pepper",
        "sugar",
        "honey",
        "syrup",
        "jam",
        "jelly",
        "peanut butter",
    ],
    "household": [
        "paper towel",
        "dish soap",
        "laundry detergent",
        "trash bag",
        "toilet paper",
        "napkin",
        "tissue",
        "cleaner",
        "sponge",
        "aluminum foil",
        "plastic wrap",
        "ziploc",
        "light bulb",
        "battery",
        "soap",
    ],
    "personal": [
        "shampoo",
        "conditioner",
        "body wash",
        "deodorant",
        "toothpaste",
        "toothbrush",
        "razor",
        "lotion",
        "sunscreen",
        "makeup",
    ],
    "baby": ["diaper", "baby food", "formula", "baby wipe", "pacifier"],
    "pet": ["dog food", "cat food", "pet food", "cat litter", "pet treat"],
}


class TodoManager:
    """
    Manages todo items and lists with SQLite persistence.

    Provides CRUD operations for todos and todo lists, with support for:
    - Multiple named lists (default, shopping, work, etc.)
    - Priority levels (0=normal, 1=high, 2=urgent)
    - Due dates and tags
    - Fuzzy content matching for completion
    """

    def __init__(self, database_path: Path | None = None):
        """
        Initialize TodoManager with database connection.

        Args:
            database_path: Path to SQLite database file (defaults to DATA_DIR/todos.db)
        """
        self.database_path = database_path or DEFAULT_DATABASE_PATH
        self._initialize_database()

    def _get_connection(self) -> sqlite3.Connection:
        """Create a database connection with row factory."""
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _get_cursor(self) -> Generator[sqlite3.Cursor, None, None]:
        """Context manager for database operations."""
        connection = self._get_connection()
        try:
            cursor = connection.cursor()
            yield cursor
            connection.commit()
        except Exception as error:
            connection.rollback()
            logger.error(f"Database error: {error}")
            raise
        finally:
            connection.close()

    def _initialize_database(self):
        """Create tables and default data if they don't exist."""
        with self._get_cursor() as cursor:
            # Create todo_lists table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS todo_lists (
                    name TEXT PRIMARY KEY,
                    description TEXT,
                    icon TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create todos table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS todos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    list_name TEXT NOT NULL DEFAULT 'default',
                    content TEXT NOT NULL,
                    priority INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    due_date TIMESTAMP,
                    tags TEXT,
                    category TEXT,
                    FOREIGN KEY (list_name) REFERENCES todo_lists(name)
                )
            """)

            # Add category column if it doesn't exist (migration for existing DBs)
            try:
                cursor.execute("ALTER TABLE todos ADD COLUMN category TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists

            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_todos_list_name
                ON todos(list_name)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_todos_status
                ON todos(status)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_todos_content
                ON todos(content)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_todos_category
                ON todos(category)
            """)

            # Create default lists
            for default_list in DEFAULT_LISTS:
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO todo_lists (name, description)
                    VALUES (?, ?)
                """,
                    (default_list["name"], default_list["description"]),
                )

        logger.info(f"TodoManager initialized with database at {self.database_path}")

    def add_todo(
        self,
        content: str,
        list_name: str = "default",
        priority: int = 0,
        due_date: datetime | None = None,
        tags: list[str] | None = None,
        category: str | None = None,
    ) -> int:
        """
        Add a new todo item.

        Args:
            content: Todo item text (required, non-empty)
            list_name: Name of the list to add to (default: 'default')
            priority: Priority level (0=normal, 1=high, 2=urgent)
            due_date: Optional deadline for the todo
            tags: Optional list of tags
            category: Category for shopping list items (auto-detected if not provided)

        Returns:
            ID of the created todo

        Raises:
            ValueError: If content is empty
        """
        if not content or not content.strip():
            raise ValueError("content cannot be empty")

        content = content.strip()

        # Ensure the list exists
        self._ensure_list_exists(list_name)

        tags_json = json.dumps(tags) if tags else None
        due_date_str = due_date.isoformat() if due_date else None

        # Auto-categorize shopping list items if no category provided
        if list_name == "shopping":
            if category is None:
                category = self._auto_categorize(content)
            elif category not in SHOPPING_CATEGORIES:
                category = "other"
        else:
            # Non-shopping lists don't use categories
            category = None

        with self._get_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO todos (list_name, content, priority, due_date, tags, category)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (list_name, content, priority, due_date_str, tags_json, category),
            )

            todo_id = cursor.lastrowid
            logger.info(
                f"Added todo {todo_id}: '{content}' to list '{list_name}'"
                + (f" (category: {category})" if category else "")
            )
            return todo_id

    def _auto_categorize(self, content: str) -> str:
        """Auto-categorize a shopping item based on keywords."""
        content_lower = content.lower()

        # Build list of (keyword, category) tuples and sort by keyword length descending
        # This ensures longer, more specific matches are checked first
        # e.g., "ice cream" matches frozen before "cream" matches dairy
        keyword_matches = []
        for category, keywords in CATEGORY_KEYWORDS.items():
            for keyword in keywords:
                keyword_matches.append((keyword, category))

        # Sort by keyword length descending (longer = more specific = higher priority)
        keyword_matches.sort(key=lambda x: len(x[0]), reverse=True)

        for keyword, category in keyword_matches:
            # Check if keyword is in the content (as a word or part of word)
            if keyword in content_lower:
                return category

        return "other"

    def get_todo(self, todo_id: int) -> dict[str, Any] | None:
        """
        Get a todo by ID.

        Args:
            todo_id: Todo item ID

        Returns:
            Todo dict or None if not found
        """
        with self._get_cursor() as cursor:
            cursor.execute("SELECT * FROM todos WHERE id = ?", (todo_id,))
            row = cursor.fetchone()

            if row is None:
                return None

            return self._row_to_dict(row)

    def get_todos(
        self,
        list_name: str | None = None,
        status: str | None = None,
        include_completed: bool = False,
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get todos with optional filtering.

        Args:
            list_name: Filter by list name (None for all lists, empty uses 'default')
            status: Filter by status (pending, completed, cancelled)
            include_completed: Include completed items (default: False)
            category: Filter by category (shopping list only)

        Returns:
            List of todo dicts ordered by priority (desc) then created_at (asc)
        """
        query = "SELECT * FROM todos WHERE 1=1"
        params = []

        if list_name is not None:
            query += " AND list_name = ?"
            params.append(list_name if list_name else "default")

        if status:
            query += " AND status = ?"
            params.append(status)
        elif not include_completed:
            query += " AND status != 'completed'"

        if category is not None:
            query += " AND category = ?"
            params.append(category)

        query += " ORDER BY priority DESC, created_at ASC"

        with self._get_cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [self._row_to_dict(row) for row in rows]

    def update_todo(self, todo_id: int, **kwargs) -> bool:
        """
        Update a todo item.

        Args:
            todo_id: Todo item ID
            **kwargs: Fields to update (content, priority, due_date, tags, status, list_name, category)

        Returns:
            True if todo was updated, False if not found
        """
        allowed_fields = {
            "content",
            "priority",
            "due_date",
            "tags",
            "status",
            "list_name",
            "category",
        }
        updates = {key: value for key, value in kwargs.items() if key in allowed_fields}

        if not updates:
            return False

        # Special handling for certain fields
        if "tags" in updates:
            updates["tags"] = json.dumps(updates["tags"]) if updates["tags"] else None
        if updates.get("due_date"):
            updates["due_date"] = (
                updates["due_date"].isoformat()
                if isinstance(updates["due_date"], datetime)
                else updates["due_date"]
            )

        # Always update updated_at
        updates["updated_at"] = datetime.now().isoformat()

        # Build dynamic SET clause - safe because keys are validated against allowed_fields
        # Column names are from allowlist, values use parameterized queries
        set_clause = ", ".join(f"{key} = ?" for key in updates)  # nosec B608
        values = list(updates.values()) + [todo_id]

        with self._get_cursor() as cursor:
            cursor.execute(f"UPDATE todos SET {set_clause} WHERE id = ?", values)  # nosec B608
            success = cursor.rowcount > 0

            if success:
                logger.info(f"Updated todo {todo_id}: {list(updates.keys())}")
            return success

    def complete_todo(self, todo_id: int) -> bool:
        """
        Mark a todo as completed.

        Args:
            todo_id: Todo item ID

        Returns:
            True if todo was completed, False if not found
        """
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                UPDATE todos
                SET status = 'completed',
                    completed_at = ?,
                    updated_at = ?
                WHERE id = ?
            """,
                (datetime.now().isoformat(), datetime.now().isoformat(), todo_id),
            )

            success = cursor.rowcount > 0
            if success:
                logger.info(f"Completed todo {todo_id}")
            return success

    def complete_todo_by_match(self, content_query: str) -> bool:
        """
        Complete the first todo matching the content query (fuzzy match).

        Args:
            content_query: Text to match against todo content

        Returns:
            True if a todo was completed, False if no match found
        """
        # Find the best matching pending todo
        with self._get_cursor() as cursor:
            # Case-insensitive partial match
            cursor.execute(
                """
                SELECT id FROM todos
                WHERE status = 'pending'
                AND LOWER(content) LIKE LOWER(?)
                ORDER BY priority DESC, created_at ASC
                LIMIT 1
            """,
                (f"%{content_query}%",),
            )

            row = cursor.fetchone()
            if row:
                return self.complete_todo(row["id"])
            return False

    def delete_todo(self, todo_id: int) -> bool:
        """
        Delete a todo item.

        Args:
            todo_id: Todo item ID

        Returns:
            True if todo was deleted, False if not found
        """
        with self._get_cursor() as cursor:
            cursor.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
            success = cursor.rowcount > 0
            if success:
                logger.info(f"Deleted todo {todo_id}")
            return success

    def create_list(self, name: str, description: str | None = None) -> bool:
        """
        Create a new todo list.

        Args:
            name: List name (unique)
            description: Optional list description

        Returns:
            True if list was created, False if already exists
        """
        try:
            with self._get_cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO todo_lists (name, description)
                    VALUES (?, ?)
                """,
                    (name, description),
                )
                logger.info(f"Created list '{name}'")
                return True
        except sqlite3.IntegrityError:
            # List already exists
            return False

    def get_lists(self) -> list[dict[str, Any]]:
        """
        Get all todo lists.

        Returns:
            List of list dicts with name, description, and item counts
        """
        with self._get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    tl.name,
                    tl.description,
                    tl.icon,
                    tl.created_at,
                    COUNT(t.id) as item_count,
                    SUM(CASE WHEN t.status = 'pending' THEN 1 ELSE 0 END) as pending_count
                FROM todo_lists tl
                LEFT JOIN todos t ON tl.name = t.list_name
                GROUP BY tl.name
                ORDER BY tl.name
            """)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def delete_list(self, name: str) -> bool:
        """
        Delete a todo list and move its items to default.

        Args:
            name: List name to delete

        Returns:
            True if list was deleted, False if not found or is default
        """
        # Cannot delete the default list
        if name == "default":
            logger.warning("Cannot delete the default list")
            return False

        with self._get_cursor() as cursor:
            # Move todos to default list first
            cursor.execute(
                """
                UPDATE todos SET list_name = 'default'
                WHERE list_name = ?
            """,
                (name,),
            )

            # Delete the list
            cursor.execute("DELETE FROM todo_lists WHERE name = ?", (name,))
            success = cursor.rowcount > 0

            if success:
                logger.info(f"Deleted list '{name}' and moved items to default")
            return success

    def search_todos(self, query: str) -> list[dict[str, Any]]:
        """
        Search todos by content.

        Args:
            query: Search query (case-insensitive)

        Returns:
            List of matching todo dicts
        """
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM todos
                WHERE LOWER(content) LIKE LOWER(?)
                ORDER BY priority DESC, created_at ASC
            """,
                (f"%{query}%",),
            )
            rows = cursor.fetchall()
            return [self._row_to_dict(row) for row in rows]

    def get_stats(self, list_name: str | None = None) -> dict[str, int]:
        """
        Get statistics about todos.

        Args:
            list_name: Optional list name to filter by

        Returns:
            Dict with total, pending, completed, and overdue counts
        """
        with self._get_cursor() as cursor:
            if list_name:
                cursor.execute(
                    """
                    SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                        SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled,
                        SUM(CASE WHEN due_date < datetime('now') AND status = 'pending' THEN 1 ELSE 0 END) as overdue
                    FROM todos
                    WHERE list_name = ?
                """,
                    (list_name,),
                )
            else:
                cursor.execute("""
                    SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                        SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled,
                        SUM(CASE WHEN due_date < datetime('now') AND status = 'pending' THEN 1 ELSE 0 END) as overdue
                    FROM todos
                """)

            row = cursor.fetchone()
            stats = {
                "total": row["total"] or 0,
                "pending": row["pending"] or 0,
                "completed": row["completed"] or 0,
                "cancelled": row["cancelled"] or 0,
                "overdue": row["overdue"] or 0,
            }

            # Add category breakdown for shopping list
            if list_name == "shopping":
                stats["categories"] = self.get_shopping_categories()

            return stats

    def get_shopping_categories(self) -> dict[str, int]:
        """
        Get category counts for shopping list items.

        Returns:
            Dict mapping category names to item counts (pending items only)
        """
        with self._get_cursor() as cursor:
            cursor.execute("""
                SELECT category, COUNT(*) as count
                FROM todos
                WHERE list_name = 'shopping' AND status = 'pending' AND category IS NOT NULL
                GROUP BY category
                ORDER BY category
            """)
            rows = cursor.fetchall()
            return {row["category"]: row["count"] for row in rows}

    def _ensure_list_exists(self, list_name: str):
        """Ensure a list exists, creating it if necessary."""
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                INSERT OR IGNORE INTO todo_lists (name, description)
                VALUES (?, ?)
            """,
                (list_name, f"Auto-created list: {list_name}"),
            )

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        """Convert a database row to a dict with parsed JSON fields."""
        result = dict(row)
        if result.get("tags"):
            result["tags"] = json.loads(result["tags"])
        return result


# Singleton instance
_todo_manager: TodoManager | None = None


def get_todo_manager() -> TodoManager:
    """Get the singleton TodoManager instance."""
    global _todo_manager
    if _todo_manager is None:
        _todo_manager = TodoManager()
    return _todo_manager
