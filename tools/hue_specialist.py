"""
Hue Specialist Agent - Expert in Philips Hue API and scene selection

This agent has deep knowledge of Hue capabilities and recommends the best
scenes and parameters for user requests.
"""

import os
from typing import Dict
from anthropic import Anthropic
from config import MODEL_NAME
from utils import load_prompts, track_api_usage


# Metadata for UI display
METADATA = {
    "name": "Hue Specialist",
    "icon": "💡",
    "when_called": "When main agent needs complex Hue effects or scene recommendations",
    "purpose": "Expert in Philips Hue API - recommends scenes and parameters for abstract lighting descriptions",
    "tools_available": ["hue.activate_scene", "light.turn_on (with advanced parameters)"],
    "examples": ["'under the sea' → Arctic aurora scene", "'fire/campfire' → Fire scene", "'romantic' → City of love scene"]
}


class HueSpecialist:
    """
    Specialist agent that understands Hue API details and can recommend scenes.

    This agent is consulted when the main agent needs to implement
    complex lighting behaviors or map abstract descriptions to Hue scenes.
    """

    def __init__(self):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = MODEL_NAME

        # Load system prompt from config
        prompts = load_prompts()
        self.system_prompt = prompts.get("hue_specialist", {}).get("system", self._get_default_prompt())

    def _get_default_prompt(self) -> str:
        """Fallback prompt if config is missing."""
        return """# Philips Hue Specialist

You are an expert in Philips Hue lighting control via Home Assistant.

## Your Role
Map abstract user descriptions to specific Hue scenes and parameters.

## Available Service Calls

### hue.activate_scene
- entity_id: Hue scene entity ID
- dynamic: Enable/disable dynamic (animated) mode
- speed: Speed of dynamic palette (0-100)
- brightness: Scene brightness override (0-100)

### light.turn_on
- brightness_pct (0-100): Brightness percentage
- color_temp_kelvin: Color temperature in Kelvin (2000-6535)
- transition: Transition time in seconds

## Scene Mapping Examples

- "under the sea" / "ocean" / "water" → Arctic aurora (cool blues/greens)
- "fire" / "campfire" / "flames" → Fire scene (warm, flickering)
- "space" / "nebula" / "cosmos" → Nebula scene (purples/blues)
- "romantic" / "date night" → City of love (pinks/reds)
- "energetic" / "party" → Tokyo (vibrant, bright)
- "calm" / "relaxing" / "sleepy" → Nighttime or Sleepy scenes

## Important Guidelines

1. **Always prefer pre-built Hue scenes** over manual light control
2. Use dynamic=true for animated effects (fire, water, etc.)
3. Adjust speed parameter based on desired intensity (0=slow, 100=fast)
4. Consider brightness for the mood (romantic=low, energetic=high)

Return recommendations as JSON:
{
  "scene": "<scene name>",
  "dynamic": true/false,
  "speed": 0-100,
  "brightness": 0-100 (optional),
  "reasoning": "<why this scene fits>"
}
"""

    def recommend_scene(self, user_description: str, available_scenes: list) -> Dict:
        """
        Recommend the best Hue scene for a user's description.

        Args:
            user_description: What the user wants (e.g., "under the sea", "cozy", "fire")
            available_scenes: List of available Hue scene names

        Returns:
            Dictionary with scene recommendation and parameters
        """
        prompt = f"""User wants: "{user_description}"

Available Hue scenes: {', '.join(available_scenes)}

Recommend the BEST scene and parameters for this description."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=512,
                system=self.system_prompt,
                messages=[{"role": "user", "content": prompt}]
            )

            # Track API usage
            if hasattr(response, 'usage'):
                track_api_usage(
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens
                )

            # Parse JSON response
            import json
            response_text = response.content[0].text.strip()

            # Remove markdown code blocks if present
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1])

            recommendation = json.loads(response_text)
            return {
                "success": True,
                **recommendation
            }

        except Exception as e:
            # Fallback: return first available scene
            return {
                "success": False,
                "error": str(e),
                "scene": available_scenes[0] if available_scenes else "Fire",
                "dynamic": True,
                "speed": 50,
                "reasoning": "Fallback recommendation due to error"
            }


# Singleton instance
_specialist = None

def get_hue_specialist() -> HueSpecialist:
    """Get the singleton Hue specialist agent."""
    global _specialist
    if _specialist is None:
        _specialist = HueSpecialist()
    return _specialist
