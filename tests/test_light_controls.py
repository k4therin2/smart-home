"""
Tests for tools/lights.py - Light Control Tools

Tests light control tool functions including room ambiance setting,
color conversion, vibe presets, and scene activation.
"""

import pytest
import responses


class TestColorNameToRGB:
    """Test color name to RGB conversion."""

    def test_basic_colors(self):
        """Basic color names should convert correctly."""
        from tools.lights import COLOR_NAME_TO_RGB

        assert COLOR_NAME_TO_RGB["red"] == (255, 0, 0)
        assert COLOR_NAME_TO_RGB["green"] == (0, 255, 0)
        assert COLOR_NAME_TO_RGB["blue"] == (0, 0, 255)

    def test_secondary_colors(self):
        """Secondary colors should convert correctly."""
        from tools.lights import COLOR_NAME_TO_RGB

        assert COLOR_NAME_TO_RGB["yellow"] == (255, 255, 0)
        assert COLOR_NAME_TO_RGB["cyan"] == (0, 255, 255)
        assert COLOR_NAME_TO_RGB["magenta"] == (255, 0, 255)

    def test_named_colors(self):
        """Named colors (purple, orange, etc.) should exist."""
        from tools.lights import COLOR_NAME_TO_RGB

        assert "purple" in COLOR_NAME_TO_RGB
        assert "orange" in COLOR_NAME_TO_RGB
        assert "pink" in COLOR_NAME_TO_RGB
        assert "lavender" in COLOR_NAME_TO_RGB

    def test_color_values_in_range(self):
        """All RGB values should be 0-255."""
        from tools.lights import COLOR_NAME_TO_RGB

        for color_name, rgb in COLOR_NAME_TO_RGB.items():
            assert len(rgb) == 3, f"{color_name} should have 3 components"
            for component in rgb:
                assert 0 <= component <= 255, \
                    f"{color_name} has invalid component: {component}"


class TestListAvailableRooms:
    """Test room listing functionality."""

    def test_list_available_rooms_returns_all_rooms(self):
        """Should return all configured rooms."""
        from tools.lights import list_available_rooms

        result = list_available_rooms()

        assert result["success"] is True
        assert "rooms" in result
        assert result["count"] > 0

    def test_list_available_rooms_structure(self):
        """Each room should have name, entity_id, and light_count."""
        from tools.lights import list_available_rooms

        result = list_available_rooms()

        for room in result["rooms"]:
            assert "name" in room
            assert "entity_id" in room
            assert "light_count" in room
            assert room["light_count"] > 0

    def test_list_available_rooms_includes_living_room(self):
        """Living room should be in the list."""
        from tools.lights import list_available_rooms

        result = list_available_rooms()
        room_names = [r["name"] for r in result["rooms"]]

        assert "living room" in room_names


