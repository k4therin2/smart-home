"""
Smart Home Assistant - Vision LLM Client for home-llm API

WP-11.4: LLaVA Integration via home-llm API

Provides a client for calling the home-llm Ollama API to get image descriptions
from LLaVA vision model. Used by camera observation system for snapshot analysis.

This module is separate from llm_client.py which handles text completions
via OpenAI/Anthropic APIs.
"""

from __future__ import annotations

import base64
import logging
import time
from pathlib import Path
from typing import Any

import requests


logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

# Default home-llm API endpoint (Ollama on colby via Tailscale)
DEFAULT_BASE_URL = "http://100.75.232.36:11434/v1/chat/completions"
DEFAULT_VISION_MODEL = "llava:7b"
DEFAULT_TEXT_MODEL = "llama3"
DEFAULT_TIMEOUT = 60
DEFAULT_MAX_RETRIES = 3

# Default prompt for image description
DEFAULT_IMAGE_PROMPT = (
    "Describe what you see in this image. "
    "Focus on people, objects, and any notable activity. "
    "Be concise but thorough."
)


# =============================================================================
# Exceptions
# =============================================================================


class VisionLLMClientError(Exception):
    """Base exception for Vision LLM client errors."""

    pass


# =============================================================================
# VisionLLMClient
# =============================================================================


class VisionLLMClient:
    """
    Client for home-llm API with LLaVA vision model support.

    Provides image description capabilities using LLaVA and text generation
    using llama3 via the Ollama OpenAI-compatible API.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        vision_model: str = DEFAULT_VISION_MODEL,
        text_model: str = DEFAULT_TEXT_MODEL,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ):
        """
        Initialize the Vision LLM client.

        Args:
            base_url: Ollama OpenAI-compatible API endpoint
            vision_model: Vision model to use (e.g., llava:7b)
            text_model: Text model to use (e.g., llama3)
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts for transient errors
        """
        self.base_url = base_url
        self.vision_model = vision_model
        self.text_model = text_model
        self.timeout = timeout
        self.max_retries = max_retries

    # =========================================================================
    # Image Description Methods
    # =========================================================================

    def describe_image(
        self,
        image_path: str,
        prompt: str = DEFAULT_IMAGE_PROMPT,
    ) -> str:
        """
        Describe an image using LLaVA vision model.

        Args:
            image_path: Path to the image file
            prompt: Custom prompt for image description

        Returns:
            Description of the image

        Raises:
            VisionLLMClientError: If image cannot be read or API call fails
        """
        # Read image file
        path = Path(image_path)
        if not path.exists():
            raise VisionLLMClientError(f"Image file not found: {image_path}")

        try:
            image_bytes = path.read_bytes()
        except IOError as error:
            raise VisionLLMClientError(f"Failed to read image: {error}") from error

        return self.describe_image_bytes(image_bytes, prompt)

    def describe_image_bytes(
        self,
        image_data: bytes,
        prompt: str = DEFAULT_IMAGE_PROMPT,
    ) -> str:
        """
        Describe an image from raw bytes using LLaVA vision model.

        Args:
            image_data: Raw image bytes
            prompt: Custom prompt for image description

        Returns:
            Description of the image

        Raises:
            VisionLLMClientError: If API call fails
        """
        # Encode image to base64
        image_b64 = base64.b64encode(image_data).decode("utf-8")

        # Build request payload (OpenAI vision format)
        payload = {
            "model": self.vision_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_b64}"
                            },
                        },
                    ],
                }
            ],
        }

        response = self._make_request(payload)
        return self._extract_content(response)

    # =========================================================================
    # Text Generation Methods
    # =========================================================================

    def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> str:
        """
        Generate text using the text model.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt

        Returns:
            Generated text

        Raises:
            VisionLLMClientError: If API call fails
        """
        messages: list[dict[str, Any]] = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.text_model,
            "messages": messages,
        }

        response = self._make_request(payload)
        return self._extract_content(response)

    # =========================================================================
    # Health Check Methods
    # =========================================================================

    def is_available(self) -> bool:
        """
        Check if the LLM server is available.

        Returns:
            True if server is reachable and responding
        """
        try:
            # Check models endpoint (Ollama-specific)
            models_url = self.base_url.replace(
                "/v1/chat/completions", "/v1/models"
            )
            response = requests.get(models_url, timeout=5)
            return response.status_code == 200
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            return False
        except Exception as error:
            logger.warning(f"Unexpected error checking LLM availability: {error}")
            return False

    # =========================================================================
    # Internal Methods
    # =========================================================================

    def _make_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Make a request to the LLM API with retry logic.

        Args:
            payload: Request payload

        Returns:
            Response JSON

        Raises:
            VisionLLMClientError: If request fails after retries
        """
        last_error: Exception | None = None

        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    self.base_url,
                    json=payload,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                return response.json()

            except requests.exceptions.Timeout as error:
                last_error = error
                logger.warning(
                    f"Request timed out (attempt {attempt + 1}/{self.max_retries})"
                )
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                continue

            except requests.exceptions.ConnectionError as error:
                last_error = error
                logger.warning(
                    f"Connection error (attempt {attempt + 1}/{self.max_retries})"
                )
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                continue

            except requests.exceptions.HTTPError as error:
                # Don't retry on client errors (4xx)
                if error.response is not None and 400 <= error.response.status_code < 500:
                    raise VisionLLMClientError(
                        f"API client error: {error}"
                    ) from error

                last_error = error
                logger.warning(
                    f"HTTP error (attempt {attempt + 1}/{self.max_retries}): {error}"
                )
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                continue

            except Exception as error:
                raise VisionLLMClientError(f"Unexpected error: {error}") from error

        # All retries exhausted
        if isinstance(last_error, requests.exceptions.Timeout):
            raise VisionLLMClientError(
                f"Request timed out after {self.max_retries} attempts"
            ) from last_error
        elif isinstance(last_error, requests.exceptions.ConnectionError):
            raise VisionLLMClientError(
                f"Connection error after {self.max_retries} attempts"
            ) from last_error
        else:
            raise VisionLLMClientError(
                f"Request failed after {self.max_retries} attempts: {last_error}"
            ) from last_error

    def _extract_content(self, response: dict[str, Any]) -> str:
        """
        Extract content from API response.

        Args:
            response: Response JSON

        Returns:
            Message content

        Raises:
            VisionLLMClientError: If response format is unexpected
        """
        try:
            choices = response.get("choices", [])
            if not choices:
                raise VisionLLMClientError("No choices in response")

            message = choices[0].get("message", {})
            content = message.get("content")

            if content is None:
                raise VisionLLMClientError("No content in response message")

            return content

        except KeyError as error:
            raise VisionLLMClientError(
                f"Unexpected response format: {error}"
            ) from error


# =============================================================================
# Module-Level Convenience Functions
# =============================================================================

_vision_client: VisionLLMClient | None = None


def get_vision_llm_client() -> VisionLLMClient:
    """Get or create the global VisionLLMClient instance."""
    global _vision_client
    if _vision_client is None:
        _vision_client = VisionLLMClient()
    return _vision_client


def describe_image(
    image_path: str,
    prompt: str = DEFAULT_IMAGE_PROMPT,
) -> str:
    """
    Describe an image using the default VisionLLMClient.

    Args:
        image_path: Path to the image file
        prompt: Custom prompt for image description

    Returns:
        Description of the image
    """
    return get_vision_llm_client().describe_image(image_path, prompt)


def is_llm_available() -> bool:
    """
    Check if the LLM server is available.

    Returns:
        True if server is reachable and responding
    """
    return get_vision_llm_client().is_available()
