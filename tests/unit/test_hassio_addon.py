"""
Tests for Home Assistant Add-on Configuration (WP-10.33)
"""

import os
import yaml
import pytest
from pathlib import Path


# Get the hassio-addon directory
ADDON_DIR = Path(__file__).parent.parent.parent / "hassio-addon" / "smarthome"


class TestAddonConfigYaml:
    """Test the add-on config.yaml file."""

    @pytest.fixture
    def config(self):
        """Load config.yaml."""
        with open(ADDON_DIR / "config.yaml") as f:
            return yaml.safe_load(f)

    def test_config_exists(self):
        """config.yaml should exist."""
        assert (ADDON_DIR / "config.yaml").exists()

    def test_required_fields_present(self, config):
        """Required fields should be present."""
        required = ["name", "version", "slug", "description", "arch"]
        for field in required:
            assert field in config, f"Missing required field: {field}"

    def test_name_is_string(self, config):
        """Name should be a string."""
        assert isinstance(config["name"], str)
        assert len(config["name"]) > 0

    def test_version_is_semver(self, config):
        """Version should follow semver format."""
        version = config["version"]
        parts = version.split(".")
        assert len(parts) == 3, "Version should be X.Y.Z format"

    def test_slug_is_uri_friendly(self, config):
        """Slug should be URI-friendly (lowercase, no spaces)."""
        slug = config["slug"]
        assert slug == slug.lower()
        assert " " not in slug
        assert slug.isidentifier() or slug.replace("-", "_").isidentifier()

    def test_architectures_valid(self, config):
        """Architectures should be valid HA architectures."""
        valid_archs = {"armhf", "armv7", "aarch64", "amd64", "i386"}
        for arch in config["arch"]:
            assert arch in valid_archs, f"Invalid architecture: {arch}"

    def test_includes_amd64_and_aarch64(self, config):
        """Should support both x86_64 and ARM64."""
        assert "amd64" in config["arch"]
        assert "aarch64" in config["arch"]

    def test_port_mappings_exist(self, config):
        """Port mappings should be defined."""
        assert "ports" in config
        assert "5050/tcp" in config["ports"]

    def test_webui_configured(self, config):
        """Web UI should be configured."""
        assert "webui" in config
        assert "[PORT:5050]" in config["webui"]

    def test_options_have_defaults(self, config):
        """Options should have default values."""
        assert "options" in config
        options = config["options"]
        assert "openai_model" in options
        assert "daily_cost_target" in options
        assert "log_level" in options

    def test_schema_validates_options(self, config):
        """Schema should validate all option keys."""
        assert "schema" in config
        schema = config["schema"]
        options = config["options"]
        for key in options:
            assert key in schema, f"Option {key} missing from schema"

    def test_healthcheck_configured(self, config):
        """Watchdog/healthcheck should be configured."""
        assert "watchdog" in config
        assert "healthz" in config["watchdog"]

    def test_ingress_enabled(self, config):
        """Ingress should be enabled for HA sidebar integration."""
        assert config.get("ingress") is True
        assert "ingress_port" in config

    def test_backup_mode_set(self, config):
        """Backup mode should be set."""
        assert "backup" in config
        assert config["backup"] in ["hot", "cold"]

    def test_not_privileged(self, config):
        """Add-on should not run in privileged mode by default."""
        assert config.get("privileged", False) is False


class TestAddonDockerfile:
    """Test the add-on Dockerfile."""

    @pytest.fixture
    def dockerfile_content(self):
        """Read Dockerfile content."""
        with open(ADDON_DIR / "Dockerfile") as f:
            return f.read()

    def test_dockerfile_exists(self):
        """Dockerfile should exist."""
        assert (ADDON_DIR / "Dockerfile").exists()

    def test_uses_ha_base_image(self, dockerfile_content):
        """Should use Home Assistant base image."""
        assert "home-assistant" in dockerfile_content.lower()
        assert "base-python" in dockerfile_content.lower()

    def test_has_healthcheck(self, dockerfile_content):
        """Should have HEALTHCHECK instruction."""
        assert "HEALTHCHECK" in dockerfile_content

    def test_has_labels(self, dockerfile_content):
        """Should have required labels."""
        assert "io.hass.type" in dockerfile_content
        assert "io.hass.name" in dockerfile_content

    def test_copies_requirements(self, dockerfile_content):
        """Should copy and install requirements.txt."""
        assert "requirements.txt" in dockerfile_content
        assert "pip install" in dockerfile_content

    def test_uses_workdir(self, dockerfile_content):
        """Should set a WORKDIR."""
        assert "WORKDIR" in dockerfile_content


