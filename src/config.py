"""
Smart Home Assistant - Configuration Module

Central configuration for the smart home system including
room mappings, device entities, and system constants.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, List

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Project Paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PROMPTS_DIR = PROJECT_ROOT / "prompts"
LOGS_DIR = DATA_DIR / "logs"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# Anthropic Configuration
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = "claude-sonnet-4-20250514"
MAX_AGENT_ITERATIONS = 5

# Home Assistant Configuration
HA_URL = os.getenv("HA_URL", "http://localhost:8123")
HA_TOKEN = os.getenv("HA_TOKEN")

# Cost Tracking
DAILY_COST_TARGET = float(os.getenv("DAILY_COST_TARGET", "2.00"))
DAILY_COST_ALERT = float(os.getenv("DAILY_COST_ALERT", "5.00"))

# Claude Sonnet 4 Pricing (per 1M tokens as of 2025)
CLAUDE_INPUT_COST_PER_MILLION = 3.00   # $3 per 1M input tokens
CLAUDE_OUTPUT_COST_PER_MILLION = 15.00  # $15 per 1M output tokens

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Room Entity Mappings
# Maps room names to Home Assistant entity IDs
ROOM_ENTITY_MAP = {
    "living_room": {
        "lights": ["light.living_room", "light.living_room_2"],
        "default_light": "light.living_room_2",  # Has color support
    },
    "bedroom": {
        "lights": ["light.bedroom", "light.bedroom_2", "light.bed_north", "light.bed_south"],
        "default_light": "light.bedroom_2",  # Has color support
    },
    "kitchen": {
        "lights": ["light.kitchen", "light.kitchen_2"],
        "default_light": "light.kitchen_2",  # Has color support
    },
    "office": {
        "lights": ["light.office_pendant", "light.office_2"],
        "default_light": "light.office_pendant",  # Has color support, is available
    },
    "upstairs": {
        "lights": ["light.upstairs", "light.top_of_stairs"],
        "default_light": "light.upstairs",
    },
    "downstairs": {
        "lights": ["light.downstairs"],
        "default_light": "light.downstairs",
    },
    "garage": {
        "lights": ["light.garage", "light.garage_2"],
        "default_light": "light.garage",
    },
    "staircase": {
        "lights": ["light.staircase", "light.top_of_stairs"],
        "default_light": "light.staircase",
    },
}

# Room name aliases for natural language processing
ROOM_ALIASES = {
    "living room": "living_room",
    "lounge": "living_room",
    "front room": "living_room",
    "bed room": "bedroom",
    "master bedroom": "bedroom",
    "bath room": "bathroom",
    "restroom": "bathroom",
    "home office": "office",
    "study": "office",
}

# Color temperature presets (in Kelvin)
COLOR_TEMP_PRESETS = {
    "warm": 2700,
    "soft_warm": 3000,
    "neutral": 4000,
    "cool": 5000,
    "daylight": 6500,
}

# Brightness presets (percentage)
BRIGHTNESS_PRESETS = {
    "dim": 20,
    "low": 35,
    "medium": 50,
    "bright": 75,
    "full": 100,
}

# Vibe to light settings mapping (basic defaults)
VIBE_PRESETS = {
    "cozy": {"brightness": 40, "color_temp_kelvin": 2700},
    "relaxed": {"brightness": 50, "color_temp_kelvin": 2700},
    "focus": {"brightness": 80, "color_temp_kelvin": 4000},
    "energetic": {"brightness": 100, "color_temp_kelvin": 5000},
    "romantic": {"brightness": 25, "color_temp_kelvin": 2200},
    "movie": {"brightness": 15, "color_temp_kelvin": 2700},
    "reading": {"brightness": 70, "color_temp_kelvin": 4000},
    "morning": {"brightness": 60, "color_temp_kelvin": 4000},
    "evening": {"brightness": 40, "color_temp_kelvin": 2700},
    "night": {"brightness": 10, "color_temp_kelvin": 2200},
}


def kelvin_to_mireds(kelvin: int) -> int:
    """Convert Kelvin to mireds (Philips Hue uses mireds)."""
    return int(1000000 / kelvin)


def mireds_to_kelvin(mireds: int) -> int:
    """Convert mireds to Kelvin."""
    return int(1000000 / mireds)


def get_room_entity(room_name: str, device_type: str = "lights") -> Optional[str]:
    """
    Get the primary entity ID for a room and device type.

    Args:
        room_name: Natural language room name
        device_type: Type of device (e.g., 'lights')

    Returns:
        Entity ID string or None if not found
    """
    # Normalize room name
    normalized = room_name.lower().strip()

    # Check aliases first
    if normalized in ROOM_ALIASES:
        normalized = ROOM_ALIASES[normalized]

    # Replace spaces with underscores
    normalized = normalized.replace(" ", "_")

    # Look up in mapping
    if normalized in ROOM_ENTITY_MAP:
        room_config = ROOM_ENTITY_MAP[normalized]
        if device_type == "lights":
            return room_config.get("default_light")
        return room_config.get(device_type)

    return None


def validate_config() -> List[str]:
    """
    Validate that required configuration is present.

    Returns:
        List of error messages (empty if valid)
    """
    errors = []

    if not ANTHROPIC_API_KEY:
        errors.append("ANTHROPIC_API_KEY is not set")

    if not HA_TOKEN:
        errors.append("HA_TOKEN is not set")

    if not HA_URL:
        errors.append("HA_URL is not set")

    return errors
