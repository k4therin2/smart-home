"""
Smart Home Assistant - Productivity Tools

Agent tools for managing todo lists and reminders.
Part of WP-4.1: Todo List & Reminders feature.
"""

from datetime import datetime, timedelta
from typing import Any

from src.reminder_manager import get_reminder_manager
from src.todo_manager import get_todo_manager
from src.utils import setup_logging


logger = setup_logging("tools.productivity")

# Tool definitions for Claude
PRODUCTIVITY_TOOLS = [
    {
        "name": "add_todo",
        "description": """Add a new todo item to a list.

Examples:
- "add milk to shopping list" -> content='milk', list_name='shopping'
- "add call mom" -> content='call mom', list_name='default'
- "add urgent: finish report to work list" -> content='finish report', list_name='work', priority='high'

Available lists: default, shopping, work, home (or create new ones by specifying a name)
Priority levels: normal (default), high, urgent""",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "The todo item text"},
                "list_name": {
                    "type": "string",
                    "description": "Name of the list (default, shopping, work, home, or custom)",
                    "default": "default",
                },
                "priority": {
                    "type": "string",
                    "enum": ["normal", "high", "urgent"],
                    "description": "Priority level",
                    "default": "normal",
                },
                "due_date": {
                    "type": "string",
                    "description": "Optional due date (e.g., 'tomorrow', '2024-12-25', 'in 3 days')",
                },
            },
            "required": ["content"],
        },
    },
    {
        "name": "list_todos",
        "description": """View todos from a list.

Examples:
- "what's on my todo list" -> list_name='default'
- "show my shopping list" -> list_name='shopping'
- "show all completed todos" -> show_completed=true

Returns a formatted list of todo items with their status and priority.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "list_name": {
                    "type": "string",
                    "description": "Name of the list to view (omit for default)",
                    "default": "default",
                },
                "show_completed": {
                    "type": "boolean",
                    "description": "Include completed items",
                    "default": False,
                },
            },
            "required": [],
        },
    },
    {
        "name": "complete_todo",
        "description": """Mark a todo item as completed.

Can complete by exact ID or by content matching.

Examples:
- "mark buy milk as done" -> content_match='buy milk'
- "complete the eggs task" -> content_match='eggs'""",
        "input_schema": {
            "type": "object",
            "properties": {
                "todo_id": {"type": "integer", "description": "The todo item ID (if known)"},
                "content_match": {
                    "type": "string",
                    "description": "Text to match against todo content (fuzzy match)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "set_reminder",
        "description": """Create a reminder for a specific time.

Examples:
- "remind me to take meds at 9pm" -> message='take meds', remind_at='9pm'
- "remind me in 30 minutes to check laundry" -> message='check laundry', remind_at='in 30 minutes'
- "remind me tomorrow at 8am about the meeting" -> message='about the meeting', remind_at='tomorrow at 8am'
- "remind me daily at 9am to take vitamins" -> message='take vitamins', remind_at='9am', repeat='daily'

Repeat options: daily, weekly, monthly""",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "What to be reminded about"},
                "remind_at": {
                    "type": "string",
                    "description": "When to remind (e.g., '3pm', 'in 2 hours', 'tomorrow at 9am')",
                },
                "repeat": {
                    "type": "string",
                    "enum": ["daily", "weekly", "monthly"],
                    "description": "Repeat interval (optional)",
                },
            },
            "required": ["message", "remind_at"],
        },
    },
    {
        "name": "list_reminders",
        "description": """View upcoming reminders.

Shows all pending reminders with their scheduled times.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "include_past": {
                    "type": "boolean",
                    "description": "Include triggered/dismissed reminders",
                    "default": False,
                }
            },
            "required": [],
        },
    },
    {
        "name": "delete_todo",
        "description": """Delete a todo item (not complete, actually remove it).

Examples:
- "delete the milk todo" -> content_match='milk'
- "remove eggs from shopping list" -> content_match='eggs'""",
        "input_schema": {
            "type": "object",
            "properties": {
                "todo_id": {"type": "integer", "description": "The todo item ID (if known)"},
                "content_match": {
                    "type": "string",
                    "description": "Text to match against todo content",
                },
            },
            "required": [],
        },
    },
    {
        "name": "dismiss_reminder",
        "description": """Dismiss or cancel a reminder without triggering it.

Examples:
- "cancel the meeting reminder" -> match='meeting'
- "dismiss the 9am reminder" -> match='9am'""",
        "input_schema": {
            "type": "object",
            "properties": {
                "reminder_id": {"type": "integer", "description": "The reminder ID (if known)"},
                "match": {
                    "type": "string",
                    "description": "Text to match against reminder message",
                },
            },
            "required": [],
        },
    },
]


