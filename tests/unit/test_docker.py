"""
Tests for Docker configuration files.

WP-10.34: Docker Compose Improvements
"""

import os
import re
from pathlib import Path

import pytest
import yaml


# Get project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent


class TestDockerfile:
    """Tests for Dockerfile configuration."""

    @pytest.fixture
    def dockerfile_content(self) -> str:
        """Read Dockerfile content."""
        dockerfile_path = PROJECT_ROOT / "Dockerfile"
        assert dockerfile_path.exists(), "Dockerfile should exist"
        return dockerfile_path.read_text()

    def test_dockerfile_exists(self):
        """Dockerfile should exist in project root."""
        assert (PROJECT_ROOT / "Dockerfile").exists()

    def test_dockerfile_uses_python_312(self, dockerfile_content: str):
        """Dockerfile should use Python 3.12."""
        assert "python:3.12" in dockerfile_content

    def test_dockerfile_multi_stage_build(self, dockerfile_content: str):
        """Dockerfile should use multi-stage build for smaller image."""
        assert "FROM python:3.12-slim as builder" in dockerfile_content
        assert "FROM python:3.12-slim as production" in dockerfile_content

    def test_dockerfile_non_root_user(self, dockerfile_content: str):
        """Dockerfile should create and use non-root user."""
        assert "useradd" in dockerfile_content
        assert "USER smarthome" in dockerfile_content

    def test_dockerfile_health_check(self, dockerfile_content: str):
        """Dockerfile should include health check."""
        assert "HEALTHCHECK" in dockerfile_content
        assert "/healthz" in dockerfile_content

    def test_dockerfile_exposes_ports(self, dockerfile_content: str):
        """Dockerfile should expose HTTP and HTTPS ports."""
        assert "EXPOSE 5049 5050" in dockerfile_content

    def test_dockerfile_creates_data_directories(self, dockerfile_content: str):
        """Dockerfile should create directories for persistent data."""
        assert "/app/data" in dockerfile_content
        assert "/app/certs" in dockerfile_content
        assert "/app/logs" in dockerfile_content

    def test_dockerfile_sets_environment_defaults(self, dockerfile_content: str):
        """Dockerfile should set sensible environment defaults."""
        assert "FLASK_ENV=production" in dockerfile_content
        assert "LOG_LEVEL=INFO" in dockerfile_content


class TestDockerCompose:
    """Tests for docker-compose.yml configuration."""

    @pytest.fixture
    def compose_config(self) -> dict:
        """Parse docker-compose.yml."""
        compose_path = PROJECT_ROOT / "docker-compose.yml"
        assert compose_path.exists(), "docker-compose.yml should exist"
        with open(compose_path) as f:
            return yaml.safe_load(f)

    def test_compose_file_exists(self):
        """docker-compose.yml should exist in project root."""
        assert (PROJECT_ROOT / "docker-compose.yml").exists()

    def test_compose_has_smarthome_service(self, compose_config: dict):
        """Compose should define smarthome service."""
        assert "services" in compose_config
        assert "smarthome" in compose_config["services"]

    def test_compose_service_uses_env_file(self, compose_config: dict):
        """Service should load environment from .env file."""
        service = compose_config["services"]["smarthome"]
        assert "env_file" in service
        assert ".env" in service["env_file"]

    def test_compose_service_has_restart_policy(self, compose_config: dict):
        """Service should have restart policy."""
        service = compose_config["services"]["smarthome"]
        assert "restart" in service
        assert service["restart"] == "unless-stopped"

    def test_compose_service_has_health_check(self, compose_config: dict):
        """Service should have health check configured."""
        service = compose_config["services"]["smarthome"]
        assert "healthcheck" in service
        healthcheck = service["healthcheck"]
        assert "test" in healthcheck
        assert "/healthz" in str(healthcheck["test"])

    def test_compose_defines_volumes(self, compose_config: dict):
        """Compose should define named volumes for persistence."""
        assert "volumes" in compose_config
        volumes = compose_config["volumes"]
        assert "smarthome_data" in volumes
        assert "smarthome_certs" in volumes
        assert "smarthome_logs" in volumes

    def test_compose_mounts_volumes(self, compose_config: dict):
        """Service should mount persistent volumes."""
        service = compose_config["services"]["smarthome"]
        assert "volumes" in service
        volume_strs = [str(v) for v in service["volumes"]]
        assert any("smarthome_data" in v for v in volume_strs)
        assert any("smarthome_certs" in v for v in volume_strs)

    def test_compose_has_port_mapping(self, compose_config: dict):
        """Service should map HTTP and HTTPS ports."""
        service = compose_config["services"]["smarthome"]
        assert "ports" in service
        ports = service["ports"]
        # Check for both ports (may use variable syntax)
        port_strs = [str(p) for p in ports]
        assert len(port_strs) == 2

    def test_compose_has_resource_limits(self, compose_config: dict):
        """Service should have resource limits for stability."""
        service = compose_config["services"]["smarthome"]
        assert "deploy" in service
        assert "resources" in service["deploy"]
        resources = service["deploy"]["resources"]
        assert "limits" in resources
        assert "memory" in resources["limits"]
        assert "cpus" in resources["limits"]

    def test_compose_has_logging_config(self, compose_config: dict):
        """Service should have logging configuration."""
        service = compose_config["services"]["smarthome"]
        assert "logging" in service
        logging = service["logging"]
        assert "driver" in logging
        assert logging["driver"] == "json-file"
        assert "options" in logging
        assert "max-size" in logging["options"]

    def test_compose_has_security_options(self, compose_config: dict):
        """Service should have security hardening options."""
        service = compose_config["services"]["smarthome"]
        assert "security_opt" in service
        security_opts = service["security_opt"]
        assert "no-new-privileges:true" in security_opts


