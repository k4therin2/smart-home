"""
Philips Hue Bridge Client - Direct API Integration

This module provides direct access to the Philips Hue Bridge API v2
for room and group management that bypasses Home Assistant.

The Hue API v2 uses HTTPS and requires an application key for authentication.
See: https://developers.meethue.com/new-hue-api/
"""

import json
import logging
import os
import ssl
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv


load_dotenv()

logger = logging.getLogger(__name__)


# Room archetype mappings for Hue API
# See: https://developers.meethue.com/develop/hue-api-v2/api-reference/#resource_room
HUE_ROOM_ARCHETYPES = {
    "living_room": "living_room",
    "bedroom": "bedroom",
    "kitchen": "kitchen",
    "bathroom": "bathroom",
    "office": "office",
    "garage": "garage",
    "hallway": "hallway",
    "dining_room": "dining",
    "laundry": "laundry_room",
    "attic": "attic",
    "basement": "basement",
    "closet": "closet",
    "nursery": "nursery",
    "recreation": "recreation",
    "staircase": "staircase",
    "storage": "storage",
    "studio": "studio",
    "balcony": "balcony",
    "porch": "front_door",
    "terrace": "terrace",
    "garden": "garden",
    "driveway": "driveway",
    "carport": "carport",
    "other": "other",
}


@dataclass
class HueRoom:
    """Represents a room on the Hue bridge."""

    id: str
    name: str
    archetype: str
    children: list[str]  # Device/light resource IDs


