#!/usr/bin/env python3
"""
End-to-end tests for the Home Automation Agent system.

Run with: pytest test_e2e.py -v
"""

import os
import pytest
import requests
from dotenv import load_dotenv

load_dotenv()

# Test configuration
BASE_URL = "http://localhost:5001"
API_URL = f"{BASE_URL}/api"


@pytest.fixture
def api_headers():
    """Common headers for API requests."""
    return {"Content-Type": "application/json"}


class TestAPIEndpoints:
    """Test suite for API endpoints."""

    def test_get_prompts(self, api_headers):
        """Test retrieving prompt configurations."""
        response = requests.get(f"{API_URL}/prompts", headers=api_headers)

        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        data = response.json()
        assert "success" in data
        assert data["success"] is True
        assert "prompts" in data

        # Verify expected prompt structure
        prompts = data["prompts"]
        assert "main_agent" in prompts
        assert "hue_specialist" in prompts
        assert "system" in prompts["main_agent"]

        print(f"✓ Retrieved prompts for {len(prompts)} agents")

    def test_get_metadata(self, api_headers):
        """Test retrieving agent metadata."""
        response = requests.get(f"{API_URL}/prompts/metadata", headers=api_headers)

        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        data = response.json()
        assert "success" in data
        assert data["success"] is True
        assert "metadata" in data

        # Verify expected metadata structure
        metadata = data["metadata"]
        assert "main_agent" in metadata
        assert "hue_specialist" in metadata

        # Check main agent metadata
        main_meta = metadata["main_agent"]
        assert "name" in main_meta
        assert "icon" in main_meta
        assert "when_called" in main_meta
        assert "purpose" in main_meta

        print(f"✓ Retrieved metadata for {len(metadata)} agents")
        print(f"  Main Agent: {main_meta['name']} {main_meta['icon']}")

    def test_lighting_command(self, api_headers):
        """Test sending a lighting command through the API."""
        # Skip if no Home Assistant token (CI/CD environment)
        ha_token = os.getenv("HA_TOKEN")
        if not ha_token:
            pytest.skip("HA_TOKEN not set - skipping live Home Assistant test")

        command = "what rooms are available?"
        response = requests.post(
            f"{API_URL}/command",
            json={"command": command},
            headers=api_headers
        )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        data = response.json()
        assert "success" in data
        assert "response" in data

        # The response should mention available rooms
        response_text = data["response"].lower()
        assert any(room in response_text for room in ["living_room", "bedroom", "kitchen", "office"]), \
            "Response should mention at least one available room"

        print(f"✓ Command executed: '{command}'")
        print(f"  Response: {data['response'][:100]}...")


class TestWebUI:
    """Test suite for web UI endpoints."""

    def test_home_page(self):
        """Test that the home page loads."""
        response = requests.get(BASE_URL)

        assert response.status_code == 200
        assert "Home Control" in response.text or "🏠" in response.text

        print("✓ Home page loads successfully")


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "--tb=short"])
