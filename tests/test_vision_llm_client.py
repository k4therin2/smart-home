"""
Tests for Vision LLM Client Module - Camera Vision Intelligence

WP-11.4: LLaVA Integration via home-llm API

Tests the VisionLLMClient that calls home-llm API for camera image descriptions.
Uses mocked API responses to test behavior without requiring actual LLM server.

Note: This tests the VisionLLMClient class for LLaVA vision model integration,
which is separate from the existing LLMClient for text completions.
"""

import base64
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests

# Import will fail until module is created - this is TDD
# from src.vision_llm_client import (
#     VisionLLMClient,
#     VisionVisionLLMClientError,
#     describe_image,
#     is_llm_available,
# )


# =============================================================================
# Test Configuration
# =============================================================================

HOME_LLM_URL = "http://100.75.232.36:11434/v1/chat/completions"
VISION_MODEL = "llava:7b"
TEXT_MODEL = "llama3"

# Sample base64 encoded 1x1 red pixel JPEG for testing
SAMPLE_IMAGE_B64 = "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAn/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBEQCEAPABAD//xAAfEQABBAIDAQEAAAAAAAAAAAABAAIDBAUREiExE2H/2gAMAwEAAhEDEQA/ALRERf/Z"


@pytest.fixture
def mock_successful_response():
    """Create a mock successful API response."""
    return {
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "created": 1234567890,
        "model": "llava:7b",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "I see a living room with a person sitting on a couch. There's a cat on the floor nearby."
                },
                "finish_reason": "stop"
            }
        ]
    }


@pytest.fixture
def mock_error_response():
    """Create a mock error response."""
    response = Mock()
    response.status_code = 500
    response.raise_for_status.side_effect = requests.exceptions.HTTPError("Internal Server Error")
    return response


@pytest.fixture
def sample_image_bytes():
    """Create sample image bytes for testing."""
    return base64.b64decode(SAMPLE_IMAGE_B64)


@pytest.fixture
def temp_image_file(tmp_path, sample_image_bytes):
    """Create a temporary image file for testing."""
    image_path = tmp_path / "test_snapshot.jpg"
    image_path.write_bytes(sample_image_bytes)
    return image_path


# =============================================================================
# Test VisionLLMClient Class
# =============================================================================


class TestVisionLLMClientInit:
    """Test VisionLLMClient initialization."""

    def test_default_initialization(self):
        """Test client initializes with default settings."""
        from src.vision_llm_client import VisionLLMClient

        client = VisionLLMClient()

        assert client.base_url == "http://100.75.232.36:11434/v1/chat/completions"
        assert client.vision_model == "llava:7b"
        assert client.text_model == "llama3"
        assert client.timeout == 60

    def test_custom_initialization(self):
        """Test client initializes with custom settings."""
        from src.vision_llm_client import VisionLLMClient

        client = VisionLLMClient(
            base_url="http://localhost:11434/v1/chat/completions",
            vision_model="llava:13b",
            text_model="llama2",
            timeout=120
        )

        assert client.base_url == "http://localhost:11434/v1/chat/completions"
        assert client.vision_model == "llava:13b"
        assert client.text_model == "llama2"
        assert client.timeout == 120


