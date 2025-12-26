#!/usr/bin/env python3
"""
Smart Home Assistant - Main Agent

Agentic loop implementation using Claude Sonnet 4 for natural language
processing and tool execution.

Usage:
    python agent.py "turn the living room lights to cozy"
    python agent.py  # Interactive mode
"""

from __future__ import annotations

import sys
import json
import argparse
from datetime import datetime
from typing import Any, Dict, List

import openai

from src.config import (
    OPENAI_API_KEY,
    OPENAI_MODEL,
    MAX_AGENT_ITERATIONS,
)
from src.utils import (
    setup_logging,
    load_prompts,
    check_setup,
    track_api_usage,
    log_command,
    log_tool_call,
    get_daily_usage,
)
from src.ha_client import get_ha_client
from tools.lights import LIGHT_TOOLS, execute_light_tool
from tools.vacuum import VACUUM_TOOLS, execute_vacuum_tool
from tools.blinds import BLINDS_TOOLS, execute_blinds_tool
from tools.plugs import PLUGS_TOOLS, execute_plug_tool
from tools.spotify import SPOTIFY_TOOLS, execute_spotify_tool
from tools.productivity import PRODUCTIVITY_TOOLS, execute_productivity_tool
from tools.automation import AUTOMATION_TOOLS, execute_automation_tool
from tools.timers import TIMER_TOOLS, execute_timer_tool
from tools.location import LOCATION_TOOLS, execute_location_tool
from tools.improvements import IMPROVEMENT_TOOLS, handle_improvement_tool
from tools.presence import PRESENCE_TOOLS, execute_presence_tool
from tools.ember_mug import EMBER_MUG_TOOLS, execute_ember_mug_tool
from tools.system import get_current_time, get_current_date, get_datetime_info

logger = setup_logging("agent")


