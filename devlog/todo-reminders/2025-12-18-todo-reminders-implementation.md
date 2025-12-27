# WP-4.1: Todo List & Reminders Implementation

**Date:** 2025-12-18
**Status:** Code Complete
**Work Package:** WP-4.1

## Summary

Implemented a full-featured todo list and reminder management system with SQLite persistence, agent tools for voice commands, web UI integration, and comprehensive test coverage.

## Components Implemented

### 1. TodoManager (`src/todo_manager.py`)

SQLite-backed todo list manager with:
- Multiple named lists (default, shopping, work, home)
- Priority levels (0=normal, 1=high, 2=urgent)
- Due dates and tags
- Fuzzy content matching for completion
- Statistics and search functionality
- Auto-creation of lists when adding items

**Key Methods:**
- `add_todo()` - Create todo with content, list, priority, due date, tags
- `get_todo()` / `get_todos()` - Retrieve single or filtered todos
- `update_todo()` - Modify todo fields
- `complete_todo()` / `complete_todo_by_match()` - Mark complete by ID or fuzzy match
- `delete_todo()` - Remove todo
- `search_todos()` - Search by content
- `get_stats()` - Get counts by status

### 2. ReminderManager (`src/reminder_manager.py`)

SQLite-backed reminder system with:
- One-time and repeating reminders (daily, weekly, monthly)
- Natural language time parsing ("3pm", "in 2 hours", "tomorrow at 9am")
- Link reminders to todo items
- Snooze functionality
- Automatic rescheduling of repeating reminders

**Key Methods:**
- `set_reminder()` - Create reminder with message, time, repeat interval
- `get_pending_reminders()` / `get_due_reminders()` - Retrieve active reminders
- `trigger_reminder()` - Mark triggered and schedule next if repeating
- `dismiss_reminder()` - Cancel without triggering
- `snooze_reminder()` - Reschedule to new time
- `parse_reminder_time()` - NL time string to datetime

### 3. Agent Tools (`tools/productivity.py`)

Seven tools for voice command integration:

| Tool | Description |
|------|-------------|
| `add_todo` | Add items to any list with priority |
| `list_todos` | View todos from a list |
| `complete_todo` | Mark done by ID or content match |
| `delete_todo` | Remove a todo item |
| `set_reminder` | Create one-time or repeating reminder |
| `list_reminders` | View upcoming reminders |
| `dismiss_reminder` | Cancel a reminder |

### 4. Web UI (`templates/index.html`, `static/app.js`)

- Todo section with tabbed list selector (Default, Shopping, Work)
- Quick add form for new items
- Checkbox to mark complete
- Delete button per item
- Show/hide completed toggle
- Responsive design for mobile

### 5. API Endpoints (`src/server.py`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/todos` | GET | List todos with filtering |
| `/api/todos` | POST | Add new todo |
| `/api/todos/<id>/complete` | POST | Mark complete |
| `/api/todos/<id>` | DELETE | Delete todo |
| `/api/reminders` | GET | List reminders |
| `/api/reminders/<id>/dismiss` | POST | Dismiss reminder |

All endpoints protected with:
- Session-based authentication (`@login_required`)
- Rate limiting (20-30 req/min)
- CSRF exemption for API calls (using Bearer token)

## Test Coverage

### Unit Tests

**test_todo_manager.py** (41+ tests):
- Initialization and table creation
- CRUD operations (add, get, update, delete)
- List management (create, delete, default protection)
- Search and fuzzy matching
- Statistics
- Priority ordering

**test_reminder_manager.py** (38+ tests):
- Initialization and table creation
- CRUD operations
- Pending and due reminder retrieval
- Trigger and reschedule logic
- Snooze functionality
- Natural language time parsing

### Integration Tests

**test_productivity.py** (33 tests):
- Tool function integration with managers
- Voice command scenarios
- Error handling
- Tool dispatcher

## Voice Command Examples

```
"add milk to shopping list"
"what's on my todo list"
"show my shopping list"
"mark buy milk as done"
"remind me to take meds at 9pm"
"remind me in 30 minutes to check laundry"
"remind me daily at 9am to take vitamins"
"cancel the meeting reminder"
```

## Files Changed

```
src/todo_manager.py          # New - TodoManager class
src/reminder_manager.py      # New - ReminderManager class
tools/productivity.py        # New - 7 agent tools
tests/unit/test_todo_manager.py      # New - 41+ tests
tests/unit/test_reminder_manager.py  # New - 38+ tests
tests/integration/test_productivity.py # New - 33 tests
templates/index.html         # Updated - Todo section UI
static/app.js                # Updated - Todo list JavaScript
src/server.py                # Updated - API endpoints
agent.py                     # Updated - Tool integration
```

## Deferred Items

1. **Background Reminder Worker** - Requires a scheduler (APScheduler or similar) to poll `get_due_reminders()` and trigger notifications. Deferred to Phase 5 self-monitoring work.

2. **Voice Puck Notifications** - Depends on WP-3.1b (USER TASK) hardware setup. TTS announcement integration ready via ResponseFormatter.

3. **Push Notifications** - PWA service worker supports web notifications. Integration with reminder triggers deferred to Phase 5.

## Acceptance Criteria Status

| Criterion | Status |
|-----------|--------|
| Add todos via voice | PASS |
| Multiple lists supported | PASS |
| Set reminders with deadlines | PASS |
| Voice/UI notifications for reminders | PARTIAL (UI complete, background worker needed) |
| Mark items complete | PASS |
| List viewing via UI | PASS |

## Architecture Notes

- Both managers use SQLite with proper indexing
- Thread-safe via connection-per-operation pattern
- Singleton pattern for application-wide instance
- Fuzzy matching uses SQL LIKE with case-insensitive search
- Repeating reminders create new records (immutable trigger history)

## Next Steps

1. Add background scheduler for reminder polling (Phase 5)
2. Integrate with voice puck TTS for spoken reminders (after WP-3.1b)
3. Add PWA push notification triggers (Phase 5)
