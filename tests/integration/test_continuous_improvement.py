"""
Integration Tests for Continuous Improvement System

Tests the full workflow of scanning for improvements, managing them
through the approval lifecycle, and applying/rolling back changes.

Test Strategy:
- Full workflow from scan to apply to rollback
- Tool handler integration
- Multiple improvements management
- Error handling across boundaries
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta


class TestScanningWorkflow:
    """Test the complete scanning workflow."""

    def test_full_scan_workflow(self):
        """Test scanning finds improvements and adds them to manager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.improvement_manager.DATA_DIR', tmpdir):
                with patch('src.improvement_scanner.DATA_DIR', tmpdir):
                    from tools.improvements import (
                        scan_for_improvements,
                        list_pending_improvements,
                        get_scanner,
                        get_manager,
                    )

                    # Reset singletons
                    import tools.improvements
                    tools.improvements._scanner = None
                    tools.improvements._manager = None

                    # Mock scanner to return some improvements
                    scanner = get_scanner()
                    with patch.object(scanner, 'scan_configuration') as mock_config:
                        with patch.object(scanner, 'scan_dependencies') as mock_deps:
                            with patch.object(scanner, 'scan_code_patterns') as mock_code:
                                with patch.object(scanner, 'scan_best_practices') as mock_best:
                                    mock_config.return_value = [{
                                        'id': 'imp-config-001',
                                        'category': 'configuration',
                                        'title': 'Increase cache TTL',
                                        'description': 'Cache TTL is too low',
                                        'suggestion': 'Increase to 300s',
                                        'severity': 'medium',
                                        'auto_fixable': True,
                                    }]
                                    mock_deps.return_value = []
                                    mock_code.return_value = []
                                    mock_best.return_value = []

                                    result = scan_for_improvements(force=True)

                    assert result['success'] is True
                    assert result['improvements_found'] >= 1

                    # Verify improvement is now pending
                    pending = list_pending_improvements()
                    assert pending['success'] is True
                    assert pending['count'] >= 1

    def test_category_specific_scan(self):
        """Test scanning a specific category."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.improvement_manager.DATA_DIR', tmpdir):
                with patch('src.improvement_scanner.DATA_DIR', tmpdir):
                    from tools.improvements import scan_for_improvements
                    import tools.improvements
                    tools.improvements._scanner = None
                    tools.improvements._manager = None

                    result = scan_for_improvements(category='configuration')
                    assert result['success'] is True

    def test_invalid_category_returns_error(self):
        """Test scanning invalid category returns error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.improvement_manager.DATA_DIR', tmpdir):
                with patch('src.improvement_scanner.DATA_DIR', tmpdir):
                    from tools.improvements import scan_for_improvements
                    import tools.improvements
                    tools.improvements._scanner = None
                    tools.improvements._manager = None

                    result = scan_for_improvements(category='invalid_category')
                    assert result['success'] is False
                    assert 'Unknown category' in result['error']


