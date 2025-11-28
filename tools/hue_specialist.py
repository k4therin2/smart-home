"""
Hue Specialist Agent - Expert in Philips Hue API and effect implementation

This agent has deep knowledge of Hue capabilities and can plan complex
lighting effects like flickering, fading, and dynamic scenes.
"""

import os
import random
from typing import List, Dict
from anthropic import Anthropic


class HueSpecialist:
    """
    Specialist agent that understands Hue API details and can plan effects.

    This agent is consulted when the main agent needs to implement
    complex lighting behaviors beyond simple color/brightness changes.
    """

    def __init__(self):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = "claude-sonnet-4-20250514"

        # Knowledge base: Hue capabilities via Home Assistant
        self.hue_knowledge = """
# Philips Hue Capabilities via Home Assistant

## Available Service Calls

### light.turn_on
Parameters:
- brightness_pct (0-100): Brightness percentage
- color_temp (mireds): Color temperature in mireds (153-500 for most Hue)
- color_temp_kelvin: Color temperature in Kelvin (2000-6535)
- transition: Transition time in seconds
- flash: 'short' or 'long' - makes light flash
- effect: Special effects like 'colorloop'
- xy_color: Precise color control [x, y] coordinates

### hue.activate_scene
Parameters:
- entity_id: Hue scene entity ID
- transition: Transition duration in seconds
- dynamic: Enable/disable dynamic (animated) mode
- speed: Speed of dynamic palette
- brightness: Scene brightness override

## Important Constraints

1. Rate Limits: Don't send commands faster than every 100ms
2. Transitions: Minimum practical transition is 0.1s
3. Groups: Can control rooms (groups of lights) or individual lights
4. Effects: Built-in effects depend on light model

## Creating Flicker/Dynamic Effects

**Approach 1: Rapid Updates**
- Send sequential turn_on commands with varying brightness/color
- Use short transitions (0.3-1.5s) for smooth changes
- Space commands 0.5-2s apart
- Randomize parameters slightly for natural feel

**Approach 2: Built-in Scenes**
- Use existing dynamic scenes with dynamic=true
- Hue handles the animation internally
- Less API control but smoother

**Approach 3: Individual Light Control**
- For multi-light rooms, offset timing per light
- Creates wave/ripple effects
- More realistic but more complex

## Best Practices for Fire Effect

Fire flickers naturally with:
- Brightness variation: 40-65% (not too low, not constant)
- Color temp variation: 2000-2400K (orange to yellow)
- Irregular timing: 0.5-2 second intervals (not metronomic)
- Smooth transitions: 0.4-1.2s (not instant, not too slow)

Recommendation: Send 8-12 commands over 15-20 seconds for convincing effect
"""

    def plan_fire_flicker(self, room: str, duration_seconds: int = 15) -> List[Dict]:
        """
        Ask the specialist agent to plan a fire flickering effect.

        Args:
            room: Room name
            duration_seconds: How long the effect should run

        Returns:
            List of commands to execute in sequence
        """
        prompt = f"""You are a Philips Hue lighting specialist. Plan a realistic fire flickering effect.

Room: {room}
Duration: {duration_seconds} seconds

Requirements:
1. Create a sequence of light.turn_on commands that simulate flickering fire
2. Vary brightness (40-65%) and color temperature (2000-2400K) naturally
3. Use random but realistic intervals (0.5-2s between commands)
4. Use smooth transitions (0.4-1.2s)
5. Create 8-12 steps over the {duration_seconds} second duration

Return ONLY a JSON array of commands. Each command should be:
{{
  "delay_seconds": <wait this long before executing>,
  "brightness_pct": <40-65>,
  "color_temp_kelvin": <2000-2400>,
  "transition": <0.4-1.2>
}}

Example:
[
  {{"delay_seconds": 0, "brightness_pct": 55, "color_temp_kelvin": 2200, "transition": 0.8}},
  {{"delay_seconds": 1.5, "brightness_pct": 48, "color_temp_kelvin": 2100, "transition": 0.5}}
]

Return ONLY the JSON array, no other text."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=self.hue_knowledge,
            messages=[{"role": "user", "content": prompt}]
        )

        # Extract JSON from response
        import json
        response_text = response.content[0].text.strip()

        # Remove markdown code blocks if present
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1])  # Remove first and last line

        try:
            commands = json.loads(response_text)
            return commands
        except json.JSONDecodeError as e:
            print(f"Warning: Specialist agent returned invalid JSON: {e}")
            # Fallback to simple hardcoded flicker
            return self._fallback_flicker_plan(duration_seconds)

    def _fallback_flicker_plan(self, duration_seconds: int) -> List[Dict]:
        """Simple fallback if specialist agent fails."""
        commands = []
        time_elapsed = 0

        while time_elapsed < duration_seconds:
            commands.append({
                "delay_seconds": random.uniform(0.5, 2.0),
                "brightness_pct": random.randint(42, 62),
                "color_temp_kelvin": random.randint(2000, 2400),
                "transition": random.uniform(0.4, 1.2)
            })
            time_elapsed += commands[-1]["delay_seconds"] + commands[-1]["transition"]

        # First command starts immediately
        if commands:
            commands[0]["delay_seconds"] = 0

        return commands


# Singleton instance
_specialist = None

def get_hue_specialist() -> HueSpecialist:
    """Get the singleton Hue specialist agent."""
    global _specialist
    if _specialist is None:
        _specialist = HueSpecialist()
    return _specialist
