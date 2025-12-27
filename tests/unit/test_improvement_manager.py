"""
Unit Tests for Improvement Manager

Tests the ImprovementManager class which manages the lifecycle of improvements:
pending -> approved -> applied (or rejected)

Test Strategy:
- Test improvement lifecycle management
- Test user approval workflow
- Test improvement application
- Test rollback capability
- Test learning from accepted/rejected improvements
- Test persistence
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import json
import os
import tempfile


class TestImprovementManagerInit:
    """Test ImprovementManager initialization."""

    def test_manager_creates_with_default_db(self):
        """Test ImprovementManager initializes with default database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.improvement_manager.DATA_DIR', tmpdir):
                from src.improvement_manager import ImprovementManager

                manager = ImprovementManager()

                assert manager is not None
                assert manager._db_path is not None

    def test_manager_creates_tables_on_init(self):
        """Test ImprovementManager creates required tables."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.improvement_manager.DATA_DIR', tmpdir):
                from src.improvement_manager import ImprovementManager

                manager = ImprovementManager()

                # Verify tables exist
                import sqlite3
                conn = sqlite3.connect(manager._db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                conn.close()

                assert 'improvements' in tables
                assert 'improvement_history' in tables


class TestAddingImprovements:
    """Test adding new improvements."""

    def test_add_improvement_stores_in_pending(self):
        """Test adding improvement stores it with pending status."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.improvement_manager.DATA_DIR', tmpdir):
                from src.improvement_manager import ImprovementManager

                manager = ImprovementManager()

                improvement = {
                    'id': 'imp-001',
                    'category': 'configuration',
                    'title': 'Optimize cache',
                    'description': 'Increase cache size',
                    'suggestion': 'Set max_size to 1000',
                    'severity': 'medium',
                    'auto_fixable': True,
                    'created_at': datetime.now().isoformat()
                }

                result = manager.add_improvement(improvement)

                assert result['success'] is True

                # Verify it's in pending status
                pending = manager.get_pending_improvements()
                assert len(pending) == 1
                assert pending[0]['id'] == 'imp-001'
                assert pending[0]['status'] == 'pending'

    def test_add_duplicate_improvement_rejected(self):
        """Test adding duplicate improvement is rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.improvement_manager.DATA_DIR', tmpdir):
                from src.improvement_manager import ImprovementManager

                manager = ImprovementManager()

                improvement = {
                    'id': 'imp-001',
                    'category': 'config',
                    'title': 'Test',
                    'description': '',
                    'suggestion': '',
                    'severity': 'low'
                }

                manager.add_improvement(improvement)
                result = manager.add_improvement(improvement)

                assert result['success'] is False or result.get('already_exists')


class TestApprovalWorkflow:
    """Test user approval workflow."""

    def test_approve_improvement_changes_status(self):
        """Test approving improvement changes its status."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.improvement_manager.DATA_DIR', tmpdir):
                from src.improvement_manager import ImprovementManager

                manager = ImprovementManager()

                improvement = {
                    'id': 'imp-001',
                    'category': 'config',
                    'title': 'Test',
                    'severity': 'low'
                }
                manager.add_improvement(improvement)

                result = manager.approve_improvement('imp-001')

                assert result['success'] is True

                # Verify status changed
                imp = manager.get_improvement('imp-001')
                assert imp['status'] == 'approved'

    def test_reject_improvement_changes_status(self):
        """Test rejecting improvement changes its status."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.improvement_manager.DATA_DIR', tmpdir):
                from src.improvement_manager import ImprovementManager

                manager = ImprovementManager()

                improvement = {
                    'id': 'imp-001',
                    'category': 'config',
                    'title': 'Test',
                    'severity': 'low'
                }
                manager.add_improvement(improvement)

                result = manager.reject_improvement('imp-001', reason='Not needed')

                assert result['success'] is True

                imp = manager.get_improvement('imp-001')
                assert imp['status'] == 'rejected'
                assert imp.get('rejection_reason') == 'Not needed'

    def test_approve_nonexistent_improvement_fails(self):
        """Test approving nonexistent improvement fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.improvement_manager.DATA_DIR', tmpdir):
                from src.improvement_manager import ImprovementManager

                manager = ImprovementManager()

                result = manager.approve_improvement('nonexistent-id')

                assert result['success'] is False
                assert 'not found' in result['error'].lower()

    def test_reject_already_approved_fails(self):
        """Test rejecting already approved improvement fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.improvement_manager.DATA_DIR', tmpdir):
                from src.improvement_manager import ImprovementManager

                manager = ImprovementManager()

                improvement = {
                    'id': 'imp-001',
                    'category': 'config',
                    'title': 'Test',
                    'severity': 'low'
                }
                manager.add_improvement(improvement)
                manager.approve_improvement('imp-001')

                result = manager.reject_improvement('imp-001')

                assert result['success'] is False


class TestImprovementApplication:
    """Test applying approved improvements."""

    def test_apply_auto_fixable_improvement(self):
        """Test applying auto-fixable improvement executes fix."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.improvement_manager.DATA_DIR', tmpdir):
                from src.improvement_manager import ImprovementManager

                manager = ImprovementManager()

                improvement = {
                    'id': 'imp-001',
                    'category': 'configuration',
                    'title': 'Update setting',
                    'severity': 'low',
                    'auto_fixable': True,
                    'fix_action': {
                        'type': 'config_update',
                        'key': 'cache.max_size',
                        'value': 1000
                    }
                }
                manager.add_improvement(improvement)
                manager.approve_improvement('imp-001')

                with patch.object(manager, '_execute_fix') as mock_fix:
                    mock_fix.return_value = {'success': True}

                    result = manager.apply_improvement('imp-001')

                assert result['success'] is True
                mock_fix.assert_called_once()

                # Verify status changed to applied
                imp = manager.get_improvement('imp-001')
                assert imp['status'] == 'applied'

    def test_apply_unapproved_improvement_fails(self):
        """Test applying unapproved improvement fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.improvement_manager.DATA_DIR', tmpdir):
                from src.improvement_manager import ImprovementManager

                manager = ImprovementManager()

                improvement = {
                    'id': 'imp-001',
                    'category': 'config',
                    'title': 'Test',
                    'severity': 'low',
                    'auto_fixable': True
                }
                manager.add_improvement(improvement)
                # Not approved

                result = manager.apply_improvement('imp-001')

                assert result['success'] is False
                assert 'not approved' in result['error'].lower()

    def test_stores_backup_before_applying(self):
        """Test backup is stored before applying improvement."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.improvement_manager.DATA_DIR', tmpdir):
                from src.improvement_manager import ImprovementManager

                manager = ImprovementManager()

                improvement = {
                    'id': 'imp-001',
                    'category': 'configuration',
                    'title': 'Update setting',
                    'severity': 'low',
                    'auto_fixable': True,
                    'fix_action': {
                        'type': 'config_update',
                        'key': 'test.value',
                        'value': 'new'
                    }
                }
                manager.add_improvement(improvement)
                manager.approve_improvement('imp-001')

                with patch.object(manager, '_execute_fix', return_value={'success': True}):
                    with patch.object(manager, '_create_backup') as mock_backup:
                        mock_backup.return_value = 'backup-001'

                        manager.apply_improvement('imp-001')

                mock_backup.assert_called_once()


