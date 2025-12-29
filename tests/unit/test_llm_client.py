"""
Tests for src/llm_client.py - LLM Client Abstraction Layer

These tests cover the LLMClient class which provides provider-agnostic
interface for LLM calls supporting OpenAI, Anthropic, and local LLMs.
"""

import pytest
from unittest.mock import patch, Mock, MagicMock
from dataclasses import fields

from src.llm_client import (
    LLMClient,
    LLMResponse,
    get_llm_client,
)


# =============================================================================
# LLMResponse Tests
# =============================================================================


class TestLLMResponse:
    """Tests for the LLMResponse dataclass."""

    def test_response_creation(self):
        """Test creating an LLMResponse with all fields."""
        response = LLMResponse(
            content="Hello, world!",
            input_tokens=10,
            output_tokens=5,
            model="gpt-4o-mini"
        )

        assert response.content == "Hello, world!"
        assert response.input_tokens == 10
        assert response.output_tokens == 5
        assert response.model == "gpt-4o-mini"

    def test_response_defaults(self):
        """Test LLMResponse default values."""
        response = LLMResponse(content="Test")

        assert response.content == "Test"
        assert response.input_tokens == 0
        assert response.output_tokens == 0
        assert response.model == ""

    def test_response_is_dataclass(self):
        """Test that LLMResponse is a dataclass with correct fields."""
        field_names = [f.name for f in fields(LLMResponse)]
        assert "content" in field_names
        assert "input_tokens" in field_names
        assert "output_tokens" in field_names
        assert "model" in field_names


# =============================================================================
# LLMClient Initialization Tests
# =============================================================================


class TestLLMClientInit:
    """Tests for LLMClient initialization."""

    def test_init_defaults_to_openai(self):
        """Test that default provider is OpenAI."""
        with patch('src.llm_client.os.getenv') as mock_getenv:
            # When env var is not set, getenv returns the default ("openai")
            def mock_env(key, default=None):
                if key == 'LLM_PROVIDER':
                    return default  # Returns "openai" (the default)
                elif key == 'LLM_MODEL':
                    return default  # Will use OPENAI_MODEL from config
                elif key == 'LLM_API_KEY':
                    return None  # Will fallback to OPENAI_API_KEY
                return default

            mock_getenv.side_effect = mock_env

            with patch('src.config.OPENAI_API_KEY', 'test-key'):
                with patch('src.config.OPENAI_MODEL', 'gpt-4o-mini'):
                    client = LLMClient()
                    assert client.provider == "openai"

    def test_init_reads_env_vars(self):
        """Test that init reads environment variables."""
        with patch('src.llm_client.os.getenv') as mock_getenv:
            mock_getenv.side_effect = lambda key, default=None: {
                'LLM_PROVIDER': 'anthropic',
                'LLM_MODEL': 'claude-3-sonnet',
                'LLM_API_KEY': 'test-anthropic-key',
                'LLM_BASE_URL': None,
            }.get(key, default)

            with patch('src.config.OPENAI_API_KEY', 'fallback-key'):
                with patch('src.config.OPENAI_MODEL', 'fallback-model'):
                    client = LLMClient()

                    assert client.provider == "anthropic"
                    assert client.model == "claude-3-sonnet"
                    assert client.api_key == "test-anthropic-key"

    def test_init_uses_base_url_for_local(self):
        """Test that base_url is used for local LLM setups."""
        with patch('src.llm_client.os.getenv') as mock_getenv:
            mock_getenv.side_effect = lambda key, default=None: {
                'LLM_PROVIDER': 'local',
                'LLM_MODEL': 'llama3',
                'LLM_API_KEY': None,
                'LLM_BASE_URL': 'http://localhost:11434/v1',
            }.get(key, default)

            with patch('src.config.OPENAI_API_KEY', None):
                with patch('src.config.OPENAI_MODEL', 'default-model'):
                    client = LLMClient()

                    assert client.provider == "local"
                    assert client.base_url == "http://localhost:11434/v1"


# =============================================================================
# Provider Client Creation Tests
# =============================================================================


