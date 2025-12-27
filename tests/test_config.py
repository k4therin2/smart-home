"""
Tests for src/config.py - Configuration Module

Tests configuration loading, room entity mapping, color temperature
conversion, and validation logic.
"""

import pytest


class TestKelvinMiredsConversion:
    """Test Kelvin to mireds and back conversions."""

    def test_kelvin_to_mireds_warm(self):
        """2700K (warm) should convert to approximately 370 mireds."""
        from src.config import kelvin_to_mireds

        result = kelvin_to_mireds(2700)
        assert result == 370

    def test_kelvin_to_mireds_neutral(self):
        """4000K (neutral) should convert to 250 mireds."""
        from src.config import kelvin_to_mireds

        result = kelvin_to_mireds(4000)
        assert result == 250

    def test_kelvin_to_mireds_daylight(self):
        """6500K (daylight) should convert to approximately 153 mireds."""
        from src.config import kelvin_to_mireds

        result = kelvin_to_mireds(6500)
        assert result == 153

    def test_mireds_to_kelvin_warm(self):
        """370 mireds should convert back to approximately 2700K."""
        from src.config import mireds_to_kelvin

        result = mireds_to_kelvin(370)
        assert result == 2702  # slight rounding difference is acceptable

    def test_mireds_to_kelvin_neutral(self):
        """250 mireds should convert to 4000K."""
        from src.config import mireds_to_kelvin

        result = mireds_to_kelvin(250)
        assert result == 4000

    def test_roundtrip_conversion(self):
        """Converting K to mireds and back should be approximately equal."""
        from src.config import kelvin_to_mireds, mireds_to_kelvin

        original_kelvin = 3500
        mireds = kelvin_to_mireds(original_kelvin)
        back_to_kelvin = mireds_to_kelvin(mireds)

        # Allow small rounding error (within 50K)
        assert abs(back_to_kelvin - original_kelvin) < 50


class TestRoomEntityLookup:
    """Test room name normalization and entity lookup."""

    def test_get_room_entity_exact_match(self):
        """Exact room name should return the default light entity."""
        from src.config import get_room_entity

        result = get_room_entity("living_room")
        assert result == "light.living_room_2"

    def test_get_room_entity_with_spaces(self):
        """Room names with spaces should be normalized."""
        from src.config import get_room_entity

        result = get_room_entity("living room")
        assert result == "light.living_room_2"

    def test_get_room_entity_mixed_case(self):
        """Room names should be case-insensitive."""
        from src.config import get_room_entity

        result = get_room_entity("Living Room")
        assert result == "light.living_room_2"

    def test_get_room_entity_with_alias(self):
        """Room aliases should resolve to canonical names."""
        from src.config import get_room_entity

        # "lounge" is an alias for "living_room"
        result = get_room_entity("lounge")
        assert result == "light.living_room_2"

    def test_get_room_entity_front_room_alias(self):
        """Front room alias should resolve to living room."""
        from src.config import get_room_entity

        result = get_room_entity("front room")
        assert result == "light.living_room_2"

    def test_get_room_entity_home_office_alias(self):
        """Home office alias should resolve to office."""
        from src.config import get_room_entity

        result = get_room_entity("home office")
        assert result == "light.office_pendant"

    def test_get_room_entity_unknown_room(self):
        """Unknown room should return None."""
        from src.config import get_room_entity

        result = get_room_entity("nonexistent_room")
        assert result is None

    def test_get_room_entity_empty_string(self):
        """Empty string should return None."""
        from src.config import get_room_entity

        result = get_room_entity("")
        assert result is None

    def test_get_room_entity_whitespace_only(self):
        """Whitespace-only string should return None."""
        from src.config import get_room_entity

        result = get_room_entity("   ")
        assert result is None


class TestRoomEntityMap:
    """Test the room entity map configuration."""

    def test_all_rooms_have_default_light(self):
        """Every room should have a default_light defined."""
        from src.config import ROOM_ENTITY_MAP

        for room_name, room_config in ROOM_ENTITY_MAP.items():
            assert "default_light" in room_config, f"Room '{room_name}' missing default_light"
            assert room_config["default_light"].startswith("light."), \
                f"Room '{room_name}' default_light should start with 'light.'"

    def test_all_rooms_have_lights_list(self):
        """Every room should have a lights list."""
        from src.config import ROOM_ENTITY_MAP

        for room_name, room_config in ROOM_ENTITY_MAP.items():
            assert "lights" in room_config, f"Room '{room_name}' missing lights list"
            assert len(room_config["lights"]) > 0, f"Room '{room_name}' has empty lights list"

    def test_default_light_in_lights_list(self):
        """Default light should be in the room's lights list."""
        from src.config import ROOM_ENTITY_MAP

        for room_name, room_config in ROOM_ENTITY_MAP.items():
            default_light = room_config["default_light"]
            lights_list = room_config["lights"]
            assert default_light in lights_list, \
                f"Room '{room_name}' default_light '{default_light}' not in lights list"


