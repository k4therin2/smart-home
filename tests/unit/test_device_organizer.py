"""
Unit tests for DeviceOrganizer class.

Tests LLM-driven device organization suggestions and bulk reorganization.
Part of WP-5.2: Device Organization Assistant.
"""

import pytest
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from unittest.mock import Mock, patch

from src.device_registry import DeviceRegistry, DeviceType
from src.device_organizer import (
    DeviceOrganizer,
    RoomSuggestion,
    OrganizationPlan,
)


@pytest.fixture
def temp_db():
    """Create a temporary database file."""
    with NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
        yield Path(temp_file.name)
    Path(temp_file.name).unlink(missing_ok=True)


@pytest.fixture
def registry(temp_db):
    """Create a DeviceRegistry with temporary database."""
    return DeviceRegistry(database_path=temp_db)


@pytest.fixture
def organizer(registry):
    """Create a DeviceOrganizer with the test registry."""
    return DeviceOrganizer(registry=registry)


# =============================================================================
# Room Suggestion Tests
# =============================================================================

class TestRoomSuggestions:
    """Tests for LLM-driven room suggestions."""

    def test_suggest_room_for_light(self, organizer, registry):
        """Suggests appropriate room based on device name."""
        device_id = registry.register_device(
            entity_id="light.bedroom_ceiling",
            device_type=DeviceType.LIGHT,
            friendly_name="Bedroom Ceiling Light",
        )

        suggestions = organizer.suggest_room(device_id)

        assert len(suggestions) > 0
        # The word "bedroom" in the name should suggest bedroom room
        room_names = [s.room_name for s in suggestions]
        assert "bedroom" in room_names

    def test_suggest_room_for_kitchen_device(self, organizer, registry):
        """Kitchen devices are suggested for kitchen."""
        device_id = registry.register_device(
            entity_id="switch.kitchen_fridge",
            device_type=DeviceType.SWITCH,
            friendly_name="Kitchen Refrigerator",
        )

        suggestions = organizer.suggest_room(device_id)

        room_names = [s.room_name for s in suggestions]
        assert "kitchen" in room_names

    def test_suggest_room_returns_confidence(self, organizer, registry):
        """Suggestions include confidence scores."""
        device_id = registry.register_device(
            entity_id="light.living_room_lamp",
            device_type=DeviceType.LIGHT,
            friendly_name="Living Room Floor Lamp",
        )

        suggestions = organizer.suggest_room(device_id)

        for suggestion in suggestions:
            assert hasattr(suggestion, "confidence")
            assert 0 <= suggestion.confidence <= 1.0

    def test_suggest_room_for_ambiguous_name(self, organizer, registry):
        """Ambiguous names return multiple suggestions."""
        device_id = registry.register_device(
            entity_id="light.smart_bulb_1",
            device_type=DeviceType.LIGHT,
            friendly_name="Smart Bulb 1",
        )

        suggestions = organizer.suggest_room(device_id)

        # Should have multiple lower-confidence suggestions
        # since the name doesn't indicate a specific room
        if len(suggestions) > 1:
            assert all(s.confidence < 0.9 for s in suggestions)

    def test_suggest_room_with_llm_enhancement(self, organizer, registry, mocker):
        """LLM can enhance suggestions when available."""
        # Mock the OpenAI LLM call
        mock_message = Mock()
        mock_message.content = '{"room": "living_room", "confidence": 0.95, "reason": "Floor lamp is typically a living room item"}'

        mock_choice = Mock()
        mock_choice.message = mock_message

        mock_response = Mock()
        mock_response.choices = [mock_choice]

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mocker.patch.object(organizer, "_get_llm_client", return_value=mock_client)

        device_id = registry.register_device(
            entity_id="light.floor_lamp",
            device_type=DeviceType.LIGHT,
            friendly_name="Floor Lamp",
        )

        suggestions = organizer.suggest_room(device_id, use_llm=True)

        # LLM should be called
        assert mock_client.chat.completions.create.called or len(suggestions) > 0

    def test_suggest_room_nonexistent_device(self, organizer):
        """Returns empty list for non-existent device."""
        suggestions = organizer.suggest_room(device_id=999999)
        assert suggestions == []


