"""
Smart Home Assistant - Improvement Scanner

Scans the codebase and configuration for potential improvements
and optimization opportunities. Supports periodic scanning with
configurable intervals.

Categories:
- Configuration: Suboptimal config values, missing recommended settings
- Dependencies: Outdated packages, security vulnerabilities
- Code: Deprecated patterns, hardcoded values
- Best Practices: Lighting optimizations, automation improvements
"""

import json
import logging
import os
import re
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, TypedDict


logger = logging.getLogger("improvement_scanner")

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
SRC_DIR = PROJECT_ROOT / "src"
DATA_DIR = PROJECT_ROOT / "data"


class Improvement(TypedDict, total=False):
    """Type definition for improvement suggestions."""

    id: str
    category: str
    title: str
    description: str
    suggestion: str
    severity: str
    auto_fixable: bool
    created_at: str
    fix_action: dict[str, Any]


# Configuration thresholds for detecting suboptimal values
CONFIG_THRESHOLDS = {
    "cache": {
        "ttl_seconds": {"min": 30, "recommended": 300},
        "max_size": {"min": 100, "recommended": 1000},
    },
    "server": {
        "ssl_enabled": {"recommended": True},
    },
}

# Deprecated patterns to detect in code
DEPRECATED_PATTERNS = [
    {
        "pattern": r"os\.system\s*\(",
        "replacement": "subprocess.run()",
        "severity": "medium",
        "description": "os.system() is deprecated and insecure",
    },
    {
        "pattern": r"from collections import [^)]*Callable",
        "replacement": "from typing import Callable",
        "severity": "low",
        "description": "collections.abc.Callable should be imported from typing",
    },
    {
        "pattern": r"\.format\s*\(",
        "replacement": "f-strings",
        "severity": "low",
        "description": "Consider using f-strings for better readability",
    },
]