class TestSetRoomAmbiance:
    """Test room ambiance setting functionality."""

    def test_unknown_room_returns_error(self, mock_ha_full):
        """Should return error for unknown room."""
        from tools.lights import set_room_ambiance

        result = set_room_ambiance(room="nonexistent_room", action="on")

        assert result["success"] is False
        assert "error" in result
        assert "Unknown room" in result["error"]
        assert "available_rooms" in result

    def test_turn_on_room(self, mock_ha_full):
        """Should turn on room lights."""
        from tools.lights import set_room_ambiance

        result = set_room_ambiance(room="living room", action="on")

        assert result["success"] is True
        assert result["action"] == "on"
        assert result["room"] == "living room"
        assert "entity_id" in result

    def test_turn_off_room(self, mock_ha_full):
        """Should turn off room lights."""
        from tools.lights import set_room_ambiance

        result = set_room_ambiance(room="living room", action="off")

        assert result["success"] is True
        assert result["action"] == "off"

    def test_set_brightness(self, mock_ha_full):
        """Should set room brightness."""
        from tools.lights import set_room_ambiance

        result = set_room_ambiance(
            room="living room",
            action="set",
            brightness=50,
        )

        assert result["success"] is True
        assert result["brightness"] == 50

    def test_set_color_by_name(self, mock_ha_full):
        """Should convert color name to RGB."""
        from tools.lights import set_room_ambiance

        result = set_room_ambiance(
            room="bedroom",
            action="set",
            color="blue",
        )

        assert result["success"] is True
        assert result["color"] == "blue"
        assert result["rgb_color"] == (0, 0, 255)

    def test_set_color_temp(self, mock_ha_full):
        """Should set color temperature."""
        from tools.lights import set_room_ambiance

        result = set_room_ambiance(
            room="kitchen",
            action="set",
            color_temp_kelvin=4000,
        )

        assert result["success"] is True
        assert result["color_temp_kelvin"] == 4000

    def test_apply_vibe_preset(self, mock_ha_full):
        """Should apply vibe preset settings."""
        from tools.lights import set_room_ambiance

        result = set_room_ambiance(
            room="living room",
            action="set",
            vibe="cozy",
        )

        assert result["success"] is True
        assert result["vibe_applied"] == "cozy"
        # Cozy preset has brightness=40
        assert result["brightness"] == 40

    def test_vibe_preset_doesnt_override_explicit_brightness(self, mock_ha_full):
        """Explicit brightness should override vibe preset."""
        from tools.lights import set_room_ambiance

        result = set_room_ambiance(
            room="living room",
            action="set",
            vibe="cozy",
            brightness=80,  # Override cozy's default 40
        )

        assert result["success"] is True
        assert result["brightness"] == 80

    def test_unknown_color_ignored(self, mock_ha_full):
        """Unknown color name should be ignored gracefully."""
        from tools.lights import set_room_ambiance

        result = set_room_ambiance(
            room="living room",
            action="set",
            color="nonexistent_color",
        )

        # Should still succeed, just without color
        assert result["success"] is True
        assert "rgb_color" not in result

    def test_unknown_vibe_uses_explicit_settings(self, mock_ha_full):
        """Unknown vibe should fall back to explicit settings."""
        from tools.lights import set_room_ambiance

        result = set_room_ambiance(
            room="living room",
            action="set",
            vibe="nonexistent_vibe",
            brightness=60,
        )

        assert result["success"] is True
        assert result["brightness"] == 60
        # Note: vibe_applied is still set in result even for unknown vibes
        # (the warning is logged but the key is present)

    def test_rgb_color_overrides_color_temp(self, mock_ha_full):
        """RGB color should take precedence over color_temp."""
        from tools.lights import set_room_ambiance

        result = set_room_ambiance(
            room="bedroom",
            action="set",
            color="red",
            color_temp_kelvin=4000,  # Should be ignored
        )

        assert result["success"] is True
        assert "rgb_color" in result
        assert "color_temp_kelvin" not in result

    def test_unknown_action_returns_error(self, mock_ha_full):
        """Unknown action should return error."""
        from tools.lights import set_room_ambiance

        result = set_room_ambiance(room="living room", action="invalid_action")

        assert result["success"] is False
        assert "Unknown action" in result["error"]


class TestGetLightStatus:
    """Test light status retrieval."""

    def test_get_light_status_success(self, mock_ha_full):
        """Should return light status for valid room."""
        from tools.lights import get_light_status

        result = get_light_status("living room")

        assert result["success"] is True
        assert result["room"] == "living room"
        assert "state" in result
        assert "is_on" in result
        assert "entity_id" in result

    def test_get_light_status_brightness_conversion(self, mock_ha_full):
        """Should convert brightness from 0-255 to 0-100."""
        from tools.lights import get_light_status

        result = get_light_status("living room")

        # living_room uses light.living_room_2 (default_light in config)
        # which has brightness: 200 in fixture
        # 200/255 * 100 = 78%
        assert result["brightness_pct"] == 78

    def test_get_light_status_color_temp_conversion(self, mock_ha_full):
        """Should convert mireds to Kelvin."""
        from tools.lights import get_light_status

        result = get_light_status("living room")

        # living_room uses light.living_room_2 (default_light in config)
        # which has color_temp: 300 mireds in fixture
        # 1000000 / 300 = 3333K
        assert result["color_temp_kelvin"] is not None
        assert 3200 <= result["color_temp_kelvin"] <= 3400

    def test_get_light_status_unknown_room(self, mock_ha_full):
        """Should return error for unknown room."""
        from tools.lights import get_light_status

        result = get_light_status("nonexistent_room")

        assert result["success"] is False
        assert "Unknown room" in result["error"]