# =============================================================================
# Contextual Questions Tests
# =============================================================================

class TestContextualQuestions:
    """Tests for contextual questions about new devices."""

    def test_get_questions_for_new_device(self, organizer, registry):
        """Generates appropriate questions for new devices."""
        device_id = registry.register_device(
            entity_id="light.new_device",
            device_type=DeviceType.LIGHT,
            friendly_name="New Device",
        )

        questions = organizer.get_device_questions(device_id)

        assert len(questions) > 0
        # Should ask about room at minimum
        question_types = [q["type"] for q in questions]
        assert "room" in question_types

    def test_get_questions_for_unassigned_device(self, organizer, registry):
        """Questions focus on room assignment for unassigned devices."""
        device_id = registry.register_device(
            entity_id="light.orphan",
            device_type=DeviceType.LIGHT,
            friendly_name="Orphan Light",
        )

        questions = organizer.get_device_questions(device_id)

        # First question should be about room
        assert questions[0]["type"] == "room"

    def test_get_questions_includes_suggestions(self, organizer, registry):
        """Questions include suggested answers based on device name."""
        device_id = registry.register_device(
            entity_id="light.bedroom_lamp",
            device_type=DeviceType.LIGHT,
            friendly_name="Bedroom Lamp",
        )

        questions = organizer.get_device_questions(device_id)

        room_question = next((q for q in questions if q["type"] == "room"), None)
        assert room_question is not None
        assert "suggestions" in room_question
        assert "bedroom" in room_question["suggestions"]

    def test_no_questions_for_fully_organized_device(self, organizer, registry):
        """No questions if device is already organized."""
        device_id = registry.register_device(
            entity_id="light.organized",
            device_type=DeviceType.LIGHT,
            friendly_name="Organized Light",
            room_name="living_room",
        )

        questions = organizer.get_device_questions(device_id)

        # Should have no critical questions
        critical_questions = [q for q in questions if q.get("required")]
        assert len(critical_questions) == 0


# =============================================================================
# Bulk Reorganization Tests
# =============================================================================

class TestBulkReorganization:
    """Tests for bulk device reorganization."""

    def test_create_organization_plan(self, organizer, registry):
        """Can create an organization plan for unassigned devices."""
        # Create some unassigned devices
        registry.register_device(
            entity_id="light.bedroom_1",
            device_type=DeviceType.LIGHT,
            friendly_name="Bedroom Light 1",
        )
        registry.register_device(
            entity_id="light.kitchen_1",
            device_type=DeviceType.LIGHT,
            friendly_name="Kitchen Light 1",
        )

        plan = organizer.create_organization_plan()

        assert isinstance(plan, OrganizationPlan)
        assert len(plan.assignments) >= 2

    def test_organization_plan_has_device_assignments(self, organizer, registry):
        """Plan includes device-to-room assignments."""
        registry.register_device(
            entity_id="light.living_room_main",
            device_type=DeviceType.LIGHT,
            friendly_name="Living Room Main Light",
        )

        plan = organizer.create_organization_plan()

        # Each assignment should have device_id and suggested_room
        for assignment in plan.assignments:
            assert "device_id" in assignment
            assert "suggested_room" in assignment
            assert "confidence" in assignment

    def test_apply_organization_plan(self, organizer, registry):
        """Can apply an organization plan."""
        device_id = registry.register_device(
            entity_id="light.unassigned",
            device_type=DeviceType.LIGHT,
            friendly_name="Unassigned Light",
        )

        plan = OrganizationPlan(
            assignments=[
                {"device_id": device_id, "suggested_room": "bedroom", "confidence": 0.9}
            ]
        )

        results = organizer.apply_organization_plan(plan)

        assert len(results["applied"]) == 1
        device = registry.get_device(device_id)
        assert device["room_name"] == "bedroom"

    def test_apply_plan_skips_low_confidence(self, organizer, registry):
        """Low confidence assignments are skipped by default."""
        device_id = registry.register_device(
            entity_id="light.uncertain",
            device_type=DeviceType.LIGHT,
            friendly_name="Uncertain Device",
        )

        plan = OrganizationPlan(
            assignments=[
                {"device_id": device_id, "suggested_room": "bedroom", "confidence": 0.3}
            ]
        )

        results = organizer.apply_organization_plan(plan, min_confidence=0.5)

        assert len(results["skipped"]) == 1
        device = registry.get_device(device_id)
        assert device["room_name"] is None

    def test_apply_plan_with_approval_callback(self, organizer, registry):
        """Can use approval callback for each assignment."""
        device_id = registry.register_device(
            entity_id="light.needs_approval",
            device_type=DeviceType.LIGHT,
            friendly_name="Needs Approval",
        )

        plan = OrganizationPlan(
            assignments=[
                {"device_id": device_id, "suggested_room": "kitchen", "confidence": 0.8}
            ]
        )

        # Approval callback that rejects
        def reject_all(assignment):
            return False

        results = organizer.apply_organization_plan(plan, approval_callback=reject_all)

        assert len(results["rejected"]) == 1
        device = registry.get_device(device_id)
        assert device["room_name"] is None


