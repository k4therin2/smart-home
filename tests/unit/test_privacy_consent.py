"""
Tests for Privacy & Consent Management Module (WP-10.36)
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

from src.privacy_consent import (
    PRIVACY_OPENAI_ENABLED,
    PRIVACY_SPOTIFY_ENABLED,
    PRIVACY_SLACK_ENABLED,
    PRIVACY_COMMAND_HISTORY_ENABLED,
    PRIVACY_COMMAND_HISTORY_RETENTION_DAYS,
    PRIVACY_DEVICE_HISTORY_ENABLED,
    PRIVACY_DEVICE_HISTORY_RETENTION_DAYS,
    PRIVACY_CONSENT_ACCEPTED,
    PRIVACY_CONSENT_VERSION,
    CURRENT_CONSENT_VERSION,
    get_privacy_defaults,
    get_privacy_setting,
    set_privacy_setting,
    get_all_privacy_settings,
    accept_privacy_consent,
    revoke_privacy_consent,
    is_consent_valid,
    is_third_party_enabled,
    get_consent_status,
    clear_command_history,
)


class TestPrivacyDefaults:
    """Test privacy default values."""

    def test_defaults_exist(self):
        """All expected privacy settings have defaults."""
        defaults = get_privacy_defaults()

        assert PRIVACY_OPENAI_ENABLED in defaults
        assert PRIVACY_SPOTIFY_ENABLED in defaults
        assert PRIVACY_SLACK_ENABLED in defaults
        assert PRIVACY_COMMAND_HISTORY_ENABLED in defaults
        assert PRIVACY_COMMAND_HISTORY_RETENTION_DAYS in defaults
        assert PRIVACY_DEVICE_HISTORY_ENABLED in defaults
        assert PRIVACY_DEVICE_HISTORY_RETENTION_DAYS in defaults
        assert PRIVACY_CONSENT_ACCEPTED in defaults

    def test_openai_enabled_by_default(self):
        """OpenAI is enabled by default (required for core function)."""
        defaults = get_privacy_defaults()
        assert defaults[PRIVACY_OPENAI_ENABLED] is True

    def test_optional_services_disabled_by_default(self):
        """Optional services are disabled by default (privacy-friendly)."""
        defaults = get_privacy_defaults()
        assert defaults[PRIVACY_SPOTIFY_ENABLED] is False
        assert defaults[PRIVACY_SLACK_ENABLED] is False

    def test_consent_not_accepted_by_default(self):
        """Consent is not accepted by default."""
        defaults = get_privacy_defaults()
        assert defaults[PRIVACY_CONSENT_ACCEPTED] is False

    def test_retention_days_have_reasonable_defaults(self):
        """Retention periods have reasonable defaults."""
        defaults = get_privacy_defaults()
        assert defaults[PRIVACY_COMMAND_HISTORY_RETENTION_DAYS] == 30
        assert defaults[PRIVACY_DEVICE_HISTORY_RETENTION_DAYS] == 30


class TestPrivacySettings:
    """Test get/set privacy settings."""

    @patch("src.privacy_consent.get_setting")
    def test_get_privacy_setting_returns_stored_value(self, mock_get):
        """Returns stored value when set."""
        mock_get.return_value = False
        result = get_privacy_setting(PRIVACY_OPENAI_ENABLED)
        assert result is False

    @patch("src.privacy_consent.get_setting")
    def test_get_privacy_setting_returns_default_when_not_set(self, mock_get):
        """Returns default value when not set."""
        mock_get.return_value = None
        result = get_privacy_setting(PRIVACY_OPENAI_ENABLED)
        assert result is True  # Default is True for OpenAI

    def test_get_privacy_setting_raises_for_unknown_key(self):
        """Raises ValueError for unknown settings."""
        with pytest.raises(ValueError, match="Unknown privacy setting"):
            get_privacy_setting("unknown.setting.key")

    @patch("src.privacy_consent.set_setting")
    def test_set_privacy_setting_updates_value(self, mock_set):
        """Successfully updates a privacy setting."""
        result = set_privacy_setting(PRIVACY_SPOTIFY_ENABLED, True)
        assert result is True
        mock_set.assert_called_once()

    def test_set_privacy_setting_raises_for_unknown_key(self):
        """Raises ValueError for unknown settings."""
        with pytest.raises(ValueError, match="Unknown privacy setting"):
            set_privacy_setting("unknown.setting.key", True)

    @patch("src.privacy_consent.get_privacy_setting")
    def test_get_all_privacy_settings(self, mock_get):
        """Returns all privacy settings."""
        mock_get.side_effect = lambda k: get_privacy_defaults()[k]

        result = get_all_privacy_settings()

        assert len(result) == len(get_privacy_defaults())
        assert all(key in result for key in get_privacy_defaults())


class TestConsentManagement:
    """Test consent accept/revoke functionality."""

    @patch("src.privacy_consent.set_privacy_setting")
    def test_accept_privacy_consent(self, mock_set):
        """Accepting consent sets all required fields."""
        result = accept_privacy_consent()

        assert result is True
        assert mock_set.call_count == 3
        # Check the calls include accepted=True, date, and version
        call_args = [call[0] for call in mock_set.call_args_list]
        assert (PRIVACY_CONSENT_ACCEPTED, True) in call_args
        assert call_args[2][0] == PRIVACY_CONSENT_VERSION

    @patch("src.privacy_consent.set_privacy_setting")
    def test_accept_privacy_consent_with_version(self, mock_set):
        """Can accept specific version."""
        result = accept_privacy_consent(version="2.0.0")

        assert result is True
        # Version should be "2.0.0"
        version_call = [c for c in mock_set.call_args_list if c[0][0] == PRIVACY_CONSENT_VERSION]
        assert version_call[0][0][1] == "2.0.0"

    @patch("src.privacy_consent.set_privacy_setting")
    def test_revoke_privacy_consent(self, mock_set):
        """Revoking consent clears all consent fields."""
        result = revoke_privacy_consent()

        assert result is True
        assert mock_set.call_count == 3
        # Check accepted is set to False
        call_args = [call[0] for call in mock_set.call_args_list]
        assert (PRIVACY_CONSENT_ACCEPTED, False) in call_args

    @patch("src.privacy_consent.get_privacy_setting")
    def test_is_consent_valid_when_accepted_current_version(self, mock_get):
        """Valid when accepted and version matches current."""
        mock_get.side_effect = lambda k: {
            PRIVACY_CONSENT_ACCEPTED: True,
            PRIVACY_CONSENT_VERSION: CURRENT_CONSENT_VERSION,
        }.get(k)

        assert is_consent_valid() is True

    @patch("src.privacy_consent.get_privacy_setting")
    def test_is_consent_invalid_when_not_accepted(self, mock_get):
        """Invalid when not accepted."""
        mock_get.side_effect = lambda k: {
            PRIVACY_CONSENT_ACCEPTED: False,
            PRIVACY_CONSENT_VERSION: CURRENT_CONSENT_VERSION,
        }.get(k)

        assert is_consent_valid() is False

    @patch("src.privacy_consent.get_privacy_setting")
    def test_is_consent_invalid_when_old_version(self, mock_get):
        """Invalid when version doesn't match current."""
        mock_get.side_effect = lambda k: {
            PRIVACY_CONSENT_ACCEPTED: True,
            PRIVACY_CONSENT_VERSION: "0.9.0",  # Old version
        }.get(k)

        assert is_consent_valid() is False


