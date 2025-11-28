#!/usr/bin/env python3
"""
Home Automation Agent - Phase 1: The "Fire" Problem

This agent interprets natural language descriptions of lighting ambiance
and controls Philips Hue lights via Home Assistant.

Usage:
    python agent.py "turn living room to fire"
    python agent.py "make the bedroom cozy"
"""

import os
import sys
import json
from dotenv import load_dotenv
from anthropic import Anthropic

# Import our custom tools
from tools.lights import set_room_ambiance, get_available_rooms, apply_fire_flicker
from tools.effects import apply_abstract_effect


# Load environment variables
load_dotenv()


def load_system_prompt() -> str:
    """Load the system prompt from file."""
    prompt_path = os.path.join("prompts", "system_prompt.txt")
    try:
        with open(prompt_path, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        print(f"Warning: System prompt not found at {prompt_path}")
        return "You are a helpful home lighting assistant."


def process_tool_call(tool_name: str, tool_input: dict) -> dict:
    """
    Execute the requested tool and return the result.

    Args:
        tool_name: Name of the tool to execute
        tool_input: Dictionary of tool parameters

    Returns:
        Dictionary with the tool execution result
    """
    if tool_name == "set_room_ambiance":
        return set_room_ambiance(
            room=tool_input["room"],
            color_temp_kelvin=tool_input["color_temp_kelvin"],
            brightness_pct=tool_input["brightness_pct"],
            description=tool_input.get("description")
        )
    elif tool_name == "get_available_rooms":
        return get_available_rooms()
    elif tool_name == "apply_fire_flicker":
        return apply_fire_flicker(
            room=tool_input["room"],
            duration_seconds=tool_input.get("duration_seconds", 15)
        )
    elif tool_name == "apply_abstract_effect":
        return apply_abstract_effect(
            description=tool_input["description"],
            room=tool_input["room"]
        )
    else:
        return {
            "success": False,
            "error": f"Unknown tool: {tool_name}"
        }


def run_agent(user_input: str, verbose: bool = True) -> str:
    """
    Run the agent with the given user input.

    Args:
        user_input: Natural language command from user
        verbose: Whether to print detailed execution info

    Returns:
        Agent's text response
    """
    # Initialize Anthropic client
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return "Error: ANTHROPIC_API_KEY not set. Please add it to your .env file."

    client = Anthropic(api_key=api_key)

    # Load system prompt
    system_prompt = load_system_prompt()

    # Define available tools
    tools = [
        {
            "name": "set_room_ambiance",
            "description": "Set lighting ambiance for a room based on mood/description. Use this to control the lights when the user asks for a specific atmosphere, mood, or scene.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "room": {
                        "type": "string",
                        "description": "Room name (e.g., 'living_room', 'bedroom', 'kitchen', 'office')"
                    },
                    "color_temp_kelvin": {
                        "type": "integer",
                        "description": "Color temperature in Kelvin (2000-6500). Warm tones are 2000-2700K, neutral is 3000-4000K, cool is 5000-6500K."
                    },
                    "brightness_pct": {
                        "type": "integer",
                        "description": "Brightness percentage (0-100)"
                    },
                    "description": {
                        "type": "string",
                        "description": "What this ambiance represents (e.g., 'fire', 'ocean', 'cozy')"
                    }
                },
                "required": ["room", "color_temp_kelvin", "brightness_pct"]
            }
        },
        {
            "name": "get_available_rooms",
            "description": "Query Home Assistant to see what lights/rooms are available. Use this if you're unsure what rooms exist.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "apply_fire_flicker",
            "description": "Apply a realistic fire flickering effect to a room. Use this when the user wants dynamic fire-like lighting that flickers and varies naturally. This tool consults a specialist Hue agent that plans a sequence of lighting changes to simulate realistic fire movement.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "room": {
                        "type": "string",
                        "description": "Room name (e.g., 'living_room', 'bedroom')"
                    },
                    "duration_seconds": {
                        "type": "integer",
                        "description": "How long the flickering effect should run in seconds (default 15)"
                    }
                },
                "required": ["room"]
            }
        },
        {
            "name": "apply_abstract_effect",
            "description": "Apply a looping effect based on abstract description like 'under the sea', 'swamp', 'strobing green', etc. This uses Hue's built-in dynamic scenes which loop indefinitely without continuous API calls. A specialist agent maps the description to the best available Hue scene with appropriate speed and brightness. PREFER THIS over fire_flicker for abstract/creative descriptions.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "Abstract description of desired atmosphere (e.g., 'under the sea', 'swamp', 'strobing green', 'northern lights', 'cosmic nebula')"
                    },
                    "room": {
                        "type": "string",
                        "description": "Room name (e.g., 'living_room', 'bedroom')"
                    }
                },
                "required": ["description", "room"]
            }
        }
    ]

    # Start the agent loop
    messages = [{"role": "user", "content": user_input}]

    if verbose:
        print(f"\n{'='*60}")
        print(f"User: {user_input}")
        print(f"{'='*60}\n")

    # Agentic loop (can handle multiple tool calls if needed)
    max_iterations = 5
    for iteration in range(max_iterations):
        # Call Claude
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=system_prompt,
            tools=tools,
            messages=messages
        )

        if verbose:
            print(f"[Iteration {iteration + 1}] Stop reason: {response.stop_reason}")

        # Process the response
        if response.stop_reason == "end_turn":
            # Agent is done, extract final text response
            final_response = ""
            for block in response.content:
                if block.type == "text":
                    final_response += block.text
            return final_response.strip()

        elif response.stop_reason == "tool_use":
            # Agent wants to use tools
            # Add assistant's response to messages
            messages.append({"role": "assistant", "content": response.content})

            # Process each tool call
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_name = block.name
                    tool_input = block.input

                    if verbose:
                        print(f"\n[Tool Call: {tool_name}]")
                        print(f"Input: {json.dumps(tool_input, indent=2)}")

                    # Execute the tool
                    result = process_tool_call(tool_name, tool_input)

                    if verbose:
                        print(f"Result: {json.dumps(result, indent=2)}\n")

                    # Add tool result to messages
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result)
                    })

            # Add all tool results as a user message
            messages.append({"role": "user", "content": tool_results})

        else:
            # Unexpected stop reason
            return f"Unexpected stop reason: {response.stop_reason}"

    return "Agent reached maximum iterations without completing."


def main():
    """Main entry point for the agent."""
    if len(sys.argv) < 2:
        print("Usage: python agent.py \"your command here\"")
        print("\nExamples:")
        print("  python agent.py \"turn living room to fire\"")
        print("  python agent.py \"make the bedroom cozy\"")
        print("  python agent.py \"set kitchen to energizing\"")
        sys.exit(1)

    # Get command from arguments
    command = " ".join(sys.argv[1:])

    # Run the agent
    response = run_agent(command, verbose=True)

    # Print the final response
    print(f"\n{'='*60}")
    print(f"Agent: {response}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