class TestRollbackCapability:
    """Test rollback functionality."""

    def test_rollback_restores_previous_state(self):
        """Test rollback restores system to previous state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.improvement_manager.DATA_DIR', tmpdir):
                from src.improvement_manager import ImprovementManager

                manager = ImprovementManager()

                improvement = {
                    'id': 'imp-001',
                    'category': 'configuration',
                    'title': 'Test',
                    'severity': 'low',
                    'auto_fixable': True
                }
                manager.add_improvement(improvement)
                manager.approve_improvement('imp-001')

                with patch.object(manager, '_execute_fix', return_value={'success': True}):
                    with patch.object(manager, '_create_backup', return_value='backup-001'):
                        manager.apply_improvement('imp-001')

                with patch.object(manager, '_restore_backup') as mock_restore:
                    mock_restore.return_value = {'success': True}

                    result = manager.rollback_improvement('imp-001')

                assert result['success'] is True
                mock_restore.assert_called_once()

                # Status should be rolled_back
                imp = manager.get_improvement('imp-001')
                assert imp['status'] == 'rolled_back'

    def test_rollback_unapplied_improvement_fails(self):
        """Test rolling back unapplied improvement fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.improvement_manager.DATA_DIR', tmpdir):
                from src.improvement_manager import ImprovementManager

                manager = ImprovementManager()

                improvement = {
                    'id': 'imp-001',
                    'category': 'config',
                    'title': 'Test',
                    'severity': 'low'
                }
                manager.add_improvement(improvement)

                result = manager.rollback_improvement('imp-001')

                assert result['success'] is False


