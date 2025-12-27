"""
Smart Home Assistant - Device Organizer

Provides LLM-driven device organization suggestions and bulk reorganization.
Part of WP-5.2: Device Organization Assistant.
"""

import json
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from src.device_registry import DeviceRegistry, DeviceType, get_device_registry


logger = logging.getLogger(__name__)


@dataclass
class RoomSuggestion:
    """A room assignment suggestion with confidence."""

    room_name: str
    confidence: float
    reason: str = ""


@dataclass
class OrganizationPlan:
    """A plan for organizing multiple devices."""

    assignments: list[dict[str, Any]] = field(default_factory=list)
    created_at: str | None = None


# Room keywords for rule-based suggestions
ROOM_KEYWORDS = {
    "living_room": ["living", "lounge", "family", "front", "sitting", "tv", "couch"],
    "bedroom": ["bed", "bedroom", "sleep", "master"],
    "kitchen": ["kitchen", "cooking", "fridge", "oven", "stove", "pantry"],
    "bathroom": ["bath", "bathroom", "shower", "toilet", "restroom"],
    "office": ["office", "work", "desk", "study", "computer"],
    "garage": ["garage", "car", "parking", "workshop"],
    "hallway": ["hall", "hallway", "corridor", "entry", "foyer"],
    "dining_room": ["dining", "dinner", "eat"],
    "basement": ["basement", "cellar"],
    "attic": ["attic", "loft"],
    "outdoor": ["outdoor", "patio", "deck", "porch", "garden", "yard"],
    "guest_room": ["guest", "spare"],
    "laundry": ["laundry", "washer", "dryer"],
    "nursery": ["nursery", "baby", "kid", "child"],
}

# Device type to common room associations
DEVICE_TYPE_ROOMS = {
    DeviceType.VACUUM: ["living_room", "hallway"],
    DeviceType.CLIMATE: ["living_room", "bedroom"],
    DeviceType.MEDIA_PLAYER: ["living_room", "bedroom", "office"],
    DeviceType.CAMERA: ["outdoor", "garage", "hallway"],
}