class TestThirdPartyControls:
    """Test third-party service enable/disable."""

    @patch("src.privacy_consent.get_privacy_setting")
    def test_is_third_party_enabled_openai(self, mock_get):
        """Checks OpenAI enabled status."""
        mock_get.return_value = True
        assert is_third_party_enabled("openai") is True

        mock_get.return_value = False
        assert is_third_party_enabled("openai") is False

    @patch("src.privacy_consent.get_privacy_setting")
    def test_is_third_party_enabled_spotify(self, mock_get):
        """Checks Spotify enabled status."""
        mock_get.return_value = True
        assert is_third_party_enabled("spotify") is True

    @patch("src.privacy_consent.get_privacy_setting")
    def test_is_third_party_enabled_slack(self, mock_get):
        """Checks Slack enabled status."""
        mock_get.return_value = True
        assert is_third_party_enabled("slack") is True

    def test_is_third_party_enabled_unknown_service(self):
        """Returns False for unknown services."""
        assert is_third_party_enabled("unknown_service") is False

    @patch("src.privacy_consent.get_privacy_setting")
    def test_is_third_party_enabled_case_insensitive(self, mock_get):
        """Service names are case-insensitive."""
        mock_get.return_value = True

        assert is_third_party_enabled("OPENAI") is True
        assert is_third_party_enabled("OpenAI") is True
        assert is_third_party_enabled("Spotify") is True