class TestGetClient:
    """Tests for _get_client method."""

    def test_get_client_openai(self):
        """Test creating OpenAI client."""
        with patch('src.llm_client.os.getenv') as mock_getenv:
            mock_getenv.side_effect = lambda key, default=None: {
                'LLM_PROVIDER': 'openai',
                'LLM_MODEL': 'gpt-4o-mini',
                'LLM_API_KEY': 'test-key',
                'LLM_BASE_URL': None,
            }.get(key, default)

            with patch('src.config.OPENAI_API_KEY', 'test-key'):
                with patch('src.config.OPENAI_MODEL', 'gpt-4o-mini'):
                    client = LLMClient()

                    with patch('openai.OpenAI') as mock_openai:
                        mock_openai.return_value = Mock()
                        result = client._get_client()

                        mock_openai.assert_called_once_with(api_key='test-key')
                        assert result is not None

    def test_get_client_local_with_base_url(self):
        """Test creating local client with custom base_url."""
        with patch('src.llm_client.os.getenv') as mock_getenv:
            mock_getenv.side_effect = lambda key, default=None: {
                'LLM_PROVIDER': 'local',
                'LLM_MODEL': 'llama3',
                'LLM_API_KEY': 'not-needed',
                'LLM_BASE_URL': 'http://localhost:11434/v1',
            }.get(key, default)

            with patch('src.config.OPENAI_API_KEY', None):
                with patch('src.config.OPENAI_MODEL', 'default'):
                    client = LLMClient()

                    with patch('openai.OpenAI') as mock_openai:
                        mock_openai.return_value = Mock()
                        client._get_client()

                        mock_openai.assert_called_once_with(
                            api_key='not-needed',
                            base_url='http://localhost:11434/v1'
                        )

    def test_get_client_anthropic(self):
        """Test creating Anthropic client."""
        with patch('src.llm_client.os.getenv') as mock_getenv:
            mock_getenv.side_effect = lambda key, default=None: {
                'LLM_PROVIDER': 'anthropic',
                'LLM_MODEL': 'claude-3-sonnet',
                'LLM_API_KEY': 'anthropic-key',
                'LLM_BASE_URL': None,
            }.get(key, default)

            with patch('src.config.OPENAI_API_KEY', None):
                with patch('src.config.OPENAI_MODEL', 'default'):
                    client = LLMClient()

                    with patch('anthropic.Anthropic') as mock_anthropic:
                        mock_anthropic.return_value = Mock()
                        result = client._get_client()

                        mock_anthropic.assert_called_once_with(api_key='anthropic-key')
                        assert result is not None

    def test_get_client_unknown_provider_raises(self):
        """Test that unknown provider raises ValueError."""
        with patch('src.llm_client.os.getenv') as mock_getenv:
            mock_getenv.side_effect = lambda key, default=None: {
                'LLM_PROVIDER': 'unknown_provider',
                'LLM_MODEL': 'model',
                'LLM_API_KEY': 'key',
                'LLM_BASE_URL': None,
            }.get(key, default)

            with patch('src.config.OPENAI_API_KEY', 'key'):
                with patch('src.config.OPENAI_MODEL', 'model'):
                    client = LLMClient()

                    with pytest.raises(ValueError, match="Unknown LLM provider"):
                        client._get_client()

    def test_get_client_caches_client(self):
        """Test that _get_client returns cached client."""
        with patch('src.llm_client.os.getenv') as mock_getenv:
            mock_getenv.side_effect = lambda key, default=None: {
                'LLM_PROVIDER': 'openai',
                'LLM_MODEL': 'model',
                'LLM_API_KEY': 'key',
                'LLM_BASE_URL': None,
            }.get(key, default)

            with patch('src.config.OPENAI_API_KEY', 'key'):
                with patch('src.config.OPENAI_MODEL', 'model'):
                    client = LLMClient()

                    with patch('openai.OpenAI') as mock_openai:
                        mock_client = Mock()
                        mock_openai.return_value = mock_client

                        result1 = client._get_client()
                        result2 = client._get_client()

                        # Should only create client once
                        mock_openai.assert_called_once()
                        assert result1 is result2


# =============================================================================
# Complete Method Tests (OpenAI)
# =============================================================================