class TestDockerDevCompose:
    """Tests for docker-compose.dev.yml development override."""

    @pytest.fixture
    def dev_compose_config(self) -> dict:
        """Parse docker-compose.dev.yml."""
        dev_compose_path = PROJECT_ROOT / "docker-compose.dev.yml"
        assert dev_compose_path.exists(), "docker-compose.dev.yml should exist"
        with open(dev_compose_path) as f:
            return yaml.safe_load(f)

    def test_dev_compose_file_exists(self):
        """docker-compose.dev.yml should exist for development."""
        assert (PROJECT_ROOT / "docker-compose.dev.yml").exists()

    def test_dev_compose_sets_debug_mode(self, dev_compose_config: dict):
        """Dev compose should enable debug mode."""
        service = dev_compose_config["services"]["smarthome"]
        env = service.get("environment", [])
        env_str = str(env)
        assert "FLASK_DEBUG=true" in env_str or "debug" in env_str.lower()

    def test_dev_compose_mounts_source_code(self, dev_compose_config: dict):
        """Dev compose should bind-mount source code for hot-reload."""
        service = dev_compose_config["services"]["smarthome"]
        assert "volumes" in service
        volume_strs = [str(v) for v in service["volumes"]]
        # Check for source code mounts
        assert any("./src:" in v or "./src/" in v for v in volume_strs)


class TestDockerIgnore:
    """Tests for .dockerignore file."""

    @pytest.fixture
    def dockerignore_content(self) -> str:
        """Read .dockerignore content."""
        dockerignore_path = PROJECT_ROOT / ".dockerignore"
        assert dockerignore_path.exists(), ".dockerignore should exist"
        return dockerignore_path.read_text()

    def test_dockerignore_exists(self):
        """.dockerignore should exist."""
        assert (PROJECT_ROOT / ".dockerignore").exists()

    def test_dockerignore_excludes_git(self, dockerignore_content: str):
        """.dockerignore should exclude .git directory."""
        assert ".git" in dockerignore_content

    def test_dockerignore_excludes_venv(self, dockerignore_content: str):
        """.dockerignore should exclude virtual environment."""
        assert "venv/" in dockerignore_content or "env/" in dockerignore_content

    def test_dockerignore_excludes_tests(self, dockerignore_content: str):
        """.dockerignore should exclude tests (not needed in production)."""
        assert "tests/" in dockerignore_content

    def test_dockerignore_excludes_pycache(self, dockerignore_content: str):
        """.dockerignore should exclude Python cache files."""
        assert "__pycache__" in dockerignore_content

    def test_dockerignore_excludes_local_data(self, dockerignore_content: str):
        """.dockerignore should exclude local data files (use volumes instead)."""
        assert "data/" in dockerignore_content or "*.db" in dockerignore_content


class TestDockerDocumentation:
    """Tests for Docker documentation."""

    def test_docker_docs_exist(self):
        """Docker deployment documentation should exist."""
        docs_path = PROJECT_ROOT / "docs" / "docker-deployment.md"
        assert docs_path.exists(), "docs/docker-deployment.md should exist"

    def test_docker_docs_has_quick_start(self):
        """Docker docs should include quick start instructions."""
        docs_path = PROJECT_ROOT / "docs" / "docker-deployment.md"
        content = docs_path.read_text()
        assert "Quick Start" in content
        assert "docker-compose up" in content

    def test_docker_docs_has_configuration_section(self):
        """Docker docs should document configuration."""
        docs_path = PROJECT_ROOT / "docs" / "docker-deployment.md"
        content = docs_path.read_text()
        assert "Configuration" in content
        assert ".env" in content

    def test_docker_docs_has_volume_section(self):
        """Docker docs should document persistent volumes."""
        docs_path = PROJECT_ROOT / "docs" / "docker-deployment.md"
        content = docs_path.read_text()
        assert "Persistent" in content or "Volume" in content
        assert "smarthome_data" in content

    def test_docker_docs_has_health_check_section(self):
        """Docker docs should document health checks."""
        docs_path = PROJECT_ROOT / "docs" / "docker-deployment.md"
        content = docs_path.read_text()
        assert "Health" in content
        assert "healthz" in content or "/health" in content