def _parse_priority(priority_str: str) -> int:
    """Convert priority string to integer."""
    priority_map = {"normal": 0, "high": 1, "urgent": 2}
    return priority_map.get(priority_str.lower(), 0)


def _parse_due_date(due_str: str) -> datetime | None:
    """Parse a due date string into datetime."""
    if not due_str:
        return None

    due_str = due_str.lower().strip()
    now = datetime.now()

    if due_str == "today":
        return now.replace(hour=23, minute=59, second=59)
    elif due_str == "tomorrow":
        return (now + timedelta(days=1)).replace(hour=23, minute=59, second=59)
    elif due_str.startswith("in "):
        # Parse "in X days"
        import re

        match = re.match(r"in\s+(\d+)\s+days?", due_str)
        if match:
            days = int(match.group(1))
            return (now + timedelta(days=days)).replace(hour=23, minute=59, second=59)

    # Try ISO format
    try:
        return datetime.fromisoformat(due_str)
    except ValueError:
        pass

    return None


def _format_todos(todos: list[dict], list_name: str) -> str:
    """Format todos for voice/text output."""
    if not todos:
        return f"No items on your {list_name} list."

    lines = [f"Your {list_name} list ({len(todos)} items):"]
    for todo in todos:
        priority_marker = ""
        if todo["priority"] == 2:
            priority_marker = "[URGENT] "
        elif todo["priority"] == 1:
            priority_marker = "[HIGH] "

        status_marker = ""
        if todo["status"] == "completed":
            status_marker = "[done] "

        lines.append(f"- {status_marker}{priority_marker}{todo['content']}")

    return "\n".join(lines)


def _format_reminders(reminders: list[dict]) -> str:
    """Format reminders for voice/text output."""
    if not reminders:
        return "No upcoming reminders."

    lines = ["Your upcoming reminders:"]
    for reminder in reminders:
        remind_time = datetime.fromisoformat(reminder["remind_at"])
        time_str = remind_time.strftime("%I:%M %p on %b %d")
        repeat_str = (
            f" (repeats {reminder['repeat_interval']})" if reminder.get("repeat_interval") else ""
        )
        lines.append(f"- {reminder['message']} at {time_str}{repeat_str}")

    return "\n".join(lines)


def add_todo(
    content: str,
    list_name: str = "default",
    priority: str = "normal",
    due_date: str | None = None,
) -> dict[str, Any]:
    """
    Add a new todo item.

    Args:
        content: Todo item text
        list_name: Name of the list
        priority: Priority level (normal, high, urgent)
        due_date: Optional due date string

    Returns:
        Result dictionary with success status
    """
    if not content or not content.strip():
        return {"success": False, "error": "Content cannot be empty"}

    try:
        manager = get_todo_manager()
        priority_int = _parse_priority(priority)
        due_datetime = _parse_due_date(due_date) if due_date else None

        todo_id = manager.add_todo(
            content=content.strip(),
            list_name=list_name,
            priority=priority_int,
            due_date=due_datetime,
        )

        logger.info(f"Added todo: '{content}' to {list_name}")

        return {
            "success": True,
            "todo_id": todo_id,
            "content": content,
            "list_name": list_name,
            "message": f"Added '{content}' to your {list_name} list.",
        }

    except Exception as error:
        logger.error(f"Error adding todo: {error}")
        return {"success": False, "error": str(error)}