class TestCompleteOpenAI:
    """Tests for complete method with OpenAI provider."""

    @pytest.fixture
    def openai_client(self):
        """Create an LLMClient configured for OpenAI."""
        with patch('src.llm_client.os.getenv') as mock_getenv:
            mock_getenv.side_effect = lambda key, default=None: {
                'LLM_PROVIDER': 'openai',
                'LLM_MODEL': 'gpt-4o-mini',
                'LLM_API_KEY': 'test-key',
                'LLM_BASE_URL': None,
            }.get(key, default)

            with patch('src.config.OPENAI_API_KEY', 'test-key'):
                with patch('src.config.OPENAI_MODEL', 'gpt-4o-mini'):
                    yield LLMClient()

    def test_complete_basic(self, openai_client):
        """Test basic completion."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Hello back!"
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5

        mock_openai = Mock()
        mock_openai.chat.completions.create.return_value = mock_response

        with patch.object(openai_client, '_get_client', return_value=mock_openai):
            result = openai_client.complete("Hello")

            assert isinstance(result, LLMResponse)
            assert result.content == "Hello back!"
            assert result.input_tokens == 10
            assert result.output_tokens == 5

    def test_complete_with_system_prompt(self, openai_client):
        """Test completion with system prompt."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Response"
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 20
        mock_response.usage.completion_tokens = 10

        mock_openai = Mock()
        mock_openai.chat.completions.create.return_value = mock_response

        with patch.object(openai_client, '_get_client', return_value=mock_openai):
            openai_client.complete("User message", system_prompt="You are a helpful assistant")

            call_kwargs = mock_openai.chat.completions.create.call_args.kwargs
            messages = call_kwargs['messages']

            assert len(messages) == 2
            assert messages[0]['role'] == 'system'
            assert messages[0]['content'] == 'You are a helpful assistant'
            assert messages[1]['role'] == 'user'

    def test_complete_with_parameters(self, openai_client):
        """Test completion with custom parameters."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Response"
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5

        mock_openai = Mock()
        mock_openai.chat.completions.create.return_value = mock_response

        with patch.object(openai_client, '_get_client', return_value=mock_openai):
            openai_client.complete(
                "Hello",
                max_tokens=500,
                temperature=0.5
            )

            call_kwargs = mock_openai.chat.completions.create.call_args.kwargs
            assert call_kwargs['max_tokens'] == 500
            assert call_kwargs['temperature'] == 0.5

    def test_complete_handles_none_content(self, openai_client):
        """Test completion handles None content gracefully."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = None
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 0

        mock_openai = Mock()
        mock_openai.chat.completions.create.return_value = mock_response

        with patch.object(openai_client, '_get_client', return_value=mock_openai):
            result = openai_client.complete("Hello")

            assert result.content == ""


# =============================================================================
# Complete Method Tests (Anthropic)
# =============================================================================


class TestCompleteAnthropic:
    """Tests for complete method with Anthropic provider."""

    @pytest.fixture
    def anthropic_client(self):
        """Create an LLMClient configured for Anthropic."""
        with patch('src.llm_client.os.getenv') as mock_getenv:
            mock_getenv.side_effect = lambda key, default=None: {
                'LLM_PROVIDER': 'anthropic',
                'LLM_MODEL': 'claude-3-sonnet',
                'LLM_API_KEY': 'anthropic-key',
                'LLM_BASE_URL': None,
            }.get(key, default)

            with patch('src.config.OPENAI_API_KEY', None):
                with patch('src.config.OPENAI_MODEL', 'default'):
                    yield LLMClient()

    def test_complete_anthropic(self, anthropic_client):
        """Test completion with Anthropic provider."""
        mock_response = Mock()
        mock_response.content = [Mock()]
        mock_response.content[0].text = "Hello from Claude!"
        mock_response.usage = Mock()
        mock_response.usage.input_tokens = 15
        mock_response.usage.output_tokens = 8

        mock_anthropic = Mock()
        mock_anthropic.messages.create.return_value = mock_response

        with patch.object(anthropic_client, '_get_client', return_value=mock_anthropic):
            result = anthropic_client.complete("Hello")

            assert result.content == "Hello from Claude!"
            assert result.input_tokens == 15
            assert result.output_tokens == 8

    def test_complete_anthropic_with_system(self, anthropic_client):
        """Test Anthropic completion with system prompt."""
        mock_response = Mock()
        mock_response.content = [Mock()]
        mock_response.content[0].text = "Response"
        mock_response.usage = Mock()
        mock_response.usage.input_tokens = 20
        mock_response.usage.output_tokens = 10

        mock_anthropic = Mock()
        mock_anthropic.messages.create.return_value = mock_response

        with patch.object(anthropic_client, '_get_client', return_value=mock_anthropic):
            anthropic_client.complete("User message", system_prompt="You are Claude")

            call_kwargs = mock_anthropic.messages.create.call_args.kwargs
            assert call_kwargs['system'] == "You are Claude"


