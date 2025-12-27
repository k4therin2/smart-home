"""
Smart Home Assistant - Philips Hue Specialist Agent

A specialist agent that translates abstract vibe descriptions and scene requests
into specific Philips Hue settings. Uses Claude to interpret complex requests
that don't map directly to presets.
"""

import json
from typing import Any

import openai

from src.config import (
    OPENAI_API_KEY,
    OPENAI_MODEL,
    VIBE_PRESETS,
)
from src.utils import load_prompts, setup_logging, track_api_usage


logger = setup_logging("hue_specialist")

# Known Hue scene mappings for common abstract requests
HUE_SCENE_MAPPINGS = {
    # Fire/warm themes
    "fire": {"scene": "savanna_sunset", "dynamic": True, "speed": 30, "brightness": 60},
    "fireplace": {"scene": "savanna_sunset", "dynamic": True, "speed": 25, "brightness": 50},
    "campfire": {"scene": "savanna_sunset", "dynamic": True, "speed": 35, "brightness": 55},
    "sunset": {"scene": "savanna_sunset", "dynamic": True, "speed": 20, "brightness": 70},
    # Ocean/water themes
    "ocean": {"scene": "tropical_twilight", "dynamic": True, "speed": 40, "brightness": 50},
    "under the sea": {"scene": "tropical_twilight", "dynamic": True, "speed": 45, "brightness": 45},
    "underwater": {"scene": "tropical_twilight", "dynamic": True, "speed": 50, "brightness": 40},
    "aquarium": {"scene": "tropical_twilight", "dynamic": True, "speed": 30, "brightness": 55},
    "beach": {"scene": "tropical_twilight", "dynamic": True, "speed": 25, "brightness": 65},
    # Aurora/sky themes
    "aurora": {"scene": "arctic_aurora", "dynamic": True, "speed": 50, "brightness": 60},
    "northern lights": {"scene": "arctic_aurora", "dynamic": True, "speed": 55, "brightness": 55},
    "aurora borealis": {"scene": "arctic_aurora", "dynamic": True, "speed": 50, "brightness": 60},
    "galaxy": {"scene": "arctic_aurora", "dynamic": True, "speed": 40, "brightness": 45},
    "space": {"scene": "arctic_aurora", "dynamic": True, "speed": 35, "brightness": 40},
    # Nature themes
    "forest": {"scene": "spring_blossom", "dynamic": True, "speed": 25, "brightness": 55},
    "nature": {"scene": "spring_blossom", "dynamic": True, "speed": 20, "brightness": 60},
    "spring": {"scene": "spring_blossom", "dynamic": True, "speed": 30, "brightness": 65},
    "garden": {"scene": "spring_blossom", "dynamic": True, "speed": 25, "brightness": 60},
    # Party/energy themes
    "party": {"scene": "tokyo", "dynamic": True, "speed": 80, "brightness": 100},
    "disco": {"scene": "tokyo", "dynamic": True, "speed": 90, "brightness": 100},
    "rave": {"scene": "tokyo", "dynamic": True, "speed": 100, "brightness": 100},
    "club": {"scene": "tokyo", "dynamic": True, "speed": 85, "brightness": 90},
    # Holiday/Christmas themes - festive reds and golds
    "christmas": {"scene": "chinatown", "dynamic": True, "speed": 20, "brightness": 70},
    "holiday": {"scene": "chinatown", "dynamic": True, "speed": 15, "brightness": 65},
    "festive": {"scene": "chinatown", "dynamic": True, "speed": 25, "brightness": 75},
    "merry christmas": {"scene": "chinatown", "dynamic": True, "speed": 20, "brightness": 70},
    "xmas": {"scene": "chinatown", "dynamic": True, "speed": 20, "brightness": 70},
}

# Scene descriptions for the LLM to understand available options
AVAILABLE_SCENES = {
    "arctic_aurora": "Cool blues and greens with purple accents, mimics northern lights",
    "tropical_twilight": "Ocean blues transitioning through sunset colors",
    "savanna_sunset": "Warm oranges, reds, and yellows like African sunset",
    "spring_blossom": "Soft pinks, greens, and whites like cherry blossoms",
    "tokyo": "Vibrant neons - pink, blue, purple, for high energy",
    "honolulu": "Tropical warm colors, sunset pinks and oranges",
    "chinatown": "Deep reds and golds, festive feeling",
    "golden_pond": "Warm golden yellows and soft greens",
}


def interpret_vibe_request(
    description: str, room: str | None = None, time_of_day: str | None = None
) -> dict[str, Any]:
    """
    Interpret an abstract vibe description and return light settings.

    First checks for direct mappings in presets and scene mappings.
    Falls back to LLM interpretation for complex requests.

    Args:
        description: The vibe description (e.g., "cozy evening", "under the sea")
        room: Optional room context
        time_of_day: Optional time context

    Returns:
        Dictionary with either basic settings or scene settings
    """
    description_lower = description.lower().strip()

    # Check for exact vibe preset match
    if description_lower in VIBE_PRESETS:
        preset = VIBE_PRESETS[description_lower]
        logger.info(f"Matched vibe preset: {description_lower}")
        return {
            "type": "basic",
            "brightness": preset["brightness"],
            "color_temp_kelvin": preset["color_temp_kelvin"],
            "source": "preset",
        }

    # Check for Hue scene mappings
    for keyword, scene_config in HUE_SCENE_MAPPINGS.items():
        if keyword in description_lower:
            logger.info(f"Matched Hue scene: {keyword} -> {scene_config['scene']}")
            return {
                "type": "scene",
                "scene_name": scene_config["scene"],
                "dynamic": scene_config["dynamic"],
                "speed": scene_config["speed"],
                "brightness": scene_config["brightness"],
                "source": "scene_mapping",
            }

    # Fall back to LLM interpretation for complex requests
    logger.info(f"Using LLM to interpret: {description}")
    return _llm_interpret_vibe(description, room, time_of_day)


