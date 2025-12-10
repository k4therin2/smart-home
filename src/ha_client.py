"""
Smart Home Assistant - Home Assistant Client Module

Handles all communication with the Home Assistant API.
"""

import requests
from typing import Any

from src.config import HA_URL, HA_TOKEN
from src.utils import setup_logging

logger = setup_logging("ha_client")


class HomeAssistantClient:
    """Client for interacting with Home Assistant REST API."""

    def __init__(self, url: str | None = None, token: str | None = None):
        """
        Initialize the Home Assistant client.

        Args:
            url: Home Assistant URL (defaults to config)
            token: Long-lived access token (defaults to config)
        """
        self.url = (url or HA_URL).rstrip("/")
        self.token = token or HA_TOKEN
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def _request(
        self,
        method: str,
        endpoint: str,
        data: dict | None = None,
        timeout: int = 10
    ) -> dict | list | None:
        """
        Make a request to the Home Assistant API.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., /api/states)
            data: Request body data
            timeout: Request timeout in seconds

        Returns:
            Response JSON or None on error
        """
        url = f"{self.url}{endpoint}"
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                json=data,
                timeout=timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            logger.error(f"Request timeout: {method} {url}")
            return None
        except requests.exceptions.ConnectionError as error:
            logger.error(f"Connection error to Home Assistant: {error}")
            return None
        except requests.exceptions.HTTPError as error:
            logger.error(f"HTTP error: {error}")
            return None
        except requests.exceptions.JSONDecodeError:
            logger.warning(f"Empty or non-JSON response from {url}")
            return {}

    def check_connection(self) -> bool:
        """
        Check if Home Assistant is reachable.

        Returns:
            True if connected, False otherwise
        """
        result = self._request("GET", "/api/")
        if result and "message" in result:
            logger.info(f"Connected to Home Assistant: {result.get('message')}")
            return True
        return False

    def get_state(self, entity_id: str) -> dict | None:
        """
        Get the current state of an entity.

        Args:
            entity_id: Entity ID (e.g., light.living_room)

        Returns:
            State dictionary or None
        """
        result = self._request("GET", f"/api/states/{entity_id}")
        if result:
            logger.debug(f"State of {entity_id}: {result.get('state')}")
        return result

    def get_all_states(self) -> list[dict]:
        """
        Get states of all entities.

        Returns:
            List of state dictionaries
        """
        result = self._request("GET", "/api/states")
        return result if isinstance(result, list) else []

    def call_service(
        self,
        domain: str,
        service: str,
        service_data: dict | None = None,
        target: dict | None = None
    ) -> bool:
        """
        Call a Home Assistant service.

        Args:
            domain: Service domain (e.g., 'light')
            service: Service name (e.g., 'turn_on')
            service_data: Service data payload
            target: Target entities (entity_id, device_id, area_id)

        Returns:
            True if successful, False otherwise
        """
        endpoint = f"/api/services/{domain}/{service}"
        data = service_data or {}

        if target:
            data.update(target)

        logger.info(f"Calling service: {domain}.{service} with {data}")
        result = self._request("POST", endpoint, data)
        return result is not None

    def turn_on_light(
        self,
        entity_id: str,
        brightness_pct: int | None = None,
        color_temp_kelvin: int | None = None,
        rgb_color: tuple[int, int, int] | None = None,
        transition: float | None = None
    ) -> bool:
        """
        Turn on a light with optional settings.

        Args:
            entity_id: Light entity ID
            brightness_pct: Brightness percentage (0-100)
            color_temp_kelvin: Color temperature in Kelvin
            rgb_color: RGB color tuple (r, g, b)
            transition: Transition time in seconds

        Returns:
            True if successful
        """
        service_data = {"entity_id": entity_id}

        if brightness_pct is not None:
            service_data["brightness_pct"] = max(0, min(100, brightness_pct))

        if color_temp_kelvin is not None:
            # Convert Kelvin to mireds for HA
            mireds = int(1000000 / color_temp_kelvin)
            service_data["color_temp"] = max(153, min(500, mireds))

        if rgb_color is not None:
            service_data["rgb_color"] = list(rgb_color)

        if transition is not None:
            service_data["transition"] = transition

        return self.call_service("light", "turn_on", service_data)

    def turn_off_light(self, entity_id: str, transition: float | None = None) -> bool:
        """
        Turn off a light.

        Args:
            entity_id: Light entity ID
            transition: Transition time in seconds

        Returns:
            True if successful
        """
        service_data = {"entity_id": entity_id}
        if transition is not None:
            service_data["transition"] = transition

        return self.call_service("light", "turn_off", service_data)

    def set_light_brightness(self, entity_id: str, brightness_pct: int) -> bool:
        """
        Set light brightness.

        Args:
            entity_id: Light entity ID
            brightness_pct: Brightness percentage (0-100)

        Returns:
            True if successful
        """
        return self.turn_on_light(entity_id, brightness_pct=brightness_pct)

    def activate_hue_scene(
        self,
        scene_entity_id: str,
        dynamic: bool = False,
        speed: int | None = None,
        brightness: int | None = None
    ) -> bool:
        """
        Activate a Philips Hue scene.

        Args:
            scene_entity_id: Scene entity ID (e.g., scene.living_room_arctic_aurora)
            dynamic: Enable dynamic scene (colors shift over time)
            speed: Dynamic scene speed (0-100)
            brightness: Scene brightness (0-100)

        Returns:
            True if successful
        """
        service_data = {"entity_id": scene_entity_id}

        if dynamic:
            service_data["dynamic"] = True

        if speed is not None:
            service_data["speed"] = max(0, min(100, speed))

        if brightness is not None:
            service_data["brightness"] = max(0, min(100, brightness))

        return self.call_service("hue", "activate_scene", service_data)

    def get_lights(self) -> list[dict]:
        """
        Get all light entities.

        Returns:
            List of light entity states
        """
        all_states = self.get_all_states()
        return [s for s in all_states if s.get("entity_id", "").startswith("light.")]

    def get_hue_scenes(self) -> list[dict]:
        """
        Get all Hue scene entities.

        Returns:
            List of scene entity states
        """
        all_states = self.get_all_states()
        return [s for s in all_states if s.get("entity_id", "").startswith("scene.")]

    def get_light_state(self, entity_id: str) -> dict | None:
        """
        Get detailed light state including attributes.

        Args:
            entity_id: Light entity ID

        Returns:
            Dictionary with state and attributes
        """
        state = self.get_state(entity_id)
        if not state:
            return None

        return {
            "entity_id": entity_id,
            "state": state.get("state"),
            "brightness": state.get("attributes", {}).get("brightness"),
            "color_temp": state.get("attributes", {}).get("color_temp"),
            "rgb_color": state.get("attributes", {}).get("rgb_color"),
            "friendly_name": state.get("attributes", {}).get("friendly_name"),
        }


# Singleton instance for convenience
_client: HomeAssistantClient | None = None


def get_ha_client() -> HomeAssistantClient:
    """Get or create the Home Assistant client singleton."""
    global _client
    if _client is None:
        _client = HomeAssistantClient()
    return _client
