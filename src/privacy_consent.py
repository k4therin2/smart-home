"""
SmartHome Privacy & Consent Management Module (WP-10.36)

Provides consent management for privacy-sensitive features:
- Third-party data sharing controls
- Command history retention settings
- Data export functionality
"""

import json
import logging
from datetime import datetime
from typing import Any

from src.database import (
    get_setting,
    set_setting,
    get_cursor,
)

logger = logging.getLogger(__name__)


# Privacy Setting Keys
PRIVACY_OPENAI_ENABLED = "privacy.third_party.openai_enabled"
PRIVACY_SPOTIFY_ENABLED = "privacy.third_party.spotify_enabled"
PRIVACY_SLACK_ENABLED = "privacy.third_party.slack_enabled"
PRIVACY_COMMAND_HISTORY_ENABLED = "privacy.command_history.enabled"
PRIVACY_COMMAND_HISTORY_RETENTION_DAYS = "privacy.command_history.retention_days"
PRIVACY_DEVICE_HISTORY_ENABLED = "privacy.device_history.enabled"
PRIVACY_DEVICE_HISTORY_RETENTION_DAYS = "privacy.device_history.retention_days"
PRIVACY_CONSENT_ACCEPTED = "privacy.consent.accepted"
PRIVACY_CONSENT_ACCEPTED_DATE = "privacy.consent.accepted_date"
PRIVACY_CONSENT_VERSION = "privacy.consent.version"

# Current privacy policy version
CURRENT_CONSENT_VERSION = "1.0.0"


def get_privacy_defaults() -> dict[str, Any]:
    """
    Get default privacy settings.

    Defaults are privacy-friendly:
    - All third-party services disabled until explicitly enabled
    - Command history enabled but with limited retention
    """
    return {
        PRIVACY_OPENAI_ENABLED: True,  # Required for core functionality
        PRIVACY_SPOTIFY_ENABLED: False,  # Optional feature
        PRIVACY_SLACK_ENABLED: False,  # Optional feature
        PRIVACY_COMMAND_HISTORY_ENABLED: True,
        PRIVACY_COMMAND_HISTORY_RETENTION_DAYS: 30,
        PRIVACY_DEVICE_HISTORY_ENABLED: True,
        PRIVACY_DEVICE_HISTORY_RETENTION_DAYS: 30,
        PRIVACY_CONSENT_ACCEPTED: False,
        PRIVACY_CONSENT_ACCEPTED_DATE: None,
        PRIVACY_CONSENT_VERSION: None,
    }


def get_privacy_setting(key: str) -> Any:
    """
    Get a privacy setting value.

    Args:
        key: Privacy setting key

    Returns:
        Setting value, or default if not set
    """
    defaults = get_privacy_defaults()
    if key not in defaults:
        raise ValueError(f"Unknown privacy setting: {key}")

    value = get_setting(key)
    if value is None:
        return defaults[key]
    return value


def set_privacy_setting(key: str, value: Any) -> bool:
    """
    Update a privacy setting.

    Args:
        key: Privacy setting key
        value: New value

    Returns:
        True if successful

    Raises:
        ValueError: If key is unknown
    """
    defaults = get_privacy_defaults()
    if key not in defaults:
        raise ValueError(f"Unknown privacy setting: {key}")

    set_setting(key, value, description=f"Privacy setting: {key}")
    logger.info(f"Privacy setting updated: {key}={value}")
    return True


def get_all_privacy_settings() -> dict[str, Any]:
    """
    Get all privacy settings with their current values.

    Returns:
        Dict of all privacy settings
    """
    settings = {}
    for key in get_privacy_defaults():
        settings[key] = get_privacy_setting(key)
    return settings


def accept_privacy_consent(version: str = CURRENT_CONSENT_VERSION) -> bool:
    """
    Record user's acceptance of privacy policy.

    Args:
        version: Privacy policy version being accepted

    Returns:
        True if recorded successfully
    """
    set_privacy_setting(PRIVACY_CONSENT_ACCEPTED, True)
    set_privacy_setting(PRIVACY_CONSENT_ACCEPTED_DATE, datetime.now().isoformat())
    set_privacy_setting(PRIVACY_CONSENT_VERSION, version)
    logger.info(f"Privacy consent accepted for version {version}")
    return True


def revoke_privacy_consent() -> bool:
    """
    Revoke previously given consent.

    Returns:
        True if revoked successfully
    """
    set_privacy_setting(PRIVACY_CONSENT_ACCEPTED, False)
    set_privacy_setting(PRIVACY_CONSENT_ACCEPTED_DATE, None)
    set_privacy_setting(PRIVACY_CONSENT_VERSION, None)
    logger.info("Privacy consent revoked")
    return True