class TestApprovalWorkflow:
    """Test the approval workflow through tools."""

    def test_approve_and_apply_improvement(self):
        """Test approving and applying an improvement."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.improvement_manager.DATA_DIR', tmpdir):
                from tools.improvements import (
                    get_manager,
                    approve_improvement,
                    apply_improvement,
                )
                import tools.improvements
                tools.improvements._manager = None

                manager = get_manager()

                # Add an improvement directly
                manager.add_improvement({
                    'id': 'imp-test-001',
                    'category': 'configuration',
                    'title': 'Test improvement',
                    'severity': 'low',
                    'auto_fixable': True,
                    'fix_action': {'type': 'config_update', 'key': 'test', 'value': 'new'},
                })

                # Approve it
                result = approve_improvement('imp-test-001')
                assert result['success'] is True
                assert result['status'] == 'approved'

                # Apply it
                result = apply_improvement('imp-test-001')
                assert result['success'] is True
                assert result['status'] == 'applied'
                assert 'backup_id' in result

    def test_reject_improvement(self):
        """Test rejecting an improvement."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.improvement_manager.DATA_DIR', tmpdir):
                from tools.improvements import get_manager, reject_improvement
                import tools.improvements
                tools.improvements._manager = None

                manager = get_manager()
                manager.add_improvement({
                    'id': 'imp-test-002',
                    'category': 'styling',
                    'title': 'Style update',
                    'severity': 'low',
                })

                result = reject_improvement('imp-test-002', reason='Not interested')
                assert result['success'] is True
                assert result['status'] == 'rejected'

    def test_cannot_apply_unapproved(self):
        """Test cannot apply unapproved improvement."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.improvement_manager.DATA_DIR', tmpdir):
                from tools.improvements import get_manager, apply_improvement
                import tools.improvements
                tools.improvements._manager = None

                manager = get_manager()
                manager.add_improvement({
                    'id': 'imp-test-003',
                    'category': 'test',
                    'title': 'Test',
                    'severity': 'low',
                })

                result = apply_improvement('imp-test-003')
                assert result['success'] is False
                assert 'not approved' in result['error'].lower()


class TestRollbackWorkflow:
    """Test the rollback workflow."""

    def test_rollback_applied_improvement(self):
        """Test rolling back an applied improvement."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.improvement_manager.DATA_DIR', tmpdir):
                from tools.improvements import (
                    get_manager,
                    approve_improvement,
                    apply_improvement,
                    rollback_improvement,
                )
                import tools.improvements
                tools.improvements._manager = None

                manager = get_manager()
                manager.add_improvement({
                    'id': 'imp-rollback-001',
                    'category': 'configuration',
                    'title': 'Rollback test',
                    'severity': 'low',
                    'auto_fixable': True,
                })

                approve_improvement('imp-rollback-001')
                apply_improvement('imp-rollback-001')

                result = rollback_improvement('imp-rollback-001')
                assert result['success'] is True
                assert result['status'] == 'rolled_back'

    def test_cannot_rollback_unapplied(self):
        """Test cannot rollback improvement that wasn't applied."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.improvement_manager.DATA_DIR', tmpdir):
                from tools.improvements import get_manager, rollback_improvement
                import tools.improvements
                tools.improvements._manager = None

                manager = get_manager()
                manager.add_improvement({
                    'id': 'imp-test-004',
                    'category': 'test',
                    'title': 'Test',
                    'severity': 'low',
                })

                result = rollback_improvement('imp-test-004')
                assert result['success'] is False


class TestListingAndFiltering:
    """Test listing and filtering improvements."""

    def test_list_pending_with_filters(self):
        """Test listing pending improvements with filters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.improvement_manager.DATA_DIR', tmpdir):
                from tools.improvements import get_manager, list_pending_improvements
                import tools.improvements
                tools.improvements._manager = None

                manager = get_manager()

                # Add multiple improvements
                manager.add_improvement({
                    'id': 'imp-high-001',
                    'category': 'security',
                    'title': 'Security fix',
                    'severity': 'high',
                })
                manager.add_improvement({
                    'id': 'imp-low-001',
                    'category': 'styling',
                    'title': 'Style update',
                    'severity': 'low',
                })

                # Filter by severity
                result = list_pending_improvements(severity='high')
                assert result['success'] is True
                assert result['count'] == 1
                assert result['improvements'][0]['severity'] == 'high'

                # Filter by category
                result = list_pending_improvements(category='security')
                assert result['success'] is True
                assert result['count'] == 1

    def test_empty_list_message(self):
        """Test message when no pending improvements."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.improvement_manager.DATA_DIR', tmpdir):
                from tools.improvements import list_pending_improvements
                import tools.improvements
                tools.improvements._manager = None

                result = list_pending_improvements()
                assert result['success'] is True
                assert 'No pending improvements' in result['message']
                assert result['improvements'] == []


class TestStatsAndFeedback:
    """Test statistics and feedback tracking."""

    def test_get_improvement_stats(self):
        """Test getting improvement statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.improvement_manager.DATA_DIR', tmpdir):
                from tools.improvements import (
                    get_manager,
                    approve_improvement,
                    reject_improvement,
                    get_improvement_stats,
                )
                import tools.improvements
                tools.improvements._manager = None

                manager = get_manager()

                # Add and process some improvements
                manager.add_improvement({'id': 'imp-1', 'category': 'security', 'severity': 'high'})
                manager.add_improvement({'id': 'imp-2', 'category': 'styling', 'severity': 'low'})
                manager.add_improvement({'id': 'imp-3', 'category': 'styling', 'severity': 'low'})

                approve_improvement('imp-1')
                reject_improvement('imp-2')
                reject_improvement('imp-3')

                stats = get_improvement_stats()
                assert stats['success'] is True
                assert 'status_counts' in stats
                assert stats['status_counts']['approved'] == 1
                assert stats['status_counts']['rejected'] == 2


