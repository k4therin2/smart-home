"""
Smart Home Assistant - Device Onboarding Tools

Agent tools for device organization via color identification.
Part of WP-8.2: Device Onboarding & Organization System.
"""

from typing import Any, Optional, Dict, List

from src.onboarding_agent import OnboardingAgent, get_onboarding_agent
from src.utils import setup_logging

logger = setup_logging("tools.onboarding")


# Tool definitions for Claude
ONBOARDING_TOOLS = [
    {
        "name": "start_device_onboarding",
        "description": """Start the device onboarding workflow.

Discovers unassigned lights and prepares them for room identification.
All lights will turn on with unique colors so the user can identify them.

Parameters:
- skip_organized: If true, skip lights already assigned to rooms (default true)

Examples:
- "start device onboarding" -> Start with unassigned lights only
- "let's organize my lights" -> Start onboarding
- "help me set up my lights" -> Start onboarding
- "onboard all lights including organized ones" -> skip_organized=false

After starting, each light shows a different color. Ask the user which room
each colored light is in.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "skip_organized": {
                    "type": "boolean",
                    "description": "Skip lights already assigned to rooms (default true)",
                    "default": True
                }
            },
            "required": []
        }
    },
    {
        "name": "identify_light_room",
        "description": """Record which room a light belongs to during onboarding.

Called when the user tells you which room a colored light is in.
Maps the color to the room for later assignment.

Parameters:
- color_name: The color of the light (e.g., 'red', 'blue', 'green')
- room_name: The room the user specified (e.g., 'living room', 'bedroom')

Examples:
- User: "the red one is in the living room" -> color_name='red', room_name='living room'
- User: "blue is bedroom" -> color_name='blue', room_name='bedroom'
- User: "kitchen" (context: you just asked about orange) -> color_name='orange', room_name='kitchen'

Flash the light after recording to confirm.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "color_name": {
                    "type": "string",
                    "description": "The color the light is showing (e.g., 'red', 'blue', 'green')"
                },
                "room_name": {
                    "type": "string",
                    "description": "The room the light is in (e.g., 'living room', 'bedroom')"
                }
            },
            "required": ["color_name", "room_name"]
        }
    },
    {
        "name": "get_onboarding_progress",
        "description": """Get progress of the current onboarding session.

Shows how many lights have been mapped vs total, and lists remaining.
Use this to tell the user how many more lights to identify.

Examples:
- "how many lights left?" -> Check progress
- "what's remaining?" -> Check progress
- "are we done?" -> Check if complete""",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "list_pending_lights",
        "description": """List lights not yet mapped to rooms.

Shows which colors still need room assignments.
Use this to tell the user what's left to identify.

Examples:
- "which lights are left?" -> List pending
- "what colors haven't been assigned?" -> List pending""",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "apply_onboarding_mappings",
        "description": """Apply all room mappings from the onboarding session.

Saves all the room assignments to the device registry.
Call this when the user confirms all mappings are correct.

Examples:
- "save the room assignments" -> Apply mappings
- "apply the changes" -> Apply mappings
- "yes, that's all correct" (after showing summary) -> Apply mappings""",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "cancel_onboarding",
        "description": """Cancel the current onboarding session.

Discards all mappings and turns off identification lights.
Use if the user wants to stop or start over.

Examples:
- "cancel onboarding" -> Cancel
- "stop" -> Cancel
- "never mind" -> Cancel""",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "resume_onboarding",
        "description": """Resume an interrupted onboarding session.

If onboarding was interrupted, this resumes where it left off.
Progress is preserved.

Examples:
- "resume onboarding" -> Resume previous session
- "continue where I left off" -> Resume""",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "show_identification_lights",
        "description": """Turn on all identification lights again.

Re-displays all lights with their assigned colors.
Useful if user needs to see the colors again.

Examples:
- "show the colors again" -> Turn on lights
- "I forgot which was which" -> Turn on lights""",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_onboarding_summary",
        "description": """Get summary of all mappings in current session.

Shows all lights and their assigned rooms.
Use this before applying to confirm with user.

Examples:
- "show me what you've recorded" -> Get summary
- "what rooms did I assign?" -> Get summary""",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "sync_rooms_to_hue",
        "description": """Sync room assignments to the Philips Hue bridge.

After applying mappings, optionally sync to Hue app.
This organizes lights in the Hue app to match your assignments.

Examples:
- "sync to hue" -> Sync to Hue bridge
- "update hue app" -> Sync to Hue bridge""",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
]


# ========== Tool Handler Functions ==========

