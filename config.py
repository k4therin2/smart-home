"""
Shared configuration constants for the Home Automation Agent system.

This module centralizes all configuration values to avoid duplication and
make it easier to update system-wide settings.
"""

# ============================================================================
# API Configuration
# ============================================================================

# Claude API model to use for all agents
MODEL_NAME = "claude-sonnet-4-20250514"

# Maximum iterations for agentic tool-use loops
MAX_AGENT_ITERATIONS = 5

# Maximum chat history to keep in multi-turn conversations (to avoid token overflow)
MAX_CHAT_HISTORY = 10


# ============================================================================
# Home Assistant Configuration
# ============================================================================

# Mapping of friendly room names to Home Assistant entity IDs
# This is the single source of truth for all room mappings
ROOM_ENTITY_MAP = {
    "living_room": "light.living_room",
    "bedroom": "light.bedroom",
    "kitchen": "light.kitchen",
    "office": "light.office",
}


# ============================================================================
# Lighting Configuration
# ============================================================================

# Valid color temperature range for lights (in Kelvin)
MIN_KELVIN = 2000
MAX_KELVIN = 6500

# Effect loop configuration
EFFECT_LOOP_DELAY = 2.0  # seconds between effect iterations