class TestVibePresets:
    """Test vibe preset configuration."""

    def test_all_vibes_have_brightness(self):
        """Every vibe preset should have brightness defined."""
        from src.config import VIBE_PRESETS

        for vibe_name, settings in VIBE_PRESETS.items():
            assert "brightness" in settings, f"Vibe '{vibe_name}' missing brightness"

    def test_all_vibes_have_color_temp(self):
        """Every vibe preset should have color_temp_kelvin defined."""
        from src.config import VIBE_PRESETS

        for vibe_name, settings in VIBE_PRESETS.items():
            assert "color_temp_kelvin" in settings, f"Vibe '{vibe_name}' missing color_temp_kelvin"

    def test_vibe_brightness_in_valid_range(self):
        """Vibe brightness should be between 0 and 100."""
        from src.config import VIBE_PRESETS

        for vibe_name, settings in VIBE_PRESETS.items():
            brightness = settings["brightness"]
            assert 0 <= brightness <= 100, \
                f"Vibe '{vibe_name}' brightness {brightness} out of range"

    def test_vibe_color_temp_in_valid_range(self):
        """Vibe color temperature should be in a reasonable Kelvin range."""
        from src.config import VIBE_PRESETS

        for vibe_name, settings in VIBE_PRESETS.items():
            color_temp = settings["color_temp_kelvin"]
            # Typical range for smart lights: 2000K to 6500K
            assert 2000 <= color_temp <= 6500, \
                f"Vibe '{vibe_name}' color_temp {color_temp}K out of range"

    def test_cozy_vibe_settings(self):
        """Cozy vibe should have warm, dim settings."""
        from src.config import VIBE_PRESETS

        cozy = VIBE_PRESETS["cozy"]
        assert cozy["brightness"] < 60, "Cozy should be dimmer"
        assert cozy["color_temp_kelvin"] <= 3000, "Cozy should be warm white"

    def test_focus_vibe_settings(self):
        """Focus vibe should have bright, neutral settings."""
        from src.config import VIBE_PRESETS

        focus = VIBE_PRESETS["focus"]
        assert focus["brightness"] >= 70, "Focus should be bright"
        assert focus["color_temp_kelvin"] >= 4000, "Focus should be neutral/cool"


class TestColorTempPresets:
    """Test color temperature preset configuration."""

    def test_warm_preset_value(self):
        """Warm preset should be 2700K."""
        from src.config import COLOR_TEMP_PRESETS

        assert COLOR_TEMP_PRESETS["warm"] == 2700

    def test_daylight_preset_value(self):
        """Daylight preset should be 6500K."""
        from src.config import COLOR_TEMP_PRESETS

        assert COLOR_TEMP_PRESETS["daylight"] == 6500

    def test_neutral_preset_between_warm_and_cool(self):
        """Neutral should be between warm and cool."""
        from src.config import COLOR_TEMP_PRESETS

        warm = COLOR_TEMP_PRESETS["warm"]
        neutral = COLOR_TEMP_PRESETS["neutral"]
        cool = COLOR_TEMP_PRESETS["cool"]

        assert warm < neutral < cool


class TestBrightnessPresets:
    """Test brightness preset configuration."""

    def test_dim_is_lowest(self):
        """Dim should be the lowest brightness."""
        from src.config import BRIGHTNESS_PRESETS

        dim = BRIGHTNESS_PRESETS["dim"]
        for preset_name, value in BRIGHTNESS_PRESETS.items():
            if preset_name != "dim":
                assert dim <= value, f"Dim ({dim}) should be <= {preset_name} ({value})"

    def test_full_is_100(self):
        """Full brightness should be 100%."""
        from src.config import BRIGHTNESS_PRESETS

        assert BRIGHTNESS_PRESETS["full"] == 100

    def test_brightness_presets_in_valid_range(self):
        """All brightness presets should be 0-100."""
        from src.config import BRIGHTNESS_PRESETS

        for preset_name, value in BRIGHTNESS_PRESETS.items():
            assert 0 <= value <= 100, f"Preset '{preset_name}' value {value} out of range"


class TestConfigValidation:
    """Test configuration validation function."""

    def test_validate_config_with_all_vars_set(self, monkeypatch):
        """Validation should pass when all required vars are set."""
        # The autouse fixture already sets these, just verify
        from src.config import validate_config, OPENAI_API_KEY, HA_TOKEN, HA_URL

        # Verify the environment is set up correctly
        assert OPENAI_API_KEY is not None
        assert HA_TOKEN is not None
        assert HA_URL is not None

        errors = validate_config()
        assert len(errors) == 0

    def test_validate_config_missing_openai_key(self, monkeypatch):
        """Validation should fail when OPENAI_API_KEY is missing."""
        # Patch the module-level constant directly
        monkeypatch.setattr("src.config.OPENAI_API_KEY", None)

        from src.config import validate_config

        errors = validate_config()
        assert any("OPENAI_API_KEY" in e for e in errors)

    def test_validate_config_missing_ha_token(self, monkeypatch):
        """Validation should fail when HA_TOKEN is missing."""
        # Patch the module-level constant directly
        monkeypatch.setattr("src.config.HA_TOKEN", None)

        from src.config import validate_config

        errors = validate_config()
        assert any("HA_TOKEN" in e for e in errors)


class TestProjectPaths:
    """Test project path configuration."""

    def test_project_root_exists(self):
        """PROJECT_ROOT should point to an existing directory."""
        from src.config import PROJECT_ROOT

        assert PROJECT_ROOT.exists()
        assert PROJECT_ROOT.is_dir()

    def test_data_dir_created(self):
        """DATA_DIR should be created on module load."""
        from src.config import DATA_DIR

        assert DATA_DIR.exists()
        assert DATA_DIR.is_dir()