class TestVisionLLMClientDescribeImage:
    """Test image description functionality."""

    @patch('requests.post')
    def test_describe_image_success(self, mock_post, mock_successful_response, temp_image_file):
        """Test successful image description."""
        from src.vision_llm_client import VisionLLMClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_successful_response
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        client = VisionLLMClient()
        description = client.describe_image(str(temp_image_file))

        assert description is not None
        assert "living room" in description.lower()
        assert "person" in description.lower() or "cat" in description.lower()

    @patch('requests.post')
    def test_describe_image_with_custom_prompt(self, mock_post, mock_successful_response, temp_image_file):
        """Test image description with custom prompt."""
        from src.vision_llm_client import VisionLLMClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_successful_response
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        client = VisionLLMClient()
        description = client.describe_image(
            str(temp_image_file),
            prompt="Count the number of people visible in this image."
        )

        assert description is not None
        # Verify custom prompt was sent
        call_args = mock_post.call_args
        payload = call_args.kwargs['json']
        assert "Count the number" in payload['messages'][0]['content'][0]['text']

    @patch('requests.post')
    def test_describe_image_timeout(self, mock_post, temp_image_file):
        """Test image description handles timeout."""
        from src.vision_llm_client import VisionLLMClient, VisionLLMClientError

        mock_post.side_effect = requests.exceptions.Timeout("Request timed out")

        client = VisionLLMClient()

        with pytest.raises(VisionLLMClientError) as excinfo:
            client.describe_image(str(temp_image_file))

        assert "timeout" in str(excinfo.value).lower() or "timed out" in str(excinfo.value).lower()

    @patch('requests.post')
    def test_describe_image_connection_error(self, mock_post, temp_image_file):
        """Test image description handles connection error."""
        from src.vision_llm_client import VisionLLMClient, VisionLLMClientError

        mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")

        client = VisionLLMClient()

        with pytest.raises(VisionLLMClientError) as excinfo:
            client.describe_image(str(temp_image_file))

        assert "connection" in str(excinfo.value).lower()

    @patch('requests.post')
    def test_describe_image_http_error(self, mock_post, mock_error_response, temp_image_file):
        """Test image description handles HTTP errors."""
        from src.vision_llm_client import VisionLLMClient, VisionLLMClientError

        mock_post.return_value = mock_error_response

        client = VisionLLMClient()

        with pytest.raises(VisionLLMClientError):
            client.describe_image(str(temp_image_file))

    def test_describe_image_file_not_found(self):
        """Test error when image file doesn't exist."""
        from src.vision_llm_client import VisionLLMClient, VisionLLMClientError

        client = VisionLLMClient()

        with pytest.raises(VisionLLMClientError) as excinfo:
            client.describe_image("/nonexistent/path/image.jpg")

        assert "not found" in str(excinfo.value).lower() or "does not exist" in str(excinfo.value).lower()

    @patch('requests.post')
    def test_describe_image_bytes(self, mock_post, mock_successful_response, sample_image_bytes):
        """Test describing image from raw bytes."""
        from src.vision_llm_client import VisionLLMClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_successful_response
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        client = VisionLLMClient()
        description = client.describe_image_bytes(sample_image_bytes)

        assert description is not None


class TestVisionLLMClientHealthCheck:
    """Test LLM client health check functionality."""

    @patch('requests.get')
    def test_is_available_when_healthy(self, mock_get):
        """Test health check when server is healthy."""
        from src.vision_llm_client import VisionLLMClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"id": "llava:7b"}, {"id": "llama3"}]}
        mock_get.return_value = mock_response

        client = VisionLLMClient()
        assert client.is_available() is True

    @patch('requests.get')
    def test_is_available_when_down(self, mock_get):
        """Test health check when server is down."""
        from src.vision_llm_client import VisionLLMClient

        mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")

        client = VisionLLMClient()
        assert client.is_available() is False

    @patch('requests.get')
    def test_is_available_timeout(self, mock_get):
        """Test health check timeout."""
        from src.vision_llm_client import VisionLLMClient

        mock_get.side_effect = requests.exceptions.Timeout("Request timed out")

        client = VisionLLMClient()
        assert client.is_available() is False


class TestVisionLLMClientTextGeneration:
    """Test text generation functionality."""

    @patch('requests.post')
    def test_generate_text_success(self, mock_post):
        """Test successful text generation."""
        from src.vision_llm_client import VisionLLMClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-123",
            "choices": [{"message": {"content": "Hello! How can I help you?"}}]
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        client = VisionLLMClient()
        result = client.generate_text("Hello!")

        assert result == "Hello! How can I help you?"

    @patch('requests.post')
    def test_generate_text_with_system_prompt(self, mock_post):
        """Test text generation with system prompt."""
        from src.vision_llm_client import VisionLLMClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-123",
            "choices": [{"message": {"content": "I am a helpful assistant."}}]
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        client = VisionLLMClient()
        result = client.generate_text(
            "Who are you?",
            system_prompt="You are a helpful assistant."
        )

        # Verify system prompt was included
        call_args = mock_post.call_args
        payload = call_args.kwargs['json']
        messages = payload['messages']
        assert any(m['role'] == 'system' for m in messages)


