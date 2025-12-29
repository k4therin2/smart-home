"""
Frontend Performance Tests for WP-10.25

Test Strategy:
- Test CSS minification produces valid output
- Test JS minification produces valid output
- Test build script functionality
- Test minified assets are served correctly in production mode
- Test defer attribute is present on scripts

REQ-017: Mobile-Optimized Web Interface
WP-10.25: Frontend Performance Optimization
Acceptance Criteria:
- JS bundle size reduced by 30%+
- CSS minified in production
- Images optimized and compressed
- TTI < 2 seconds on 3G connection
- Performance metrics tracked
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestBuildScript:
    """Test the asset build script functionality."""

    @pytest.fixture
    def build_module(self):
        """Import the build_assets module."""
        scripts_path = Path(__file__).parent.parent / "scripts"
        sys.path.insert(0, str(scripts_path))
        import build_assets
        return build_assets

    def test_minify_css_removes_comments(self, build_module):
        """Test CSS minification removes comments."""
        css = """
        /* This is a comment */
        .class {
            color: red; /* inline comment */
        }
        """
        minified = build_module.minify_css(css)
        assert "/*" not in minified
        assert "comment" not in minified

    def test_minify_css_removes_whitespace(self, build_module):
        """Test CSS minification removes unnecessary whitespace."""
        css = """
        .class {
            color:    red;
            margin: 0;
        }
        """
        minified = build_module.minify_css(css)
        # Should not have leading/trailing whitespace
        assert minified.strip() == minified
        # Should be more compact
        assert len(minified) < len(css)

    def test_minify_css_preserves_functionality(self, build_module):
        """Test CSS minification preserves essential content."""
        css = ".test{color:red;margin:10px}"
        minified = build_module.minify_css(css)
        assert ".test" in minified
        assert "color" in minified
        assert "red" in minified
        assert "margin" in minified
        assert "10px" in minified

    def test_minify_js_removes_comments(self, build_module):
        """Test JS minification removes comments."""
        js = """
        // Single line comment
        function test() {
            /* Multi-line
               comment */
            return true;
        }
        """
        minified = build_module.minify_js(js)
        assert "//" not in minified
        assert "/*" not in minified
        assert "Single line" not in minified
        assert "Multi-line" not in minified

    def test_minify_js_preserves_strings(self, build_module):
        """Test JS minification preserves string literals."""
        js = '''
        const msg = "Hello // World"; // real comment
        const msg2 = 'Another /* string */';
        '''
        minified = build_module.minify_js(js)
        assert '"Hello // World"' in minified
        assert "'Another /* string */'" in minified
        assert "real comment" not in minified

    def test_minify_js_preserves_functionality(self, build_module):
        """Test JS minification preserves essential code."""
        js = "function test() { return 42; }"
        minified = build_module.minify_js(js)
        assert "function" in minified
        assert "test" in minified
        assert "return" in minified
        assert "42" in minified

    def test_content_hash_is_consistent(self, build_module):
        """Test content hash is consistent for same content."""
        content = "test content"
        hash1 = build_module.get_content_hash(content)
        hash2 = build_module.get_content_hash(content)
        assert hash1 == hash2

    def test_content_hash_differs_for_different_content(self, build_module):
        """Test content hash differs for different content."""
        hash1 = build_module.get_content_hash("content a")
        hash2 = build_module.get_content_hash("content b")
        assert hash1 != hash2


class TestMinifiedAssets:
    """Test that minified assets exist and are smaller."""

    @pytest.fixture
    def static_dir(self):
        """Return static directory path."""
        return Path(__file__).parent.parent / "static"

    @pytest.fixture
    def build_dir(self):
        """Return build directory path."""
        return Path(__file__).parent.parent / "static" / "build"

    def test_build_directory_exists(self, build_dir):
        """Test build directory exists after running build script."""
        # Build should have been run - if not, this documents the need
        if not build_dir.exists():
            pytest.skip("Build directory not created - run: python scripts/build_assets.py")
        assert build_dir.is_dir()

    def test_minified_css_exists(self, build_dir):
        """Test minified CSS file exists."""
        if not build_dir.exists():
            pytest.skip("Build directory not created")
        min_css = build_dir / "style.min.css"
        assert min_css.exists(), "style.min.css not found in build directory"

    def test_minified_js_exists(self, build_dir):
        """Test minified JS files exist."""
        if not build_dir.exists():
            pytest.skip("Build directory not created")
        min_app = build_dir / "app.min.js"
        min_sw = build_dir / "sw.min.js"
        assert min_app.exists(), "app.min.js not found in build directory"
        assert min_sw.exists(), "sw.min.js not found in build directory"

    def test_minified_css_is_smaller(self, static_dir, build_dir):
        """Test minified CSS is smaller than original."""
        if not build_dir.exists():
            pytest.skip("Build directory not created")

        original = static_dir / "style.css"
        minified = build_dir / "style.min.css"

        if not original.exists() or not minified.exists():
            pytest.skip("CSS files not found")

        original_size = original.stat().st_size
        minified_size = minified.stat().st_size

        # Should be at least 20% smaller
        reduction = (original_size - minified_size) / original_size
        assert reduction > 0.2, f"CSS reduction only {reduction*100:.1f}%, expected >20%"

    def test_minified_js_is_smaller(self, static_dir, build_dir):
        """Test minified JS is smaller than original."""
        if not build_dir.exists():
            pytest.skip("Build directory not created")

        original = static_dir / "app.js"
        minified = build_dir / "app.min.js"

        if not original.exists() or not minified.exists():
            pytest.skip("JS files not found")

        original_size = original.stat().st_size
        minified_size = minified.stat().st_size

        # Should be at least 20% smaller
        reduction = (original_size - minified_size) / original_size
        assert reduction > 0.2, f"JS reduction only {reduction*100:.1f}%, expected >20%"

    def test_build_manifest_exists(self, build_dir):
        """Test build manifest is created."""
        if not build_dir.exists():
            pytest.skip("Build directory not created")

        manifest = build_dir / "build-manifest.json"
        assert manifest.exists(), "build-manifest.json not found"

        # Check manifest is valid JSON
        with open(manifest) as f:
            data = json.load(f)

        assert "version" in data
        assert "files" in data
        assert "hashes" in data


class TestTemplatePerformanceFeatures:
    """Test performance-related features in templates."""

    @pytest.fixture
    def index_html(self):
        """Load the index.html template."""
        html_path = Path(__file__).parent.parent / "templates" / "index.html"
        with open(html_path) as f:
            return f.read()

    @pytest.fixture
    def diagnostics_html(self):
        """Load the diagnostics.html template."""
        html_path = Path(__file__).parent.parent / "templates" / "diagnostics.html"
        with open(html_path) as f:
            return f.read()

    def test_script_has_defer_attribute(self, index_html):
        """Test that scripts use defer attribute for non-blocking load."""
        # Check for defer in script tags
        assert "defer" in index_html, "Script tag should have defer attribute"

    def test_production_uses_minified_css(self, index_html):
        """Test template conditionally uses minified CSS."""
        assert "style.min.css" in index_html, "Template should reference minified CSS"
        assert "USE_MINIFIED_ASSETS" in index_html, "Template should check USE_MINIFIED_ASSETS"

    def test_production_uses_minified_js(self, index_html):
        """Test template conditionally uses minified JS."""
        assert "app.min.js" in index_html, "Template should reference minified JS"

    def test_diagnostics_uses_minified_assets(self, diagnostics_html):
        """Test diagnostics page uses minified assets."""
        assert "style.min.css" in diagnostics_html
        assert "diagnostics.min.js" in diagnostics_html
        assert "defer" in diagnostics_html


class TestServerPerformanceConfig:
    """Test server configuration for performance."""

    @pytest.fixture
    def client(self, temp_data_dir):
        """Flask test client with test configuration."""
        from src.server import app
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['LOGIN_DISABLED'] = True
        app.config['USE_MINIFIED_ASSETS'] = False  # Default to source

        with app.test_client() as test_client:
            yield test_client

    @pytest.fixture
    def production_client(self, temp_data_dir):
        """Flask test client simulating production."""
        from src.server import app
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['LOGIN_DISABLED'] = True
        app.config['USE_MINIFIED_ASSETS'] = True

        with app.test_client() as test_client:
            yield test_client

    def test_service_worker_served_correctly(self, client):
        """Test service worker is served with correct headers."""
        response = client.get('/sw.js')
        assert response.status_code == 200
        assert 'javascript' in response.content_type
        assert response.headers.get('Service-Worker-Allowed') == '/'
        assert 'no-cache' in response.headers.get('Cache-Control', '')

    def test_manifest_served_correctly(self, client):
        """Test manifest.json is served correctly."""
        response = client.get('/manifest.json')
        assert response.status_code == 200
        assert response.content_type == 'application/json'


class TestPerformanceMetrics:
    """Test performance measurement utilities."""

    def test_total_asset_size_under_threshold(self):
        """Test total minified asset size is under threshold."""
        build_dir = Path(__file__).parent.parent / "static" / "build"
        if not build_dir.exists():
            pytest.skip("Build directory not created")

        total_size = 0
        for asset in ['style.min.css', 'app.min.js', 'sw.min.js']:
            asset_path = build_dir / asset
            if asset_path.exists():
                total_size += asset_path.stat().st_size

        # Total should be under 100KB for fast 3G loading
        max_size = 100 * 1024  # 100KB
        assert total_size < max_size, \
            f"Total minified size {total_size/1024:.1f}KB exceeds {max_size/1024:.0f}KB target"

    def test_css_size_under_threshold(self):
        """Test minified CSS is under size threshold."""
        css_path = Path(__file__).parent.parent / "static" / "build" / "style.min.css"
        if not css_path.exists():
            pytest.skip("Minified CSS not found")

        size = css_path.stat().st_size
        max_size = 30 * 1024  # 30KB threshold for CSS

        assert size < max_size, \
            f"CSS size {size/1024:.1f}KB exceeds {max_size/1024:.0f}KB threshold"

    def test_js_size_under_threshold(self):
        """Test minified JS is under size threshold."""
        js_path = Path(__file__).parent.parent / "static" / "build" / "app.min.js"
        if not js_path.exists():
            pytest.skip("Minified JS not found")

        size = js_path.stat().st_size
        max_size = 50 * 1024  # 50KB threshold for main JS

        assert size < max_size, \
            f"JS size {size/1024:.1f}KB exceeds {max_size/1024:.0f}KB threshold"