class TestActivateHueScene:
    """Test Hue scene activation."""

    def test_activate_hue_scene_success(self, mock_ha_full):
        """Should activate a Hue scene."""
        from tools.lights import activate_hue_scene

        result = activate_hue_scene(
            room="living room",
            scene_name="arctic_aurora",
        )

        assert result["success"] is True
        assert result["scene"] == "arctic_aurora"
        assert result["room"] == "living room"
        assert "scene_entity_id" in result

    def test_activate_hue_scene_entity_id_format(self, mock_ha_full):
        """Should construct correct scene entity ID."""
        from tools.lights import activate_hue_scene

        result = activate_hue_scene(
            room="living room",
            scene_name="tropical twilight",
        )

        # Should be: scene.living_room_tropical_twilight
        assert result["scene_entity_id"] == "scene.living_room_tropical_twilight"

    def test_activate_hue_scene_with_dynamic(self, mock_ha_full):
        """Should include dynamic setting."""
        from tools.lights import activate_hue_scene

        result = activate_hue_scene(
            room="living room",
            scene_name="arctic_aurora",
            dynamic=True,
        )

        assert result["dynamic"] is True

    def test_activate_hue_scene_with_speed(self, mock_ha_full):
        """Should include speed setting."""
        from tools.lights import activate_hue_scene

        result = activate_hue_scene(
            room="living room",
            scene_name="arctic_aurora",
            speed=75,
        )

        assert result["speed"] == 75

    def test_activate_hue_scene_with_brightness(self, mock_ha_full):
        """Should include brightness setting."""
        from tools.lights import activate_hue_scene

        result = activate_hue_scene(
            room="living room",
            scene_name="arctic_aurora",
            brightness=50,
        )

        assert result["brightness"] == 50


class TestExecuteLightTool:
    """Test the tool execution dispatcher."""

    def test_execute_set_room_ambiance(self, mock_ha_full):
        """Should dispatch to set_room_ambiance."""
        from tools.lights import execute_light_tool

        result = execute_light_tool(
            "set_room_ambiance",
            {"room": "living room", "action": "on"},
        )

        assert result["success"] is True
        assert result["action"] == "on"

    def test_execute_get_light_status(self, mock_ha_full):
        """Should dispatch to get_light_status."""
        from tools.lights import execute_light_tool

        result = execute_light_tool(
            "get_light_status",
            {"room": "living room"},
        )

        assert result["success"] is True
        assert "state" in result

    def test_execute_activate_hue_scene(self, mock_ha_full):
        """Should dispatch to activate_hue_scene."""
        from tools.lights import execute_light_tool

        result = execute_light_tool(
            "activate_hue_scene",
            {"room": "living room", "scene_name": "arctic_aurora"},
        )

        assert result["success"] is True
        assert result["scene"] == "arctic_aurora"

    def test_execute_list_available_rooms(self, mock_ha_full):
        """Should dispatch to list_available_rooms."""
        from tools.lights import execute_light_tool

        result = execute_light_tool("list_available_rooms", {})

        assert result["success"] is True
        assert "rooms" in result

    def test_execute_unknown_tool(self, mock_ha_full):
        """Should return error for unknown tool."""
        from tools.lights import execute_light_tool

        result = execute_light_tool("nonexistent_tool", {})

        assert result["success"] is False
        assert "Unknown tool" in result["error"]


