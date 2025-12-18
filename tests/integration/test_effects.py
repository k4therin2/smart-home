"""
Integration tests for the effects module.

Test Strategy:
- Test real interactions between effects.py, hue_specialist.py, and ha_client
- Mock only at the boundary (Home Assistant API)
- Test vibe routing logic, scene selection, and error handling
- Test integration with VIBE_PRESETS and HUE_SCENE_MAPPINGS

Follows project guidelines:
- Integration tests over unit tests
- Mock at boundaries only (HA API)
- Test actual code paths users execute
"""

import json
from unittest.mock import MagicMock, patch

import pytest
import responses

from tools.effects import apply_vibe, get_vibe_preview, list_vibes
from tools.hue_specialist import HUE_SCENE_MAPPINGS
from src.config import VIBE_PRESETS, ROOM_ENTITY_MAP


# =============================================================================
# Vibe Application Tests
# =============================================================================

def test_apply_vibe_basic_light(mock_ha_full):
    """
    Test applying a vibe that maps to basic light settings.

    Tests:
    - Vibe preset matching (cozy -> basic light settings)
    - Integration with hue_specialist interpret_vibe_request
    - Integration with ha_client turn_on_light
    - Correct parameters passed to HA API
    """
    # "cozy" is a preset that maps to basic light settings
    result = apply_vibe(room="living_room", vibe_description="cozy")

    assert result["success"] is True
    assert result["type"] == "basic"
    assert result["room"] == "living_room"
    assert result["vibe"] == "cozy"
    assert result["entity_id"] == "light.living_room_2"  # Default light for living_room
    assert result["brightness"] == 40  # From VIBE_PRESETS
    assert result["color_temp_kelvin"] == 2700  # From VIBE_PRESETS
    assert result["source"] == "preset"


def test_apply_vibe_scene(mock_ha_full):
    """
    Test applying a vibe that maps to a Hue scene.

    Tests:
    - Scene keyword matching (fire -> savanna_sunset scene)
    - Integration with hue_specialist scene mapping
    - Integration with ha_client activate_hue_scene
    - Scene entity ID construction
    - Dynamic scene parameters
    """
    # "fire" should match HUE_SCENE_MAPPINGS and activate a scene
    result = apply_vibe(room="living_room", vibe_description="fire")

    assert result["success"] is True
    assert result["type"] == "scene"
    assert result["room"] == "living_room"
    assert result["vibe"] == "fire"
    assert result["scene_name"] == "savanna_sunset"
    assert result["scene_entity_id"] == "scene.living_room_savanna_sunset"
    assert result["dynamic"] is True
    assert result["speed"] == 30  # From HUE_SCENE_MAPPINGS
    assert result["brightness"] == 60  # From HUE_SCENE_MAPPINGS
    assert result["source"] == "scene_mapping"


def test_apply_vibe_unknown_room(mock_ha_full):
    """
    Test applying a vibe to an unknown room.

    Tests:
    - Room validation via get_room_entity
    - Error handling for unknown room
    - Helpful error response with available rooms
    """
    result = apply_vibe(room="nonexistent_room", vibe_description="cozy")

    assert result["success"] is False
    assert "error" in result
    assert "Unknown room" in result["error"]
    assert "available_rooms" in result
    assert isinstance(result["available_rooms"], list)
    assert "living_room" in result["available_rooms"]


def test_apply_vibe_error_handling(mock_ha_api):
    """
    Test error handling when HA API fails.

    Tests:
    - Exception handling in apply_vibe
    - Error response structure
    - Graceful failure
    """
    # Reset HA client singleton
    import src.ha_client as ha_module
    ha_module._client = None

    # Mock HA API with error response for turn_on
    mock_ha_api.add(
        responses.GET,
        "http://test-ha.local:8123/api/",
        json={"message": "API running."},
        status=200,
    )

    # Add POST endpoint that returns 500 error
    mock_ha_api.add(
        responses.POST,
        "http://test-ha.local:8123/api/services/light/turn_on",
        json={"error": "Internal server error"},
        status=500,
    )

    result = apply_vibe(room="living_room", vibe_description="cozy")

    assert result["success"] is False
    assert "error" in result
    assert result["room"] == "living_room"
    assert result["vibe"] == "cozy"

    # Clean up singleton
    ha_module._client = None


# =============================================================================
# Vibe Preview Tests
# =============================================================================

def test_get_vibe_preview():
    """
    Test getting a preview of vibe settings without executing.

    Tests:
    - Preview functionality for basic light vibes
    - Preview functionality for scene vibes
    - No actual HA API calls made
    - Integration with interpret_vibe_request
    """
    # Test basic vibe preview
    preview = get_vibe_preview("cozy")

    assert preview["vibe"] == "cozy"
    assert preview["type"] == "basic"
    assert preview["brightness"] == 40
    assert preview["color_temp_kelvin"] == 2700
    assert preview["source"] == "preset"

    # Test scene vibe preview
    scene_preview = get_vibe_preview("fire")

    assert scene_preview["vibe"] == "fire"
    assert scene_preview["type"] == "scene"
    assert scene_preview["scene_name"] == "savanna_sunset"
    assert scene_preview["dynamic"] is True
    assert scene_preview["speed"] == 30
    assert scene_preview["brightness"] == 60
    assert scene_preview["source"] == "scene_mapping"


