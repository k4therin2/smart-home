"""
Smart Home Assistant - Configuration Module

Central configuration for the smart home system including
room mappings, device entities, and system constants.
"""

from __future__ import annotations

import os
from pathlib import Path

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

# OpenAI Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = "gpt-4o-mini"
MAX_AGENT_ITERATIONS = 5

# Home Assistant Configuration
HA_URL = os.getenv("HA_URL", "http://localhost:8123")
HA_TOKEN = os.getenv("HA_TOKEN")

# Spotify Configuration
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:8888/callback")

# MQTT Configuration (WP-10.28)
MQTT_BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "localhost")
MQTT_BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
MQTT_TOPIC_PREFIX = os.getenv("MQTT_TOPIC_PREFIX", "smarthome")

# Cost Tracking
DAILY_COST_TARGET = float(os.getenv("DAILY_COST_TARGET", "2.00"))
DAILY_COST_ALERT = float(os.getenv("DAILY_COST_ALERT", "5.00"))

# Vacuum Configuration
# Entity ID for the Dreame L10s Ultra vacuum (model r2228o)
# The Dreame HACS integration uses the model number in the entity ID
VACUUM_ENTITY_ID = os.getenv("VACUUM_ENTITY_ID", "vacuum.dreame_r2228o_ce6c_robot_cleaner")

# GPT-4o-mini Pricing (per 1M tokens as of 2025)
OPENAI_INPUT_COST_PER_MILLION = 0.15  # $0.15 per 1M input tokens
OPENAI_OUTPUT_COST_PER_MILLION = 0.60  # $0.60 per 1M output tokens

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Cache Configuration
CACHE_ENABLED = os.getenv("CACHE_ENABLED", "true").lower() == "true"
HA_STATE_CACHE_TTL = int(os.getenv("HA_STATE_CACHE_TTL", "10"))  # seconds
CACHE_MAX_SIZE = int(os.getenv("CACHE_MAX_SIZE", "1000"))  # entries

# Rate Limiting Configuration (WP-10.23)
RATE_LIMIT_DEFAULT_PER_DAY = int(os.getenv("RATE_LIMIT_DEFAULT_PER_DAY", "200"))
RATE_LIMIT_DEFAULT_PER_HOUR = int(os.getenv("RATE_LIMIT_DEFAULT_PER_HOUR", "50"))
RATE_LIMIT_API_PER_MINUTE = int(os.getenv("RATE_LIMIT_API_PER_MINUTE", "30"))
RATE_LIMIT_COMMAND_PER_MINUTE = int(os.getenv("RATE_LIMIT_COMMAND_PER_MINUTE", "10"))
RATE_LIMIT_ADMIN_MULTIPLIER = int(
    os.getenv("RATE_LIMIT_ADMIN_MULTIPLIER", "5")
)  # 5x normal limits for admins