# System tools (non-device)
SYSTEM_TOOLS = [
    {
        "name": "get_current_time",
        "description": "Get the current time. Use this when the user asks what time it is.",
        "input_schema": {
            "type": "object",
            "properties": {
                "format_24h": {
                    "type": "boolean",
                    "description": "If true, return 24-hour format (e.g., 14:30). If false, return 12-hour format (e.g., 2:30 PM). Default is false.",
                }
            },
            "required": []
        }
    },
    {
        "name": "get_current_date",
        "description": "Get the current date with day of week. Use this when the user asks what today's date is or what day of the week it is.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_datetime_info",
        "description": "Get comprehensive datetime information including time, date, day of week, timestamp, and timezone. Use this for detailed datetime queries.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_system_status",
        "description": "Get the current status of the smart home system including daily API cost and Home Assistant connection.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
]

# Combine all tools - device tools come from tools/*.py modules
TOOLS = SYSTEM_TOOLS + LIGHT_TOOLS + VACUUM_TOOLS + BLINDS_TOOLS + PLUGS_TOOLS + SPOTIFY_TOOLS + PRODUCTIVITY_TOOLS + AUTOMATION_TOOLS + TIMER_TOOLS + LOCATION_TOOLS + IMPROVEMENT_TOOLS + PRESENCE_TOOLS + EMBER_MUG_TOOLS


def execute_tool(tool_name: str, tool_input: dict) -> str:
    """
    Execute a tool and return the result as a string.

    Args:
        tool_name: Name of the tool to execute
        tool_input: Tool input parameters

    Returns:
        Result string to send back to Claude
    """
    logger.info(f"Executing tool: {tool_name}")

    # System tools
    if tool_name == "get_current_time":
        format_24h = tool_input.get("format_24h", False)
        result = get_current_time(format_24h=format_24h)
        log_tool_call(tool_name, tool_input, result)
        return result

    elif tool_name == "get_current_date":
        result = get_current_date()
        log_tool_call(tool_name, tool_input, result)
        return result

    elif tool_name == "get_datetime_info":
        result = json.dumps(get_datetime_info())
        log_tool_call(tool_name, tool_input, result)
        return result

    elif tool_name == "get_system_status":
        daily_cost = get_daily_usage()
        ha_client = get_ha_client()
        ha_connected = ha_client.check_connection()
        result = json.dumps({
            "status": "operational",
            "daily_api_cost_usd": round(daily_cost, 4),
            "home_assistant": "connected" if ha_connected else "not_connected",
        })
        log_tool_call(tool_name, tool_input, result)
        return result

    # Light tools - delegate to tools/lights.py
    light_tool_names = [tool["name"] for tool in LIGHT_TOOLS]
    if tool_name in light_tool_names:
        result = execute_light_tool(tool_name, tool_input)
        log_tool_call(tool_name, tool_input, result)
        return json.dumps(result) if isinstance(result, dict) else str(result)

    # Vacuum tools - delegate to tools/vacuum.py
    vacuum_tool_names = [tool["name"] for tool in VACUUM_TOOLS]
    if tool_name in vacuum_tool_names:
        result = execute_vacuum_tool(tool_name, tool_input)
        log_tool_call(tool_name, tool_input, result)
        return json.dumps(result) if isinstance(result, dict) else str(result)

    # Blinds tools - delegate to tools/blinds.py
    blinds_tool_names = [tool["name"] for tool in BLINDS_TOOLS]
    if tool_name in blinds_tool_names:
        result = execute_blinds_tool(tool_name, tool_input)
        log_tool_call(tool_name, tool_input, result)
        return json.dumps(result) if isinstance(result, dict) else str(result)

    # Smart plug tools - delegate to tools/plugs.py
    plug_tool_names = [tool["name"] for tool in PLUGS_TOOLS]
    if tool_name in plug_tool_names:
        result = execute_plug_tool(tool_name, tool_input)
        log_tool_call(tool_name, tool_input, result)
        return json.dumps(result) if isinstance(result, dict) else str(result)

    # Spotify tools - delegate to tools/spotify.py
    spotify_tool_names = [tool["name"] for tool in SPOTIFY_TOOLS]
    if tool_name in spotify_tool_names:
        result = execute_spotify_tool(tool_name, tool_input)
        log_tool_call(tool_name, tool_input, result)
        return json.dumps(result) if isinstance(result, dict) else str(result)

    # Productivity tools - delegate to tools/productivity.py
    productivity_tool_names = [tool["name"] for tool in PRODUCTIVITY_TOOLS]
    if tool_name in productivity_tool_names:
        result = execute_productivity_tool(tool_name, tool_input)
        log_tool_call(tool_name, tool_input, result)
        return json.dumps(result) if isinstance(result, dict) else str(result)

    # Automation tools - delegate to tools/automation.py
    automation_tool_names = [tool["name"] for tool in AUTOMATION_TOOLS]
    if tool_name in automation_tool_names:
        result = execute_automation_tool(tool_name, tool_input)
        log_tool_call(tool_name, tool_input, result)
        return json.dumps(result) if isinstance(result, dict) else str(result)

    # Timer/alarm tools - delegate to tools/timers.py
    timer_tool_names = [tool["name"] for tool in TIMER_TOOLS]
    if tool_name in timer_tool_names:
        result = execute_timer_tool(tool_name, tool_input)
        log_tool_call(tool_name, tool_input, result)
        return json.dumps(result) if isinstance(result, dict) else str(result)

    # Location tools - delegate to tools/location.py
    location_tool_names = [tool["name"] for tool in LOCATION_TOOLS]
    if tool_name in location_tool_names:
        result = execute_location_tool(tool_name, tool_input)
        log_tool_call(tool_name, tool_input, result)
        return json.dumps(result) if isinstance(result, dict) else str(result)

    # Improvement tools - delegate to tools/improvements.py
    improvement_tool_names = [tool["name"] for tool in IMPROVEMENT_TOOLS]
    if tool_name in improvement_tool_names:
        result = handle_improvement_tool(tool_name, tool_input)
        log_tool_call(tool_name, tool_input, result)
        return json.dumps(result) if isinstance(result, dict) else str(result)

    # Presence tools - delegate to tools/presence.py
    presence_tool_names = [tool["name"] for tool in PRESENCE_TOOLS]
    if tool_name in presence_tool_names:
        result = execute_presence_tool(tool_name, tool_input)
        log_tool_call(tool_name, tool_input, result)
        return json.dumps(result) if isinstance(result, dict) else str(result)

    # Ember Mug tools - delegate to tools/ember_mug.py
    ember_mug_tool_names = [tool["name"] for tool in EMBER_MUG_TOOLS]
    if tool_name in ember_mug_tool_names:
        result = execute_ember_mug_tool(tool_name, tool_input)
        log_tool_call(tool_name, tool_input, result)
        return json.dumps(result) if isinstance(result, dict) else str(result)

    # Unknown tool
    result = f"Unknown tool: {tool_name}"
    log_tool_call(tool_name, tool_input, result)
    return result


def convert_tools_to_openai_format(tools: List[Dict]) -> List[Dict]:
    """Convert Anthropic-style tool definitions to OpenAI function format."""
    openai_tools = []
    for tool in tools:
        openai_tools.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["input_schema"]
            }
        })
    return openai_tools


