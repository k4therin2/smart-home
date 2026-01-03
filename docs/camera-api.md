# Camera Query REST API

REST API endpoints for querying camera observation data from external systems.

**WP-11.6: MCP Query API for Cross-System Access**

## Overview

The Camera Query API provides programmatic access to camera event data stored by the smart home system. It enables external systems (like the agent-automation system) to query camera observations without direct database access.

## Authentication

The API supports two authentication methods:

### 1. Tailscale Network (Recommended)

Requests from Tailscale IPs (100.x.x.x range) are automatically authenticated. This is the recommended method for trusted internal systems.

```bash
# From a machine on the Tailscale network
curl http://colby:5049/api/camera/events
```

### 2. API Key

For non-Tailscale access, include an API key in the `X-API-Key` header:

```bash
curl -H "X-API-Key: your-api-key" http://colby:5050/api/camera/events
```

API keys are configured via the `CAMERA_API_KEYS` environment variable (comma-separated list).

## Endpoints

### GET /api/camera/events

Query camera events with optional filters.

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `object` | string | Filter by detected object type (e.g., `cat`, `person`, `dog`, `package`) |
| `camera` | string | Filter by camera ID (partial match, e.g., `front_door`) |
| `time_range` | string | Time range filter (see Time Ranges below) |
| `limit` | integer | Maximum results (default: 50, max: 500) |

#### Time Range Values

| Value | Description |
|-------|-------------|
| `today` | From midnight today to now |
| `yesterday` | Full day yesterday |
| `this_morning` | 6am - 12pm today |
| `this_afternoon` | 12pm - 6pm today |
| `this_evening` | 6pm - midnight today |
| `last_hour` | Past 60 minutes |
| `last_3_hours` | Past 3 hours |
| `last_24_hours` | Past 24 hours |
| `this_week` | Past 7 days |

#### Response

```json
{
  "success": true,
  "events": [
    {
      "id": 123,
      "timestamp": "2026-01-03T10:30:00",
      "camera_id": "camera.front_door",
      "objects_detected": ["person", "package"],
      "description": "Delivery person dropping off a package at the front door",
      "motion_triggered": true
    }
  ],
  "count": 1
}
```

#### Examples

```bash
# Get all events from today
curl "http://colby:5049/api/camera/events?time_range=today"

# Find cat sightings this morning
curl "http://colby:5049/api/camera/events?object=cat&time_range=this_morning"

# Front door activity in the last hour
curl "http://colby:5049/api/camera/events?camera=front_door&time_range=last_hour&limit=10"

# Package deliveries today
curl "http://colby:5049/api/camera/events?object=package&time_range=today"
```

### GET /api/camera/summary

Get an activity summary for a time period.

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `time_range` | string | Time range filter (see Time Ranges above) |
| `camera` | string | Filter by camera ID (partial match) |

#### Response

```json
{
  "success": true,
  "total_events": 47,
  "period_start": "2026-01-03T00:00:00",
  "period_end": "2026-01-03T15:30:00",
  "motion_events": 35,
  "objects_detected": {
    "cat": 12,
    "person": 8,
    "dog": 5,
    "package": 2
  },
  "top_objects": [
    ["cat", 12],
    ["person", 8],
    ["dog", 5],
    ["package", 2]
  ]
}
```

#### Examples

```bash
# Today's activity summary
curl "http://colby:5049/api/camera/summary?time_range=today"

# Yesterday's summary
curl "http://colby:5049/api/camera/summary?time_range=yesterday"

# This week's summary
curl "http://colby:5049/api/camera/summary?time_range=this_week"
```

## Error Responses

### 401 Unauthorized

```json
{
  "success": false,
  "error": "Unauthorized"
}
```

Returned when authentication fails (not on Tailscale network and no valid API key).

### 500 Internal Server Error

```json
{
  "success": false,
  "error": "Internal server error"
}
```

Returned when a server error occurs. In debug mode, the actual error message is included.

## Rate Limits

- `/api/camera/events`: 60 requests per minute
- `/api/camera/summary`: 30 requests per minute

## Integration Example

### Python

```python
import requests

def get_camera_events(object_type=None, time_range="today"):
    """Query camera events from the smart home system."""
    params = {"time_range": time_range}
    if object_type:
        params["object"] = object_type

    response = requests.get(
        "http://colby:5049/api/camera/events",
        params=params,
        headers={"X-API-Key": "your-api-key"}  # Only needed if not on Tailscale
    )
    response.raise_for_status()
    return response.json()

# Example: Get cat sightings today
events = get_camera_events(object_type="cat", time_range="today")
for event in events["events"]:
    print(f"{event['timestamp']}: {event['description']}")
```

### Agent Tool Integration

The camera query API is designed to work with the agent-automation system. Agents can query camera data to answer user questions like:

- "What did the cat do today?"
- "Were there any packages delivered?"
- "Who was at the front door this morning?"

See `tools/camera_query.py` for the voice query tool that uses this API internally.
