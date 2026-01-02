"""
Response Feedback Handler

Handles user feedback on assistant responses:
- Files bugs in Vikunja when users report issues
- Alerts developers via NATS
- Retries commands with user-provided context
"""

import asyncio
import logging
import os
import ssl
import sys
from datetime import datetime
from pathlib import Path

# Add agent-automation to path for Vikunja client
AGENT_AUTOMATION_PATH = Path.home() / "projects" / "agent-automation" / "orchestrator"
sys.path.insert(0, str(AGENT_AUTOMATION_PATH / "vikunja-migration"))

from nats.aio.client import Client as NATS

logger = logging.getLogger(__name__)

# NATS configuration
NATS_URL = os.getenv("NATS_URL", "nats://100.75.232.36:4222")


def get_vikunja_client():
    """Get configured Vikunja client."""
    try:
        from vikunja_client import VikunjaClient, VikunjaConfig
        config = VikunjaConfig.from_env()
        return VikunjaClient(config)
    except Exception as e:
        logger.error(f"Failed to create Vikunja client: {e}")
        return None


SMARTHOME_PROJECT_ID = 93  # Pre-created Smarthome project in Vikunja


def file_bug_in_vikunja(
    command: str,
    response: str,
) -> str | None:
    """
    File a bug in Vikunja for a failed response.

    Args:
        command: The original command
        response: The response that was given

    Returns:
        Bug ID (e.g., "BUG-123") or None if failed
    """
    client = get_vikunja_client()
    if not client:
        logger.error("Could not create Vikunja client")
        return None

    try:
        # Use the known Smarthome project ID directly
        # (find_project_by_title has pagination issues)
        try:
            project = client.get_project(SMARTHOME_PROJECT_ID)
        except Exception:
            project = None

        if not project:
            logger.error(f"Smarthome project (ID {SMARTHOME_PROJECT_ID}) not found in Vikunja")
            return None

        # Generate bug ID from timestamp
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        bug_id = f"BUG-{timestamp}"

        # Create task title
        command_preview = command[:50] + "..." if len(command) > 50 else command
        task_title = f"{bug_id}: User-Reported Response Failure"

        # Build description
        description = f"""User marked this response as unsuccessful.

## Command
```
{command}
```

## Response Given
```
{response[:500]}{"..." if len(response) > 500 else ""}
```

---
Reported: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Reporter: User (via feedback button)
Priority: P2
"""

        # Create the task
        task = client.create_task(
            project_id=project["id"],
            title=task_title,
            description=description
        )

        if not task:
            logger.error("Failed to create Vikunja task")
            return None

        task_id = task["id"]

        # Add labels
        bug_label = client.get_or_create_label("bug", "e74c3c")
        p2_label = client.get_or_create_label("P2", "f39c12")
        source_label = client.get_or_create_label("bug:user-filed", "e74c3c")

        for label in [bug_label, p2_label, source_label]:
            if label:
                client.add_label_to_task(task_id, label["id"])

        logger.info(f"Filed {bug_id} in Vikunja (task {task_id})")
        return bug_id

    except Exception as e:
        logger.error(f"Error filing bug in Vikunja: {e}")
        return None


async def _send_nats_alert(bug_id: str, command: str, response: str):
    """Send async NATS message to alert developers."""
    nc = NATS()
    try:
        # Create SSL context that accepts self-signed certificates
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

        await nc.connect(NATS_URL, tls=ssl_ctx, allow_reconnect=False)

        message = f"""New Bug Filed: {bug_id}

**Command:** {command[:100]}{"..." if len(command) > 100 else ""}
**Response:** {response[:150]}{"..." if len(response) > 150 else ""}

User marked this response as unsuccessful. Please investigate.
Project: smarthome"""

        # Post to coordination channel for developer visibility
        await nc.publish("agent-chat.coordination", message.encode())
        await nc.flush()
        logger.info(f"NATS alert sent for {bug_id}")
    except Exception as e:
        logger.warning(f"NATS alert failed: {e}")
    finally:
        try:
            await nc.close()
        except Exception:
            pass


def alert_developers_via_nats(bug_id: str, command: str, response: str):
    """
    Alert developers via NATS about a new bug.

    Args:
        bug_id: The bug ID that was filed
        command: Original command
        response: Original response
    """
    try:
        # Use asyncio with timeout to prevent hanging
        asyncio.run(asyncio.wait_for(_send_nats_alert(bug_id, command, response), timeout=2.0))
    except asyncio.TimeoutError:
        logger.warning(f"NATS alert timed out for {bug_id}")
    except Exception as e:
        logger.warning(f"Failed to send NATS alert: {e}")


def update_bug_with_retry_result(
    bug_id: str,
    feedback_text: str,
    retry_response: str,
    retry_success: bool
) -> bool:
    """
    Update a Vikunja bug with retry results.

    Args:
        bug_id: The bug ID (e.g., "BUG-20260102120000")
        feedback_text: User's feedback about what went wrong
        retry_response: The response from the retry attempt
        retry_success: Whether the retry was successful

    Returns:
        True if update succeeded, False otherwise
    """
    client = get_vikunja_client()
    if not client:
        logger.error("Could not create Vikunja client for update")
        return False

    try:
        # Find the task by searching for bug_id in title
        tasks = client.list_tasks(SMARTHOME_PROJECT_ID)
        task = None
        for t in tasks:
            if bug_id in t.get("title", ""):
                task = t
                break

        if not task:
            logger.error(f"Could not find task for {bug_id}")
            return False

        # Append retry information to description
        current_desc = task.get("description", "")
        retry_status = "✅ SUCCESS" if retry_success else "❌ FAILED"

        updated_desc = f"""{current_desc}

---

## User Feedback
```
{feedback_text}
```

## Retry Attempt ({retry_status})
```
{retry_response[:500]}{"..." if len(retry_response) > 500 else ""}
```

Updated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""

        # Update the task
        client.update_task(task["id"], description=updated_desc)

        # If retry succeeded, add "resolved" label
        if retry_success:
            resolved_label = client.get_or_create_label("resolved-by-retry", "27ae60")
            if resolved_label:
                client.add_label_to_task(task["id"], resolved_label["id"])

        logger.info(f"Updated {bug_id} with retry result (success={retry_success})")
        return True

    except Exception as e:
        logger.error(f"Error updating bug {bug_id}: {e}")
        return False


def retry_with_feedback(
    original_command: str,
    original_response: str,
    feedback_text: str
) -> dict:
    """
    Retry a command with additional context from user feedback.

    Args:
        original_command: The original command that failed
        original_response: The response that was given
        feedback_text: User's feedback about what went wrong

    Returns:
        Dict with success status and new response
    """
    # Import here to avoid circular imports
    from agent import run_agent

    # Construct augmented prompt with context
    augmented_command = f"""Previous attempt failed. User feedback: "{feedback_text}"

Original command: {original_command}
Previous response: {original_response}

Please try again, taking the user's feedback into account."""

    logger.info(f"Retrying command with feedback: {original_command[:50]}...")

    try:
        new_response = run_agent(augmented_command)
        return {
            "success": True,
            "response": new_response
        }
    except Exception as e:
        logger.error(f"Retry failed: {e}")
        return {
            "success": False,
            "response": f"Retry also failed: {str(e)}"
        }