class TestConsentStatus:
    """Test consent status reporting."""

    @patch("src.privacy_consent.is_consent_valid")
    @patch("src.privacy_consent.get_privacy_setting")
    def test_get_consent_status_accepted(self, mock_get, mock_valid):
        """Returns complete status when accepted."""
        mock_valid.return_value = True
        mock_get.side_effect = lambda k: {
            PRIVACY_CONSENT_ACCEPTED: True,
            "privacy.consent.accepted_date": "2025-12-29T10:00:00",
            PRIVACY_CONSENT_VERSION: CURRENT_CONSENT_VERSION,
        }.get(k)

        status = get_consent_status()

        assert status["accepted"] is True
        assert status["current_version"] == CURRENT_CONSENT_VERSION
        assert status["is_current"] is True

    @patch("src.privacy_consent.is_consent_valid")
    @patch("src.privacy_consent.get_privacy_setting")
    def test_get_consent_status_not_accepted(self, mock_get, mock_valid):
        """Returns status when not accepted."""
        mock_valid.return_value = False
        mock_get.side_effect = lambda k: {
            PRIVACY_CONSENT_ACCEPTED: False,
            "privacy.consent.accepted_date": None,
            PRIVACY_CONSENT_VERSION: None,
        }.get(k)

        status = get_consent_status()

        assert status["accepted"] is False
        assert status["is_current"] is False

    @patch("src.privacy_consent.is_consent_valid")
    @patch("src.privacy_consent.get_privacy_setting")
    def test_get_consent_status_requires_update(self, mock_get, mock_valid):
        """Detects when consent needs update."""
        mock_valid.return_value = False
        mock_get.side_effect = lambda k: {
            PRIVACY_CONSENT_ACCEPTED: True,
            "privacy.consent.accepted_date": "2025-12-29T10:00:00",
            PRIVACY_CONSENT_VERSION: "0.9.0",
        }.get(k)

        status = get_consent_status()

        assert status["requires_update"] is True


class TestDataExportAndClear:
    """Test data export and clearing functionality."""

    @patch("src.privacy_consent.get_cursor")
    def test_clear_command_history(self, mock_cursor):
        """Clears command history and returns count."""
        mock_ctx = MagicMock()
        mock_cursor.return_value.__enter__.return_value = mock_ctx
        mock_ctx.fetchone.return_value = (42,)

        count = clear_command_history()

        assert count == 42
        # Should have SELECT COUNT and DELETE
        assert mock_ctx.execute.call_count == 2


class TestCurrentConsentVersion:
    """Test consent version handling."""

    def test_current_version_is_semantic(self):
        """Current version follows semantic versioning."""
        parts = CURRENT_CONSENT_VERSION.split(".")
        assert len(parts) == 3
        assert all(part.isdigit() for part in parts)

    def test_current_version_exists(self):
        """Current version is defined."""
        assert CURRENT_CONSENT_VERSION is not None
        assert len(CURRENT_CONSENT_VERSION) > 0