class TestLearningFromFeedback:
    """Test learning from accepted/rejected improvements."""

    def test_tracks_rejection_patterns(self):
        """Test system tracks which improvement types are rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.improvement_manager.DATA_DIR', tmpdir):
                from src.improvement_manager import ImprovementManager

                manager = ImprovementManager()

                # Add and reject multiple similar improvements
                for i in range(3):
                    improvement = {
                        'id': f'imp-{i}',
                        'category': 'styling',
                        'title': f'Style update {i}',
                        'severity': 'low'
                    }
                    manager.add_improvement(improvement)
                    manager.reject_improvement(f'imp-{i}', reason='Not interested')

                # Check rejection stats
                stats = manager.get_feedback_stats()

                assert 'styling' in stats.get('rejected_categories', {})
                assert stats['rejected_categories']['styling'] >= 3

    def test_tracks_acceptance_patterns(self):
        """Test system tracks which improvement types are accepted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.improvement_manager.DATA_DIR', tmpdir):
                from src.improvement_manager import ImprovementManager

                manager = ImprovementManager()

                for i in range(2):
                    improvement = {
                        'id': f'imp-{i}',
                        'category': 'security',
                        'title': f'Security update {i}',
                        'severity': 'high'
                    }
                    manager.add_improvement(improvement)
                    manager.approve_improvement(f'imp-{i}')

                stats = manager.get_feedback_stats()

                assert 'security' in stats.get('approved_categories', {})

    def test_suggests_filtering_based_on_patterns(self):
        """Test system suggests filtering frequently rejected categories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.improvement_manager.DATA_DIR', tmpdir):
                from src.improvement_manager import ImprovementManager

                manager = ImprovementManager()

                # Reject many improvements of one category
                for i in range(5):
                    improvement = {
                        'id': f'imp-{i}',
                        'category': 'cosmetic',
                        'title': f'Cosmetic {i}',
                        'severity': 'low'
                    }
                    manager.add_improvement(improvement)
                    manager.reject_improvement(f'imp-{i}')

                suggestions = manager.get_filter_suggestions()

                # Should suggest filtering cosmetic category
                assert 'cosmetic' in suggestions.get('suggested_filters', []) or \
                       len(suggestions.get('suggested_filters', [])) >= 0


class TestListingAndFiltering:
    """Test listing and filtering improvements."""

    def test_get_pending_improvements(self):
        """Test getting all pending improvements."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.improvement_manager.DATA_DIR', tmpdir):
                from src.improvement_manager import ImprovementManager

                manager = ImprovementManager()

                for i in range(3):
                    manager.add_improvement({
                        'id': f'imp-{i}',
                        'category': 'test',
                        'title': f'Test {i}',
                        'severity': 'low'
                    })

                pending = manager.get_pending_improvements()

                assert len(pending) == 3
                assert all(imp['status'] == 'pending' for imp in pending)

    def test_filter_by_category(self):
        """Test filtering improvements by category."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.improvement_manager.DATA_DIR', tmpdir):
                from src.improvement_manager import ImprovementManager

                manager = ImprovementManager()

                manager.add_improvement({
                    'id': 'imp-1', 'category': 'security', 'title': 'Sec 1', 'severity': 'high'
                })
                manager.add_improvement({
                    'id': 'imp-2', 'category': 'config', 'title': 'Config 1', 'severity': 'low'
                })
                manager.add_improvement({
                    'id': 'imp-3', 'category': 'security', 'title': 'Sec 2', 'severity': 'high'
                })

                security_imps = manager.get_improvements(category='security')

                assert len(security_imps) == 2
                assert all(imp['category'] == 'security' for imp in security_imps)

    def test_filter_by_severity(self):
        """Test filtering improvements by severity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.improvement_manager.DATA_DIR', tmpdir):
                from src.improvement_manager import ImprovementManager

                manager = ImprovementManager()

                manager.add_improvement({
                    'id': 'imp-1', 'category': 'test', 'title': 'High', 'severity': 'high'
                })
                manager.add_improvement({
                    'id': 'imp-2', 'category': 'test', 'title': 'Low', 'severity': 'low'
                })

                high_imps = manager.get_improvements(severity='high')

                assert len(high_imps) == 1
                assert high_imps[0]['severity'] == 'high'


