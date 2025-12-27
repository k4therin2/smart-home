"""
Smart Home Assistant - LLM Client Abstraction Layer

Provides a provider-agnostic interface for LLM calls.
Supports OpenAI, Anthropic, and local LLMs (Ollama, LM Studio, etc.).

To switch providers, update LLM_PROVIDER in .env:
- "openai" - OpenAI API (gpt-4o-mini, gpt-4o, etc.)
- "anthropic" - Anthropic API (claude-sonnet-4, etc.)
- "local" - Local LLM via OpenAI-compatible API (Ollama, LM Studio, vLLM)
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass


logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Standardized LLM response."""

    content: str
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""


class LLMClient:
    """
    Provider-agnostic LLM client.

    Supports:
    - OpenAI (default)
    - Anthropic
    - Local LLMs via OpenAI-compatible API
    """

    def __init__(self):
        from src.config import OPENAI_API_KEY, OPENAI_MODEL

        self.provider = os.getenv("LLM_PROVIDER", "openai").lower()
        self.model = os.getenv("LLM_MODEL", OPENAI_MODEL)
        self.api_key = os.getenv("LLM_API_KEY") or OPENAI_API_KEY
        self.base_url = os.getenv("LLM_BASE_URL")  # For local LLMs

        self._client = None

    def _get_client(self):
        """Get or create the appropriate client."""
        if self._client is not None:
            return self._client

        if self.provider == "openai" or self.provider == "local":
            import openai

            if self.base_url:
                # Local LLM with OpenAI-compatible API
                self._client = openai.OpenAI(
                    api_key=self.api_key or "not-needed", base_url=self.base_url
                )
            else:
                self._client = openai.OpenAI(api_key=self.api_key)

        elif self.provider == "anthropic":
            import anthropic

            self._client = anthropic.Anthropic(api_key=self.api_key)

        else:
            raise ValueError(f"Unknown LLM provider: {self.provider}")

        return self._client

    def complete(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """
        Generate a completion.

        Args:
            prompt: User message/prompt
            system_prompt: System message (optional)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            LLMResponse with content and usage stats
        """
        client = self._get_client()

        if self.provider == "anthropic":
            return self._complete_anthropic(client, prompt, system_prompt, max_tokens, temperature)
        else:
            # OpenAI and local LLMs use the same API
            return self._complete_openai(client, prompt, system_prompt, max_tokens, temperature)

    def _complete_openai(
        self,
        client,
        prompt: str,
        system_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        """Complete using OpenAI-compatible API."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=messages,
        )

        return LLMResponse(
            content=response.choices[0].message.content or "",
            input_tokens=getattr(response.usage, "prompt_tokens", 0),
            output_tokens=getattr(response.usage, "completion_tokens", 0),
            model=self.model,
        )

    def _complete_anthropic(
        self,
        client,
        prompt: str,
        system_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        """Complete using Anthropic API."""
        response = client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt if system_prompt else None,
            messages=[{"role": "user", "content": prompt}],
        )

        return LLMResponse(
            content=response.content[0].text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            model=self.model,
        )

    def complete_with_tools(
        self,
        prompt: str,
        tools: list[dict],
        system_prompt: str = "",
        max_tokens: int = 1024,
    ) -> tuple[str | None, list[dict]]:
        """
        Generate a completion with tool calling.

        Args:
            prompt: User message
            tools: List of tool definitions (Anthropic format)
            system_prompt: System message
            max_tokens: Maximum tokens

        Returns:
            Tuple of (text_response, tool_calls)
            tool_calls is list of {"name": str, "arguments": dict, "id": str}
        """
        client = self._get_client()

        if self.provider == "anthropic":
            return self._complete_with_tools_anthropic(
                client, prompt, tools, system_prompt, max_tokens
            )
        else:
            return self._complete_with_tools_openai(
                client, prompt, tools, system_prompt, max_tokens
            )

    def _complete_with_tools_openai(
        self,
        client,
        prompt: str,
        tools: list[dict],
        system_prompt: str,
        max_tokens: int,
    ) -> tuple[str | None, list[dict]]:
        """Complete with tools using OpenAI API."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Convert Anthropic tool format to OpenAI
        openai_tools = []
        for tool in tools:
            openai_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool["description"],
                        "parameters": tool["input_schema"],
                    },
                }
            )

        response = client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=messages,
            tools=openai_tools if openai_tools else None,
            tool_choice="auto" if openai_tools else None,
        )

        message = response.choices[0].message
        text_response = message.content

        tool_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append(
                    {
                        "name": tc.function.name,
                        "arguments": json.loads(tc.function.arguments),
                        "id": tc.id,
                    }
                )

        return text_response, tool_calls

    def _complete_with_tools_anthropic(
        self,
        client,
        prompt: str,
        tools: list[dict],
        system_prompt: str,
        max_tokens: int,
    ) -> tuple[str | None, list[dict]]:
        """Complete with tools using Anthropic API."""
        response = client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system_prompt if system_prompt else None,
            tools=tools,
            messages=[{"role": "user", "content": prompt}],
        )

        text_response = None
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                text_response = block.text
            elif block.type == "tool_use":
                tool_calls.append(
                    {
                        "name": block.name,
                        "arguments": block.input,
                        "id": block.id,
                    }
                )

        return text_response, tool_calls


# Singleton instance
_llm_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """Get the singleton LLMClient instance."""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
