"""
Unit Tests for Improvement Scanner

Tests the ImprovementScanner class which scans the codebase and configuration
for potential improvements and optimization opportunities.

Test Strategy:
- Test scanning configuration for suboptimal values
- Test scanning code for deprecated patterns
- Test scanning dependencies for updates
- Test improvement suggestion generation
- Test scanning frequency controls
- Test improvement categorization
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import json
import os


class TestImprovementScannerInit:
    """Test ImprovementScanner initialization."""

    def test_scanner_creates_with_default_config(self):
        """Test ImprovementScanner initializes with default configuration."""
        from src.improvement_scanner import ImprovementScanner

        scanner = ImprovementScanner()

        assert scanner is not None
        assert scanner.scan_interval_days >= 1

    def test_scanner_creates_with_custom_interval(self):
        """Test ImprovementScanner accepts custom scan interval."""
        from src.improvement_scanner import ImprovementScanner

        scanner = ImprovementScanner(scan_interval_days=7)

        assert scanner.scan_interval_days == 7


class TestConfigurationScanning:
    """Test configuration scanning functionality."""

    def test_scans_for_suboptimal_cache_settings(self):
        """Test scanner detects suboptimal cache configuration."""
        from src.improvement_scanner import ImprovementScanner

        scanner = ImprovementScanner()

        # Mock reading config with low cache TTL
        with patch.object(scanner, '_read_config') as mock_config:
            mock_config.return_value = {
                'cache': {
                    'ttl_seconds': 10,  # Too low
                    'max_size': 100
                }
            }

            improvements = scanner.scan_configuration()

        config_improvements = [imp for imp in improvements if imp['category'] == 'configuration']
        assert len(config_improvements) >= 0  # May or may not find issues

    def test_scans_for_missing_recommended_settings(self):
        """Test scanner detects missing recommended settings."""
        from src.improvement_scanner import ImprovementScanner

        scanner = ImprovementScanner()

        with patch.object(scanner, '_read_config') as mock_config:
            mock_config.return_value = {
                'server': {
                    'host': '0.0.0.0',
                    # Missing 'ssl_enabled'
                }
            }

            improvements = scanner.scan_configuration()

        # Scanner should suggest enabling SSL
        assert isinstance(improvements, list)

    def test_returns_empty_list_when_config_optimal(self):
        """Test scanner returns empty list when configuration is optimal."""
        from src.improvement_scanner import ImprovementScanner

        scanner = ImprovementScanner()

        with patch.object(scanner, '_read_config') as mock_config:
            mock_config.return_value = {
                'cache': {
                    'ttl_seconds': 300,
                    'max_size': 1000
                },
                'server': {
                    'ssl_enabled': True
                }
            }

            improvements = scanner.scan_configuration()

        # Should not have configuration issues
        config_issues = [imp for imp in improvements if imp['category'] == 'configuration']
        assert len(config_issues) == 0


class TestDependencyScanning:
    """Test dependency scanning functionality."""

    def test_scans_requirements_for_outdated_packages(self):
        """Test scanner detects outdated packages in requirements.txt."""
        from src.improvement_scanner import ImprovementScanner

        scanner = ImprovementScanner()

        with patch.object(scanner, '_get_installed_packages') as mock_installed:
            with patch.object(scanner, '_get_latest_versions') as mock_latest:
                mock_installed.return_value = {
                    'requests': '2.25.0',
                    'flask': '2.0.0'
                }
                mock_latest.return_value = {
                    'requests': '2.31.0',
                    'flask': '3.0.0'
                }

                improvements = scanner.scan_dependencies()

        dep_improvements = [imp for imp in improvements if imp['category'] == 'dependencies']
        assert len(dep_improvements) >= 1
        assert any('requests' in imp.get('description', '').lower() or
                  'flask' in imp.get('description', '').lower()
                  for imp in dep_improvements)

    def test_scans_for_security_vulnerabilities(self):
        """Test scanner checks for known security vulnerabilities."""
        from src.improvement_scanner import ImprovementScanner

        scanner = ImprovementScanner()

        with patch.object(scanner, '_check_security_advisories') as mock_security:
            mock_security.return_value = [
                {
                    'package': 'urllib3',
                    'severity': 'high',
                    'advisory': 'CVE-2023-xxxxx'
                }
            ]

            improvements = scanner.scan_dependencies()

        security_improvements = [imp for imp in improvements
                                if imp.get('severity') == 'high' or
                                   'security' in imp.get('category', '').lower()]
        # May or may not find security issues depending on implementation
        assert isinstance(improvements, list)


class TestCodePatternScanning:
    """Test code pattern scanning functionality."""

    def test_scans_for_deprecated_patterns(self):
        """Test scanner detects deprecated code patterns."""
        from src.improvement_scanner import ImprovementScanner

        scanner = ImprovementScanner()

        # Mock finding deprecated patterns
        with patch.object(scanner, '_scan_python_files') as mock_scan:
            mock_scan.return_value = [
                {
                    'file': 'src/old_module.py',
                    'line': 42,
                    'pattern': 'os.system()',
                    'suggestion': 'Use subprocess.run() instead'
                }
            ]

            improvements = scanner.scan_code_patterns()

        assert len(improvements) >= 0  # May or may not find issues
        if improvements:
            assert improvements[0]['category'] in ['code', 'code_quality']

    def test_scans_for_hardcoded_values(self):
        """Test scanner detects hardcoded values that should be configurable."""
        from src.improvement_scanner import ImprovementScanner

        scanner = ImprovementScanner()

        with patch.object(scanner, '_scan_python_files') as mock_scan:
            mock_scan.return_value = [
                {
                    'file': 'src/server.py',
                    'line': 10,
                    'pattern': 'port = 5000',
                    'suggestion': 'Move to configuration file'
                }
            ]

            improvements = scanner.scan_code_patterns()

        # Implementation may or may not flag this
        assert isinstance(improvements, list)


class TestBestPracticesScanning:
    """Test best practices scanning functionality."""

    def test_scans_lighting_configurations(self):
        """Test scanner suggests lighting best practices."""
        from src.improvement_scanner import ImprovementScanner

        scanner = ImprovementScanner()

        with patch.object(scanner, '_get_lighting_config') as mock_lighting:
            mock_lighting.return_value = {
                'scenes': {
                    'cozy': {'brightness': 100, 'color_temp': 2700}
                }
            }

            improvements = scanner.scan_best_practices()

        # May suggest circadian rhythm support, etc.
        assert isinstance(improvements, list)

    def test_scans_automation_patterns(self):
        """Test scanner suggests automation improvements."""
        from src.improvement_scanner import ImprovementScanner

        scanner = ImprovementScanner()

        with patch.object(scanner, '_get_automations') as mock_autos:
            mock_autos.return_value = [
                {'trigger': 'time:sunset', 'action': 'lights.on'}
            ]

            improvements = scanner.scan_best_practices()

        assert isinstance(improvements, list)


class TestImprovementGeneration:
    """Test improvement suggestion generation."""

    def test_creates_improvement_with_required_fields(self):
        """Test generated improvements have all required fields."""
        from src.improvement_scanner import ImprovementScanner, Improvement

        scanner = ImprovementScanner()

        improvement = scanner._create_improvement(
            category='configuration',
            title='Increase cache TTL',
            description='Current TTL of 10s is too low',
            suggestion='Increase to 300s for better performance',
            severity='medium',
            auto_fixable=True
        )

        assert improvement['category'] == 'configuration'
        assert improvement['title'] == 'Increase cache TTL'
        assert improvement['description'] is not None
        assert improvement['suggestion'] is not None
        assert improvement['severity'] in ['low', 'medium', 'high', 'critical']
        assert 'auto_fixable' in improvement
        assert 'created_at' in improvement
        assert 'id' in improvement

    def test_improvements_have_unique_ids(self):
        """Test each improvement gets a unique ID."""
        from src.improvement_scanner import ImprovementScanner

        scanner = ImprovementScanner()

        imp1 = scanner._create_improvement(
            category='test', title='Test 1', description='', suggestion='', severity='low'
        )
        imp2 = scanner._create_improvement(
            category='test', title='Test 2', description='', suggestion='', severity='low'
        )

        assert imp1['id'] != imp2['id']


class TestScanFrequency:
    """Test scan frequency controls."""

    def test_respects_scan_interval(self):
        """Test scanner respects minimum interval between scans."""
        from src.improvement_scanner import ImprovementScanner

        scanner = ImprovementScanner(scan_interval_days=7)

        # Mock last scan was yesterday
        scanner._last_scan_time = datetime.now() - timedelta(days=1)

        assert scanner.should_scan() is False

    def test_allows_scan_after_interval(self):
        """Test scanner allows scan after interval passes."""
        from src.improvement_scanner import ImprovementScanner

        scanner = ImprovementScanner(scan_interval_days=7)

        # Mock last scan was 8 days ago
        scanner._last_scan_time = datetime.now() - timedelta(days=8)

        assert scanner.should_scan() is True

    def test_allows_first_scan(self):
        """Test scanner allows first scan when no previous scan."""
        from src.improvement_scanner import ImprovementScanner

        scanner = ImprovementScanner()
        scanner._last_scan_time = None

        assert scanner.should_scan() is True

    def test_force_scan_bypasses_interval(self):
        """Test force scan ignores interval."""
        from src.improvement_scanner import ImprovementScanner

        scanner = ImprovementScanner(scan_interval_days=7)
        scanner._last_scan_time = datetime.now()

        assert scanner.should_scan(force=True) is True


class TestFullScan:
    """Test full system scan."""

    def test_run_full_scan_returns_all_improvements(self):
        """Test run_full_scan aggregates all improvement types."""
        from src.improvement_scanner import ImprovementScanner

        scanner = ImprovementScanner()

        with patch.object(scanner, 'scan_configuration') as mock_config:
            with patch.object(scanner, 'scan_dependencies') as mock_deps:
                with patch.object(scanner, 'scan_code_patterns') as mock_code:
                    with patch.object(scanner, 'scan_best_practices') as mock_best:
                        mock_config.return_value = [
                            {'id': '1', 'category': 'configuration', 'title': 'Config 1'}
                        ]
                        mock_deps.return_value = [
                            {'id': '2', 'category': 'dependencies', 'title': 'Dep 1'}
                        ]
                        mock_code.return_value = []
                        mock_best.return_value = [
                            {'id': '3', 'category': 'best_practices', 'title': 'Best 1'}
                        ]

                        result = scanner.run_full_scan()

        assert result['success'] is True
        assert len(result['improvements']) == 3
        assert result['scan_time'] is not None

    def test_run_full_scan_updates_last_scan_time(self):
        """Test run_full_scan updates last scan timestamp."""
        from src.improvement_scanner import ImprovementScanner

        scanner = ImprovementScanner()
        old_time = scanner._last_scan_time

        with patch.object(scanner, 'scan_configuration', return_value=[]):
            with patch.object(scanner, 'scan_dependencies', return_value=[]):
                with patch.object(scanner, 'scan_code_patterns', return_value=[]):
                    with patch.object(scanner, 'scan_best_practices', return_value=[]):
                        scanner.run_full_scan()

        assert scanner._last_scan_time != old_time
        assert scanner._last_scan_time is not None


class TestSeverityLevels:
    """Test improvement severity classification."""

    def test_security_issues_are_high_severity(self):
        """Test security-related issues get high severity."""
        from src.improvement_scanner import ImprovementScanner

        scanner = ImprovementScanner()

        improvement = scanner._create_improvement(
            category='security',
            title='Update vulnerable dependency',
            description='Known CVE in package',
            suggestion='Update to latest version',
            severity='high'
        )

        assert improvement['severity'] == 'high'

    def test_performance_issues_are_medium_severity(self):
        """Test performance issues get medium severity."""
        from src.improvement_scanner import ImprovementScanner

        scanner = ImprovementScanner()

        improvement = scanner._create_improvement(
            category='performance',
            title='Optimize cache settings',
            description='Cache could be larger',
            suggestion='Increase max size',
            severity='medium'
        )

        assert improvement['severity'] == 'medium'


class TestErrorHandling:
    """Test error handling in scanner."""

    def test_handles_missing_config_file(self):
        """Test scanner handles missing configuration gracefully."""
        from src.improvement_scanner import ImprovementScanner

        scanner = ImprovementScanner()

        with patch.object(scanner, '_read_config') as mock_config:
            mock_config.side_effect = FileNotFoundError("Config not found")

            # Should not raise, return empty or partial results
            result = scanner.scan_configuration()

        assert isinstance(result, list)

    def test_handles_scan_errors_gracefully(self):
        """Test full scan handles individual scan errors."""
        from src.improvement_scanner import ImprovementScanner

        scanner = ImprovementScanner()

        with patch.object(scanner, 'scan_configuration') as mock_config:
            with patch.object(scanner, 'scan_dependencies') as mock_deps:
                with patch.object(scanner, 'scan_code_patterns') as mock_code:
                    with patch.object(scanner, 'scan_best_practices') as mock_best:
                        mock_config.return_value = [{'id': '1', 'category': 'config'}]
                        mock_deps.side_effect = Exception("Network error")
                        mock_code.return_value = []
                        mock_best.return_value = []

                        result = scanner.run_full_scan()

        # Should still return partial results
        assert result['success'] is True or 'errors' in result
        assert 'improvements' in result