class TestLightToolDefinitions:
    """Test tool definitions for Claude agent."""

    def test_light_tools_have_required_fields(self):
        """All tools should have name, description, and input_schema."""
        from tools.lights import LIGHT_TOOLS

        for tool in LIGHT_TOOLS:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool

    def test_set_room_ambiance_schema(self):
        """set_room_ambiance should have correct required fields."""
        from tools.lights import LIGHT_TOOLS

        tool = next(t for t in LIGHT_TOOLS if t["name"] == "set_room_ambiance")
        schema = tool["input_schema"]

        assert schema["required"] == ["room", "action"]
        assert "brightness" in schema["properties"]
        assert "color" in schema["properties"]
        assert "color_temp_kelvin" in schema["properties"]
        assert "vibe" in schema["properties"]

    def test_get_light_status_schema(self):
        """get_light_status should require room."""
        from tools.lights import LIGHT_TOOLS

        tool = next(t for t in LIGHT_TOOLS if t["name"] == "get_light_status")
        schema = tool["input_schema"]

        assert schema["required"] == ["room"]

    def test_activate_hue_scene_schema(self):
        """activate_hue_scene should require room and scene_name."""
        from tools.lights import LIGHT_TOOLS

        tool = next(t for t in LIGHT_TOOLS if t["name"] == "activate_hue_scene")
        schema = tool["input_schema"]

        assert "room" in schema["required"]
        assert "scene_name" in schema["required"]

    def test_list_available_rooms_schema(self):
        """list_available_rooms should have no required fields."""
        from tools.lights import LIGHT_TOOLS

        tool = next(t for t in LIGHT_TOOLS if t["name"] == "list_available_rooms")
        schema = tool["input_schema"]

        assert schema["required"] == []


class TestVibePresetApplication:
    """Test vibe preset integration with lights."""

    def test_all_vibes_work(self, mock_ha_full):
        """All configured vibes should apply successfully."""
        from tools.lights import set_room_ambiance
        from src.config import VIBE_PRESETS

        for vibe_name in VIBE_PRESETS.keys():
            result = set_room_ambiance(
                room="living room",
                action="set",
                vibe=vibe_name,
            )

            assert result["success"] is True, f"Vibe '{vibe_name}' failed"
            assert result["vibe_applied"] == vibe_name

    def test_cozy_vibe_applies_warm_dim(self, mock_ha_full):
        """Cozy vibe should set warm, dim lighting."""
        from tools.lights import set_room_ambiance

        result = set_room_ambiance(
            room="living room",
            action="set",
            vibe="cozy",
        )

        assert result["success"] is True
        assert result["brightness"] == 40
        # color_temp_kelvin should be 2700 but may not be in result if RGB overrides

    def test_focus_vibe_applies_bright_neutral(self, mock_ha_full):
        """Focus vibe should set bright, neutral lighting."""
        from tools.lights import set_room_ambiance

        result = set_room_ambiance(
            room="living room",
            action="set",
            vibe="focus",
        )

        assert result["success"] is True
        assert result["brightness"] == 80


class TestRoomAliasIntegration:
    """Test room alias handling in light tools."""

    def test_living_room_alias_lounge(self, mock_ha_full):
        """'lounge' should work as alias for living room."""
        from tools.lights import set_room_ambiance

        result = set_room_ambiance(room="lounge", action="on")

        assert result["success"] is True
        assert "living_room" in result["entity_id"]

    def test_office_alias_home_office(self, mock_ha_full):
        """'home office' should work as alias for office."""
        from tools.lights import set_room_ambiance

        result = set_room_ambiance(room="home office", action="on")

        assert result["success"] is True
        assert "office" in result["entity_id"]

    def test_case_insensitive_room_names(self, mock_ha_full):
        """Room names should be case-insensitive."""
        from tools.lights import set_room_ambiance

        result1 = set_room_ambiance(room="LIVING ROOM", action="on")
        result2 = set_room_ambiance(room="Living Room", action="on")
        result3 = set_room_ambiance(room="living room", action="on")

        assert result1["success"] is True
        assert result2["success"] is True
        assert result3["success"] is True
        assert result1["entity_id"] == result2["entity_id"] == result3["entity_id"]