def start_device_onboarding(skip_organized: bool = True) -> Dict[str, Any]:
    """Start the device onboarding workflow."""
    try:
        agent = get_onboarding_agent()

        # Check for existing session
        existing = agent.get_current_session()
        if existing:
            return {
                "success": False,
                "error": "An onboarding session is already active. Resume it or cancel first.",
                "session_id": existing.get("session_id")
            }

        session = agent.start_session(skip_organized=skip_organized)

        if session["total_lights"] == 0:
            return {
                "success": True,
                "message": "No unassigned lights found. All lights are already organized!",
                "total_lights": 0
            }

        # Turn on lights with colors
        lights = agent._session_lights
        agent.turn_on_identification_lights(lights)

        # Build color list for response
        color_list = [f"- {l['color_name']}: {l.get('friendly_name', l['entity_id'])}"
                      for l in lights]

        return {
            "success": True,
            "session_id": session["session_id"],
            "total_lights": session["total_lights"],
            "lights": lights,
            "message": f"Started onboarding with {session['total_lights']} lights. "
                      f"Each light is now showing a unique color. Ask the user which room each color is in.",
            "color_summary": "\n".join(color_list)
        }
    except ValueError as error:
        return {"success": False, "error": str(error)}
    except Exception as error:
        logger.error(f"Error starting onboarding: {error}")
        return {"success": False, "error": str(error)}


def identify_light_room(color_name: str, room_name: str) -> Dict[str, Any]:
    """Record which room a colored light belongs to."""
    try:
        agent = get_onboarding_agent()
        session = agent.get_current_session()

        if not session:
            return {
                "success": False,
                "error": "No onboarding session active. Start onboarding first."
            }

        # Find the light with this color
        lights = agent._session_lights
        matching_light = None
        for light in lights:
            if light["color_name"].lower() == color_name.lower():
                matching_light = light
                break

        if not matching_light:
            available_colors = [l["color_name"] for l in lights]
            return {
                "success": False,
                "error": f"No light with color '{color_name}'. Available colors: {', '.join(available_colors)}"
            }

        # Record the mapping
        entity_id = matching_light["entity_id"]
        result = agent.record_room_mapping(entity_id, color_name, room_name)

        if result:
            # Flash the light to confirm
            agent.flash_light(entity_id, times=2)

            progress = agent.get_progress()

            return {
                "success": True,
                "entity_id": entity_id,
                "color": color_name,
                "room": agent.normalize_room_name(room_name),
                "progress": progress,
                "message": f"Got it! The {color_name} light is in the {room_name}. "
                          f"({progress['completed']}/{progress['total']} done)"
            }
        else:
            return {"success": False, "error": "Failed to record mapping"}

    except Exception as error:
        logger.error(f"Error identifying light: {error}")
        return {"success": False, "error": str(error)}


def get_onboarding_progress() -> Dict[str, Any]:
    """Get progress of the current onboarding session."""
    try:
        agent = get_onboarding_agent()
        session = agent.get_current_session()

        if not session:
            return {
                "success": False,
                "error": "No onboarding session active."
            }

        progress = agent.get_progress()
        is_complete = agent.is_mapping_complete()

        return {
            "success": True,
            "completed": progress["completed"],
            "total": progress["total"],
            "remaining": progress["remaining"],
            "percentage": progress["percentage"],
            "is_complete": is_complete,
            "message": (
                f"{progress['completed']} of {progress['total']} lights mapped "
                f"({progress['percentage']:.0f}%). "
                + ("All done!" if is_complete else f"{progress['remaining']} remaining.")
            )
        }
    except Exception as error:
        logger.error(f"Error getting progress: {error}")
        return {"success": False, "error": str(error)}


def list_pending_lights() -> Dict[str, Any]:
    """List lights not yet mapped to rooms."""
    try:
        agent = get_onboarding_agent()
        session = agent.get_current_session()

        if not session:
            return {
                "success": False,
                "error": "No onboarding session active."
            }

        pending = agent.get_pending_mappings()

        if not pending:
            return {
                "success": True,
                "count": 0,
                "pending": [],
                "message": "All lights have been mapped!"
            }

        pending_list = [f"- {l['color_name']}: {l.get('friendly_name', l['entity_id'])}"
                        for l in pending]

        return {
            "success": True,
            "count": len(pending),
            "pending": pending,
            "message": f"{len(pending)} lights remaining:\n" + "\n".join(pending_list)
        }
    except Exception as error:
        logger.error(f"Error listing pending: {error}")
        return {"success": False, "error": str(error)}


def apply_onboarding_mappings() -> Dict[str, Any]:
    """Apply all room mappings to the device registry."""
    try:
        agent = get_onboarding_agent()
        session = agent.get_current_session()

        if not session:
            return {
                "success": False,
                "error": "No onboarding session active."
            }

        # Apply mappings
        result = agent.apply_mappings()

        if result["success"]:
            # Turn off identification lights
            agent.turn_off_all_onboarding_lights()

            # Complete the session
            agent.complete_session()

            return {
                "success": True,
                "applied": result["applied"],
                "message": f"Successfully assigned {result['applied']} lights to rooms. "
                          "The Hue app won't show these changes until you sync."
            }
        else:
            return {
                "success": False,
                "applied": result.get("applied", 0),
                "errors": result.get("errors", []),
                "error": "Some mappings failed to apply"
            }

    except Exception as error:
        logger.error(f"Error applying mappings: {error}")
        return {"success": False, "error": str(error)}


