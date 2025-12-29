# WP-10.36: Privacy Policy & Terms of Service

**Date:** 2025-12-29
**Agent:** Agent-Nadia
**Status:** Complete

## Summary

Implemented comprehensive privacy documentation and consent management for SmartHome, preparing the project for community release.

## Deliverables

### 1. Privacy Policy (`PRIVACY_POLICY.md`)
- Data collection disclosure (devices, commands, API usage, state history)
- Third-party data sharing (OpenAI, Spotify, Slack)
- Data security practices
- User rights (access, export, deletion, modification)
- Data retention policies

### 2. Terms of Service (`TERMS_OF_SERVICE.md`)
- MIT License terms for open-source software
- User responsibilities (hardware, API keys, security)
- Third-party service terms references
- Disclaimer of warranties
- Limitation of liability
- Home automation risk acknowledgment

### 3. Consent Management Module (`src/privacy_consent.py`)
- Privacy settings management
- Third-party service enable/disable controls
- Consent acceptance/revocation tracking
- Consent versioning for policy updates
- Data export functionality
- Data retention policy enforcement
- 28 unit tests

## Technical Details

### Privacy Settings
```python
PRIVACY_OPENAI_ENABLED = True  # Required for core function
PRIVACY_SPOTIFY_ENABLED = False  # Optional, disabled by default
PRIVACY_SLACK_ENABLED = False  # Optional, disabled by default
PRIVACY_COMMAND_HISTORY_RETENTION_DAYS = 30
PRIVACY_DEVICE_HISTORY_RETENTION_DAYS = 30
```

### Key Functions
- `accept_privacy_consent()` - Record user consent with version
- `revoke_privacy_consent()` - Clear consent records
- `is_consent_valid()` - Check if consent is current
- `is_third_party_enabled(service)` - Check service status
- `export_user_data()` - GDPR-style data export
- `apply_retention_policy()` - Clean old data per settings

## Test Results

```
28 passed in 0.08s
```

## Acceptance Criteria

| Criterion | Status |
|-----------|--------|
| Privacy policy complete | ✅ |
| Terms of service complete | ✅ |
| Data retention policy documented | ✅ |
| Third-party data sharing disclosed | ✅ |
| Consent management implemented | ✅ |
| Legal review (if needed) | ⏸️ Deferred (open-source project) |

## Files Changed

- `PRIVACY_POLICY.md` (new)
- `TERMS_OF_SERVICE.md` (new)
- `src/privacy_consent.py` (new)
- `tests/unit/test_privacy_consent.py` (new)

## Notes

- Privacy-friendly defaults: optional services disabled by default
- OpenAI enabled by default as it's required for core LLM functionality
- Consent versioning allows automatic prompts when policy updates
- Data export enables GDPR-style data portability
- Legal review deferred as this is an open-source personal project
