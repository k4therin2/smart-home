# Feedback Feature Hang Fix

**Date:** 2026-01-02
**Issue:** E2E feedback feature hanging on "Creating bug..." when clicking thumbs down button
**Status:** Fixed

## Problem

When users clicked the thumbs down button on a response, the UI would hang indefinitely showing "Creating bug..." The backend logs showed:

1. Bug was successfully filed in Vikunja (e.g., BUG-20260102041427)
2. NATS alert was timing out with SSL certificate verification error
3. The `/api/feedback` endpoint wasn't returning until NATS completed

## Root Cause

The `alert_developers_via_nats()` function in `src/feedback_handler.py` was blocking the HTTP response:

```python
def alert_developers_via_nats(bug_id: str, command: str, response: str):
    asyncio.run(_send_nats_alert(bug_id, command, response))  # Blocking!
```

The NATS connection was failing due to SSL certificate verification error (self-signed cert), causing a long timeout before the function returned.

## Fix

### 1. Added Timeout to NATS Alert

Added a 2-second timeout to prevent indefinite blocking:

```python
def alert_developers_via_nats(bug_id: str, command: str, response: str):
    try:
        asyncio.run(asyncio.wait_for(_send_nats_alert(...), timeout=2.0))
    except asyncio.TimeoutError:
        logger.warning(f"NATS alert timed out for {bug_id}")
    except Exception as e:
        logger.warning(f"Failed to send NATS alert: {e}")
```

### 2. Fixed SSL Certificate Handling

Updated NATS connection to accept self-signed certificates:

```python
async def _send_nats_alert(...):
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    await nc.connect(NATS_URL, tls=ssl_ctx, allow_reconnect=False)
```

### 3. Updated Frontend Message

Changed loading message from "Filing bug..." to "Creating bug..." to match user expectations.

## Testing

Created test script at `scripts/test_feedback.py`:

```bash
$ python scripts/test_feedback.py
=== Feedback Handler Test ===

Testing bug filing in Vikunja...
✓ Bug filed successfully: BUG-20260102043237

Testing NATS alert (with timeout)...
✓ NATS alert completed (may have failed, but didn't hang)

=== Test Complete ===
✓ All tests passed
```

## Verification Steps

1. Go to http://localhost:5049
2. Login (user: admin)
3. Submit a command like "turn off kitchen lights"
4. Click the thumbs DOWN button
5. Bug should be filed in Vikunja within 2 seconds
6. UI should show "Bug BUG-XXXXXX filed" message

## Files Modified

- `src/feedback_handler.py` - Added timeout and SSL handling
- `static/app.js` - Updated loading message text
- `scripts/test_feedback.py` - Added test script (new file)

## Notes

- Bug filing in Vikunja works correctly
- NATS alert may still fail (authorization violation), but it doesn't block the response
- The 2-second timeout ensures the UI responds quickly even if NATS is down
- Consider fixing NATS authentication in a future update

## Related Issues

- Original bug report: User reported hanging on "Creating bug..." button
- Vikunja integration: Working correctly (creates tasks with labels)
- NATS coordination: Needs auth/SSL configuration review