class DeviceOrganizer:
    """
    Provides LLM-driven device organization suggestions.

    Features:
    - Suggests room assignments based on device name and type
    - Generates contextual questions for new devices
    - Creates and applies bulk organization plans
    - Provides organization status reports
    """

    def __init__(self, registry: DeviceRegistry | None = None):
        """
        Initialize DeviceOrganizer.

        Args:
            registry: DeviceRegistry instance (uses singleton if not provided)
        """
        self.registry = registry or get_device_registry()
        self._llm_client = None

    def _get_llm_client(self):
        """Get or create LLM client."""
        if self._llm_client is None:
            try:
                import openai

                from src.config import OPENAI_API_KEY

                if OPENAI_API_KEY:
                    self._llm_client = openai.OpenAI(api_key=OPENAI_API_KEY)
            except ImportError:
                logger.warning("OpenAI not available, using rule-based suggestions only")
        return self._llm_client

    # =========================================================================
    # Room Suggestions
    # =========================================================================

    def suggest_room(
        self,
        device_id: int,
        use_llm: bool = False,
    ) -> list[RoomSuggestion]:
        """
        Suggest room assignments for a device.

        Args:
            device_id: Device record ID
            use_llm: Whether to use LLM for enhanced suggestions

        Returns:
            List of RoomSuggestion objects sorted by confidence
        """
        device = self.registry.get_device(device_id)
        if not device:
            return []

        # Get rule-based suggestions first
        suggestions = self._get_rule_based_suggestions(device)

        # Enhance with LLM if requested and available
        if use_llm:
            llm_suggestions = self._get_llm_suggestions(device)
            suggestions = self._merge_suggestions(suggestions, llm_suggestions)

        # Sort by confidence descending
        suggestions.sort(key=lambda s: s.confidence, reverse=True)

        return suggestions

    def _get_rule_based_suggestions(self, device: dict) -> list[RoomSuggestion]:
        """Get rule-based room suggestions from device name and type."""
        suggestions = []
        name_lower = (device.get("friendly_name") or device.get("entity_id", "")).lower()
        entity_id = device.get("entity_id", "")

        # Check name against room keywords
        for room, keywords in ROOM_KEYWORDS.items():
            for keyword in keywords:
                if keyword in name_lower:
                    confidence = 0.8 if keyword == room.replace("_", "") else 0.6
                    suggestions.append(
                        RoomSuggestion(
                            room_name=room,
                            confidence=confidence,
                            reason=f"Name contains '{keyword}'",
                        )
                    )
                    break

        # Check entity_id for room hints
        if "." in entity_id:
            entity_name = entity_id.split(".")[1]
            for room, keywords in ROOM_KEYWORDS.items():
                for keyword in keywords:
                    if keyword in entity_name:
                        # Only add if not already suggested with higher confidence
                        existing = next((s for s in suggestions if s.room_name == room), None)
                        if not existing or existing.confidence < 0.7:
                            suggestions.append(
                                RoomSuggestion(
                                    room_name=room,
                                    confidence=0.7,
                                    reason=f"Entity ID contains '{keyword}'",
                                )
                            )
                        break

        # Device type associations
        device_type_str = device.get("device_type", "")
        try:
            device_type = DeviceType(device_type_str)
            if device_type in DEVICE_TYPE_ROOMS:
                for room in DEVICE_TYPE_ROOMS[device_type]:
                    existing = next((s for s in suggestions if s.room_name == room), None)
                    if not existing:
                        suggestions.append(
                            RoomSuggestion(
                                room_name=room,
                                confidence=0.3,
                                reason=f"{device_type.value} commonly found in {room}",
                            )
                        )
        except ValueError:
            pass

        # Deduplicate keeping highest confidence
        seen = {}
        for suggestion in suggestions:
            if (
                suggestion.room_name not in seen
                or seen[suggestion.room_name].confidence < suggestion.confidence
            ):
                seen[suggestion.room_name] = suggestion

        return list(seen.values())

    def _get_llm_suggestions(self, device: dict) -> list[RoomSuggestion]:
        """Get LLM-enhanced room suggestions."""
        client = self._get_llm_client()
        if not client:
            return []

        try:
            from src.config import OPENAI_MODEL

            rooms = self.registry.get_rooms()
            room_names = [r["name"] for r in rooms]

            prompt = f"""Given a smart home device with:
- Entity ID: {device.get("entity_id")}
- Friendly Name: {device.get("friendly_name")}
- Device Type: {device.get("device_type")}

Available rooms: {", ".join(room_names)}

Which room should this device be assigned to? Respond with JSON:
{{"room": "room_name", "confidence": 0.0-1.0, "reason": "explanation"}}"""

            response = client.chat.completions.create(
                model=OPENAI_MODEL, max_tokens=200, messages=[{"role": "user", "content": prompt}]
            )

            content = response.choices[0].message.content
            # Extract JSON from response
            json_match = re.search(r"\{[^}]+\}", content)
            if json_match:
                data = json.loads(json_match.group())
                return [
                    RoomSuggestion(
                        room_name=data.get("room", ""),
                        confidence=float(data.get("confidence", 0.5)),
                        reason=data.get("reason", "LLM suggestion"),
                    )
                ]
        except Exception as error:
            logger.warning(f"LLM suggestion failed: {error}")

        return []

    def _merge_suggestions(
        self, rule_based: list[RoomSuggestion], llm_based: list[RoomSuggestion]
    ) -> list[RoomSuggestion]:
        """Merge and deduplicate suggestions, preferring higher confidence."""
        all_suggestions = {}

        for suggestion in rule_based + llm_based:
            key = suggestion.room_name
            if (
                key not in all_suggestions
                or all_suggestions[key].confidence < suggestion.confidence
            ):
                all_suggestions[key] = suggestion

        return list(all_suggestions.values())

    # =========================================================================
    # Contextual Questions
    # =========================================================================

    def get_device_questions(self, device_id: int) -> list[dict[str, Any]]:
        """
        Get contextual questions for a device.

        Args:
            device_id: Device record ID

        Returns:
            List of question dicts with type, text, and suggestions
        """
        device = self.registry.get_device(device_id)
        if not device:
            return []

        questions = []

        # Room assignment question (if not assigned)
        if not device.get("room_name"):
            suggestions = self.suggest_room(device_id)
            suggested_rooms = [s.room_name for s in suggestions[:3]]

            # Add all existing rooms as options
            all_rooms = [r["name"] for r in self.registry.get_rooms()]

            questions.append(
                {
                    "type": "room",
                    "text": f"Which room is '{device.get('friendly_name')}' located in?",
                    "suggestions": suggested_rooms,
                    "options": all_rooms,
                    "required": True,
                }
            )

        # Friendly name question (if using entity_id as name)
        if device.get("friendly_name") == device.get("entity_id"):
            questions.append(
                {
                    "type": "name",
                    "text": "What should we call this device?",
                    "current": device.get("friendly_name"),
                    "suggestion": self.suggest_friendly_name(device_id),
                    "required": False,
                }
            )

        return questions

    # =========================================================================
    # Bulk Reorganization
    # =========================================================================

    def create_organization_plan(self) -> OrganizationPlan:
        """
        Create an organization plan for all unassigned devices.

        Returns:
            OrganizationPlan with suggested assignments
        """
        from datetime import datetime

        unassigned = self.registry.get_unassigned_devices()
        assignments = []

        for device in unassigned:
            suggestions = self.suggest_room(device["id"])
            if suggestions:
                best = suggestions[0]
                assignments.append(
                    {
                        "device_id": device["id"],
                        "entity_id": device["entity_id"],
                        "friendly_name": device["friendly_name"],
                        "suggested_room": best.room_name,
                        "confidence": best.confidence,
                        "reason": best.reason,
                    }
                )

        return OrganizationPlan(
            assignments=assignments,
            created_at=datetime.now().isoformat(),
        )

    def apply_organization_plan(
        self,
        plan: OrganizationPlan,
        min_confidence: float = 0.5,
        approval_callback: Callable[[dict], bool] | None = None,
    ) -> dict[str, list]:
        """
        Apply an organization plan to assign devices to rooms.

        Args:
            plan: OrganizationPlan to apply
            min_confidence: Minimum confidence threshold (0.0-1.0)
            approval_callback: Optional callback to approve each assignment

        Returns:
            Dict with 'applied', 'skipped', and 'rejected' lists
        """
        results = {
            "applied": [],
            "skipped": [],
            "rejected": [],
        }

        for assignment in plan.assignments:
            device_id = assignment["device_id"]
            confidence = assignment.get("confidence", 0)

            # Check confidence threshold
            if confidence < min_confidence:
                results["skipped"].append(assignment)
                continue

            # Check approval callback
            if approval_callback and not approval_callback(assignment):
                results["rejected"].append(assignment)
                continue

            # Apply the assignment
            success = self.registry.move_device_to_room(device_id, assignment["suggested_room"])

            if success:
                results["applied"].append(assignment)
            else:
                results["skipped"].append(assignment)

        return results

    # =========================================================================
    # Renaming Suggestions
    # =========================================================================

    def suggest_friendly_name(
        self,
        device_id: int,
        include_room: bool = False,
    ) -> str | None:
        """
        Suggest a friendly name for a device.

        Args:
            device_id: Device record ID
            include_room: Whether to include room in the name

        Returns:
            Suggested name or None
        """
        device = self.registry.get_device(device_id)
        if not device:
            return None

        entity_id = device.get("entity_id", "")
        current_name = device.get("friendly_name", "")

        # Start with entity_id name part
        if "." in entity_id:
            name = entity_id.split(".")[1]
        else:
            name = entity_id

        # Convert from snake_case to Title Case
        name = name.replace("_", " ").title()

        # Remove common prefixes
        prefixes_to_remove = ["Hue", "Philips", "Smart", "Wiz", "Tuya"]
        for prefix in prefixes_to_remove:
            if name.startswith(prefix + " "):
                name = name[len(prefix) + 1 :]

        # Clean up numeric suffixes
        name = re.sub(r"\s+\d+$", "", name)

        # Add room context if requested
        if include_room and device.get("room_name"):
            room_display = device["room_name"].replace("_", " ").title()
            name = f"{room_display} {name}"

        return name.strip() if name.strip() else current_name

    # =========================================================================
    # Organization Reports
    # =========================================================================

    def get_organization_status(self) -> dict[str, Any]:
        """
        Get overall organization status.

        Returns:
            Dict with organization statistics
        """
        stats = self.registry.get_stats()

        total = stats["total_devices"]
        organized = stats["assigned_devices"]
        unorganized = stats["unassigned_devices"]

        percentage = (organized / total * 100) if total > 0 else 100

        return {
            "total_devices": total,
            "organized_devices": organized,
            "unorganized_devices": unorganized,
            "organization_percentage": round(percentage, 1),
            "total_rooms": stats["total_rooms"],
            "devices_by_type": stats["devices_by_type"],
        }

    def get_room_summary(self) -> dict[str, dict[str, Any]]:
        """
        Get device count by room.

        Returns:
            Dict mapping room names to summary info
        """
        summary = {}
        rooms = self.registry.get_rooms()

        for room in rooms:
            room_name = room["name"]
            devices = self.registry.get_devices_by_room(room_name)

            device_types = {}
            for device in devices:
                device_type = device.get("device_type", "other")
                device_types[device_type] = device_types.get(device_type, 0) + 1

            summary[room_name] = {
                "display_name": room.get("display_name", room_name),
                "zone": room.get("zone_name"),
                "device_count": len(devices),
                "device_types": device_types,
            }

        return summary

    def get_recommendations(self) -> list[dict[str, Any]]:
        """
        Get actionable organization recommendations.

        Returns:
            List of recommendation dicts with type and details
        """
        recommendations = []

        # Check for unassigned devices
        unassigned = self.registry.get_unassigned_devices()
        if unassigned:
            recommendations.append(
                {
                    "type": "organize_unassigned",
                    "priority": "high",
                    "message": f"{len(unassigned)} device(s) need room assignment",
                    "devices": [d["entity_id"] for d in unassigned[:5]],
                    "action": "Run organization plan to assign rooms",
                }
            )

        # Check for rooms with no devices
        rooms = self.registry.get_rooms()
        for room in rooms:
            devices = self.registry.get_devices_by_room(room["name"])
            if not devices:
                recommendations.append(
                    {
                        "type": "empty_room",
                        "priority": "low",
                        "message": f"Room '{room['name']}' has no devices",
                        "action": "Consider removing unused room or adding devices",
                    }
                )

        # Check naming consistency
        validation_issues = self._check_naming_consistency()
        for issue in validation_issues:
            recommendations.append(
                {
                    "type": "naming_issue",
                    "priority": "medium",
                    "message": issue["message"],
                    "action": issue.get("suggestion", "Review device naming"),
                }
            )

        return recommendations

    def _check_naming_consistency(self) -> list[dict[str, str]]:
        """Check for naming consistency issues."""
        issues = []
        devices = self.registry.get_all_devices()

        # Check for devices still using entity_id as friendly name
        for device in devices:
            if device.get("friendly_name") == device.get("entity_id"):
                issues.append(
                    {
                        "message": f"Device '{device['entity_id']}' needs a friendly name",
                        "suggestion": f"Consider renaming to '{self.suggest_friendly_name(device['id'])}'",
                    }
                )

        return issues[:5]  # Limit to top 5 issues


# Singleton instance
_device_organizer: DeviceOrganizer | None = None


def get_device_organizer() -> DeviceOrganizer:
    """Get the singleton DeviceOrganizer instance."""
    global _device_organizer
    if _device_organizer is None:
        _device_organizer = DeviceOrganizer()
    return _device_organizer
