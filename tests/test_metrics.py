"""
Tests for Prometheus metrics exporter (WP-10.20)

Tests cover:
- Metrics endpoint availability
- Metrics format (Prometheus text format)
- Counter, gauge, and histogram metrics
- Integration with existing tracking systems
"""

import re
import time
from unittest.mock import patch, MagicMock

import pytest


class TestMetricsEndpoint:
    """Test /metrics endpoint availability and format."""

    def test_metrics_endpoint_exists(self, client):
        """Metrics endpoint should be accessible."""
        response = client.get("/metrics")
        assert response.status_code == 200

    def test_metrics_content_type(self, client):
        """Metrics should return text/plain content type."""
        response = client.get("/metrics")
        content_type = response.content_type
        # Prometheus expects text/plain or text/plain; version=0.0.4
        assert "text/plain" in content_type

    def test_metrics_no_auth_required(self, client):
        """Metrics endpoint should not require authentication."""
        # Make request without any auth
        response = client.get("/metrics")
        # Should not redirect to login
        assert response.status_code == 200
        assert "/login" not in response.data.decode()

    def test_metrics_prometheus_format(self, client):
        """Metrics should be in Prometheus text format."""
        response = client.get("/metrics")
        data = response.data.decode()

        # Prometheus format has # HELP and # TYPE lines
        assert "# HELP" in data
        assert "# TYPE" in data

        # Should have metric lines (name{labels} value)
        lines = data.strip().split("\n")
        metric_lines = [l for l in lines if not l.startswith("#") and l.strip()]
        assert len(metric_lines) > 0


class TestRequestMetrics:
    """Test HTTP request metrics."""

    def test_http_requests_total_counter(self, client):
        """Should track total HTTP requests."""
        # Make some requests
        client.get("/healthz")
        client.get("/readyz")

        # Check metrics
        response = client.get("/metrics")
        data = response.data.decode()

        # Should have request counter
        assert "http_requests_total" in data
        assert "# TYPE smarthome_http_requests_total counter" in data

    def test_http_request_duration_histogram(self, client):
        """Should track request duration."""
        client.get("/healthz")

        response = client.get("/metrics")
        data = response.data.decode()

        # Should have duration histogram
        assert "http_request_duration_seconds" in data
        assert "# TYPE smarthome_http_request_duration_seconds histogram" in data

    def test_request_metrics_have_labels(self, client):
        """Request metrics should have method, endpoint, status labels."""
        client.get("/healthz")

        response = client.get("/metrics")
        data = response.data.decode()

        # Check for labeled metrics
        assert 'method="GET"' in data
        assert 'status="200"' in data


class TestAPIUsageMetrics:
    """Test API usage and cost metrics."""

    def test_api_cost_counter(self, client):
        """Should track API cost."""
        response = client.get("/metrics")
        data = response.data.decode()

        # Should have cost counter
        assert "api_cost_usd_total" in data
        assert "# TYPE smarthome_api_cost_usd_total counter" in data

    def test_api_tokens_counter(self, client):
        """Should track API tokens."""
        response = client.get("/metrics")
        data = response.data.decode()

        # Should have token counters
        assert "api_tokens_total" in data or "api_input_tokens_total" in data

    def test_daily_cost_gauge(self, client):
        """Should expose daily cost as gauge."""
        response = client.get("/metrics")
        data = response.data.decode()

        # Should have daily cost gauge
        assert "daily_cost_usd" in data
        assert "# TYPE smarthome_daily_cost_usd gauge" in data

    def test_api_requests_counter(self, client):
        """Should track API request count."""
        response = client.get("/metrics")
        data = response.data.decode()

        # Should have API request counter
        assert "api_requests_total" in data or "http_requests_total" in data


class TestHealthMetrics:
    """Test component health metrics."""

    def test_component_health_gauge(self, client):
        """Should expose component health status."""
        response = client.get("/metrics")
        data = response.data.decode()

        # Should have component health gauge
        assert "component_health" in data or "health_status" in data

    def test_home_assistant_latency(self, client):
        """Should track Home Assistant response time."""
        response = client.get("/metrics")
        data = response.data.decode()

        # Should have HA latency metric
        assert "home_assistant" in data.lower() or "ha_response" in data.lower()


class TestCacheMetrics:
    """Test cache performance metrics."""

    def test_cache_hit_rate_gauge(self, client):
        """Should track cache hit rate."""
        response = client.get("/metrics")
        data = response.data.decode()

        # Should have cache metrics
        assert "cache" in data.lower()

    def test_cache_size_gauge(self, client):
        """Should track cache size."""
        response = client.get("/metrics")
        data = response.data.decode()

        # Should have cache size or entries metric
        assert "cache" in data.lower()


class TestMetricsModule:
    """Test metrics module functions."""

    def test_track_request_duration(self, test_db):
        """Should track request duration correctly."""
        from src.metrics import track_request_duration, get_request_metrics

        # Track a request
        track_request_duration("GET", "/api/test", 200, 0.5)

        # Verify tracking
        metrics = get_request_metrics()
        assert metrics["total_requests"] >= 1

    def test_track_api_cost(self, test_db):
        """Should track API cost correctly."""
        from src.metrics import track_api_cost, get_cost_metrics

        # Track some cost
        track_api_cost("claude-sonnet", 0.05)

        # Verify tracking
        metrics = get_cost_metrics()
        assert metrics["total_cost"] >= 0.05

    def test_update_health_status(self, test_db):
        """Should update component health status."""
        from src.metrics import update_health_status, get_health_metrics

        # Update health status
        update_health_status("home_assistant", True, 50.0)

        # Verify
        metrics = get_health_metrics()
        assert "home_assistant" in metrics


class TestMetricsIntegration:
    """Test integration with existing systems."""

    def test_metrics_with_rate_limiter(self, client):
        """Metrics should work alongside rate limiter."""
        # Make requests within limits
        for _ in range(3):
            response = client.get("/healthz")
            assert response.status_code == 200

        # Metrics should still be accessible
        response = client.get("/metrics")
        assert response.status_code == 200

    def test_metrics_not_counted_in_rate_limit(self, client):
        """Metrics endpoint should be exempt from rate limiting."""
        # Make many metrics requests
        for _ in range(100):
            response = client.get("/metrics")
            # Should always succeed (no rate limit)
            assert response.status_code == 200