# =============================================================================
# Complete With Tools Tests
# =============================================================================


class TestCompleteWithToolsOpenAI:
    """Tests for complete_with_tools method with OpenAI."""

    @pytest.fixture
    def openai_client(self):
        """Create an LLMClient configured for OpenAI."""
        with patch('src.llm_client.os.getenv') as mock_getenv:
            mock_getenv.side_effect = lambda key, default=None: {
                'LLM_PROVIDER': 'openai',
                'LLM_MODEL': 'gpt-4o-mini',
                'LLM_API_KEY': 'test-key',
                'LLM_BASE_URL': None,
            }.get(key, default)

            with patch('src.config.OPENAI_API_KEY', 'test-key'):
                with patch('src.config.OPENAI_MODEL', 'gpt-4o-mini'):
                    yield LLMClient()

    def test_complete_with_tools_no_tool_call(self, openai_client):
        """Test completion with tools when no tool is called."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Plain response"
        mock_response.choices[0].message.tool_calls = None

        mock_openai = Mock()
        mock_openai.chat.completions.create.return_value = mock_response

        tools = [
            {
                "name": "get_weather",
                "description": "Get weather info",
                "input_schema": {"type": "object", "properties": {}}
            }
        ]

        with patch.object(openai_client, '_get_client', return_value=mock_openai):
            text, tool_calls = openai_client.complete_with_tools("What's the weather?", tools)

            assert text == "Plain response"
            assert tool_calls == []

    def test_complete_with_tools_tool_called(self, openai_client):
        """Test completion with tools when a tool is called."""
        mock_tool_call = Mock()
        mock_tool_call.function.name = "get_weather"
        mock_tool_call.function.arguments = '{"location": "NYC"}'
        mock_tool_call.id = "call_123"

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = None
        mock_response.choices[0].message.tool_calls = [mock_tool_call]

        mock_openai = Mock()
        mock_openai.chat.completions.create.return_value = mock_response

        tools = [
            {
                "name": "get_weather",
                "description": "Get weather info",
                "input_schema": {"type": "object", "properties": {"location": {"type": "string"}}}
            }
        ]

        with patch.object(openai_client, '_get_client', return_value=mock_openai):
            text, tool_calls = openai_client.complete_with_tools("What's the weather in NYC?", tools)

            assert text is None
            assert len(tool_calls) == 1
            assert tool_calls[0]["name"] == "get_weather"
            assert tool_calls[0]["arguments"] == {"location": "NYC"}
            assert tool_calls[0]["id"] == "call_123"

    def test_complete_with_tools_converts_format(self, openai_client):
        """Test that Anthropic tool format is converted to OpenAI format."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Response"
        mock_response.choices[0].message.tool_calls = None

        mock_openai = Mock()
        mock_openai.chat.completions.create.return_value = mock_response

        tools = [
            {
                "name": "test_tool",
                "description": "A test tool",
                "input_schema": {"type": "object", "properties": {"param": {"type": "string"}}}
            }
        ]

        with patch.object(openai_client, '_get_client', return_value=mock_openai):
            openai_client.complete_with_tools("Test", tools)

            call_kwargs = mock_openai.chat.completions.create.call_args.kwargs
            openai_tools = call_kwargs['tools']

            assert len(openai_tools) == 1
            assert openai_tools[0]["type"] == "function"
            assert openai_tools[0]["function"]["name"] == "test_tool"
            assert openai_tools[0]["function"]["description"] == "A test tool"
            assert openai_tools[0]["function"]["parameters"]["type"] == "object"


