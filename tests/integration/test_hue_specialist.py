"""
Integration tests for Hue Specialist Agent.

Test Strategy:
- Test real hue_specialist.py logic (no internal mocking)
- Mock OpenAI API at boundary (external service)
- Test fallback logic without API key
- Test JSON parsing from various LLM response formats
- Verify preset and scene mapping lookups

Following project testing philosophy:
- Integration tests over unit tests
- Mock at boundaries only (OpenAI API)
- Test real code paths users execute
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from tools.hue_specialist import (
    interpret_vibe_request,
    get_scene_suggestions,
    list_available_effects,
)


# =============================================================================
# Helper to create OpenAI mock response
# =============================================================================

def create_openai_mock_response(text: str, prompt_tokens: int = 150, completion_tokens: int = 40):
    """Create a properly structured OpenAI mock response."""
    mock_message = MagicMock()
    mock_message.content = text

    mock_choice = MagicMock()
    mock_choice.message = mock_message

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage = MagicMock(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)

    return mock_response


# =============================================================================
# Vibe Interpretation Tests - Preset Matching
# =============================================================================

def test_interpret_vibe_preset_exact_match():
    """Test exact vibe preset match returns preset settings."""
    result = interpret_vibe_request("cozy")

    assert result["type"] == "basic"
    assert result["brightness"] == 40
    assert result["color_temp_kelvin"] == 2700
    assert result["source"] == "preset"


def test_interpret_vibe_scene_keyword_match():
    """Test scene keyword match returns scene settings."""
    result = interpret_vibe_request("fire")

    assert result["type"] == "scene"
    assert result["scene_name"] == "savanna_sunset"
    assert result["dynamic"] is True
    assert result["speed"] == 30
    assert result["brightness"] == 60
    assert result["source"] == "scene_mapping"


# =============================================================================
# Vibe Interpretation Tests - LLM Interpretation
# =============================================================================

def test_interpret_vibe_llm_basic(mock_openai):
    """Test LLM interpretation for non-preset requests."""
    # Mock LLM response with JSON (OpenAI format)
    mock_response = create_openai_mock_response(
        '{"type": "basic", "brightness": 65, "color_temp_kelvin": 3200}'
    )
    mock_openai.chat.completions.create.return_value = mock_response

    with patch("tools.hue_specialist.openai.OpenAI", return_value=mock_openai):
        result = interpret_vibe_request("study time with natural light")

    assert result["type"] == "basic"
    assert result["brightness"] == 65
    assert result["color_temp_kelvin"] == 3200
    assert result["source"] == "llm"

    # Verify API was called
    mock_openai.chat.completions.create.assert_called_once()


def test_interpret_vibe_llm_json_extraction(mock_openai):
    """Test JSON extraction from LLM response with surrounding text."""
    # Mock LLM response with text + JSON
    mock_response = create_openai_mock_response(
        'Here is my interpretation:\n{"type": "scene", "scene_name": "arctic_aurora", "dynamic": true, "speed": 50, "brightness": 60}\nThis should work well.'
    )
    mock_openai.chat.completions.create.return_value = mock_response

    with patch("tools.hue_specialist.openai.OpenAI", return_value=mock_openai):
        # Use a description that won't match scene keywords
        result = interpret_vibe_request("arctic mystical vibe")

    assert result["type"] == "scene"
    assert result["scene_name"] == "arctic_aurora"
    assert result["dynamic"] is True
    assert result["speed"] == 50
    assert result["brightness"] == 60
    assert result["source"] == "llm"


def test_interpret_vibe_llm_with_markdown_code_block(mock_openai):
    """Test JSON extraction from markdown code block."""
    # Mock LLM response with markdown code block
    mock_response = create_openai_mock_response(
        '```json\n{"type": "basic", "brightness": 55, "color_temp_kelvin": 2800}\n```'
    )
    mock_openai.chat.completions.create.return_value = mock_response

    with patch("tools.hue_specialist.openai.OpenAI", return_value=mock_openai):
        result = interpret_vibe_request("warm afternoon glow")

    assert result["type"] == "basic"
    assert result["brightness"] == 55
    assert result["color_temp_kelvin"] == 2800
    assert result["source"] == "llm"


# =============================================================================
# Fallback Logic Tests
# =============================================================================

def test_interpret_vibe_fallback_warm_keywords():
    """Test fallback interpretation for warm keywords."""
    with patch("tools.hue_specialist.OPENAI_API_KEY", None):
        result = interpret_vibe_request("warm and comfortable")

    assert result["type"] == "basic"
    assert result["brightness"] == 45
    assert result["color_temp_kelvin"] == 2700
    assert result["source"] == "fallback"


def test_interpret_vibe_fallback_cool_keywords():
    """Test fallback interpretation for cool/focus keywords."""
    with patch("tools.hue_specialist.OPENAI_API_KEY", None):
        result = interpret_vibe_request("bright and focused")

    assert result["type"] == "basic"
    assert result["brightness"] == 80
    assert result["color_temp_kelvin"] == 4500
    assert result["source"] == "fallback"


def test_interpret_vibe_fallback_dim_keywords():
    """Test fallback interpretation for dim/night keywords."""
    with patch("tools.hue_specialist.OPENAI_API_KEY", None):
        result = interpret_vibe_request("dim for movie night")

    assert result["type"] == "basic"
    assert result["brightness"] == 20
    assert result["color_temp_kelvin"] == 2200
    assert result["source"] == "fallback"


def test_interpret_vibe_no_api_key_uses_fallback(monkeypatch):
    """Test that missing API key triggers fallback logic."""
    # Patch the OPENAI_API_KEY in the module directly
    with patch("tools.hue_specialist.OPENAI_API_KEY", None):
        result = interpret_vibe_request("make it relaxing")

    # Should use fallback (relax contains "relax" keyword)
    assert result["type"] == "basic"
    assert result["source"] == "fallback"
    assert result["brightness"] == 45
    assert result["color_temp_kelvin"] == 2700


# =============================================================================
# Scene Suggestion Tests
# =============================================================================

def test_get_scene_suggestions():
    """Test scene suggestions based on keywords."""
    suggestions = get_scene_suggestions(["fire", "ocean", "party"])

    assert len(suggestions) == 3

    # Check fire suggestion
    fire_suggestion = next(s for s in suggestions if s["match_keyword"] == "fire")
    assert fire_suggestion["scene_name"] == "savanna_sunset"
    assert "settings" in fire_suggestion
    assert fire_suggestion["settings"]["dynamic"] is True

    # Check ocean suggestion
    ocean_suggestion = next(s for s in suggestions if s["match_keyword"] == "ocean")
    assert ocean_suggestion["scene_name"] == "tropical_twilight"

    # Check party suggestion
    party_suggestion = next(s for s in suggestions if s["match_keyword"] == "party")
    assert party_suggestion["scene_name"] == "tokyo"


# =============================================================================
# Available Effects Tests
# =============================================================================

def test_list_available_effects():
    """Test listing all available effects and scenes."""
    effects = list_available_effects()

    assert "vibe_presets" in effects
    assert "scene_keywords" in effects
    assert "hue_scenes" in effects

    # Check vibe presets
    assert "cozy" in effects["vibe_presets"]
    assert "focus" in effects["vibe_presets"]
    assert "romantic" in effects["vibe_presets"]

    # Check scene keywords
    assert "fire" in effects["scene_keywords"]
    assert "ocean" in effects["scene_keywords"]
    assert "aurora" in effects["scene_keywords"]

    # Check Hue scenes
    assert "arctic_aurora" in effects["hue_scenes"]
    assert "tropical_twilight" in effects["hue_scenes"]
    assert "savanna_sunset" in effects["hue_scenes"]

    # Verify descriptions exist
    assert effects["hue_scenes"]["arctic_aurora"]  # Should have description
    assert "northern lights" in effects["hue_scenes"]["arctic_aurora"].lower()