def is_consent_valid() -> bool:
    """
    Check if user has valid consent for current privacy policy version.

    Returns:
        True if consent is valid and current
    """
    accepted = get_privacy_setting(PRIVACY_CONSENT_ACCEPTED)
    version = get_privacy_setting(PRIVACY_CONSENT_VERSION)

    return accepted and version == CURRENT_CONSENT_VERSION


def is_third_party_enabled(service: str) -> bool:
    """
    Check if a third-party service is enabled.

    Args:
        service: Service name ('openai', 'spotify', 'slack')

    Returns:
        True if service is enabled
    """
    key_map = {
        "openai": PRIVACY_OPENAI_ENABLED,
        "spotify": PRIVACY_SPOTIFY_ENABLED,
        "slack": PRIVACY_SLACK_ENABLED,
    }

    if service.lower() not in key_map:
        logger.warning(f"Unknown third-party service: {service}")
        return False

    return get_privacy_setting(key_map[service.lower()])


def export_user_data() -> dict[str, Any]:
    """
    Export all user data for GDPR-style data portability.

    Returns:
        Dict containing all user data
    """
    export_data = {
        "export_date": datetime.now().isoformat(),
        "privacy_settings": get_all_privacy_settings(),
        "command_history": [],
        "devices": [],
        "device_state_history": [],
        "api_usage": [],
        "settings": {},
    }

    with get_cursor() as cursor:
        # Export command history
        cursor.execute("SELECT * FROM command_history ORDER BY created_at DESC")
        export_data["command_history"] = [dict(row) for row in cursor.fetchall()]

        # Export devices
        cursor.execute("SELECT * FROM devices ORDER BY entity_id")
        export_data["devices"] = [dict(row) for row in cursor.fetchall()]

        # Export device state history
        if get_privacy_setting(PRIVACY_DEVICE_HISTORY_ENABLED):
            cursor.execute(
                "SELECT * FROM device_state_history ORDER BY recorded_at DESC LIMIT 1000"
            )
            export_data["device_state_history"] = [dict(row) for row in cursor.fetchall()]

        # Export API usage
        cursor.execute("SELECT * FROM api_usage ORDER BY date DESC")
        export_data["api_usage"] = [dict(row) for row in cursor.fetchall()]

        # Export all settings
        cursor.execute("SELECT key, value FROM settings")
        for row in cursor.fetchall():
            try:
                export_data["settings"][row["key"]] = json.loads(row["value"])
            except json.JSONDecodeError:
                export_data["settings"][row["key"]] = row["value"]

    return export_data


def clear_command_history() -> int:
    """
    Clear all command history.

    Returns:
        Number of records deleted
    """
    with get_cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM command_history")
        count = cursor.fetchone()[0]
        cursor.execute("DELETE FROM command_history")

    logger.info(f"Cleared {count} command history records")
    return count


def apply_retention_policy() -> dict[str, int]:
    """
    Apply data retention policies by deleting old records.

    Returns:
        Dict with counts of deleted records by type
    """
    deleted = {"command_history": 0, "device_state_history": 0}

    # Clear old command history
    if get_privacy_setting(PRIVACY_COMMAND_HISTORY_ENABLED):
        retention_days = get_privacy_setting(PRIVACY_COMMAND_HISTORY_RETENTION_DAYS)
        if retention_days and retention_days > 0:
            with get_cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM command_history
                    WHERE created_at < datetime('now', ?)
                    """,
                    (f"-{retention_days} days",),
                )
                deleted["command_history"] = cursor.rowcount

    # Clear old device state history
    if get_privacy_setting(PRIVACY_DEVICE_HISTORY_ENABLED):
        retention_days = get_privacy_setting(PRIVACY_DEVICE_HISTORY_RETENTION_DAYS)
        if retention_days and retention_days > 0:
            with get_cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM device_state_history
                    WHERE recorded_at < datetime('now', ?)
                    """,
                    (f"-{retention_days} days",),
                )
                deleted["device_state_history"] = cursor.rowcount

    if any(deleted.values()):
        logger.info(f"Applied retention policy: deleted {deleted}")

    return deleted


def get_consent_status() -> dict[str, Any]:
    """
    Get current consent status for display.

    Returns:
        Dict with consent status details
    """
    return {
        "accepted": get_privacy_setting(PRIVACY_CONSENT_ACCEPTED),
        "accepted_date": get_privacy_setting(PRIVACY_CONSENT_ACCEPTED_DATE),
        "accepted_version": get_privacy_setting(PRIVACY_CONSENT_VERSION),
        "current_version": CURRENT_CONSENT_VERSION,
        "is_current": is_consent_valid(),
        "requires_update": (
            get_privacy_setting(PRIVACY_CONSENT_ACCEPTED) and
            get_privacy_setting(PRIVACY_CONSENT_VERSION) != CURRENT_CONSENT_VERSION
        ),
    }