# =============================================================================
# Vibe Listing Tests
# =============================================================================

def test_list_vibes():
    """
    Test listing all available vibes.

    Tests:
    - Returns preset vibes from VIBE_PRESETS
    - Returns scene keywords from HUE_SCENE_MAPPINGS
    - Returns example vibes
    - Integration with config module
    """
    vibes = list_vibes()

    assert "preset_vibes" in vibes
    assert "scene_keywords" in vibes
    assert "examples" in vibes

    # Check preset vibes are included
    assert "cozy" in vibes["preset_vibes"]
    assert "focus" in vibes["preset_vibes"]
    assert "romantic" in vibes["preset_vibes"]
    assert "movie" in vibes["preset_vibes"]

    # Check each preset has required fields
    for name, settings in vibes["preset_vibes"].items():
        assert "brightness" in settings
        assert "color_temp_kelvin" in settings

    # Check scene keywords are included
    assert "fire" in vibes["scene_keywords"]
    assert "ocean" in vibes["scene_keywords"]
    assert "aurora" in vibes["scene_keywords"]

    # Check examples are provided
    assert len(vibes["examples"]) > 0
    assert "cozy" in vibes["examples"]


# =============================================================================
# Scene Entity ID Construction Tests
# =============================================================================

def test_scene_entity_id_construction(mock_ha_full):
    """
    Test scene entity ID construction for different rooms.

    Tests:
    - Correct entity ID format (scene.{room}_{scene_name})
    - Room name normalization (spaces to underscores, lowercase)
    - Integration across multiple rooms
    """
    # Test living room
    result = apply_vibe(room="living_room", vibe_description="northern lights")
    assert result["scene_entity_id"] == "scene.living_room_arctic_aurora"

    # Test bedroom
    result = apply_vibe(room="bedroom", vibe_description="under the sea")
    assert result["scene_entity_id"] == "scene.bedroom_tropical_twilight"

    # Test kitchen
    result = apply_vibe(room="kitchen", vibe_description="sunset")
    assert result["scene_entity_id"] == "scene.kitchen_savanna_sunset"


# =============================================================================
# Additional Integration Tests
# =============================================================================

def test_apply_vibe_with_transition(mock_ha_full):
    """
    Test applying a vibe with custom transition time.

    Tests:
    - Transition parameter passing through the stack
    - Integration with ha_client transition parameter
    """
    result = apply_vibe(
        room="living_room",
        vibe_description="focus",
        transition=3.0
    )

    assert result["success"] is True
    assert result["type"] == "basic"
    # Note: We can't directly assert the transition was used without
    # inspecting the actual API call, but we verify no errors occurred


def test_apply_vibe_ocean_scene(mock_ha_full):
    """
    Test applying ocean-themed vibe.

    Tests:
    - Multiple keyword matching (ocean, under the sea, underwater)
    - Scene parameter variations
    """
    result = apply_vibe(room="bedroom", vibe_description="ocean vibes")

    assert result["success"] is True
    assert result["type"] == "scene"
    assert result["scene_name"] == "tropical_twilight"
    assert result["dynamic"] is True


def test_apply_vibe_fallback_interpretation(mock_ha_full, monkeypatch):
    """
    Test fallback interpretation when no preset or scene matches.

    Tests:
    - Fallback to LLM or keyword-based interpretation
    - Handling of complex vibe descriptions
    - Integration with hue_specialist fallback logic
    """
    # Remove API key to force fallback
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    import src.config as config_module
    config_module.ANTHROPIC_API_KEY = None

    # Test with a description that doesn't match presets or scenes
    # but has fallback keywords
    result = apply_vibe(room="living_room", vibe_description="warm and comfortable")

    assert result["success"] is True
    assert result["type"] == "basic"
    assert result["source"] == "fallback"
    # Fallback for warm keywords
    assert result["brightness"] == 45
    assert result["color_temp_kelvin"] == 2700


def test_vibe_preset_brightness_range(mock_ha_full):
    """
    Test that all vibe presets have valid brightness values.

    Tests:
    - Preset validation
    - Brightness range (0-100)
    - Color temperature range (2200-6500K)
    """
    for vibe_name in ["cozy", "focus", "romantic", "movie"]:
        result = apply_vibe(room="living_room", vibe_description=vibe_name)

        assert result["success"] is True
        assert 0 <= result["brightness"] <= 100
        assert 2200 <= result["color_temp_kelvin"] <= 6500