def list_todos(
    list_name: str = "default",
    show_completed: bool = False,
) -> dict[str, Any]:
    """
    Get todos from a list.

    Args:
        list_name: Name of the list
        show_completed: Include completed items

    Returns:
        Result dictionary with todos
    """
    try:
        manager = get_todo_manager()
        todos = manager.get_todos(list_name=list_name, include_completed=show_completed)

        return {
            "success": True,
            "todos": todos,
            "count": len(todos),
            "list_name": list_name,
            "message": _format_todos(todos, list_name),
        }

    except Exception as error:
        logger.error(f"Error listing todos: {error}")
        return {"success": False, "error": str(error)}


def complete_todo(
    todo_id: int | None = None,
    content_match: str | None = None,
) -> dict[str, Any]:
    """
    Mark a todo as completed.

    Args:
        todo_id: Todo ID (if known)
        content_match: Text to match against content

    Returns:
        Result dictionary with success status
    """
    if not todo_id and not content_match:
        return {"success": False, "error": "Either todo_id or content_match is required"}

    try:
        manager = get_todo_manager()

        if todo_id:
            success = manager.complete_todo(todo_id)
            if success:
                todo = manager.get_todo(todo_id)
                return {
                    "success": True,
                    "todo_id": todo_id,
                    "message": f"Marked '{todo['content']}' as complete.",
                }
            else:
                return {"success": False, "error": f"Todo {todo_id} not found"}
        else:
            success = manager.complete_todo_by_match(content_match)
            if success:
                return {"success": True, "message": f"Marked '{content_match}' as complete."}
            else:
                return {"success": False, "error": f"No matching todo found for '{content_match}'"}

    except Exception as error:
        logger.error(f"Error completing todo: {error}")
        return {"success": False, "error": str(error)}


def delete_todo(
    todo_id: int | None = None,
    content_match: str | None = None,
) -> dict[str, Any]:
    """
    Delete a todo item.

    Args:
        todo_id: Todo ID (if known)
        content_match: Text to match against content

    Returns:
        Result dictionary with success status
    """
    if not todo_id and not content_match:
        return {"success": False, "error": "Either todo_id or content_match is required"}

    try:
        manager = get_todo_manager()

        if todo_id:
            success = manager.delete_todo(todo_id)
            if success:
                return {"success": True, "message": f"Deleted todo {todo_id}."}
            else:
                return {"success": False, "error": f"Todo {todo_id} not found"}
        else:
            # Find matching todo first
            todos = manager.search_todos(content_match)
            if todos:
                todo = todos[0]
                manager.delete_todo(todo["id"])
                return {"success": True, "message": f"Deleted '{todo['content']}'."}
            else:
                return {"success": False, "error": f"No matching todo found for '{content_match}'"}

    except Exception as error:
        logger.error(f"Error deleting todo: {error}")
        return {"success": False, "error": str(error)}


def set_reminder(
    message: str,
    remind_at: str,
    repeat: str | None = None,
) -> dict[str, Any]:
    """
    Create a reminder.

    Args:
        message: What to be reminded about
        remind_at: When to remind (natural language)
        repeat: Repeat interval (daily, weekly, monthly)

    Returns:
        Result dictionary with success status
    """
    if not message or not message.strip():
        return {"success": False, "error": "Message cannot be empty"}

    try:
        manager = get_reminder_manager()

        # Parse the reminder time
        remind_datetime = manager.parse_reminder_time(remind_at)
        if not remind_datetime:
            return {
                "success": False,
                "error": f"Could not understand time '{remind_at}'. Try '3pm', 'in 2 hours', or 'tomorrow at 9am'.",
            }

        reminder_id = manager.set_reminder(
            message=message.strip(),
            remind_at=remind_datetime,
            repeat_interval=repeat,
        )

        time_str = remind_datetime.strftime("%I:%M %p on %b %d")
        repeat_msg = f" (repeating {repeat})" if repeat else ""

        logger.info(f"Set reminder: '{message}' at {remind_datetime}")

        return {
            "success": True,
            "reminder_id": reminder_id,
            "message": message,
            "remind_at": remind_datetime.isoformat(),
            "response_message": f"I'll remind you to {message} at {time_str}{repeat_msg}.",
        }

    except ValueError as error:
        return {"success": False, "error": str(error)}
    except Exception as error:
        logger.error(f"Error setting reminder: {error}")
        return {"success": False, "error": str(error)}