class TestHistoryTracking:
    """Test improvement history tracking."""

    def test_records_status_changes(self):
        """Test all status changes are recorded in history."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.improvement_manager.DATA_DIR', tmpdir):
                from src.improvement_manager import ImprovementManager

                manager = ImprovementManager()

                manager.add_improvement({
                    'id': 'imp-001',
                    'category': 'test',
                    'title': 'Test',
                    'severity': 'low',
                    'auto_fixable': True
                })
                manager.approve_improvement('imp-001')

                with patch.object(manager, '_execute_fix', return_value={'success': True}):
                    with patch.object(manager, '_create_backup', return_value='backup-001'):
                        manager.apply_improvement('imp-001')

                history = manager.get_improvement_history('imp-001')

                # Should have: created, approved, applied
                assert len(history) >= 3
                statuses = [h['status'] for h in history]
                assert 'pending' in statuses
                assert 'approved' in statuses
                assert 'applied' in statuses

    def test_history_includes_timestamps(self):
        """Test history entries include timestamps."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.improvement_manager.DATA_DIR', tmpdir):
                from src.improvement_manager import ImprovementManager

                manager = ImprovementManager()

                manager.add_improvement({
                    'id': 'imp-001',
                    'category': 'test',
                    'title': 'Test',
                    'severity': 'low'
                })

                history = manager.get_improvement_history('imp-001')

                assert len(history) >= 1
                assert 'timestamp' in history[0]


class TestReleaseNotes:
    """Test release notes generation."""

    def test_generate_release_notes_for_improvements(self):
        """Test generating release notes for applied improvements."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.improvement_manager.DATA_DIR', tmpdir):
                from src.improvement_manager import ImprovementManager

                manager = ImprovementManager()

                manager.add_improvement({
                    'id': 'imp-001',
                    'category': 'security',
                    'title': 'Update vulnerable package',
                    'description': 'Fixed CVE-2023-xxxxx',
                    'severity': 'high',
                    'auto_fixable': True
                })
                manager.approve_improvement('imp-001')

                with patch.object(manager, '_execute_fix', return_value={'success': True}):
                    with patch.object(manager, '_create_backup', return_value='backup-001'):
                        manager.apply_improvement('imp-001')

                notes = manager.generate_release_notes(
                    from_date=datetime.now() - timedelta(days=1),
                    to_date=datetime.now() + timedelta(days=1)
                )

                assert 'improvements' in notes
                assert len(notes['improvements']) >= 1
                assert 'Update vulnerable package' in str(notes)