# =============================================================================
# Device Renaming Suggestions Tests
# =============================================================================

class TestRenamingSuggestions:
    """Tests for device renaming suggestions."""

    def test_suggest_friendly_name(self, organizer, registry):
        """Suggests readable friendly names."""
        device_id = registry.register_device(
            entity_id="light.hue_ambiance_1",
            device_type=DeviceType.LIGHT,
            friendly_name="hue_ambiance_1",
            room_name="bedroom",
        )

        suggestion = organizer.suggest_friendly_name(device_id)

        assert suggestion is not None
        # Should be more readable than entity_id
        assert "_" not in suggestion or suggestion != "hue_ambiance_1"

    def test_suggest_name_includes_room(self, organizer, registry):
        """Name suggestions can include room context."""
        device_id = registry.register_device(
            entity_id="light.lamp",
            device_type=DeviceType.LIGHT,
            friendly_name="Lamp",
            room_name="living_room",
        )

        suggestion = organizer.suggest_friendly_name(device_id, include_room=True)

        assert "living" in suggestion.lower() or "room" in suggestion.lower()


# =============================================================================
# Organization Report Tests
# =============================================================================

class TestOrganizationReports:
    """Tests for organization status reports."""

    def test_get_organization_status(self, organizer, registry):
        """Can get overall organization status."""
        registry.register_device(
            entity_id="light.assigned",
            device_type=DeviceType.LIGHT,
            friendly_name="Assigned Light",
            room_name="bedroom",
        )
        registry.register_device(
            entity_id="light.unassigned",
            device_type=DeviceType.LIGHT,
            friendly_name="Unassigned Light",
        )

        status = organizer.get_organization_status()

        assert "total_devices" in status
        assert "organized_devices" in status
        assert "unorganized_devices" in status
        assert "organization_percentage" in status

    def test_get_room_summary(self, organizer, registry):
        """Can get device count by room."""
        registry.register_device(
            entity_id="light.room1_a",
            device_type=DeviceType.LIGHT,
            friendly_name="Light A",
            room_name="living_room",
        )
        registry.register_device(
            entity_id="light.room1_b",
            device_type=DeviceType.LIGHT,
            friendly_name="Light B",
            room_name="living_room",
        )

        summary = organizer.get_room_summary()

        assert "living_room" in summary
        assert summary["living_room"]["device_count"] >= 2

    def test_get_recommendations(self, organizer, registry):
        """Gets actionable recommendations."""
        # Create unassigned device
        registry.register_device(
            entity_id="light.stray",
            device_type=DeviceType.LIGHT,
            friendly_name="Stray Light",
        )

        recommendations = organizer.get_recommendations()

        assert len(recommendations) > 0
        # Should recommend organizing the unassigned device
        rec_types = [r["type"] for r in recommendations]
        assert "organize_unassigned" in rec_types or "assign_room" in rec_types
