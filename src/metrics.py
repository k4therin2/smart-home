"""
Prometheus Metrics Exporter (WP-10.20)

Provides Prometheus-compatible metrics for monitoring the Smarthome application.

Metrics exposed:
- HTTP request counts and durations
- API usage (tokens, cost, requests)
- Component health status
- Cache performance

Usage:
    from src.metrics import init_metrics, track_request_duration, track_api_cost

    # Initialize in Flask app
    init_metrics(app)

    # Track request (usually via middleware)
    track_request_duration("GET", "/api/status", 200, 0.5)

    # Track API cost
    track_api_cost("claude-sonnet", 0.05)
"""

import time
import logging
from functools import wraps
from typing import Callable, Optional

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    CollectorRegistry,
    generate_latest,
    CONTENT_TYPE_LATEST,
    REGISTRY,
)

logger = logging.getLogger(__name__)

# Metric prefix for namespacing
METRIC_PREFIX = "smarthome"

# =============================================================================
# Prometheus Metrics Definitions
# =============================================================================

# HTTP Request metrics
HTTP_REQUESTS_TOTAL = Counter(
    f"{METRIC_PREFIX}_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

HTTP_REQUEST_DURATION = Histogram(
    f"{METRIC_PREFIX}_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# API Usage metrics
API_COST_TOTAL = Counter(
    f"{METRIC_PREFIX}_api_cost_usd_total",
    "Total API cost in USD",
    ["model"],
)

API_INPUT_TOKENS_TOTAL = Counter(
    f"{METRIC_PREFIX}_api_input_tokens_total",
    "Total API input tokens",
    ["model"],
)

API_OUTPUT_TOKENS_TOTAL = Counter(
    f"{METRIC_PREFIX}_api_output_tokens_total",
    "Total API output tokens",
    ["model"],
)

API_REQUESTS_TOTAL = Counter(
    f"{METRIC_PREFIX}_api_requests_total",
    "Total API requests",
    ["model"],
)

DAILY_COST_USD = Gauge(
    f"{METRIC_PREFIX}_daily_cost_usd",
    "Current day API cost in USD",
)

# Health metrics
COMPONENT_HEALTH = Gauge(
    f"{METRIC_PREFIX}_component_health",
    "Component health status (1=healthy, 0=unhealthy)",
    ["component"],
)

COMPONENT_LATENCY_MS = Gauge(
    f"{METRIC_PREFIX}_component_latency_ms",
    "Component response latency in milliseconds",
    ["component"],
)

HOME_ASSISTANT_RESPONSE_MS = Histogram(
    f"{METRIC_PREFIX}_home_assistant_response_ms",
    "Home Assistant response time in milliseconds",
    buckets=(10, 25, 50, 100, 250, 500, 1000, 2500, 5000),
)

# Cache metrics
CACHE_HIT_RATE = Gauge(
    f"{METRIC_PREFIX}_cache_hit_rate",
    "Cache hit rate (0.0-1.0)",
)

CACHE_SIZE = Gauge(
    f"{METRIC_PREFIX}_cache_size",
    "Current cache size (entries)",
)

CACHE_CAPACITY_RATIO = Gauge(
    f"{METRIC_PREFIX}_cache_capacity_ratio",
    "Cache capacity utilization ratio (0.0-1.0)",
)

# =============================================================================
# Tracking Functions
# =============================================================================

# Internal counters for get_*_metrics functions
_request_metrics = {
    "total_requests": 0,
    "total_duration": 0.0,
}

_cost_metrics = {
    "total_cost": 0.0,
    "total_tokens": 0,
}

_health_metrics = {}


def track_request_duration(
    method: str,
    endpoint: str,
    status: int,
    duration: float,
) -> None:
    """
    Track an HTTP request.

    Args:
        method: HTTP method (GET, POST, etc.)
        endpoint: Request path
        status: HTTP status code
        duration: Request duration in seconds
    """
    # Normalize endpoint (remove query params, IDs)
    normalized_endpoint = _normalize_endpoint(endpoint)

    HTTP_REQUESTS_TOTAL.labels(
        method=method,
        endpoint=normalized_endpoint,
        status=str(status),
    ).inc()

    HTTP_REQUEST_DURATION.labels(
        method=method,
        endpoint=normalized_endpoint,
    ).observe(duration)

    # Update internal counters
    _request_metrics["total_requests"] += 1
    _request_metrics["total_duration"] += duration


def track_api_cost(
    model: str,
    cost_usd: float,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> None:
    """
    Track API usage cost.

    Args:
        model: Model name (e.g., "claude-sonnet-4")
        cost_usd: Cost in USD
        input_tokens: Number of input tokens (optional)
        output_tokens: Number of output tokens (optional)
    """
    API_COST_TOTAL.labels(model=model).inc(cost_usd)
    API_REQUESTS_TOTAL.labels(model=model).inc()

    if input_tokens > 0:
        API_INPUT_TOKENS_TOTAL.labels(model=model).inc(input_tokens)
    if output_tokens > 0:
        API_OUTPUT_TOKENS_TOTAL.labels(model=model).inc(output_tokens)

    # Update internal counters
    _cost_metrics["total_cost"] += cost_usd
    _cost_metrics["total_tokens"] += input_tokens + output_tokens


def update_daily_cost(cost_usd: float) -> None:
    """
    Update the daily cost gauge.

    Args:
        cost_usd: Current day's total cost in USD
    """
    DAILY_COST_USD.set(cost_usd)


def update_health_status(
    component: str,
    is_healthy: bool,
    latency_ms: float = 0.0,
) -> None:
    """
    Update component health status.

    Args:
        component: Component name (e.g., "home_assistant", "database")
        is_healthy: Whether the component is healthy
        latency_ms: Component response latency in milliseconds
    """
    COMPONENT_HEALTH.labels(component=component).set(1 if is_healthy else 0)
    COMPONENT_LATENCY_MS.labels(component=component).set(latency_ms)

    # Track HA latency separately for histogram
    if component == "home_assistant" and latency_ms > 0:
        HOME_ASSISTANT_RESPONSE_MS.observe(latency_ms)

    # Update internal tracking
    _health_metrics[component] = {
        "healthy": is_healthy,
        "latency_ms": latency_ms,
    }


def update_cache_metrics(
    hit_rate: float,
    size: int,
    capacity_ratio: float,
) -> None:
    """
    Update cache performance metrics.

    Args:
        hit_rate: Cache hit rate (0.0-1.0)
        size: Current cache size
        capacity_ratio: Cache utilization ratio (0.0-1.0)
    """
    CACHE_HIT_RATE.set(hit_rate)
    CACHE_SIZE.set(size)
    CACHE_CAPACITY_RATIO.set(capacity_ratio)


# =============================================================================
# Getter Functions (for testing and internal use)
# =============================================================================


def get_request_metrics() -> dict:
    """Get current request metrics."""
    return _request_metrics.copy()


def get_cost_metrics() -> dict:
    """Get current cost metrics."""
    return _cost_metrics.copy()


def get_health_metrics() -> dict:
    """Get current health metrics."""
    return _health_metrics.copy()


def reset_metrics() -> None:
    """Reset internal metric counters (for testing)."""
    global _request_metrics, _cost_metrics, _health_metrics
    _request_metrics = {"total_requests": 0, "total_duration": 0.0}
    _cost_metrics = {"total_cost": 0.0, "total_tokens": 0}
    _health_metrics = {}


# =============================================================================
# Flask Integration
# =============================================================================


def _normalize_endpoint(path: str) -> str:
    """
    Normalize endpoint path for consistent labeling.

    Replaces dynamic segments (IDs, UUIDs) with placeholders.
    """
    import re

    # Replace UUIDs
    path = re.sub(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        "{id}",
        path,
        flags=re.IGNORECASE,
    )
    # Replace numeric IDs
    path = re.sub(r"/\d+(?=/|$)", "/{id}", path)
    return path


def metrics_middleware():
    """
    Create a Flask middleware for tracking request metrics.

    Returns:
        Tuple of (before_request, after_request) functions
    """
    from flask import request, g

    def before_request():
        g.start_time = time.perf_counter()

    def after_request(response):
        if hasattr(g, "start_time"):
            duration = time.perf_counter() - g.start_time
            track_request_duration(
                method=request.method,
                endpoint=request.path,
                status=response.status_code,
                duration=duration,
            )
        return response

    return before_request, after_request


def get_metrics_response():
    """
    Generate Prometheus metrics response.

    Returns:
        Tuple of (response_body, content_type)
    """
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST


def init_metrics(app, limiter=None):
    """
    Initialize metrics for a Flask application.

    Args:
        app: Flask application instance
        limiter: Optional Flask-Limiter instance (to exempt /metrics)
    """
    from flask import Response

    # Register middleware
    before_request, after_request = metrics_middleware()
    app.before_request(before_request)
    app.after_request(after_request)

    # Register /metrics endpoint (rate limit exempt)
    @app.route("/metrics")
    def metrics_endpoint():
        body, content_type = get_metrics_response()
        return Response(body, mimetype=content_type)

    # Exempt /metrics from rate limiting if limiter provided
    if limiter is not None:
        limiter.exempt(metrics_endpoint)

    logger.info("Prometheus metrics initialized")