def run_agent(user_message: str) -> str:
    """
    Run the agentic loop with OpenAI.

    Args:
        user_message: User's natural language command

    Returns:
        Final response from the agent
    """
    if not OPENAI_API_KEY:
        return "Error: OPENAI_API_KEY not configured. Please set it in .env file."

    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    prompts = load_prompts()
    system_prompt = prompts.get("main_agent", {}).get("system", "You are a helpful smart home assistant.")

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ]

    openai_tools = convert_tools_to_openai_format(TOOLS)

    log_command(user_message)

    for iteration in range(MAX_AGENT_ITERATIONS):
        logger.debug(f"Agent iteration {iteration + 1}/{MAX_AGENT_ITERATIONS}")

        try:
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                max_tokens=1024,
                messages=messages,
                tools=openai_tools,
                tool_choice="auto"
            )
        except openai.APIError as error:
            logger.error(f"OpenAI API error: {error}")
            return f"API Error: {error}"

        message = response.choices[0].message

        # Track usage
        track_api_usage(
            model=OPENAI_MODEL,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
            command=user_message[:100]
        )

        logger.debug(f"Finish reason: {response.choices[0].finish_reason}")

        # Check if we're done (no tool calls)
        if response.choices[0].finish_reason == "stop":
            return message.content or "Done."

        # Process tool calls
        if message.tool_calls:
            # Add assistant message with tool calls
            messages.append(message)

            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                tool_input = json.loads(tool_call.function.arguments)

                logger.info(f"Tool use: {tool_name} with {tool_input}")

                # Execute tool
                result = execute_tool(tool_name, tool_input)

                # Add tool result
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                })
        else:
            # No tool calls and not stopped - return content
            return message.content or "Done."

    # Max iterations reached
    logger.warning("Max agent iterations reached")
    return "I've reached my processing limit. Please try a simpler request."


def interactive_mode() -> None:
    """Run the agent in interactive mode."""
    print("Smart Home Assistant - Interactive Mode")
    print("Type 'quit' or 'exit' to stop.\n")

    while True:
        try:
            user_input = input("You: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ("quit", "exit", "q"):
                print("Goodbye!")
                break

            response = run_agent(user_input)
            print(f"Assistant: {response}\n")

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except EOFError:
            break


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Smart Home Assistant - AI-powered home control"
    )
    parser.add_argument(
        "command",
        nargs="?",
        help="Command to execute (omit for interactive mode)"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify system setup and exit"
    )
    parser.add_argument(
        "--cost",
        action="store_true",
        help="Show today's API cost and exit"
    )

    args = parser.parse_args()

    # Check setup
    if args.check:
        is_valid, errors = check_setup()
        if is_valid:
            print("Setup OK!")
            return 0
        else:
            print("Setup errors:")
            for error in errors:
                print(f"  - {error}")
            return 1

    # Show daily cost
    if args.cost:
        cost = get_daily_usage()
        print(f"Today's API cost: ${cost:.4f}")
        return 0

    # Validate before running
    is_valid, errors = check_setup()
    if not is_valid:
        print("Configuration errors:")
        for error in errors:
            print(f"  - {error}")
        print("\nRun 'python agent.py --check' for more details.")
        return 1

    # Execute command or enter interactive mode
    if args.command:
        response = run_agent(args.command)
        print(response)
    else:
        interactive_mode()

    return 0


if __name__ == "__main__":
    sys.exit(main())
