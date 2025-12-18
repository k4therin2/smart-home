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

import anthropic

from src.config import (
    ANTHROPIC_API_KEY,
    CLAUDE_MODEL,
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

logger = setup_logging("agent")


# System tools (non-device)
SYSTEM_TOOLS = [
    {
        "name": "get_current_time",
        "description": "Get the current date and time. Use this when the user asks what time it is.",
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
TOOLS = SYSTEM_TOOLS + LIGHT_TOOLS + VACUUM_TOOLS


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
        now = datetime.now()
        result = f"Current time: {now.strftime('%I:%M %p')}, Date: {now.strftime('%A, %B %d, %Y')}"
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

    # Unknown tool
    result = f"Unknown tool: {tool_name}"
    log_tool_call(tool_name, tool_input, result)
    return result


def run_agent(user_message: str) -> str:
    """
    Run the agentic loop with Claude.

    Args:
        user_message: User's natural language command

    Returns:
        Final response from the agent
    """
    if not ANTHROPIC_API_KEY:
        return "Error: ANTHROPIC_API_KEY not configured. Please set it in .env file."

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    prompts = load_prompts()
    system_prompt = prompts.get("main_agent", {}).get("system", "You are a helpful smart home assistant.")

    messages = [{"role": "user", "content": user_message}]

    log_command(user_message)

    for iteration in range(MAX_AGENT_ITERATIONS):
        logger.debug(f"Agent iteration {iteration + 1}/{MAX_AGENT_ITERATIONS}")

        try:
            response = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=1024,
                system=system_prompt,
                tools=TOOLS,
                messages=messages
            )
        except anthropic.APIError as error:
            logger.error(f"Anthropic API error: {error}")
            return f"API Error: {error}"

        # Track usage
        track_api_usage(
            model=CLAUDE_MODEL,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            command=user_message[:100]
        )

        logger.debug(f"Stop reason: {response.stop_reason}")

        # Check if we're done (no more tool use)
        if response.stop_reason == "end_turn":
            # Extract text response
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text
            return "Done."

        # Process tool use
        tool_results = []
        text_response = None

        for block in response.content:
            if block.type == "text":
                text_response = block.text
            elif block.type == "tool_use":
                tool_name = block.name
                tool_input = block.input
                tool_use_id = block.id

                logger.info(f"Tool use: {tool_name} with {tool_input}")

                # Execute tool
                result = execute_tool(tool_name, tool_input)

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": result
                })

        # Add assistant message and tool results to conversation
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

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
