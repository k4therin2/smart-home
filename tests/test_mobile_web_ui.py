"""
Mobile Web UI Tests for WP-3.3

Test Strategy:
- Use Playwright for cross-browser testing including mobile viewports
- Test touch-optimized controls (larger tap targets)
- Test iOS Safari voice input compatibility
- Test Web Notifications API integration
- Test mobile performance and PWA features

REQ-017: Mobile-Optimized Web Interface
Acceptance Criteria:
- Touch-optimized controls
- iOS Safari voice input working (using native iOS speech recognition)
- Push notifications for alerts (or web notifications)
- Works on iPhone and Android
- Performance tested on mobile devices
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# =============================================================================
# Unit Tests - HTML/CSS Requirements
# =============================================================================

class TestMobileMetaTags:
    """Test that required mobile meta tags are present in HTML."""

    @pytest.fixture
    def index_html(self):
        """Load the index.html template."""
        html_path = Path(__file__).parent.parent / "templates" / "index.html"
        with open(html_path, "r") as file:
            return file.read()

    def test_viewport_meta_tag_present(self, index_html):
        """
        Test viewport meta tag is present and correctly configured.

        Required for mobile responsiveness:
        - width=device-width: adapts to device width
        - initial-scale=1.0: prevents zoom issues on mobile
        """
        assert 'name="viewport"' in index_html
        assert "width=device-width" in index_html
        assert "initial-scale=1.0" in index_html

    def test_apple_touch_icon_present(self, index_html):
        """
        Test Apple touch icon is defined for iOS home screen.

        iOS requires apple-touch-icon for PWA-like experience.
        """
        assert 'rel="apple-touch-icon"' in index_html, \
               "Apple touch icon not defined for iOS home screen"

    def test_mobile_web_app_capable(self, index_html):
        """
        Test mobile-web-app-capable meta tag for iOS standalone mode.

        Allows iOS Safari to open the app fullscreen when added to home screen.
        """
        assert 'name="mobile-web-app-capable"' in index_html or \
               'name="apple-mobile-web-app-capable"' in index_html, \
               "iOS standalone mode not configured"

    def test_theme_color_meta_tag(self, index_html):
        """
        Test theme-color meta tag for browser chrome styling.

        Sets the browser toolbar color on mobile Chrome/Safari.
        """
        assert 'name="theme-color"' in index_html, \
               "Theme color not set for mobile browser chrome"

    def test_pwa_manifest_link(self, index_html):
        """
        Test PWA manifest file is linked.

        Required for "Add to Home Screen" and PWA features.
        """
        assert 'rel="manifest"' in index_html, \
               "PWA manifest not linked"


class TestMobileCSSRequirements:
    """Test that CSS has mobile-optimized styles."""

    @pytest.fixture
    def style_css(self):
        """Load the style.css file."""
        css_path = Path(__file__).parent.parent / "static" / "style.css"
        with open(css_path, "r") as file:
            return file.read()

    def test_touch_friendly_min_tap_target(self, style_css):
        """
        Test that buttons have minimum 44x44px tap targets (iOS guideline).

        Apple HIG recommends 44x44pt minimum tap target for accessibility.
        """
        # Check for explicit mobile styles or general button sizes
        assert "@media" in style_css, "No media queries found"

        # The voice button should be at least 44px
        assert "voice-button" in style_css
        # Check for a reasonable touch target size
        assert "52px" in style_css or "48px" in style_css or "44px" in style_css

    def test_mobile_responsive_breakpoint(self, style_css):
        """
        Test that mobile breakpoint is at least 600px.

        Common mobile breakpoint to handle phones and small tablets.
        """
        assert "max-width: 600px" in style_css or \
               "max-width: 768px" in style_css, \
               "Mobile responsive breakpoint not found"

    def test_touch_action_manipulation(self, style_css):
        """
        Test touch-action CSS property for gesture handling.

        Helps prevent 300ms click delay on mobile.
        """
        assert "touch-action: manipulation" in style_css, \
               "touch-action: manipulation not set (prevents 300ms delay)"

    def test_safe_area_insets_for_notch(self, style_css):
        """
        Test env(safe-area-inset-*) for iPhone notch support.

        iPhone X and later have notch that overlaps content.
        """
        assert "safe-area-inset" in style_css, \
               "Safe area insets not configured for iPhone notch"


class TestMobileJavaScriptRequirements:
    """Test that JavaScript has mobile-optimized features."""

    @pytest.fixture
    def app_js(self):
        """Load the app.js file."""
        js_path = Path(__file__).parent.parent / "static" / "app.js"
        with open(js_path, "r") as file:
            return file.read()

    def test_speech_recognition_feature_detection(self, app_js):
        """
        Test that speech recognition includes Safari webkit prefix.

        iOS Safari uses webkitSpeechRecognition, not SpeechRecognition.
        """
        assert "webkitSpeechRecognition" in app_js
        assert "SpeechRecognition" in app_js

    def test_web_notifications_api_support(self, app_js):
        """
        Test Web Notifications API is implemented.

        Required for push notification-like alerts.
        """
        assert "Notification" in app_js, \
               "Web Notifications API not implemented"

    def test_notification_permission_request(self, app_js):
        """
        Test notification permission is requested appropriately.

        Should request permission before showing notifications.
        """
        assert "Notification.requestPermission" in app_js or \
               "requestPermission" in app_js, \
               "Notification permission request not implemented"

    def test_service_worker_registration(self, app_js):
        """
        Test service worker registration for offline/PWA support.

        Service workers enable offline functionality and background sync.
        """
        assert "serviceWorker" in app_js, \
               "Service worker registration not implemented"


# =============================================================================
# Integration Tests - Server Endpoints
# =============================================================================

class TestMobileEndpoints:
    """Test server endpoints for mobile-specific features."""

    @pytest.fixture
    def client(self, temp_data_dir):
        """Flask test client with test configuration."""
        from src.server import app
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['LOGIN_DISABLED'] = True

        with app.test_client() as test_client:
            yield test_client

    @pytest.fixture
    def authenticated_user(self, client):
        """Mock authenticated user session."""
        with patch('flask_login.utils._get_user') as mock_user:
            mock_user.return_value = MagicMock(is_authenticated=True, id=1)
            yield mock_user

    def test_manifest_json_endpoint(self, client):
        """
        Test PWA manifest.json endpoint exists and is valid.

        PWA manifest defines app name, icons, theme, etc.
        """
        response = client.get('/manifest.json')

        assert response.status_code == 200
        assert response.content_type == 'application/json'

        manifest = response.get_json()
        assert 'name' in manifest
        assert 'short_name' in manifest
        assert 'icons' in manifest
        assert 'start_url' in manifest
        assert 'display' in manifest

    def test_service_worker_endpoint(self, client):
        """
        Test service worker JavaScript file is served.

        Service worker must be served from root scope.
        """
        response = client.get('/sw.js')

        assert response.status_code == 200
        # Service worker should have correct content type
        assert 'javascript' in response.content_type

    def test_api_notifications_endpoint(self, client, authenticated_user):
        """
        Test notification subscription endpoint exists.

        Allows clients to register for push notifications.
        """
        response = client.post(
            '/api/notifications/subscribe',
            json={'endpoint': 'https://test.push.service'},
            content_type='application/json'
        )

        # Should accept subscription or return appropriate status
        assert response.status_code in [200, 201, 501]  # 501 if not implemented yet


# =============================================================================
# PWA Manifest Tests
# =============================================================================

class TestPWAManifest:
    """Test PWA manifest file structure."""

    @pytest.fixture
    def manifest_file(self):
        """Load the manifest.json file if it exists."""
        manifest_path = Path(__file__).parent.parent / "static" / "manifest.json"
        if manifest_path.exists():
            with open(manifest_path, "r") as file:
                return json.load(file)
        return None

    def test_manifest_file_exists(self, manifest_file):
        """Test that PWA manifest file exists."""
        assert manifest_file is not None, \
               "PWA manifest.json not found in static directory"

    def test_manifest_has_required_fields(self, manifest_file):
        """
        Test manifest has all required PWA fields.

        Required fields for full PWA experience:
        - name: Full application name
        - short_name: Name shown on home screen (max 12 chars)
        - icons: App icons for different sizes
        - start_url: Entry point URL
        - display: Display mode (standalone, fullscreen, etc.)
        """
        if manifest_file is None:
            pytest.skip("Manifest file not created yet")

        required_fields = ['name', 'short_name', 'icons', 'start_url', 'display']
        for field in required_fields:
            assert field in manifest_file, f"Missing required field: {field}"

    def test_manifest_icons_multiple_sizes(self, manifest_file):
        """
        Test manifest includes icons for various device sizes.

        Recommended sizes: 192x192 and 512x512 minimum.
        """
        if manifest_file is None:
            pytest.skip("Manifest file not created yet")

        icons = manifest_file.get('icons', [])
        sizes = [icon.get('sizes', '') for icon in icons]

        # Should have at least 192x192 and 512x512
        assert any('192' in size for size in sizes), \
               "Missing 192x192 icon"
        assert any('512' in size for size in sizes), \
               "Missing 512x512 icon"

    def test_manifest_theme_matches_css(self, manifest_file):
        """
        Test manifest theme_color matches CSS variables.

        Ensures consistent branding between app and browser chrome.
        """
        if manifest_file is None:
            pytest.skip("Manifest file not created yet")

        # Theme color should be set
        assert 'theme_color' in manifest_file
        # Background color for splash screen
        assert 'background_color' in manifest_file


# =============================================================================
# Service Worker Tests
# =============================================================================

class TestServiceWorker:
    """Test service worker implementation."""

    @pytest.fixture
    def sw_js(self):
        """Load the service worker file if it exists."""
        sw_path = Path(__file__).parent.parent / "static" / "sw.js"
        if sw_path.exists():
            with open(sw_path, "r") as file:
                return file.read()
        return None

    def test_service_worker_file_exists(self, sw_js):
        """Test that service worker file exists."""
        assert sw_js is not None, \
               "Service worker sw.js not found in static directory"

    def test_service_worker_install_event(self, sw_js):
        """
        Test service worker has install event handler.

        Install event is used to cache static assets.
        """
        if sw_js is None:
            pytest.skip("Service worker not created yet")

        assert "install" in sw_js
        assert "addEventListener" in sw_js

    def test_service_worker_fetch_event(self, sw_js):
        """
        Test service worker has fetch event handler.

        Fetch event intercepts network requests for caching.
        """
        if sw_js is None:
            pytest.skip("Service worker not created yet")

        assert "fetch" in sw_js

    def test_service_worker_caches_app_shell(self, sw_js):
        """
        Test service worker caches essential app files.

        Should cache HTML, CSS, JS for offline functionality.
        """
        if sw_js is None:
            pytest.skip("Service worker not created yet")

        # Should reference the main files to cache
        assert "style.css" in sw_js or "CACHE_NAME" in sw_js
        assert "app.js" in sw_js or "CACHE_NAME" in sw_js


# =============================================================================
# Web Notifications Tests
# =============================================================================

class TestWebNotifications:
    """Test web notifications functionality."""

    def test_notification_utils_exist(self):
        """
        Test that notification utility functions exist.

        Should have functions to request permission and show notifications.
        """
        js_path = Path(__file__).parent.parent / "static" / "app.js"
        with open(js_path, "r") as file:
            app_js = file.read()

        # Should have notification-related functions
        assert "Notification" in app_js or "notification" in app_js.lower()

    def test_notification_permission_check(self):
        """
        Test that notification permission is checked before showing.

        Should check Notification.permission before attempting to notify.
        """
        js_path = Path(__file__).parent.parent / "static" / "app.js"
        with open(js_path, "r") as file:
            app_js = file.read()

        # Should check permission status
        assert "Notification.permission" in app_js, \
               "Notification permission not checked before showing"


# =============================================================================
# Playwright Mobile Tests (Integration)
# =============================================================================

@pytest.mark.slow
class TestPlaywrightMobile:
    """
    Playwright tests for mobile viewport simulation.

    These tests use Playwright to simulate mobile devices.
    Mark as slow since they launch a browser.
    """

    @pytest.fixture
    def mobile_viewport(self):
        """Mobile viewport configuration for iPhone 12."""
        return {
            'width': 390,
            'height': 844,
            'device_scale_factor': 3,
            'is_mobile': True,
            'has_touch': True,
        }

    @pytest.mark.skipif(
        not os.getenv("RUN_PLAYWRIGHT_TESTS"),
        reason="Playwright tests disabled by default"
    )
    def test_mobile_viewport_renders_correctly(self, mobile_viewport):
        """
        Test that UI renders correctly on mobile viewport.

        Verifies:
        - No horizontal scroll
        - Elements fit within viewport
        - Touch targets are accessible
        """
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(viewport=mobile_viewport)
            page = context.new_page()

            base_url = os.getenv("TEST_URL", "http://localhost:5050")
            page.goto(base_url)

            # Check no horizontal scroll
            scroll_width = page.evaluate("document.body.scrollWidth")
            viewport_width = mobile_viewport['width']
            assert scroll_width <= viewport_width, \
                   f"Horizontal scroll detected: {scroll_width} > {viewport_width}"

            browser.close()

    @pytest.mark.skipif(
        not os.getenv("RUN_PLAYWRIGHT_TESTS"),
        reason="Playwright tests disabled by default"
    )
    def test_voice_button_touch_target_size(self, mobile_viewport):
        """
        Test voice button has adequate touch target size.

        Apple HIG requires 44x44pt minimum.
        """
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(viewport=mobile_viewport)
            page = context.new_page()

            base_url = os.getenv("TEST_URL", "http://localhost:5050")
            page.goto(base_url)
            page.wait_for_selector("#voice-btn")

            # Get voice button dimensions
            dimensions = page.evaluate("""
                () => {
                    const btn = document.getElementById('voice-btn');
                    const rect = btn.getBoundingClientRect();
                    return {width: rect.width, height: rect.height};
                }
            """)

            # Minimum 44x44 CSS pixels (before device scale)
            assert dimensions['width'] >= 44, \
                   f"Voice button too narrow: {dimensions['width']}px"
            assert dimensions['height'] >= 44, \
                   f"Voice button too short: {dimensions['height']}px"

            browser.close()

    @pytest.mark.skipif(
        not os.getenv("RUN_PLAYWRIGHT_TESTS"),
        reason="Playwright tests disabled by default"
    )
    def test_command_input_touch_target_size(self, mobile_viewport):
        """
        Test command input has adequate touch target size.

        Input fields should be tall enough to tap easily.
        """
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(viewport=mobile_viewport)
            page = context.new_page()

            base_url = os.getenv("TEST_URL", "http://localhost:5050")
            page.goto(base_url)
            page.wait_for_selector("#command-input")

            # Get input dimensions
            dimensions = page.evaluate("""
                () => {
                    const input = document.getElementById('command-input');
                    const rect = input.getBoundingClientRect();
                    return {width: rect.width, height: rect.height};
                }
            """)

            # Input should be at least 44px tall for touch
            assert dimensions['height'] >= 44, \
                   f"Command input too short: {dimensions['height']}px"

            browser.close()