class TestAddonRunScript:
    """Test the add-on run.sh script."""

    @pytest.fixture
    def run_script(self):
        """Read run.sh content."""
        with open(ADDON_DIR / "run.sh") as f:
            return f.read()

    def test_run_script_exists(self):
        """run.sh should exist."""
        assert (ADDON_DIR / "run.sh").exists()

    def test_uses_bashio(self, run_script):
        """Should use bashio for HA integration."""
        assert "bashio" in run_script

    def test_reads_config(self, run_script):
        """Should read configuration using bashio::config."""
        assert "bashio::config" in run_script
        assert "openai_api_key" in run_script

    def test_sets_ha_environment(self, run_script):
        """Should set HA_URL and HA_TOKEN."""
        assert "HA_URL" in run_script
        assert "SUPERVISOR_TOKEN" in run_script

    def test_starts_server(self, run_script):
        """Should start the SmartHome server."""
        assert "server.py" in run_script


class TestAddonBuildYaml:
    """Test the add-on build.yaml file."""

    @pytest.fixture
    def build_config(self):
        """Load build.yaml."""
        with open(ADDON_DIR / "build.yaml") as f:
            return yaml.safe_load(f)

    def test_build_yaml_exists(self):
        """build.yaml should exist."""
        assert (ADDON_DIR / "build.yaml").exists()

    def test_build_from_defined(self, build_config):
        """build_from should define images for each arch."""
        assert "build_from" in build_config
        build_from = build_config["build_from"]
        assert "amd64" in build_from
        assert "aarch64" in build_from

    def test_labels_defined(self, build_config):
        """Labels should be defined."""
        assert "labels" in build_config
        labels = build_config["labels"]
        assert "org.opencontainers.image.title" in labels


class TestAddonTranslations:
    """Test the add-on translations."""

    @pytest.fixture
    def en_translations(self):
        """Load English translations."""
        with open(ADDON_DIR / "translations" / "en.yaml") as f:
            return yaml.safe_load(f)

    def test_english_translations_exist(self):
        """English translations should exist."""
        assert (ADDON_DIR / "translations" / "en.yaml").exists()

    def test_all_options_have_translations(self, en_translations):
        """All config options should have translations."""
        # Load config to get options
        with open(ADDON_DIR / "config.yaml") as f:
            config = yaml.safe_load(f)

        config_section = en_translations.get("configuration", {})
        for option in config.get("options", {}).keys():
            assert option in config_section, f"Missing translation for {option}"


class TestAddonDocs:
    """Test the add-on documentation."""

    def test_docs_md_exists(self):
        """DOCS.md should exist."""
        assert (ADDON_DIR / "DOCS.md").exists()

    def test_changelog_exists(self):
        """CHANGELOG.md should exist."""
        assert (ADDON_DIR / "CHANGELOG.md").exists()

    def test_docs_has_installation(self):
        """DOCS.md should include installation instructions."""
        with open(ADDON_DIR / "DOCS.md") as f:
            content = f.read()
        assert "Installation" in content
        assert "Configuration" in content

    def test_docs_has_troubleshooting(self):
        """DOCS.md should include troubleshooting section."""
        with open(ADDON_DIR / "DOCS.md") as f:
            content = f.read()
        assert "Troubleshooting" in content


class TestRepositoryYaml:
    """Test the repository.yaml file."""

    @pytest.fixture
    def repo_config(self):
        """Load repository.yaml."""
        repo_file = ADDON_DIR.parent / "repository.yaml"
        with open(repo_file) as f:
            return yaml.safe_load(f)

    def test_repository_yaml_exists(self):
        """repository.yaml should exist."""
        assert (ADDON_DIR.parent / "repository.yaml").exists()

    def test_repository_has_name(self, repo_config):
        """Repository should have a name."""
        assert "name" in repo_config
        assert len(repo_config["name"]) > 0

    def test_repository_has_url(self, repo_config):
        """Repository should have a URL."""
        assert "url" in repo_config
        assert repo_config["url"].startswith("http")