def list_reminders(include_past: bool = False) -> dict[str, Any]:
    """
    Get upcoming reminders.

    Args:
        include_past: Include triggered/dismissed reminders

    Returns:
        Result dictionary with reminders
    """
    try:
        manager = get_reminder_manager()

        if include_past:
            # Get all reminders (would need to add method)
            reminders = manager.get_pending_reminders()
        else:
            reminders = manager.get_pending_reminders()

        return {
            "success": True,
            "reminders": reminders,
            "count": len(reminders),
            "message": _format_reminders(reminders),
        }

    except Exception as error:
        logger.error(f"Error listing reminders: {error}")
        return {"success": False, "error": str(error)}


def dismiss_reminder(
    reminder_id: int | None = None,
    match: str | None = None,
) -> dict[str, Any]:
    """
    Dismiss a reminder.

    Args:
        reminder_id: Reminder ID (if known)
        match: Text to match against message

    Returns:
        Result dictionary with success status
    """
    if not reminder_id and not match:
        return {"success": False, "error": "Either reminder_id or match is required"}

    try:
        manager = get_reminder_manager()

        if reminder_id:
            success = manager.dismiss_reminder(reminder_id)
            if success:
                return {"success": True, "message": f"Dismissed reminder {reminder_id}."}
            else:
                return {"success": False, "error": f"Reminder {reminder_id} not found"}
        else:
            # Find matching reminder
            reminders = manager.get_pending_reminders()
            for reminder in reminders:
                if match.lower() in reminder["message"].lower():
                    manager.dismiss_reminder(reminder["id"])
                    return {
                        "success": True,
                        "message": f"Dismissed reminder: {reminder['message']}",
                    }
            return {"success": False, "error": f"No matching reminder found for '{match}'"}

    except Exception as error:
        logger.error(f"Error dismissing reminder: {error}")
        return {"success": False, "error": str(error)}


def execute_productivity_tool(tool_name: str, tool_input: dict) -> dict[str, Any]:
    """
    Execute a productivity tool by name.

    Args:
        tool_name: Name of the tool
        tool_input: Tool input parameters

    Returns:
        Tool result dictionary
    """
    logger.info(f"Executing productivity tool: {tool_name}")

    if tool_name == "add_todo":
        return add_todo(
            content=tool_input.get("content", ""),
            list_name=tool_input.get("list_name", "default"),
            priority=tool_input.get("priority", "normal"),
            due_date=tool_input.get("due_date"),
        )

    elif tool_name == "list_todos":
        return list_todos(
            list_name=tool_input.get("list_name", "default"),
            show_completed=tool_input.get("show_completed", False),
        )

    elif tool_name == "complete_todo":
        return complete_todo(
            todo_id=tool_input.get("todo_id"),
            content_match=tool_input.get("content_match"),
        )

    elif tool_name == "delete_todo":
        return delete_todo(
            todo_id=tool_input.get("todo_id"),
            content_match=tool_input.get("content_match"),
        )

    elif tool_name == "set_reminder":
        return set_reminder(
            message=tool_input.get("message", ""),
            remind_at=tool_input.get("remind_at", ""),
            repeat=tool_input.get("repeat"),
        )

    elif tool_name == "list_reminders":
        return list_reminders(
            include_past=tool_input.get("include_past", False),
        )

    elif tool_name == "dismiss_reminder":
        return dismiss_reminder(
            reminder_id=tool_input.get("reminder_id"),
            match=tool_input.get("match"),
        )

    else:
        return {"success": False, "error": f"Unknown tool: {tool_name}"}
