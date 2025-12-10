"""
Smart Home Assistant - Home Assistant Integration Module

Provides connection and communication with Home Assistant API.
Handles authentication, service calls, and device state queries.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import urljoin

import requests

from src.config import HA_URL, HA_TOKEN

logger = logging.getLogger(__name__)


class HomeAssistantError(Exception):
    """Base exception for Home Assistant errors."""
    pass


class HomeAssistantConnectionError(HomeAssistantError):
    """Raised when connection to Home Assistant fails."""
    pass


class HomeAssistantAuthError(HomeAssistantError):
    """Raised when authentication with Home Assistant fails."""
    pass


class HomeAssistantClient:
    """
    Client for communicating with Home Assistant REST API.

    Handles authentication, service calls, and state queries.
    """

    def __init__(self, base_url: Optional[str] = None, token: Optional[str] = None):
        """
        Initialize Home Assistant client.

        Args:
            base_url: Home Assistant URL (defaults to HA_URL from config)
            token: Long-lived access token (defaults to HA_TOKEN from config)
        """
        self.base_url = (base_url or HA_URL or "").rstrip("/")
        self.token = token or HA_TOKEN

        if not self.base_url:
            raise HomeAssistantError("Home Assistant URL not configured")
        if not self.token:
            raise HomeAssistantAuthError("Home Assistant token not configured")

        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        })
        self._timeout = 10  # seconds

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None
    ) -> Union[Dict, List]:
        """
        Make HTTP request to Home Assistant API.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            data: Optional JSON data for POST requests

        Returns:
            JSON response from API

        Raises:
            HomeAssistantConnectionError: On connection failures
            HomeAssistantAuthError: On authentication failures
            HomeAssistantError: On other API errors
        """
        url = urljoin(self.base_url, endpoint)

        try:
            response = self._session.request(
                method=method,
                url=url,
                json=data,
                timeout=self._timeout,
            )

            if response.status_code == 401:
                raise HomeAssistantAuthError("Invalid or expired access token")

            if response.status_code == 404:
                raise HomeAssistantError(f"Endpoint not found: {endpoint}")

            response.raise_for_status()

            # Some endpoints return empty response
            if not response.text:
                return {}

            return response.json()

        except requests.exceptions.ConnectionError as error:
            logger.error(f"Failed to connect to Home Assistant at {self.base_url}: {error}")
            raise HomeAssistantConnectionError(
                f"Cannot connect to Home Assistant at {self.base_url}"
            ) from error
        except requests.exceptions.Timeout as error:
            logger.error(f"Request to Home Assistant timed out: {error}")
            raise HomeAssistantConnectionError(
                "Request to Home Assistant timed out"
            ) from error
        except requests.exceptions.RequestException as error:
            logger.error(f"Home Assistant API error: {error}")
            raise HomeAssistantError(f"API request failed: {error}") from error

    # -------------------------------------------------------------------------
    # Connection & Health
    # -------------------------------------------------------------------------

    def check_connection(self) -> bool:
        """
        Verify connection to Home Assistant.

        Returns:
            True if connection is successful

        Raises:
            HomeAssistantConnectionError: If connection fails
            HomeAssistantAuthError: If authentication fails
        """
        try:
            self._make_request("GET", "/api/")
            logger.info(f"Successfully connected to Home Assistant at {self.base_url}")
            return True
        except HomeAssistantError:
            raise

    def get_config(self) -> dict:
        """
        Get Home Assistant configuration.

        Returns:
            Configuration dict with location, units, version, etc.
        """
        return self._make_request("GET", "/api/config")

    def is_running(self) -> bool:
        """
        Check if Home Assistant is running and accessible.

        Returns:
            True if HA is running, False otherwise
        """
        try:
            self.check_connection()
            return True
        except HomeAssistantError:
            return False

    # -------------------------------------------------------------------------
    # State Queries
    # -------------------------------------------------------------------------

    def get_states(self) -> List[Dict]:
        """
        Get states of all entities.

        Returns:
            List of entity state dicts
        """
        return self._make_request("GET", "/api/states")

    def get_state(self, entity_id: str) -> dict:
        """
        Get state of a specific entity.

        Args:
            entity_id: Entity ID (e.g., 'light.living_room')

        Returns:
            Entity state dict with state, attributes, last_changed, etc.
        """
        return self._make_request("GET", f"/api/states/{entity_id}")

    def get_entity_state_value(self, entity_id: str) -> str:
        """
        Get just the state value of an entity.

        Args:
            entity_id: Entity ID

        Returns:
            State value string (e.g., 'on', 'off', '23.5')
        """
        state = self.get_state(entity_id)
        return state.get("state", "unknown")

    def get_entities_by_domain(self, domain: str) -> List[Dict]:
        """
        Get all entities for a specific domain.

        Args:
            domain: Entity domain (e.g., 'light', 'switch', 'sensor')

        Returns:
            List of entity state dicts matching the domain
        """
        all_states = self.get_states()
        return [
            state for state in all_states
            if state.get("entity_id", "").startswith(f"{domain}.")
        ]

    def get_lights(self) -> List[Dict]:
        """Get all light entities."""
        return self.get_entities_by_domain("light")

    def get_switches(self) -> List[Dict]:
        """Get all switch entities."""
        return self.get_entities_by_domain("switch")

    def get_sensors(self) -> List[Dict]:
        """Get all sensor entities."""
        return self.get_entities_by_domain("sensor")

    # -------------------------------------------------------------------------
    # Service Calls
    # -------------------------------------------------------------------------

    def call_service(
        self,
        domain: str,
        service: str,
        data: Optional[Dict] = None,
        target: Optional[Dict] = None,
    ) -> List[Dict]:
        """
        Call a Home Assistant service.

        Args:
            domain: Service domain (e.g., 'light', 'switch', 'scene')
            service: Service name (e.g., 'turn_on', 'turn_off', 'toggle')
            data: Optional service data
            target: Optional target specification (entity_id, area_id, device_id)

        Returns:
            List of updated entity states

        Example:
            client.call_service(
                domain='light',
                service='turn_on',
                target={'entity_id': 'light.living_room'},
                data={'brightness_pct': 50, 'color_temp_kelvin': 2700}
            )
        """
        endpoint = f"/api/services/{domain}/{service}"

        payload = {}
        if data:
            payload.update(data)
        if target:
            payload.update(target)

        logger.info(f"Calling service {domain}.{service} with payload: {payload}")

        result = self._make_request("POST", endpoint, data=payload if payload else None)

        logger.debug(f"Service call result: {result}")
        return result if isinstance(result, list) else []

    # -------------------------------------------------------------------------
    # Light Control Helpers
    # -------------------------------------------------------------------------

    def turn_on_light(
        self,
        entity_id: str,
        brightness_pct: Optional[int] = None,
        color_temp_kelvin: Optional[int] = None,
        rgb_color: Optional[Tuple[int, int, int]] = None,
        transition: Optional[float] = None,
    ) -> List[Dict]:
        """
        Turn on a light with optional settings.

        Args:
            entity_id: Light entity ID
            brightness_pct: Brightness percentage (0-100)
            color_temp_kelvin: Color temperature in Kelvin
            rgb_color: RGB color tuple (r, g, b) each 0-255
            transition: Transition time in seconds

        Returns:
            List of updated entity states
        """
        data = {}

        if brightness_pct is not None:
            data["brightness_pct"] = max(0, min(100, brightness_pct))

        if color_temp_kelvin is not None:
            # Convert Kelvin to mireds for HA
            data["color_temp_kelvin"] = color_temp_kelvin

        if rgb_color is not None:
            data["rgb_color"] = list(rgb_color)

        if transition is not None:
            data["transition"] = transition

        return self.call_service(
            domain="light",
            service="turn_on",
            target={"entity_id": entity_id},
            data=data if data else None,
        )

    def turn_off_light(
        self,
        entity_id: str,
        transition: Optional[float] = None
    ) -> List[Dict]:
        """
        Turn off a light.

        Args:
            entity_id: Light entity ID
            transition: Optional transition time in seconds

        Returns:
            List of updated entity states
        """
        data = {}
        if transition is not None:
            data["transition"] = transition

        return self.call_service(
            domain="light",
            service="turn_off",
            target={"entity_id": entity_id},
            data=data if data else None,
        )

    def toggle_light(self, entity_id: str) -> List[Dict]:
        """
        Toggle a light on/off.

        Args:
            entity_id: Light entity ID

        Returns:
            List of updated entity states
        """
        return self.call_service(
            domain="light",
            service="toggle",
            target={"entity_id": entity_id},
        )

    # -------------------------------------------------------------------------
    # Switch Control Helpers
    # -------------------------------------------------------------------------

    def turn_on_switch(self, entity_id: str) -> List[Dict]:
        """Turn on a switch."""
        return self.call_service(
            domain="switch",
            service="turn_on",
            target={"entity_id": entity_id},
        )

    def turn_off_switch(self, entity_id: str) -> List[Dict]:
        """Turn off a switch."""
        return self.call_service(
            domain="switch",
            service="turn_off",
            target={"entity_id": entity_id},
        )

    def toggle_switch(self, entity_id: str) -> List[Dict]:
        """Toggle a switch."""
        return self.call_service(
            domain="switch",
            service="toggle",
            target={"entity_id": entity_id},
        )

    # -------------------------------------------------------------------------
    # Scene Control
    # -------------------------------------------------------------------------

    def activate_scene(self, entity_id: str) -> List[Dict]:
        """
        Activate a scene.

        Args:
            entity_id: Scene entity ID (e.g., 'scene.movie_time')

        Returns:
            List of updated entity states
        """
        return self.call_service(
            domain="scene",
            service="turn_on",
            target={"entity_id": entity_id},
        )

    def activate_hue_scene(
        self,
        entity_id: str,
        dynamic: bool = False,
        speed: Optional[int] = None,
        brightness: Optional[int] = None,
    ) -> List[Dict]:
        """
        Activate a Philips Hue scene with optional dynamic mode.

        Args:
            entity_id: Scene entity ID
            dynamic: Enable dynamic/animated scene
            speed: Animation speed (1-100) for dynamic scenes
            brightness: Brightness percentage (0-100)

        Returns:
            List of updated entity states
        """
        data = {}

        if dynamic:
            data["dynamic"] = True

        if speed is not None:
            data["speed"] = max(1, min(100, speed))

        if brightness is not None:
            data["brightness"] = max(0, min(100, brightness))

        return self.call_service(
            domain="hue",
            service="activate_scene",
            target={"entity_id": entity_id},
            data=data if data else None,
        )

    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------

    def get_available_services(self) -> dict:
        """
        Get all available services.

        Returns:
            Dict mapping domain to list of available services
        """
        return self._make_request("GET", "/api/services")

    def get_history(
        self,
        entity_id: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> List:
        """
        Get entity history.

        Args:
            entity_id: Optional entity ID to filter
            start_time: ISO format start time
            end_time: ISO format end time

        Returns:
            List of history entries
        """
        endpoint = "/api/history/period"

        if start_time:
            endpoint = f"{endpoint}/{start_time}"

        params = []
        if entity_id:
            params.append(f"filter_entity_id={entity_id}")
        if end_time:
            params.append(f"end_time={end_time}")

        if params:
            endpoint = f"{endpoint}?{'&'.join(params)}"

        return self._make_request("GET", endpoint)

    def close(self):
        """Close the HTTP session."""
        self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Module-level convenience functions using default configuration

_default_client: Optional[HomeAssistantClient] = None


def get_client() -> HomeAssistantClient:
    """
    Get or create the default Home Assistant client.

    Returns:
        HomeAssistantClient instance
    """
    global _default_client
    if _default_client is None:
        _default_client = HomeAssistantClient()
    return _default_client


def check_connection() -> bool:
    """Check connection to Home Assistant using default client."""
    return get_client().check_connection()


def get_state(entity_id: str) -> dict:
    """Get entity state using default client."""
    return get_client().get_state(entity_id)


def call_service(
    domain: str,
    service: str,
    data: Optional[Dict] = None,
    target: Optional[Dict] = None,
) -> List[Dict]:
    """Call a service using default client."""
    return get_client().call_service(domain, service, data, target)


def turn_on_light(entity_id: str, **kwargs) -> List[Dict]:
    """Turn on a light using default client."""
    return get_client().turn_on_light(entity_id, **kwargs)


def turn_off_light(entity_id: str, **kwargs) -> List[Dict]:
    """Turn off a light using default client."""
    return get_client().turn_off_light(entity_id, **kwargs)
