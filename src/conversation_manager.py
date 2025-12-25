"""
Conversation Manager - Multi-turn conversation state for voice automation.

WP-9.1: Conversational Automation Setup via Voice

Manages conversation state for multi-turn voice interactions, particularly
for creating automations through back-and-forth dialogs.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional

from src.utils import setup_logging
from tools.automation import create_automation, _parse_time, _parse_days, VALID_DAYS

logger = setup_logging("conversation_manager")


class ConversationState(Enum):
    """State of a conversation."""

    IDLE = "idle"  # No active conversation
    COLLECTING = "collecting"  # Collecting automation parameters
    CONFIRMING = "confirming"  # Waiting for user confirmation

    def can_transition_to(self, target: "ConversationState") -> bool:
        """Check if transition to target state is valid."""
        valid_transitions = {
            ConversationState.IDLE: [ConversationState.COLLECTING],
            ConversationState.COLLECTING: [ConversationState.CONFIRMING, ConversationState.IDLE],
            ConversationState.CONFIRMING: [ConversationState.IDLE],
        }
        return target in valid_transitions.get(self, [])


@dataclass
class AutomationDraft:
    """Draft automation being built through conversation."""

    name: Optional[str] = None
    trigger_type: Optional[str] = None
    trigger_config: dict = field(default_factory=dict)
    action_command: Optional[str] = None

    def is_complete(self) -> bool:
        """Check if draft has all required fields."""
        # Must have trigger type
        if not self.trigger_type:
            return False

        # Must have action
        if not self.action_command:
            return False

        # Time triggers need time
        if self.trigger_type == "time":
            if "time" not in self.trigger_config:
                return False

        # State triggers need entity and to_state
        if self.trigger_type == "state":
            if "entity_id" not in self.trigger_config:
                return False
            if "to_state" not in self.trigger_config:
                return False

        return True

    def missing_fields(self) -> list[str]:
        """Get list of missing required fields."""
        missing = []

        if not self.action_command:
            missing.append("action_command")

        if not self.trigger_type:
            missing.append("trigger_type")
        elif self.trigger_type == "time":
            if "time" not in self.trigger_config:
                missing.append("trigger_time")
        elif self.trigger_type == "state":
            if "entity_id" not in self.trigger_config:
                missing.append("trigger_entity")
            if "to_state" not in self.trigger_config:
                missing.append("trigger_to_state")

        return missing

    def to_automation_params(self) -> dict[str, Any]:
        """Convert draft to automation creation parameters."""
        params = {
            "name": self.name or self._generate_name(),
            "trigger_type": self.trigger_type,
            "action_command": self.action_command,
        }

        if self.trigger_type == "time":
            params["trigger_time"] = self.trigger_config.get("time")
            params["trigger_days"] = self.trigger_config.get("days", VALID_DAYS.copy())
        elif self.trigger_type == "state":
            params["trigger_entity"] = self.trigger_config.get("entity_id")
            params["trigger_to_state"] = self.trigger_config.get("to_state")
            if "from_state" in self.trigger_config:
                params["trigger_from_state"] = self.trigger_config.get("from_state")

        return params

    def _generate_name(self) -> str:
        """Generate a name from the action command."""
        if self.action_command:
            # Clean up and truncate
            name = self.action_command[:30].strip()
            if len(self.action_command) > 30:
                name += "..."
            return name
        return "Unnamed automation"


@dataclass
class ConversationContext:
    """Context for an active conversation."""

    state: ConversationState = ConversationState.IDLE
    draft: Optional[AutomationDraft] = None
    last_activity: datetime = field(default_factory=datetime.now)
    last_question: Optional[str] = None


class ConversationManager:
    """
    Manages multi-turn conversation state for voice automation creation.

    Stores conversation context keyed by conversation_id from Home Assistant.
    Handles timeouts, state transitions, and draft accumulation.
    """

    def __init__(self, timeout_minutes: int = 10):
        """
        Initialize ConversationManager.

        Args:
            timeout_minutes: Minutes of inactivity before conversation expires
        """
        self.timeout_minutes = timeout_minutes
        self._conversations: dict[str, ConversationContext] = {}

    def _get_now(self) -> datetime:
        """Get current time (mockable for testing)."""
        return datetime.now()

    def _is_expired(self, context: ConversationContext) -> bool:
        """Check if conversation has expired."""
        elapsed = self._get_now() - context.last_activity
        return elapsed > timedelta(minutes=self.timeout_minutes)

    def _get_context(self, conversation_id: str) -> Optional[ConversationContext]:
        """Get conversation context, returning None if expired."""
        context = self._conversations.get(conversation_id)
        if context and self._is_expired(context):
            # Clean up expired conversation
            del self._conversations[conversation_id]
            return None
        return context

    def get_state(self, conversation_id: str) -> ConversationState:
        """Get current state of a conversation."""
        context = self._get_context(conversation_id)
        return context.state if context else ConversationState.IDLE

    def get_draft(self, conversation_id: str) -> Optional[AutomationDraft]:
        """Get current draft for a conversation."""
        context = self._get_context(conversation_id)
        return context.draft if context else None

    def start_automation(self, conversation_id: str) -> None:
        """Start a new automation creation conversation."""
        self._conversations[conversation_id] = ConversationContext(
            state=ConversationState.COLLECTING,
            draft=AutomationDraft(),
            last_activity=self._get_now(),
        )
        logger.info(f"Started automation conversation: {conversation_id}")

    def update_draft(self, conversation_id: str, **kwargs) -> None:
        """
        Update fields on the automation draft.

        Args:
            conversation_id: Conversation ID
            **kwargs: Fields to update (name, trigger_type, trigger_config, action_command)
        """
        context = self._get_context(conversation_id)
        if not context or not context.draft:
            logger.warning(f"No draft found for conversation: {conversation_id}")
            return

        draft = context.draft

        if "name" in kwargs:
            draft.name = kwargs["name"]
        if "trigger_type" in kwargs:
            draft.trigger_type = kwargs["trigger_type"]
        if "trigger_config" in kwargs:
            draft.trigger_config.update(kwargs["trigger_config"])
        if "action_command" in kwargs:
            draft.action_command = kwargs["action_command"]

        context.last_activity = self._get_now()

    def get_next_question(self, conversation_id: str) -> Optional[str]:
        """
        Get the next clarifying question based on missing fields.

        Returns None if draft is complete.
        """
        draft = self.get_draft(conversation_id)
        if not draft:
            return None

        if draft.is_complete():
            return None

        missing = draft.missing_fields()

        # Ask questions in priority order
        if "action_command" in missing:
            return "What would you like this automation to do?"

        if "trigger_type" in missing:
            return "When should this happen? Give me a time or describe the trigger."

        if "trigger_time" in missing:
            return "What time should this automation run?"

        if "trigger_entity" in missing:
            return "Which device or sensor should trigger this automation?"

        if "trigger_to_state" in missing:
            return "What state should trigger this automation?"

        return None

    def is_ready_for_confirmation(self, conversation_id: str) -> bool:
        """Check if draft is ready for user confirmation."""
        draft = self.get_draft(conversation_id)
        return draft is not None and draft.is_complete()

    def get_confirmation_text(self, conversation_id: str) -> str:
        """Get confirmation text describing the automation."""
        draft = self.get_draft(conversation_id)
        if not draft or not draft.is_complete():
            return "Automation is incomplete."

        if draft.trigger_type == "time":
            time_str = draft.trigger_config.get("time", "")
            days = draft.trigger_config.get("days", VALID_DAYS)

            # Format time for display
            hour, minute = map(int, time_str.split(":"))
            if hour >= 12:
                display_time = f"{hour - 12 if hour > 12 else 12}:{minute:02d}pm"
            else:
                display_time = f"{hour if hour else 12}:{minute:02d}am"

            # Format days
            if set(days) == set(VALID_DAYS):
                days_str = "every day"
            elif set(days) == {"mon", "tue", "wed", "thu", "fri"}:
                days_str = "on weekdays"
            elif set(days) == {"sat", "sun"}:
                days_str = "on weekends"
            else:
                days_str = f"on {', '.join(days)}"

            return f"I'll {draft.action_command} at {display_time} {days_str}. Should I create this automation?"

        elif draft.trigger_type == "state":
            entity = draft.trigger_config.get("entity_id", "device")
            to_state = draft.trigger_config.get("to_state", "state")
            return f"I'll {draft.action_command} when {entity} becomes {to_state}. Should I create this automation?"

        return f"I'll {draft.action_command}. Should I create this automation?"

    def transition_to_confirming(self, conversation_id: str) -> None:
        """Transition conversation to CONFIRMING state."""
        context = self._get_context(conversation_id)
        if context:
            context.state = ConversationState.CONFIRMING
            context.last_activity = self._get_now()

    def confirm(self, conversation_id: str) -> dict[str, Any]:
        """
        Confirm and create the automation.

        Returns:
            Result from automation creation
        """
        draft = self.get_draft(conversation_id)
        if not draft or not draft.is_complete():
            return {"success": False, "error": "Automation is incomplete"}

        params = draft.to_automation_params()
        result = create_automation(**params)

        # Clean up conversation
        self.cancel(conversation_id)

        return result

    def cancel(self, conversation_id: str) -> None:
        """Cancel the current conversation and clear state."""
        if conversation_id in self._conversations:
            del self._conversations[conversation_id]
            logger.info(f"Cancelled conversation: {conversation_id}")

    def get_context(self, conversation_id: str) -> str:
        """Get conversation context to prepend to agent prompt."""
        context = self._get_context(conversation_id)
        if not context or not context.draft:
            return ""

        draft = context.draft
        parts = ["[Continuing automation creation conversation]"]

        if draft.action_command:
            parts.append(f"Action: {draft.action_command}")

        if draft.trigger_type == "time":
            if "time" in draft.trigger_config:
                parts.append(f"Time: {draft.trigger_config['time']}")
            if "days" in draft.trigger_config:
                parts.append(f"Days: {', '.join(draft.trigger_config['days'])}")
        elif draft.trigger_type == "state":
            if "entity_id" in draft.trigger_config:
                parts.append(f"Trigger: {draft.trigger_config['entity_id']}")

        missing = draft.missing_fields()
        if missing:
            parts.append(f"Still needed: {', '.join(missing)}")

        return "\n".join(parts)

    def parse_response(self, conversation_id: str, response: str) -> dict[str, Any]:
        """
        Parse user response and extract updates for the draft.

        Args:
            conversation_id: Conversation ID
            response: User's voice response text

        Returns:
            Dict with extracted updates or clarification needs
        """
        response_lower = response.lower().strip()
        updates: dict[str, Any] = {}
        draft = self.get_draft(conversation_id)

        # Try to parse time patterns
        time_patterns = [
            r"at\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm))",  # "at 10pm", "at 8:30am"
            r"(\d{1,2}(?::\d{2})?\s*(?:am|pm))\s+every",  # "10pm every night"
            r"every\s+(?:day|night)\s+at\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm))",  # "every day at 8pm"
        ]

        for pattern in time_patterns:
            match = re.search(pattern, response_lower)
            if match:
                time_str = match.group(1).strip()
                parsed_time = _parse_time(time_str)
                if parsed_time:
                    updates["trigger_type"] = "time"
                    updates["trigger_config"] = {"time": parsed_time}

                    # Check for day patterns
                    if "weekday" in response_lower:
                        updates["trigger_config"]["days"] = ["mon", "tue", "wed", "thu", "fri"]
                    elif "weekend" in response_lower:
                        updates["trigger_config"]["days"] = ["sat", "sun"]

                    break

        # Try to extract action if not set
        if draft and not draft.action_command:
            # Look for action verbs
            action_patterns = [
                r"(?:to\s+)?(turn\s+(?:on|off)\s+.+?)(?:\s+at\s+\d|$)",
                r"(?:to\s+)?(start\s+.+?)(?:\s+at\s+\d|$)",
                r"(?:to\s+)?(stop\s+.+?)(?:\s+at\s+\d|$)",
            ]
            for pattern in action_patterns:
                match = re.search(pattern, response_lower)
                if match:
                    action = match.group(1).strip()
                    if action:
                        updates["action_command"] = action
                        break

        # Handle room/device specifications
        room_patterns = [
            r"(?:the\s+)?(living\s+room)\s*(?:lights?)?",  # "the living room lights"
            r"(?:the\s+)?(bed\s*room)\s*(?:lights?)?",  # "the bedroom lights"
            r"(?:the\s+)?(kitchen)\s*(?:lights?)?",  # "the kitchen"
            r"(?:the\s+)?(office)\s*(?:lights?)?",  # "the office"
            r"(?:the\s+)?(\w+\s+room)\s+lights?",  # generic "X room lights"
            r"(?:the\s+)?lights?\s+in\s+(?:the\s+)?(\w+(?:\s+room)?)",  # "lights in the X"
            r"(?:the\s+)?(\w+)\s+lights?",  # "X lights"
        ]

        for pattern in room_patterns:
            match = re.search(pattern, response_lower)
            if match:
                room = match.group(1).strip()
                # Normalize common room names
                room = room.replace("bed room", "bedroom")

                if room not in ["all", "the", "some", "my"]:
                    if draft and draft.action_command:
                        # Update action with specific room
                        if "lights" in draft.action_command.lower() and room not in draft.action_command.lower():
                            updates["action_command"] = draft.action_command.replace("lights", f"{room} lights")
                    else:
                        # Build action from room
                        if "turn on" in response_lower:
                            updates["action_command"] = f"turn on {room} lights"
                        elif "turn off" in response_lower:
                            updates["action_command"] = f"turn off {room} lights"
                        else:
                            # Just specifying the room without an action verb
                            updates["action_command"] = f"{room} lights"
                    break

        return updates

    def is_confirmation_response(self, response: str) -> bool:
        """Check if response is a confirmation."""
        response_lower = response.lower().strip()
        confirmation_words = [
            "yes", "yep", "yeah", "yup", "sure", "ok", "okay", "confirm",
            "sounds good", "that's right", "correct", "go ahead", "do it",
            "create it", "make it", "enable it"
        ]
        return any(word in response_lower for word in confirmation_words)

    def is_cancel_response(self, response: str) -> bool:
        """Check if response is a cancellation."""
        response_lower = response.lower().strip()
        cancel_words = [
            "no", "nope", "cancel", "stop", "never mind", "forget it",
            "don't", "nevermind", "abort", "quit"
        ]
        return any(word in response_lower for word in cancel_words)

    def process_message(
        self,
        conversation_id: str,
        message: str
    ) -> dict[str, Any]:
        """
        Process a voice message in conversation context.

        Args:
            conversation_id: Conversation ID from HA
            message: Voice command text

        Returns:
            Dict with response type and content:
            - type: "clarify" | "confirm" | "success" | "error" | "cancel"
            - question: Next clarifying question (for "clarify")
            - confirmation: Confirmation text (for "confirm")
            - message: Response message (for "success" or "error")
        """
        state = self.get_state(conversation_id)
        message_lower = message.lower().strip()

        # Check for automation creation intent in IDLE state
        if state == ConversationState.IDLE:
            automation_intents = [
                "create automation", "make automation", "new automation",
                "set up automation", "create a new automation", "add automation",
                "make a new automation", "automation that", "automation to"
            ]
            if any(intent in message_lower for intent in automation_intents):
                self.start_automation(conversation_id)

                # Try to parse initial message for info
                updates = self.parse_response(conversation_id, message)
                if updates:
                    self.update_draft(conversation_id, **updates)

                # Check if complete already
                if self.is_ready_for_confirmation(conversation_id):
                    self.transition_to_confirming(conversation_id)
                    return {
                        "type": "confirm",
                        "confirmation": self.get_confirmation_text(conversation_id)
                    }

                question = self.get_next_question(conversation_id)
                return {
                    "type": "clarify",
                    "question": question
                }

            # Not an automation request
            return {
                "type": "passthrough",
                "message": message
            }

        # Handle CONFIRMING state
        elif state == ConversationState.CONFIRMING:
            if self.is_confirmation_response(message):
                result = self.confirm(conversation_id)
                if result.get("success"):
                    return {
                        "type": "success",
                        "message": result.get("message", "Automation created.")
                    }
                else:
                    return {
                        "type": "error",
                        "message": result.get("error", "Failed to create automation.")
                    }

            elif self.is_cancel_response(message):
                self.cancel(conversation_id)
                return {
                    "type": "cancel",
                    "message": "Okay, cancelled the automation."
                }

            else:
                # User wants to modify something
                self._conversations[conversation_id].state = ConversationState.COLLECTING
                updates = self.parse_response(conversation_id, message)
                if updates:
                    self.update_draft(conversation_id, **updates)

                if self.is_ready_for_confirmation(conversation_id):
                    self.transition_to_confirming(conversation_id)
                    return {
                        "type": "confirm",
                        "confirmation": self.get_confirmation_text(conversation_id)
                    }

                question = self.get_next_question(conversation_id)
                return {
                    "type": "clarify",
                    "question": question
                }

        # Handle COLLECTING state
        elif state == ConversationState.COLLECTING:
            # Check for cancel
            if self.is_cancel_response(message):
                self.cancel(conversation_id)
                return {
                    "type": "cancel",
                    "message": "Okay, cancelled."
                }

            # Parse response for updates
            updates = self.parse_response(conversation_id, message)
            if updates:
                self.update_draft(conversation_id, **updates)

            # Check if ready for confirmation
            if self.is_ready_for_confirmation(conversation_id):
                self.transition_to_confirming(conversation_id)
                return {
                    "type": "confirm",
                    "confirmation": self.get_confirmation_text(conversation_id)
                }

            # Need more info
            question = self.get_next_question(conversation_id)
            if question:
                context = self._get_context(conversation_id)
                if context:
                    context.last_question = question
                return {
                    "type": "clarify",
                    "question": question
                }

            # Something went wrong
            return {
                "type": "error",
                "message": "I'm having trouble understanding. Let's start over."
            }

        return {
            "type": "error",
            "message": "Unexpected conversation state."
        }


# Placeholder for device discovery - will be integrated with HA client
def get_device_names() -> list[str]:
    """Get list of available device/room names from Home Assistant."""
    # This will be implemented to query HA for actual devices
    return ["living room", "bedroom", "kitchen", "office"]


# Singleton instance
_conversation_manager: Optional[ConversationManager] = None


def get_conversation_manager() -> ConversationManager:
    """Get the singleton ConversationManager instance."""
    global _conversation_manager
    if _conversation_manager is None:
        _conversation_manager = ConversationManager()
    return _conversation_manager