class TestVisionLLMClientRetry:
    """Test retry logic."""

    @patch('requests.post')
    def test_retry_on_timeout(self, mock_post, mock_successful_response, temp_image_file):
        """Test that client retries on timeout."""
        from src.vision_llm_client import VisionLLMClient

        # First call times out, second succeeds
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_successful_response
        mock_response.raise_for_status.return_value = None

        mock_post.side_effect = [
            requests.exceptions.Timeout("timeout"),
            mock_response
        ]

        client = VisionLLMClient(max_retries=2)
        description = client.describe_image(str(temp_image_file))

        assert description is not None
        assert mock_post.call_count == 2

    @patch('requests.post')
    def test_no_retry_on_client_error(self, mock_post, temp_image_file):
        """Test that client doesn't retry on 4xx errors."""
        from src.vision_llm_client import VisionLLMClient, VisionLLMClientError

        mock_response = Mock()
        mock_response.status_code = 400

        # Create HTTPError with response attribute properly set
        http_error = requests.exceptions.HTTPError("Bad Request")
        http_error.response = mock_response
        mock_response.raise_for_status.side_effect = http_error
        mock_post.return_value = mock_response

        client = VisionLLMClient(max_retries=3)

        with pytest.raises(VisionLLMClientError):
            client.describe_image(str(temp_image_file))

        # Should only try once for client errors
        assert mock_post.call_count == 1


# =============================================================================
# Test Convenience Functions
# =============================================================================


class TestConvenienceFunctions:
    """Test module-level convenience functions."""

    @patch('requests.post')
    def test_describe_image_function(self, mock_post, mock_successful_response, temp_image_file):
        """Test the describe_image convenience function."""
        from src.vision_llm_client import describe_image

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_successful_response
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        description = describe_image(str(temp_image_file))

        assert description is not None

    @patch('requests.get')
    def test_is_llm_available_function(self, mock_get):
        """Test the is_llm_available convenience function."""
        from src.vision_llm_client import is_llm_available

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}
        mock_get.return_value = mock_response

        assert is_llm_available() is True


# =============================================================================
# Integration-Style Tests (with mocked API)
# =============================================================================


class TestCameraIntegration:
    """Test integration with camera observation system."""

    @patch('requests.post')
    def test_describe_and_store_observation(self, mock_post, mock_successful_response, temp_image_file, tmp_path):
        """Test describing an image and storing the result."""
        from src.vision_llm_client import VisionLLMClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_successful_response
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        client = VisionLLMClient()
        description = client.describe_image(str(temp_image_file))

        # Verify we can use the description with camera_store
        assert isinstance(description, str)
        assert len(description) > 10  # Reasonable description length

    @patch('requests.post')
    def test_batch_description(self, mock_post, mock_successful_response, temp_image_file):
        """Test describing multiple images."""
        from src.vision_llm_client import VisionLLMClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_successful_response
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        client = VisionLLMClient()
        images = [str(temp_image_file)] * 3
        descriptions = [client.describe_image(img) for img in images]

        assert len(descriptions) == 3
        assert all(d is not None for d in descriptions)


class TestPerformance:
    """Test performance characteristics."""

    @patch('requests.post')
    def test_timeout_configuration(self, mock_post, temp_image_file):
        """Test that timeout is properly configured."""
        from src.vision_llm_client import VisionLLMClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"choices": [{"message": {"content": "test"}}]}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        client = VisionLLMClient(timeout=30)
        client.describe_image(str(temp_image_file))

        # Verify timeout was passed to requests
        call_args = mock_post.call_args
        assert call_args.kwargs.get('timeout') == 30


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