class ImprovementScanner:
    """
    Scans codebase and configuration for improvement opportunities.

    Supports:
    - Configuration scanning for suboptimal values
    - Dependency scanning for updates and vulnerabilities
    - Code pattern scanning for deprecated patterns
    - Best practices scanning for smart home optimizations

    Attributes:
        scan_interval_days: Minimum days between automatic scans
        _last_scan_time: Timestamp of the last completed scan
    """

    def __init__(self, scan_interval_days: int = 7):
        """
        Initialize the improvement scanner.

        Args:
            scan_interval_days: Minimum days between automatic scans (default: 7)
        """
        self.scan_interval_days = scan_interval_days
        self._last_scan_time: datetime | None = None
        self._improvement_counter = 0

    def should_scan(self, force: bool = False) -> bool:
        """
        Check if a scan should be performed.

        Args:
            force: If True, ignore the scan interval

        Returns:
            True if a scan should be performed
        """
        if force:
            return True

        if self._last_scan_time is None:
            return True

        days_since_scan = (datetime.now() - self._last_scan_time).days
        return days_since_scan >= self.scan_interval_days

    def _create_improvement(
        self,
        category: str,
        title: str,
        description: str,
        suggestion: str,
        severity: str,
        auto_fixable: bool = False,
        fix_action: dict[str, Any] | None = None,
    ) -> Improvement:
        """
        Create a new improvement suggestion with all required fields.

        Args:
            category: Category of improvement (configuration, dependencies, code, etc.)
            title: Short title describing the improvement
            description: Detailed description of the issue
            suggestion: Recommended action to resolve the issue
            severity: Severity level (low, medium, high, critical)
            auto_fixable: Whether this can be automatically fixed
            fix_action: Optional action details for auto-fix

        Returns:
            Improvement dictionary with all required fields
        """
        self._improvement_counter += 1
        improvement: Improvement = {
            "id": f"imp-{uuid.uuid4().hex[:8]}",
            "category": category,
            "title": title,
            "description": description,
            "suggestion": suggestion,
            "severity": severity,
            "auto_fixable": auto_fixable,
            "created_at": datetime.now().isoformat(),
        }
        if fix_action:
            improvement["fix_action"] = fix_action
        return improvement

    def _read_config(self) -> dict[str, Any]:
        """
        Read the current system configuration.

        Returns:
            Dictionary of configuration values

        Raises:
            FileNotFoundError: If config file doesn't exist
        """
        config = {}

        # Read from environment and config.py
        try:
            from src import config as cfg

            config["cache"] = {
                "ttl_seconds": getattr(cfg, "HA_STATE_CACHE_TTL", 10),
                "max_size": getattr(cfg, "CACHE_MAX_SIZE", 1000),
            }
            config["server"] = {
                "ssl_enabled": os.getenv("SSL_ENABLED", "false").lower() == "true",
            }
        except ImportError:
            logger.warning("Could not import config module")

        return config

    def _get_installed_packages(self) -> dict[str, str]:
        """
        Get installed Python packages and their versions.

        Returns:
            Dictionary mapping package names to versions
        """
        packages = {}
        try:
            result = subprocess.run(
                ["pip", "list", "--format=json"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                for pkg in json.loads(result.stdout):
                    packages[pkg["name"].lower()] = pkg["version"]
        except (subprocess.SubprocessError, json.JSONDecodeError) as exc:
            logger.warning(f"Failed to get installed packages: {exc}")
        return packages

    def _get_latest_versions(self) -> dict[str, str]:
        """
        Get latest versions of key packages from PyPI.

        Returns:
            Dictionary mapping package names to latest versions
        """
        # In production, this would query PyPI
        # For now, return empty dict (mocked in tests)
        return {}

    def _check_security_advisories(self) -> list[dict[str, Any]]:
        """
        Check for known security vulnerabilities in dependencies.

        Returns:
            List of security advisory objects
        """
        # In production, this would use pip-audit or safety
        # For now, return empty list (mocked in tests)
        return []

    def _scan_python_files(self) -> list[dict[str, Any]]:
        """
        Scan Python files for deprecated patterns.

        Returns:
            List of deprecated pattern findings
        """
        findings = []

        if not SRC_DIR.exists():
            return findings

        for py_file in SRC_DIR.rglob("*.py"):
            try:
                content = py_file.read_text()
                lines = content.split("\n")

                for pattern_info in DEPRECATED_PATTERNS:
                    for line_num, line in enumerate(lines, 1):
                        if re.search(pattern_info["pattern"], line):
                            findings.append(
                                {
                                    "file": str(py_file.relative_to(PROJECT_ROOT)),
                                    "line": line_num,
                                    "pattern": pattern_info["pattern"],
                                    "suggestion": pattern_info["replacement"],
                                    "severity": pattern_info["severity"],
                                    "description": pattern_info["description"],
                                }
                            )
            except (OSError, UnicodeDecodeError) as exc:
                logger.warning(f"Failed to scan {py_file}: {exc}")

        return findings

    def _get_lighting_config(self) -> dict[str, Any]:
        """
        Get current lighting configuration.

        Returns:
            Dictionary of lighting settings
        """
        try:
            from src import config as cfg

            return {
                "scenes": getattr(cfg, "VIBE_PRESETS", {}),
                "rooms": list(getattr(cfg, "ROOM_ENTITY_MAP", {}).keys()),
            }
        except ImportError:
            return {"scenes": {}, "rooms": []}

    def _get_automations(self) -> list[dict[str, Any]]:
        """
        Get configured automations.

        Returns:
            List of automation configurations
        """
        try:
            from src.automation_manager import AutomationManager

            manager = AutomationManager()
            automations = manager.get_automations()
            return automations
        except (ImportError, Exception):
            return []

    def scan_configuration(self) -> list[Improvement]:
        """
        Scan configuration for suboptimal values.

        Returns:
            List of configuration improvement suggestions
        """
        improvements = []

        try:
            config = self._read_config()
        except FileNotFoundError:
            logger.warning("Configuration file not found")
            return improvements

        # Check cache settings
        cache_config = config.get("cache", {})
        cache_ttl = cache_config.get("ttl_seconds", 0)
        if cache_ttl < CONFIG_THRESHOLDS["cache"]["ttl_seconds"]["min"]:
            improvements.append(
                self._create_improvement(
                    category="configuration",
                    title="Increase cache TTL",
                    description=f"Current cache TTL of {cache_ttl}s is too low for efficient operation",
                    suggestion=f"Increase to {CONFIG_THRESHOLDS['cache']['ttl_seconds']['recommended']}s",
                    severity="medium",
                    auto_fixable=True,
                    fix_action={
                        "type": "config_update",
                        "key": "HA_STATE_CACHE_TTL",
                        "value": CONFIG_THRESHOLDS["cache"]["ttl_seconds"]["recommended"],
                    },
                )
            )

        # Check server SSL
        server_config = config.get("server", {})
        if not server_config.get("ssl_enabled", False):
            improvements.append(
                self._create_improvement(
                    category="configuration",
                    title="Enable SSL/TLS",
                    description="SSL is not enabled, which may expose traffic on the network",
                    suggestion="Enable SSL for secure communication",
                    severity="high",
                    auto_fixable=False,
                )
            )

        return improvements

    def scan_dependencies(self) -> list[Improvement]:
        """
        Scan dependencies for updates and security issues.

        Returns:
            List of dependency improvement suggestions
        """
        improvements = []

        installed = self._get_installed_packages()
        latest = self._get_latest_versions()
        advisories = self._check_security_advisories()

        # Check for outdated packages
        for package, current_version in installed.items():
            if package in latest:
                latest_version = latest[package]
                if current_version != latest_version:
                    improvements.append(
                        self._create_improvement(
                            category="dependencies",
                            title=f"Update {package}",
                            description=f"{package} is at version {current_version}, latest is {latest_version}",
                            suggestion=f"Run: pip install --upgrade {package}",
                            severity="low",
                            auto_fixable=True,
                            fix_action={
                                "type": "pip_upgrade",
                                "package": package,
                                "version": latest_version,
                            },
                        )
                    )

        # Check for security vulnerabilities
        for advisory in advisories:
            improvements.append(
                self._create_improvement(
                    category="security",
                    title=f"Security vulnerability in {advisory['package']}",
                    description=f"Advisory: {advisory.get('advisory', 'Unknown')}",
                    suggestion=f"Update {advisory['package']} to address {advisory.get('advisory', 'the vulnerability')}",
                    severity=advisory.get("severity", "high"),
                    auto_fixable=True,
                    fix_action={
                        "type": "pip_upgrade",
                        "package": advisory["package"],
                    },
                )
            )

        return improvements

    def scan_code_patterns(self) -> list[Improvement]:
        """
        Scan code for deprecated patterns and anti-patterns.

        Returns:
            List of code improvement suggestions
        """
        improvements = []

        findings = self._scan_python_files()

        for finding in findings:
            description = finding.get(
                "description", f"Found pattern: {finding.get('pattern', 'unknown')}"
            )
            suggestion = finding.get("suggestion", "Review and update")
            severity = finding.get("severity", "low")
            file_path = finding.get("file", "unknown")
            line_num = finding.get("line", 0)

            improvements.append(
                self._create_improvement(
                    category="code_quality",
                    title=f"Deprecated pattern in {file_path}",
                    description=description,
                    suggestion=f"Line {line_num}: Use {suggestion} instead",
                    severity=severity,
                    auto_fixable=False,
                )
            )

        return improvements

    def scan_best_practices(self) -> list[Improvement]:
        """
        Scan for smart home best practices.

        Returns:
            List of best practice improvement suggestions
        """
        improvements = []

        lighting_config = self._get_lighting_config()
        scenes = lighting_config.get("scenes", {})

        # Check for circadian rhythm support
        scene_names = list(scenes.keys())
        circadian_scenes = ["morning", "evening", "night"]
        missing_circadian = [scene for scene in circadian_scenes if scene not in scene_names]

        if missing_circadian and len(scenes) > 0:
            improvements.append(
                self._create_improvement(
                    category="best_practices",
                    title="Add circadian rhythm scenes",
                    description=f"Missing scenes for circadian lighting: {', '.join(missing_circadian)}",
                    suggestion="Add time-based lighting presets for better sleep quality",
                    severity="low",
                    auto_fixable=False,
                )
            )

        # Check automations
        automations = self._get_automations()
        if len(automations) == 0:
            improvements.append(
                self._create_improvement(
                    category="best_practices",
                    title="Create automations",
                    description="No automations configured yet",
                    suggestion="Create time or trigger-based automations to automate routine tasks",
                    severity="low",
                    auto_fixable=False,
                )
            )

        return improvements

    def run_full_scan(self, force: bool = False) -> dict[str, Any]:
        """
        Run a full system scan aggregating all improvement types.

        Args:
            force: If True, run even if interval hasn't passed

        Returns:
            Dictionary with scan results:
                - success: Whether scan completed
                - improvements: List of all improvements found
                - scan_time: Timestamp of scan
                - errors: Any errors encountered
        """
        if not self.should_scan(force=force) and not force:
            return {
                "success": False,
                "message": "Scan interval not reached",
                "improvements": [],
            }

        improvements = []
        errors = []
        scan_start = datetime.now()

        # Run all scans, collecting errors but continuing on failure
        scanners = [
            ("configuration", self.scan_configuration),
            ("dependencies", self.scan_dependencies),
            ("code_patterns", self.scan_code_patterns),
            ("best_practices", self.scan_best_practices),
        ]

        for scan_name, scanner_fn in scanners:
            try:
                results = scanner_fn()
                improvements.extend(results)
            except Exception as exc:
                error_msg = f"Error in {scan_name} scan: {exc}"
                logger.error(error_msg)
                errors.append(error_msg)

        # Update last scan time
        self._last_scan_time = datetime.now()

        result = {
            "success": True,
            "improvements": improvements,
            "scan_time": scan_start.isoformat(),
            "duration_seconds": (datetime.now() - scan_start).total_seconds(),
        }

        if errors:
            result["errors"] = errors

        logger.info(
            f"Full scan completed: {len(improvements)} improvements found, {len(errors)} errors"
        )

        return result