class TestCompleteWithToolsAnthropic:
    """Tests for complete_with_tools method with Anthropic."""

    @pytest.fixture
    def anthropic_client(self):
        """Create an LLMClient configured for Anthropic."""
        with patch('src.llm_client.os.getenv') as mock_getenv:
            mock_getenv.side_effect = lambda key, default=None: {
                'LLM_PROVIDER': 'anthropic',
                'LLM_MODEL': 'claude-3-sonnet',
                'LLM_API_KEY': 'anthropic-key',
                'LLM_BASE_URL': None,
            }.get(key, default)

            with patch('src.config.OPENAI_API_KEY', None):
                with patch('src.config.OPENAI_MODEL', 'default'):
                    yield LLMClient()

    def test_complete_with_tools_anthropic_text_only(self, anthropic_client):
        """Test Anthropic completion with tools returning text only."""
        mock_text_block = Mock()
        mock_text_block.type = "text"
        mock_text_block.text = "Here's the information"

        mock_response = Mock()
        mock_response.content = [mock_text_block]

        mock_anthropic = Mock()
        mock_anthropic.messages.create.return_value = mock_response

        tools = [
            {
                "name": "test_tool",
                "description": "Test",
                "input_schema": {"type": "object"}
            }
        ]

        with patch.object(anthropic_client, '_get_client', return_value=mock_anthropic):
            text, tool_calls = anthropic_client.complete_with_tools("Test", tools)

            assert text == "Here's the information"
            assert tool_calls == []

    def test_complete_with_tools_anthropic_tool_use(self, anthropic_client):
        """Test Anthropic completion with tool use."""
        mock_tool_block = Mock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.name = "get_weather"
        mock_tool_block.input = {"location": "NYC"}
        mock_tool_block.id = "tool_use_123"

        mock_response = Mock()
        mock_response.content = [mock_tool_block]

        mock_anthropic = Mock()
        mock_anthropic.messages.create.return_value = mock_response

        tools = [
            {
                "name": "get_weather",
                "description": "Get weather",
                "input_schema": {"type": "object"}
            }
        ]

        with patch.object(anthropic_client, '_get_client', return_value=mock_anthropic):
            text, tool_calls = anthropic_client.complete_with_tools("What's the weather?", tools)

            assert text is None
            assert len(tool_calls) == 1
            assert tool_calls[0]["name"] == "get_weather"
            assert tool_calls[0]["arguments"] == {"location": "NYC"}
            assert tool_calls[0]["id"] == "tool_use_123"

    def test_complete_with_tools_anthropic_mixed_response(self, anthropic_client):
        """Test Anthropic completion with both text and tool use."""
        mock_text_block = Mock()
        mock_text_block.type = "text"
        mock_text_block.text = "Let me check that for you"

        mock_tool_block = Mock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.name = "search"
        mock_tool_block.input = {"query": "test"}
        mock_tool_block.id = "tool_456"

        mock_response = Mock()
        mock_response.content = [mock_text_block, mock_tool_block]

        mock_anthropic = Mock()
        mock_anthropic.messages.create.return_value = mock_response

        tools = [{"name": "search", "description": "Search", "input_schema": {}}]

        with patch.object(anthropic_client, '_get_client', return_value=mock_anthropic):
            text, tool_calls = anthropic_client.complete_with_tools("Search for test", tools)

            assert text == "Let me check that for you"
            assert len(tool_calls) == 1
            assert tool_calls[0]["name"] == "search"


# =============================================================================
# Singleton Tests
# =============================================================================


class TestGetLLMClient:
    """Tests for the get_llm_client singleton function."""

    def test_get_llm_client_creates_singleton(self):
        """Test that get_llm_client returns a singleton."""
        # Reset the singleton
        import src.llm_client as llm_module
        llm_module._llm_client = None

        with patch('src.llm_client.os.getenv') as mock_getenv:
            mock_getenv.side_effect = lambda key, default=None: {
                'LLM_PROVIDER': 'openai',
                'LLM_MODEL': 'test-model',
                'LLM_API_KEY': 'test-key',
                'LLM_BASE_URL': None,
            }.get(key, default)

            with patch('src.config.OPENAI_API_KEY', 'test-key'):
                with patch('src.config.OPENAI_MODEL', 'test-model'):
                    client1 = get_llm_client()
                    client2 = get_llm_client()

                    assert client1 is client2

    def test_get_llm_client_returns_llmclient(self):
        """Test that get_llm_client returns an LLMClient instance."""
        # Reset the singleton
        import src.llm_client as llm_module
        llm_module._llm_client = None

        with patch('src.llm_client.os.getenv') as mock_getenv:
            mock_getenv.side_effect = lambda key, default=None: {
                'LLM_PROVIDER': 'openai',
                'LLM_MODEL': 'model',
                'LLM_API_KEY': 'key',
                'LLM_BASE_URL': None,
            }.get(key, default)

            with patch('src.config.OPENAI_API_KEY', 'key'):
                with patch('src.config.OPENAI_MODEL', 'model'):
                    client = get_llm_client()

                    assert isinstance(client, LLMClient)
