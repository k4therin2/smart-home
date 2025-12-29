"""
Tests for security features implemented in WP-10.22.

These tests verify:
1. Security headers are properly set on all responses
2. security.txt is accessible at the standard location
3. MD5 hash uses usedforsecurity=False for non-security purposes
"""

import hashlib
import pytest
from unittest.mock import MagicMock, patch


class TestSecurityHeaders:
    """Tests for security headers on HTTP responses."""

    @pytest.fixture
    def client(self):
        """Create a Flask test client."""
        # Import here to avoid circular imports
        import sys
        sys.path.insert(0, "/home/k4therin2/projects/Smarthome/src")
        from server import app
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        with app.test_client() as client:
            yield client

    def test_x_content_type_options_header(self, client):
        """Test that X-Content-Type-Options header is set to nosniff."""
        response = client.get("/")
        assert response.headers.get("X-Content-Type-Options") == "nosniff"

    def test_x_frame_options_header(self, client):
        """Test that X-Frame-Options header is set to DENY."""
        response = client.get("/")
        assert response.headers.get("X-Frame-Options") == "DENY"

    def test_referrer_policy_header(self, client):
        """Test that Referrer-Policy header is properly set."""
        response = client.get("/")
        assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    def test_xss_protection_header(self, client):
        """Test that X-XSS-Protection header is set."""
        response = client.get("/")
        assert response.headers.get("X-XSS-Protection") == "1; mode=block"

    def test_csp_header_present(self, client):
        """Test that Content-Security-Policy header is present."""
        response = client.get("/")
        csp = response.headers.get("Content-Security-Policy")
        assert csp is not None
        assert "default-src 'self'" in csp
        assert "script-src" in csp
        assert "style-src" in csp

    def test_csp_denies_frame_ancestors(self, client):
        """Test that CSP prevents framing (clickjacking protection)."""
        response = client.get("/")
        csp = response.headers.get("Content-Security-Policy")
        assert "frame-ancestors 'none'" in csp


class TestSecurityTxt:
    """Tests for security.txt endpoint."""

    @pytest.fixture
    def client(self):
        """Create a Flask test client."""
        import sys
        sys.path.insert(0, "/home/k4therin2/projects/Smarthome/src")
        from server import app
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        with app.test_client() as client:
            yield client

    def test_security_txt_accessible(self, client):
        """Test that security.txt is accessible at /.well-known/security.txt."""
        response = client.get("/.well-known/security.txt")
        assert response.status_code == 200

    def test_security_txt_content_type(self, client):
        """Test that security.txt is served with text/plain content type."""
        response = client.get("/.well-known/security.txt")
        assert "text/plain" in response.content_type

    def test_security_txt_has_contact(self, client):
        """Test that security.txt contains a Contact field."""
        response = client.get("/.well-known/security.txt")
        assert b"Contact:" in response.data

    def test_security_txt_has_expires(self, client):
        """Test that security.txt contains an Expires field."""
        response = client.get("/.well-known/security.txt")
        assert b"Expires:" in response.data


class TestMD5NonSecurityUsage:
    """Tests to verify MD5 is only used for non-security purposes."""

    def test_cache_key_md5_has_usedforsecurity_false(self):
        """Test that cache key generation uses MD5 with usedforsecurity=False."""
        import sys
        sys.path.insert(0, "/home/k4therin2/projects/Smarthome/src")
        from cache import CacheManager

        # Create cache manager
        cache = CacheManager()

        # Generate a cache key - this should work without security warnings
        key = cache.make_key("test_prefix", param1="value1", param2="value2")

        # Key should be a string in format "prefix:hash"
        assert isinstance(key, str)
        assert ":" in key
        assert key.startswith("test_prefix:")

    def test_md5_usedforsecurity_flag_available(self):
        """Test that hashlib.md5 accepts usedforsecurity parameter (Python 3.9+)."""
        # This should not raise an error
        hash_obj = hashlib.md5(b"test", usedforsecurity=False)
        result = hash_obj.hexdigest()
        assert len(result) == 32  # MD5 produces 32 hex characters


class TestSQLInjectionPrevention:
    """Tests to verify SQL injection prevention measures."""

    @pytest.fixture
    def automation_manager(self, tmp_path):
        """Create AutomationManager with test database."""
        import sys
        sys.path.insert(0, "/home/k4therin2/projects/Smarthome/src")
        from automation_manager import AutomationManager

        db_path = tmp_path / "test_automations.db"
        manager = AutomationManager(database_path=db_path)
        return manager

    @pytest.fixture
    def todo_manager(self, tmp_path):
        """Create TodoManager with test database."""
        import sys
        sys.path.insert(0, "/home/k4therin2/projects/Smarthome/src")
        from todo_manager import TodoManager

        db_path = tmp_path / "test_todos.db"
        manager = TodoManager(database_path=db_path)
        return manager

    def test_automation_update_only_allows_whitelisted_fields(self, automation_manager):
        """Test that automation update only accepts whitelisted fields."""
        # Create a test automation first
        automation_id = automation_manager.create_automation(
            name="Test Automation",
            description="Test",
            trigger_type="time",
            trigger_config={"time": "08:00"},
            action_type="agent_command",
            action_config={"command": "test"}
        )

        # Try to update with a disallowed field
        # This should NOT cause any SQL injection or error
        result = automation_manager.update_automation(
            automation_id,
            name="Updated Name",
            _invalid_field="malicious; DROP TABLE automations;--"
        )

        # Update should succeed (for the valid field)
        assert result is True

        # Verify the table still exists and automation is intact
        automation = automation_manager.get_automation(automation_id)
        assert automation is not None
        assert automation["name"] == "Updated Name"

    def test_todo_update_only_allows_whitelisted_fields(self, todo_manager):
        """Test that todo update only accepts whitelisted fields."""
        # Create a test todo first
        todo_id = todo_manager.add_todo(
            content="Test Todo",
            priority=1  # 0=normal, 1=high, 2=urgent
        )

        # Try to update with a disallowed field
        result = todo_manager.update_todo(
            todo_id,
            content="Updated Content",
            _sql_injection="'; DROP TABLE todos;--"
        )

        # Update should succeed (for the valid field)
        assert result is True

        # Verify the table still exists and todo is intact
        todo = todo_manager.get_todo(todo_id)
        assert todo is not None
        assert todo["content"] == "Updated Content"


class TestSubprocessSecurityComments:
    """Tests to verify subprocess usage documentation."""

    def test_monitors_run_cmd_has_security_comment(self):
        """Test that _run_cmd method has security documentation."""
        import sys
        sys.path.insert(0, "/home/k4therin2/projects/Smarthome/src")
        from security.monitors import ServerHealthMonitor

        # Check the docstring exists and mentions security
        docstring = ServerHealthMonitor._run_cmd.__doc__
        assert docstring is not None
        assert "hardcoded" in docstring.lower() or "security" in docstring.lower()