def _llm_interpret_vibe(
    description: str, room: str | None = None, time_of_day: str | None = None
) -> dict[str, Any]:
    """
    Use OpenAI to interpret complex vibe requests.

    Args:
        description: The vibe description
        room: Optional room context
        time_of_day: Optional time context

    Returns:
        Interpreted settings dictionary
    """
    if not OPENAI_API_KEY:
        logger.warning("No API key, using fallback interpretation")
        return _fallback_interpretation(description)

    prompts = load_prompts()
    system_prompt = prompts.get("hue_specialist", {}).get("system", "")

    # Build context
    context_parts = [f'Vibe request: "{description}"']
    if room:
        context_parts.append(f"Room: {room}")
    if time_of_day:
        context_parts.append(f"Time of day: {time_of_day}")

    context_parts.append(f"\nAvailable Hue scenes: {json.dumps(AVAILABLE_SCENES, indent=2)}")
    context_parts.append("\nRespond with JSON only. Format:")
    context_parts.append("""{
  "type": "basic" or "scene",
  "brightness": 0-100,
  "color_temp_kelvin": 2200-6500 (for basic type),
  "scene_name": "scene_id" (for scene type),
  "dynamic": true/false (for scene type),
  "speed": 0-100 (for scene type)
}""")

    user_message = "\n".join(context_parts)

    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            max_tokens=256,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )

        # Track usage
        track_api_usage(
            model=OPENAI_MODEL,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
            command=f"hue_specialist:{description[:50]}",
        )

        # Parse response
        response_text = response.choices[0].message.content

        # Try to extract JSON from response
        try:
            # Handle potential markdown code blocks
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0]
            elif "{" in response_text and "}" in response_text:
                # Find embedded JSON object in text
                start = response_text.find("{")
                end = response_text.rfind("}") + 1
                json_str = response_text[start:end]
            else:
                json_str = response_text

            result = json.loads(json_str.strip())
            result["source"] = "llm"
            logger.info(f"LLM interpretation: {result}")
            return result

        except json.JSONDecodeError as error:
            logger.error(f"Failed to parse LLM response: {error}")
            logger.debug(f"Response was: {response_text}")
            return _fallback_interpretation(description)

    except openai.APIError as error:
        logger.error(f"API error in hue_specialist: {error}")
        return _fallback_interpretation(description)


def _fallback_interpretation(description: str) -> dict[str, Any]:
    """
    Fallback interpretation when LLM is unavailable.
    Uses simple keyword matching.
    """
    description_lower = description.lower()

    # Warm/cozy keywords
    if any(word in description_lower for word in ["warm", "cozy", "comfort", "relax"]):
        return {"type": "basic", "brightness": 45, "color_temp_kelvin": 2700, "source": "fallback"}

    # Cool/focus keywords
    if any(word in description_lower for word in ["cool", "focus", "work", "bright", "energy"]):
        return {"type": "basic", "brightness": 80, "color_temp_kelvin": 4500, "source": "fallback"}

    # Dark/dim keywords
    if any(word in description_lower for word in ["dim", "dark", "night", "sleep", "movie"]):
        return {"type": "basic", "brightness": 20, "color_temp_kelvin": 2200, "source": "fallback"}

    # Romantic keywords
    if any(word in description_lower for word in ["romantic", "intimate", "date", "candle"]):
        return {"type": "basic", "brightness": 25, "color_temp_kelvin": 2200, "source": "fallback"}

    # Holiday/Christmas keywords - warm festive glow
    if any(word in description_lower for word in ["christmas", "holiday", "festive", "xmas"]):
        return {
            "type": "scene",
            "scene_name": "chinatown",
            "dynamic": True,
            "speed": 20,
            "brightness": 70,
            "source": "fallback",
        }

    # Default: neutral medium
    return {"type": "basic", "brightness": 50, "color_temp_kelvin": 3500, "source": "fallback"}


def get_scene_suggestions(vibe_keywords: list[str]) -> list[dict[str, Any]]:
    """
    Get scene suggestions based on vibe keywords.

    Args:
        vibe_keywords: List of keywords describing the desired vibe

    Returns:
        List of scene suggestions with relevance scores
    """
    suggestions = []

    for keyword in vibe_keywords:
        keyword_lower = keyword.lower()

        # Check scene mappings
        if keyword_lower in HUE_SCENE_MAPPINGS:
            mapping = HUE_SCENE_MAPPINGS[keyword_lower]
            suggestions.append(
                {
                    "scene_name": mapping["scene"],
                    "match_keyword": keyword,
                    "settings": mapping,
                    "description": AVAILABLE_SCENES.get(mapping["scene"], ""),
                }
            )

    return suggestions


def list_available_effects() -> dict[str, Any]:
    """List all available effects and scenes."""
    return {
        "vibe_presets": list(VIBE_PRESETS.keys()),
        "scene_keywords": list(HUE_SCENE_MAPPINGS.keys()),
        "hue_scenes": AVAILABLE_SCENES,
    }
