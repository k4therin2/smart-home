"""
Smart Home Assistant - Continuous Improvement Tools

Agent tools for scanning the system for improvements and managing
the improvement lifecycle (pending -> approved -> applied).

Part of WP-5.5: Continuous Improvement & Self-Optimization feature.
"""

import logging
from typing import Any

from src.improvement_manager import ImprovementManager
from src.improvement_scanner import ImprovementScanner


logger = logging.getLogger("tools.improvements")

# Singleton instances
_scanner: ImprovementScanner | None = None
_manager: ImprovementManager | None = None


def get_scanner() -> ImprovementScanner:
    """Get or create the ImprovementScanner singleton."""
    global _scanner
    if _scanner is None:
        _scanner = ImprovementScanner()
    return _scanner


def get_manager() -> ImprovementManager:
    """Get or create the ImprovementManager singleton."""
    global _manager
    if _manager is None:
        _manager = ImprovementManager()
    return _manager


# Tool definitions for Claude
IMPROVEMENT_TOOLS = [
    {
        "name": "scan_for_improvements",
        "description": """Scan the system for potential improvements and optimization opportunities.

Scans multiple areas:
- Configuration: Suboptimal settings, missing recommended values
- Dependencies: Outdated packages, security vulnerabilities
- Code patterns: Deprecated patterns, anti-patterns
- Best practices: Smart home optimizations

Use this periodically (weekly/monthly) or when requested by the user.
Returns a list of improvement suggestions with severity and fix suggestions.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "force": {
                    "type": "boolean",
                    "description": "Force scan even if interval hasn't passed",
                    "default": False,
                },
                "category": {
                    "type": "string",
                    "description": "Scan only a specific category",
                    "enum": ["configuration", "dependencies", "code", "best_practices"],
                },
            },
            "required": [],
        },
    },
    {
        "name": "list_pending_improvements",
        "description": """List all pending improvements waiting for user approval.

Returns improvements that have been found but not yet approved or rejected.
Use this to show the user what improvements are available.

Can filter by:
- Category (configuration, dependencies, security, code_quality, best_practices)
- Severity (low, medium, high, critical)""",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Filter by category"},
                "severity": {
                    "type": "string",
                    "description": "Filter by severity level",
                    "enum": ["low", "medium", "high", "critical"],
                },
            },
            "required": [],
        },
    },
    {
        "name": "approve_improvement",
        "description": """Approve an improvement for application.

After approval, the improvement can be applied to the system.
Only approve after user explicitly confirms they want to apply it.

Args:
    improvement_id: The unique ID of the improvement to approve""",
        "input_schema": {
            "type": "object",
            "properties": {
                "improvement_id": {"type": "string", "description": "The improvement ID to approve"}
            },
            "required": ["improvement_id"],
        },
    },
    {
        "name": "reject_improvement",
        "description": """Reject an improvement suggestion.

Use when the user decides they don't want to apply an improvement.
The system learns from rejections to suggest better improvements in the future.

Args:
    improvement_id: The unique ID of the improvement to reject
    reason: Optional reason for rejection (helps the system learn)""",
        "input_schema": {
            "type": "object",
            "properties": {
                "improvement_id": {"type": "string", "description": "The improvement ID to reject"},
                "reason": {
                    "type": "string",
                    "description": "Reason for rejection (optional but helpful)",
                },
            },
            "required": ["improvement_id"],
        },
    },
    {
        "name": "apply_improvement",
        "description": """Apply an approved improvement to the system.

Creates a backup before applying so it can be rolled back if needed.
Only works on improvements that have been approved.

Args:
    improvement_id: The unique ID of the approved improvement to apply""",
        "input_schema": {
            "type": "object",
            "properties": {
                "improvement_id": {"type": "string", "description": "The improvement ID to apply"}
            },
            "required": ["improvement_id"],
        },
    },
    {
        "name": "rollback_improvement",
        "description": """Rollback a previously applied improvement.

Restores the system to its state before the improvement was applied.
Only works on improvements that have been applied and have a backup.

Use this if an improvement caused problems.

Args:
    improvement_id: The unique ID of the applied improvement to rollback""",
        "input_schema": {
            "type": "object",
            "properties": {
                "improvement_id": {
                    "type": "string",
                    "description": "The improvement ID to rollback",
                }
            },
            "required": ["improvement_id"],
        },
    },
    {
        "name": "get_improvement_stats",
        "description": """Get statistics about improvements.

Shows:
- How many improvements have been approved/rejected by category
- Suggested categories to filter (based on rejection patterns)
- Overview of system optimization status

Use this to understand the user's preferences for improvements.""",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]


def scan_for_improvements(
    force: bool = False,
    category: str | None = None,
) -> dict[str, Any]:
    """
    Scan the system for potential improvements.

    Args:
        force: Force scan even if interval hasn't passed
        category: Scan only a specific category

    Returns:
        Scan results with list of improvements found
    """
    scanner = get_scanner()
    manager = get_manager()

    if category:
        # Scan only the specified category
        scan_methods = {
            "configuration": scanner.scan_configuration,
            "dependencies": scanner.scan_dependencies,
            "code": scanner.scan_code_patterns,
            "best_practices": scanner.scan_best_practices,
        }

        if category not in scan_methods:
            return {
                "success": False,
                "error": f"Unknown category: {category}. Valid: {list(scan_methods.keys())}",
            }

        try:
            improvements = scan_methods[category]()
        except Exception as exc:
            logger.error(f"Error scanning {category}: {exc}")
            return {"success": False, "error": str(exc)}
    else:
        # Run full scan
        result = scanner.run_full_scan(force=force)
        if not result.get("success"):
            return result
        improvements = result.get("improvements", [])

    # Add improvements to the manager for tracking
    added_count = 0
    for improvement in improvements:
        add_result = manager.add_improvement(improvement)
        if add_result.get("success"):
            added_count += 1

    logger.info(f"Scan complete: found {len(improvements)} improvements, added {added_count} new")

    return {
        "success": True,
        "improvements_found": len(improvements),
        "new_improvements_added": added_count,
        "improvements": improvements,
        "message": f"Found {len(improvements)} potential improvements, {added_count} are new",
    }


def list_pending_improvements(
    category: str | None = None,
    severity: str | None = None,
) -> dict[str, Any]:
    """
    List pending improvements waiting for approval.

    Args:
        category: Filter by category
        severity: Filter by severity level

    Returns:
        List of pending improvements
    """
    manager = get_manager()

    if category or severity:
        improvements = manager.get_improvements(
            status="pending",
            category=category,
            severity=severity,
        )
    else:
        improvements = manager.get_pending_improvements()

    if not improvements:
        return {"success": True, "message": "No pending improvements found", "improvements": []}

    # Format for display
    formatted = []
    for imp in improvements:
        formatted.append(
            {
                "id": imp["id"],
                "title": imp["title"],
                "category": imp["category"],
                "severity": imp["severity"],
                "description": imp.get("description", ""),
                "suggestion": imp.get("suggestion", ""),
                "auto_fixable": imp.get("auto_fixable", False),
            }
        )

    return {
        "success": True,
        "count": len(formatted),
        "improvements": formatted,
        "message": f"Found {len(formatted)} pending improvements",
    }


def approve_improvement(improvement_id: str) -> dict[str, Any]:
    """
    Approve an improvement for application.

    Args:
        improvement_id: The improvement ID to approve

    Returns:
        Result of the approval
    """
    manager = get_manager()
    result = manager.approve_improvement(improvement_id)

    if result.get("success"):
        improvement = manager.get_improvement(improvement_id)
        return {
            "success": True,
            "message": f"Approved: {improvement.get('title')}",
            "status": "approved",
            "improvement_id": improvement_id,
        }

    return result


def reject_improvement(
    improvement_id: str,
    reason: str | None = None,
) -> dict[str, Any]:
    """
    Reject an improvement suggestion.

    Args:
        improvement_id: The improvement ID to reject
        reason: Optional reason for rejection

    Returns:
        Result of the rejection
    """
    manager = get_manager()
    result = manager.reject_improvement(improvement_id, reason=reason)

    if result.get("success"):
        return {
            "success": True,
            "message": f"Rejected improvement {improvement_id}" + (f": {reason}" if reason else ""),
            "status": "rejected",
            "improvement_id": improvement_id,
        }

    return result


def apply_improvement(improvement_id: str) -> dict[str, Any]:
    """
    Apply an approved improvement.

    Args:
        improvement_id: The improvement ID to apply

    Returns:
        Result of the application
    """
    manager = get_manager()
    result = manager.apply_improvement(improvement_id)

    if result.get("success"):
        improvement = manager.get_improvement(improvement_id)
        return {
            "success": True,
            "message": f"Applied: {improvement.get('title')}",
            "status": "applied",
            "improvement_id": improvement_id,
            "backup_id": result.get("backup_id"),
            "note": "A backup was created. Use rollback_improvement if issues occur.",
        }

    return result


def rollback_improvement(improvement_id: str) -> dict[str, Any]:
    """
    Rollback a previously applied improvement.

    Args:
        improvement_id: The improvement ID to rollback

    Returns:
        Result of the rollback
    """
    manager = get_manager()
    result = manager.rollback_improvement(improvement_id)

    if result.get("success"):
        return {
            "success": True,
            "message": f"Rolled back improvement {improvement_id}",
            "status": "rolled_back",
            "improvement_id": improvement_id,
        }

    return result


def get_improvement_stats() -> dict[str, Any]:
    """
    Get statistics about improvements.

    Returns:
        Statistics about approved/rejected improvements
    """
    manager = get_manager()

    feedback_stats = manager.get_feedback_stats()
    filter_suggestions = manager.get_filter_suggestions()

    # Get counts by status
    pending = len(manager.get_improvements(status="pending"))
    approved = len(manager.get_improvements(status="approved"))
    rejected = len(manager.get_improvements(status="rejected"))
    applied = len(manager.get_improvements(status="applied"))

    return {
        "success": True,
        "status_counts": {
            "pending": pending,
            "approved": approved,
            "rejected": rejected,
            "applied": applied,
        },
        "feedback_stats": feedback_stats,
        "suggested_filters": filter_suggestions.get("suggested_filters", []),
        "message": f"Pending: {pending}, Approved: {approved}, Rejected: {rejected}, Applied: {applied}",
    }


# Handler function for agent tool calls
def handle_improvement_tool(tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
    """
    Handle improvement tool calls from the agent.

    Args:
        tool_name: Name of the tool to call
        tool_input: Tool input parameters

    Returns:
        Tool result dictionary
    """
    handlers = {
        "scan_for_improvements": scan_for_improvements,
        "list_pending_improvements": list_pending_improvements,
        "approve_improvement": approve_improvement,
        "reject_improvement": reject_improvement,
        "apply_improvement": apply_improvement,
        "rollback_improvement": rollback_improvement,
        "get_improvement_stats": get_improvement_stats,
    }

    if tool_name not in handlers:
        return {"success": False, "error": f"Unknown tool: {tool_name}"}

    try:
        return handlers[tool_name](**tool_input)
    except Exception as exc:
        logger.error(f"Error in {tool_name}: {exc}")
        return {"success": False, "error": str(exc)}
