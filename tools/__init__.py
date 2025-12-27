"""Smart Home Assistant - Tools Package

This package contains all tools for the smart home agent:
- lights.py: Basic light control (on/off, brightness, color temp, vibes)
- hue_specialist.py: Specialist agent for abstract vibe interpretation
- effects.py: High-level effect coordination
- vacuum.py: Dreame L10s vacuum control
- blinds.py: Hapadif smart blinds control via Tuya
- productivity.py: Todo lists and reminders
- automation.py: Home automation creation and management
- timers.py: Countdown timers and scheduled alarms
- location.py: Location-aware commands and voice puck tracking
- improvements.py: Continuous improvement scanning and management
- presence.py: User presence detection and vacuum automation
- ember_mug.py: Ember Mug temperature control via HA custom integration
- camera.py: Ring camera monitoring and snapshots
"""

from tools.automation import AUTOMATION_TOOLS, execute_automation_tool
from tools.blinds import BLINDS_TOOLS, execute_blinds_tool
from tools.camera import CAMERA_TOOLS, execute_camera_tool
from tools.effects import apply_vibe, get_vibe_preview, list_vibes
from tools.ember_mug import EMBER_MUG_TOOLS, execute_ember_mug_tool
from tools.hue_specialist import interpret_vibe_request, list_available_effects
from tools.improvements import IMPROVEMENT_TOOLS, handle_improvement_tool
from tools.lights import LIGHT_TOOLS, execute_light_tool
from tools.location import LOCATION_TOOLS, execute_location_tool
from tools.presence import PRESENCE_TOOLS, execute_presence_tool
from tools.productivity import PRODUCTIVITY_TOOLS, execute_productivity_tool
from tools.timers import TIMER_TOOLS, execute_timer_tool
from tools.vacuum import VACUUM_TOOLS, execute_vacuum_tool


__all__ = [
    "AUTOMATION_TOOLS",
    "BLINDS_TOOLS",
    "CAMERA_TOOLS",
    "EMBER_MUG_TOOLS",
    "IMPROVEMENT_TOOLS",
    "LIGHT_TOOLS",
    "LOCATION_TOOLS",
    "PRESENCE_TOOLS",
    "PRODUCTIVITY_TOOLS",
    "TIMER_TOOLS",
    "VACUUM_TOOLS",
    "apply_vibe",
    "execute_automation_tool",
    "execute_blinds_tool",
    "execute_camera_tool",
    "execute_ember_mug_tool",
    "execute_light_tool",
    "execute_location_tool",
    "execute_presence_tool",
    "execute_productivity_tool",
    "execute_timer_tool",
    "execute_vacuum_tool",
    "get_vibe_preview",
    "handle_improvement_tool",
    "interpret_vibe_request",
    "list_available_effects",
    "list_vibes",
]