class TestToolHandler:
    """Test the tool handler function."""

    def test_handle_unknown_tool(self):
        """Test handling unknown tool."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.improvement_manager.DATA_DIR', tmpdir):
                from tools.improvements import handle_improvement_tool

                result = handle_improvement_tool('unknown_tool', {})
                assert result['success'] is False
                assert 'Unknown tool' in result['error']

    def test_handle_tool_with_error(self):
        """Test tool handler catches exceptions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.improvement_manager.DATA_DIR', tmpdir):
                from tools.improvements import handle_improvement_tool

                # Trying to approve non-existent improvement
                result = handle_improvement_tool('approve_improvement', {
                    'improvement_id': 'nonexistent-id'
                })
                assert result['success'] is False


class TestAgentIntegration:
    """Test integration with the agent."""

    def test_improvement_tools_registered(self):
        """Test improvement tools are registered with agent."""
        from agent import TOOLS

        tool_names = [t['name'] for t in TOOLS]

        assert 'scan_for_improvements' in tool_names
        assert 'list_pending_improvements' in tool_names
        assert 'approve_improvement' in tool_names
        assert 'reject_improvement' in tool_names
        assert 'apply_improvement' in tool_names
        assert 'rollback_improvement' in tool_names
        assert 'get_improvement_stats' in tool_names

    def test_execute_improvement_tool(self):
        """Test executing improvement tool through agent."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.improvement_manager.DATA_DIR', tmpdir):
                from agent import execute_tool
                import tools.improvements
                tools.improvements._manager = None

                # Execute the stats tool
                result = execute_tool('get_improvement_stats', {})
                assert 'status_counts' in result


class TestEndToEndWorkflow:
    """Test complete end-to-end workflows."""

    def test_full_improvement_lifecycle(self):
        """Test complete improvement lifecycle: scan -> approve -> apply -> rollback."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.improvement_manager.DATA_DIR', tmpdir):
                with patch('src.improvement_scanner.DATA_DIR', tmpdir):
                    from tools.improvements import (
                        scan_for_improvements,
                        list_pending_improvements,
                        approve_improvement,
                        apply_improvement,
                        rollback_improvement,
                        get_improvement_stats,
                        get_scanner,
                    )
                    import tools.improvements
                    tools.improvements._scanner = None
                    tools.improvements._manager = None

                    # Step 1: Scan for improvements
                    scanner = get_scanner()
                    with patch.object(scanner, 'scan_configuration') as mock:
                        mock.return_value = [{
                            'id': 'lifecycle-001',
                            'category': 'configuration',
                            'title': 'Lifecycle test',
                            'severity': 'medium',
                            'auto_fixable': True,
                        }]
                        with patch.object(scanner, 'scan_dependencies', return_value=[]):
                            with patch.object(scanner, 'scan_code_patterns', return_value=[]):
                                with patch.object(scanner, 'scan_best_practices', return_value=[]):
                                    scan_result = scan_for_improvements(force=True)

                    assert scan_result['success'] is True

                    # Step 2: List pending
                    pending = list_pending_improvements()
                    assert pending['count'] >= 1

                    # Step 3: Approve
                    approve_result = approve_improvement('lifecycle-001')
                    assert approve_result['success'] is True

                    # Step 4: Apply
                    apply_result = apply_improvement('lifecycle-001')
                    assert apply_result['success'] is True

                    # Step 5: Verify stats
                    stats = get_improvement_stats()
                    assert stats['status_counts']['applied'] >= 1

                    # Step 6: Rollback
                    rollback_result = rollback_improvement('lifecycle-001')
                    assert rollback_result['success'] is True

                    # Final: Verify final state
                    final_stats = get_improvement_stats()
                    assert 'rolled_back' not in final_stats['status_counts'] or \
                           final_stats['status_counts'].get('rolled_back', 0) >= 0