class HueBridgeClient:
    """
    Client for the Philips Hue Bridge v2 API.

    Provides direct room management for syncing room assignments
    from the SmartHome system to the Hue app.

    Attributes:
        bridge_ip: IP address of the Hue bridge
        application_key: API authentication key (username)
    """

    def __init__(
        self,
        bridge_ip: str | None = None,
        application_key: str | None = None,
    ):
        """
        Initialize the Hue Bridge client.

        Args:
            bridge_ip: IP address of Hue bridge (from env if not provided)
            application_key: API key (from env if not provided)
        """
        self.bridge_ip = bridge_ip or os.getenv("HUE_BRIDGE_IP")
        self.application_key = application_key or os.getenv("HUE_BRIDGE_KEY")

        self._ssl_context = self._create_ssl_context()

        logger.info(f"HueBridgeClient initialized for bridge at {self.bridge_ip}")

    def _create_ssl_context(self) -> ssl.SSLContext:
        """
        Create SSL context for Hue bridge communication.

        The Hue bridge uses a self-signed certificate from Signify CA.
        We disable verification for local network communication.
        """
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context

    @property
    def base_url(self) -> str:
        """Get the base URL for API v2 requests."""
        return f"https://{self.bridge_ip}/clip/v2"

    def is_configured(self) -> bool:
        """Check if bridge is configured."""
        return bool(self.bridge_ip and self.application_key)

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Make an authenticated request to the Hue bridge.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (e.g., "/resource/room")
            data: Optional JSON body

        Returns:
            Response data as dict

        Raises:
            HueBridgeError: If request fails
        """
        if not self.is_configured():
            raise HueBridgeError("Hue bridge not configured. Set HUE_BRIDGE_IP and HUE_BRIDGE_KEY.")

        url = f"{self.base_url}{endpoint}"
        headers = {
            "hue-application-key": self.application_key,
            "Content-Type": "application/json",
        }

        body = json.dumps(data).encode("utf-8") if data else None

        request = Request(url, data=body, headers=headers, method=method)

        try:
            with urlopen(request, context=self._ssl_context, timeout=10) as response:
                response_data = json.loads(response.read().decode("utf-8"))
                return response_data

        except HTTPError as error:
            error_body = error.read().decode("utf-8")
            logger.error(f"Hue API error: {error.code} - {error_body}")
            raise HueBridgeError(f"API error {error.code}: {error_body}") from error

        except URLError as error:
            logger.error(f"Hue bridge connection error: {error}")
            raise HueBridgeError(f"Connection failed: {error}") from error

    # ========== Device Discovery ==========

    def get_devices(self) -> list[dict[str, Any]]:
        """
        Get all devices from the Hue bridge.

        Returns:
            List of device resources
        """
        response = self._make_request("GET", "/resource/device")
        return response.get("data", [])

    def get_lights(self) -> list[dict[str, Any]]:
        """
        Get all light resources from the Hue bridge.

        Returns:
            List of light resources
        """
        response = self._make_request("GET", "/resource/light")
        return response.get("data", [])

    def find_device_by_name(self, name: str) -> dict[str, Any] | None:
        """
        Find a device by its friendly name.

        Args:
            name: Device name to search for

        Returns:
            Device resource or None
        """
        devices = self.get_devices()
        name_lower = name.lower()

        for device in devices:
            device_name = device.get("metadata", {}).get("name", "").lower()
            if name_lower in device_name or device_name in name_lower:
                return device

        return None

    def get_device_id_from_ha_entity(self, entity_id: str) -> str | None:
        """
        Map a Home Assistant entity ID to a Hue device resource ID.

        Args:
            entity_id: HA entity ID (e.g., "light.living_room_lamp")

        Returns:
            Hue device resource ID (UUID) or None
        """
        # Extract friendly name from entity_id
        # e.g., "light.living_room_lamp" -> "living room lamp"
        name_part = entity_id.replace("light.", "").replace("_", " ")

        device = self.find_device_by_name(name_part)
        if device:
            return device.get("id")

        return None

    # ========== Room Management ==========

    def get_rooms(self) -> list[HueRoom]:
        """
        Get all rooms from the Hue bridge.

        Returns:
            List of HueRoom objects
        """
        response = self._make_request("GET", "/resource/room")
        rooms = []

        for room_data in response.get("data", []):
            room = HueRoom(
                id=room_data.get("id", ""),
                name=room_data.get("metadata", {}).get("name", ""),
                archetype=room_data.get("metadata", {}).get("archetype", "other"),
                children=[c.get("rid", "") for c in room_data.get("children", [])],
            )
            rooms.append(room)

        return rooms

    def find_room_by_name(self, name: str) -> HueRoom | None:
        """
        Find a room by name.

        Args:
            name: Room name

        Returns:
            HueRoom or None
        """
        rooms = self.get_rooms()
        name_lower = name.lower().replace("_", " ")

        for room in rooms:
            room_name_lower = room.name.lower()
            if name_lower == room_name_lower or name_lower in room_name_lower:
                return room

        return None

    def create_room(
        self,
        name: str,
        device_ids: list[str],
        archetype: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a new room on the Hue bridge.

        Args:
            name: Room name
            device_ids: List of device resource IDs to add
            archetype: Room type (defaults based on name)

        Returns:
            API response with created room ID
        """
        # Determine archetype
        name_normalized = name.lower().replace(" ", "_")
        if archetype is None:
            archetype = HUE_ROOM_ARCHETYPES.get(name_normalized, "other")

        # Build children array
        children = [{"rid": device_id, "rtype": "device"} for device_id in device_ids]

        data = {
            "metadata": {
                "name": name.replace("_", " ").title(),
                "archetype": archetype,
            },
            "children": children,
        }

        response = self._make_request("POST", "/resource/room", data)

        logger.info(f"Created room '{name}' with {len(device_ids)} devices")
        return response

    def update_room(
        self,
        room_id: str,
        device_ids: list[str] | None = None,
        name: str | None = None,
    ) -> dict[str, Any]:
        """
        Update an existing room.

        Args:
            room_id: Room resource ID
            device_ids: New list of device IDs (replaces existing)
            name: New room name

        Returns:
            API response
        """
        data = {}

        if name:
            data["metadata"] = {"name": name.replace("_", " ").title()}

        if device_ids is not None:
            data["children"] = [{"rid": device_id, "rtype": "device"} for device_id in device_ids]

        response = self._make_request("PUT", f"/resource/room/{room_id}", data)

        logger.info(f"Updated room {room_id}")
        return response

    def add_devices_to_room(
        self,
        room_id: str,
        device_ids: list[str],
    ) -> dict[str, Any]:
        """
        Add devices to an existing room.

        Args:
            room_id: Room resource ID
            device_ids: Device IDs to add

        Returns:
            API response
        """
        # Get current room
        room = None
        for r in self.get_rooms():
            if r.id == room_id:
                room = r
                break

        if not room:
            raise HueBridgeError(f"Room {room_id} not found")

        # Merge device lists
        all_devices = list(set(room.children + device_ids))

        return self.update_room(room_id, device_ids=all_devices)

    def delete_room(self, room_id: str) -> dict[str, Any]:
        """
        Delete a room from the Hue bridge.

        Args:
            room_id: Room resource ID

        Returns:
            API response
        """
        response = self._make_request("DELETE", f"/resource/room/{room_id}")

        logger.info(f"Deleted room {room_id}")
        return response

    # ========== Sync Operations ==========

    def sync_rooms_from_mappings(
        self,
        mappings: list[dict[str, str]],
    ) -> dict[str, Any]:
        """
        Sync room assignments to the Hue bridge.

        Takes a list of entity_id -> room_name mappings and creates
        or updates rooms on the Hue bridge accordingly.

        Args:
            mappings: List of dicts with entity_id and room_name

        Returns:
            Sync result with counts and errors
        """
        if not self.is_configured():
            return {
                "success": False,
                "error": "Hue bridge not configured. Set HUE_BRIDGE_IP and HUE_BRIDGE_KEY in .env",
            }

        # Group mappings by room
        rooms_to_sync: dict[str, list[str]] = {}
        unmapped_entities: list[str] = []

        for mapping in mappings:
            entity_id = mapping.get("entity_id", "")
            room_name = mapping.get("room_name", "")

            if not room_name:
                continue

            # Get Hue device ID
            device_id = self.get_device_id_from_ha_entity(entity_id)

            if device_id:
                if room_name not in rooms_to_sync:
                    rooms_to_sync[room_name] = []
                rooms_to_sync[room_name].append(device_id)
            else:
                unmapped_entities.append(entity_id)

        # Sync each room
        created = 0
        updated = 0
        errors = []

        for room_name, device_ids in rooms_to_sync.items():
            try:
                existing_room = self.find_room_by_name(room_name)

                if existing_room:
                    self.add_devices_to_room(existing_room.id, device_ids)
                    updated += 1
                else:
                    self.create_room(room_name, device_ids)
                    created += 1

            except HueBridgeError as error:
                errors.append(f"{room_name}: {error}")

        return {
            "success": len(errors) == 0,
            "created": created,
            "updated": updated,
            "unmapped": unmapped_entities,
            "errors": errors,
            "message": f"Synced {created + updated} rooms to Hue bridge"
            + (f" ({len(unmapped_entities)} devices not found)" if unmapped_entities else ""),
        }


class HueBridgeError(Exception):
    """Exception raised for Hue bridge errors."""

    pass


# Singleton instance
_hue_bridge_client: HueBridgeClient | None = None


def get_hue_bridge_client() -> HueBridgeClient:
    """Get or create the HueBridgeClient singleton."""
    global _hue_bridge_client
    if _hue_bridge_client is None:
        _hue_bridge_client = HueBridgeClient()
    return _hue_bridge_client