def cancel_onboarding() -> Dict[str, Any]:
    """Cancel the current onboarding session."""
    try:
        agent = get_onboarding_agent()
        session = agent.get_current_session()

        if not session:
            return {
                "success": True,
                "message": "No active onboarding session to cancel."
            }

        # Turn off lights
        agent.turn_off_all_onboarding_lights()

        # Cancel session
        agent.cancel_session()

        return {
            "success": True,
            "message": "Onboarding cancelled. All progress discarded."
        }
    except Exception as error:
        logger.error(f"Error cancelling onboarding: {error}")
        return {"success": False, "error": str(error)}


def resume_onboarding() -> Dict[str, Any]:
    """Resume an interrupted onboarding session."""
    try:
        agent = get_onboarding_agent()

        # Check for existing session to resume
        session = agent.get_current_session()
        if not session:
            return {
                "success": False,
                "error": "No onboarding session to resume. Start a new one."
            }

        # Turn on lights again
        lights = agent._session_lights
        if lights:
            agent.turn_on_identification_lights(lights)

        progress = agent.get_progress()

        return {
            "success": True,
            "session_id": session["session_id"],
            "progress": progress,
            "message": f"Resumed onboarding. {progress['completed']}/{progress['total']} "
                      f"lights already mapped. {progress['remaining']} remaining."
        }
    except Exception as error:
        logger.error(f"Error resuming onboarding: {error}")
        return {"success": False, "error": str(error)}


def show_identification_lights() -> Dict[str, Any]:
    """Turn on all identification lights again."""
    try:
        agent = get_onboarding_agent()
        session = agent.get_current_session()

        if not session:
            return {
                "success": False,
                "error": "No onboarding session active."
            }

        lights = agent._session_lights
        if not lights:
            return {
                "success": False,
                "error": "No lights in session."
            }

        result = agent.turn_on_identification_lights(lights)

        return {
            "success": result,
            "message": "All lights are now showing their identification colors."
        }
    except Exception as error:
        logger.error(f"Error showing lights: {error}")
        return {"success": False, "error": str(error)}


def get_onboarding_summary() -> Dict[str, Any]:
    """Get summary of all mappings in current session."""
    try:
        agent = get_onboarding_agent()
        session = agent.get_current_session()

        if not session:
            return {
                "success": False,
                "error": "No onboarding session active."
            }

        completed = agent.get_completed_mappings()
        pending = agent.get_pending_mappings()

        # Build summary
        summary_lines = []
        if completed:
            summary_lines.append("Assigned:")
            for mapping in completed:
                summary_lines.append(
                    f"  - {mapping['color_name']} light -> {mapping['room_name']}"
                )

        if pending:
            summary_lines.append("\nNot yet assigned:")
            for light in pending:
                summary_lines.append(f"  - {light['color_name']} light")

        return {
            "success": True,
            "completed_count": len(completed),
            "pending_count": len(pending),
            "completed_mappings": completed,
            "pending_lights": pending,
            "summary": "\n".join(summary_lines),
            "message": f"{len(completed)} assigned, {len(pending)} remaining."
        }
    except Exception as error:
        logger.error(f"Error getting summary: {error}")
        return {"success": False, "error": str(error)}


def sync_rooms_to_hue() -> Dict[str, Any]:
    """Sync room assignments to the Philips Hue bridge."""
    try:
        agent = get_onboarding_agent()

        # Get completed mappings (even from completed session if recent)
        completed = agent.get_completed_mappings()

        if not completed:
            return {
                "success": False,
                "error": "No mappings to sync. Complete onboarding first."
            }

        result = agent.sync_to_hue_bridge(completed)

        return {
            "success": result["success"],
            "synced": result.get("synced", 0),
            "message": result.get("message", "Sync complete") if result["success"]
                      else result.get("error", "Sync failed")
        }
    except Exception as error:
        logger.error(f"Error syncing to Hue: {error}")
        return {"success": False, "error": str(error)}


def execute_onboarding_tool(tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
    """Execute an onboarding tool by name."""
    logger.info(f"Executing onboarding tool: {tool_name}")

    if tool_name == "start_device_onboarding":
        return start_device_onboarding(
            skip_organized=tool_input.get("skip_organized", True)
        )

    elif tool_name == "identify_light_room":
        return identify_light_room(
            color_name=tool_input.get("color_name", ""),
            room_name=tool_input.get("room_name", "")
        )

    elif tool_name == "get_onboarding_progress":
        return get_onboarding_progress()

    elif tool_name == "list_pending_lights":
        return list_pending_lights()

    elif tool_name == "apply_onboarding_mappings":
        return apply_onboarding_mappings()

    elif tool_name == "cancel_onboarding":
        return cancel_onboarding()

    elif tool_name == "resume_onboarding":
        return resume_onboarding()

    elif tool_name == "show_identification_lights":
        return show_identification_lights()

    elif tool_name == "get_onboarding_summary":
        return get_onboarding_summary()

    elif tool_name == "sync_rooms_to_hue":
        return sync_rooms_to_hue()

    else:
        return {"success": False, "error": f"Unknown onboarding tool: {tool_name}"}