# Room Entity Mappings
# Maps room names to Home Assistant entity IDs
# Blinds use the Tuya integration via Hapadif Smart Bridge Hub
#
# Philips Hue Device Descriptions (updated 2026-01-02):
# Kitchen: Two 2-bulb overhanging fixtures
# Living Room: Reading lamp (right of couch), Pendant (left, boho wicker),
#              Golden lamp (art nouveau floor lamp), Hue Play 1&2 (behind TV)
# Bedroom: Bed north/south (bedside lamps), Bubble (circular on dresser)
# Master Bathroom: Above toilet (attached to bedroom)
# Staircase: Top of Stairs
#
ROOM_ENTITY_MAP = {
    "living_room": {
        "lights": [
            "light.reading_light",      # Lamp to right of couch (reading spot)
            "light.pendant_lamp",       # Left of couch, hanging boho wicker shade
            "light.golden_lamp",        # Art nouveau floor lamp
            "light.hue_play_1",         # Behind TV console table
            "light.hue_play_2",         # Behind TV
        ],
        "default_light": "light.reading_light",  # Good for general use
        "blinds": "cover.living_room_blinds",  # Hapadif via Tuya
    },
    "bedroom": {
        "lights": [
            "light.bed_north",          # Bedside lamp (north side)
            "light.bed_south",          # Bedside lamp (south side)
            "light.bubble",             # Circular lamp on dresser
        ],
        "default_light": "light.bubble",  # Has color support
        "blinds": "cover.bedroom_blinds",  # Hapadif via Tuya
    },
    "master_bathroom": {
        "lights": [
            "light.master_bathroom",    # Hue light above toilet
            # Note: There's also a non-Hue light in here (not controllable)
        ],
        "default_light": "light.master_bathroom",
    },
    "kitchen": {
        "lights": [
            "light.hue_color_lamp_1",   # Fixture 1, bulb 1
            "light.hue_color_lamp_2",   # Fixture 1, bulb 2
            "light.hue_color_lamp_3",   # Fixture 2, bulb 1
            "light.hue_color_lamp_4",   # Fixture 2, bulb 2
        ],
        "default_light": "light.hue_color_lamp_1",  # All have color support
        "fixtures": {
            "fixture_1": ["light.hue_color_lamp_1", "light.hue_color_lamp_2"],
            "fixture_2": ["light.hue_color_lamp_3", "light.hue_color_lamp_4"],
        },
    },
    "office": {
        "lights": ["light.office_pendant", "light.office_2"],
        "default_light": "light.office_pendant",  # Has color support, is available
        "blinds": "cover.office_blinds",  # Hapadif via Tuya
    },
    "staircase": {
        "lights": ["light.top_of_stairs"],
        "default_light": "light.top_of_stairs",
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
}

# Room name aliases for natural language processing
ROOM_ALIASES = {
    "living room": "living_room",
    "lounge": "living_room",
    "front room": "living_room",
    "bed room": "bedroom",
    "master bedroom": "bedroom",
    "master bath": "master_bathroom",
    "master bathroom": "master_bathroom",
    "ensuite": "master_bathroom",
    "bathroom": "master_bathroom",  # Default bathroom is master
    "bath room": "master_bathroom",
    "restroom": "master_bathroom",
    "home office": "office",
    "study": "office",
    "stairs": "staircase",
    "top of stairs": "staircase",
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


def get_vacuum_entity() -> str | None:
    """
    Get the vacuum entity ID.

    Returns:
        Vacuum entity ID string or None if not configured
    """
    return VACUUM_ENTITY_ID if VACUUM_ENTITY_ID else None


def get_blinds_entities(room_name: str) -> str | None:
    """
    Get the blinds entity ID for a room.

    Args:
        room_name: Natural language room name

    Returns:
        Blinds entity ID string or None if not found
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
        return ROOM_ENTITY_MAP[normalized].get("blinds")

    return None


def get_room_entity(room_name: str, device_type: str = "lights") -> str | None:
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


def get_room_lights(room_name: str) -> list[str]:
    """
    Get ALL light entity IDs for a room.

    Args:
        room_name: Natural language room name

    Returns:
        List of entity ID strings (empty if room not found)
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
        return room_config.get("lights", [])

    return []


def validate_config() -> list[str]:
    """
    Validate that required configuration is present.

    Returns:
        List of error messages (empty if valid)
    """
    errors = []

    # WP-10.8: OpenAI key is now optional (home-llm is default)
    # Only warn if using OpenAI provider without key
    llm_provider = os.getenv("LLM_PROVIDER", "home_llm").lower()
    if llm_provider == "openai" and not OPENAI_API_KEY:
        errors.append("OPENAI_API_KEY is not set (required for OpenAI provider)")
    elif llm_provider == "home_llm" and not OPENAI_API_KEY:
        # Just a warning, not an error - fallback won't work but primary will
        import logging
        logging.getLogger(__name__).warning(
            "OPENAI_API_KEY not set - OpenAI fallback unavailable"
        )

    if not HA_TOKEN:
        errors.append("HA_TOKEN is not set")

    if not HA_URL:
        errors.append("HA_URL is not set")

    return errors
