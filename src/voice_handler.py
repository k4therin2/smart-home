"""
Voice Command Handler

Handles voice commands from Home Assistant voice puck:
- Parses HA conversation webhook requests
- Routes commands to agent
- Returns TTS-formatted responses
- Manages timeout and error handling
- Supports multi-turn conversations for automation creation (WP-9.1)

REQ-016: Voice Control via HA Voice Puck
WP-9.1: Conversational Automation Setup via Voice
"""

import concurrent.futures
import uuid
from collections.abc import Callable
from typing import Any

from src.conversation_manager import get_conversation_manager
from src.utils import setup_logging
from src.voice_response import ResponseFormatter


logger = setup_logging("voice_handler")


class VoiceHandler:
    """
    Handle voice commands from Home Assistant webhook.

    Processes voice input, routes to agent, and formats responses
    for text-to-speech output.
    """

    def __init__(
        self,
        agent_callback: Callable[[str], str],
        timeout_seconds: int = 30,
        response_formatter: ResponseFormatter | None = None,
    ):
        """
        Initialize the VoiceHandler.

        Args:
            agent_callback: Function to call with voice command text.
                           Should accept str and return str response.
            timeout_seconds: Maximum time to wait for agent response.
            response_formatter: Optional custom ResponseFormatter instance.
        """
        self.agent_callback = agent_callback
        self.timeout_seconds = timeout_seconds
        self.formatter = response_formatter or ResponseFormatter()

    def process_command(self, text: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Process a voice command and return formatted response.

        Args:
            text: Voice command text (from STT)
            context: Optional context from HA (device_id, room, etc.)

        Returns:
            Dict with success status and response/error
        """
        # Validate input
        if not text or not text.strip():
            logger.warning("Empty voice command received")
            return {"success": False, "error": self.formatter.error_not_understood()}

        clean_text = text.strip()
        logger.info(f"Processing voice command: {clean_text[:100]}...")

        # Get or generate conversation ID for multi-turn support
        conversation_id = self._get_conversation_id(context)

        try:
            # Check for multi-turn automation conversation
            conversation_result = self._handle_conversation(clean_text, conversation_id)
            if conversation_result is not None:
                # Handled by conversation manager
                result = {"success": True, "response": conversation_result}
                if context:
                    result["context"] = context
                logger.info(f"Conversation response: {conversation_result[:50]}...")
                return result

            # Normal flow: execute agent with timeout
            response = self._execute_with_timeout(clean_text)

            # Format response for TTS
            formatted_response = self.formatter.format(response)

            result = {"success": True, "response": formatted_response}

            # Include context if provided (for multi-room tracking)
            if context:
                result["context"] = context

            logger.info(f"Voice command successful: {formatted_response[:50]}...")
            return result

        except TimeoutError:
            logger.warning(f"Voice command timeout: {clean_text[:50]}...")
            return {"success": False, "error": self.formatter.error_timeout()}
        except Exception as error:
            logger.error(f"Voice command error: {error}")
            return {"success": False, "error": self.formatter.error(str(error))}

    def _get_conversation_id(self, context: dict[str, Any] | None) -> str:
        """
        Get conversation ID from context or generate one.

        Args:
            context: Context dict from HA webhook

        Returns:
            Conversation ID string
        """
        if context and "conversation_id" in context:
            return context["conversation_id"]
        # Generate a new ID for this session
        return f"voice-{uuid.uuid4().hex[:8]}"

    def _handle_conversation(self, text: str, conversation_id: str) -> str | None:
        """
        Handle multi-turn conversation for automation creation.

        Args:
            text: Voice command text
            conversation_id: Conversation ID for state tracking

        Returns:
            Response string if handled by conversation manager,
            None if should fall through to normal agent flow
        """
        manager = get_conversation_manager()
        result = manager.process_message(conversation_id, text)

        response_type = result.get("type")

        if response_type == "passthrough":
            # Not an automation conversation, let agent handle it
            return None

        elif response_type == "clarify":
            # Return the clarification question
            question = result.get("question", "Could you tell me more?")
            return question

        elif response_type == "confirm":
            # Return the confirmation prompt
            confirmation = result.get("confirmation", "Should I create this automation?")
            return confirmation

        elif response_type == "success":
            # Automation created successfully
            message = result.get("message", "Automation created.")
            return message

        elif response_type == "cancel":
            # User cancelled
            message = result.get("message", "Cancelled.")
            return message

        elif response_type == "error":
            # Error occurred
            message = result.get("message", "Something went wrong.")
            return message

        # Unknown type, fall through to agent
        return None

    def _execute_with_timeout(self, text: str) -> str:
        """
        Execute agent callback with timeout protection.

        Args:
            text: Command text to process

        Returns:
            Agent response string

        Raises:
            TimeoutError: If agent doesn't respond in time
            Exception: Any exception from agent
        """
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self.agent_callback, text)
            try:
                return future.result(timeout=self.timeout_seconds)
            except concurrent.futures.TimeoutError:
                logger.warning(f"Agent timeout after {self.timeout_seconds}s")
                raise TimeoutError(f"Agent did not respond within {self.timeout_seconds} seconds")

    def parse_request(self, payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """
        Parse Home Assistant conversation webhook payload.

        Args:
            payload: JSON payload from HA conversation webhook

        Returns:
            Tuple of (command_text, context_dict)

        Raises:
            ValueError: If required 'text' field is missing
        """
        if "text" not in payload:
            raise ValueError("Missing required 'text' field in request")

        text = payload["text"]

        # Extract context from HA payload
        context = {}

        if "device_id" in payload:
            context["device_id"] = payload["device_id"]

        if "language" in payload:
            context["language"] = payload["language"]

        if "conversation_id" in payload:
            context["conversation_id"] = payload["conversation_id"]

        if "source" in payload:
            context["source"] = payload["source"]

        return text, context

    def handle_webhook(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Handle a complete webhook request from HA.

        Convenience method that parses and processes in one call.

        Args:
            payload: JSON payload from HA conversation webhook

        Returns:
            Response dict with success status and response/error
        """
        try:
            text, context = self.parse_request(payload)
            return self.process_command(text, context)
        except ValueError as error:
            logger.warning(f"Invalid webhook request: {error}")
            return {"success": False, "error": str(error)}
