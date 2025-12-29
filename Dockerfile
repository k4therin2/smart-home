# SmartHome Assistant - Docker Image
# Multi-stage build for optimized production image

# Build stage
FROM python:3.12-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.12-slim as production

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash smarthome

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /root/.local /home/smarthome/.local
ENV PATH=/home/smarthome/.local/bin:$PATH

# Copy application code
COPY --chown=smarthome:smarthome . .

# Create directories for persistent data
RUN mkdir -p /app/data /app/certs /app/logs \
    && chown -R smarthome:smarthome /app/data /app/certs /app/logs

# Switch to non-root user
USER smarthome

# Expose ports (HTTP redirect and HTTPS)
EXPOSE 5049 5050

# Health check (uses Kubernetes-style liveness endpoint)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:5050/healthz || exit 1

# Environment variables with defaults
ENV FLASK_ENV=production \
    LOG_LEVEL=INFO \
    DATA_DIR=/app/data \
    CERTS_DIR=/app/certs

# Entry point
CMD ["python", "src/server.py"]
