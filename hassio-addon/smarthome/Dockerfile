# SmartHome Home Assistant Add-on
# Build using Home Assistant base images for supervisor compatibility

ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.12-alpine3.20
FROM ${BUILD_FROM}

# Labels for add-on
LABEL io.hass.type="addon" \
      io.hass.name="SmartHome Assistant" \
      io.hass.description="Privacy-focused, agentic smart home assistant" \
      io.hass.arch="amd64|aarch64|armv7" \
      io.hass.version="1.0.0"

# Install build dependencies (temporary)
RUN apk add --no-cache --virtual .build-deps \
    gcc \
    musl-dev \
    libffi-dev

# Install runtime dependencies
RUN apk add --no-cache \
    curl \
    bash

# Copy and install Python requirements
COPY requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

# Remove build dependencies
RUN apk del .build-deps

# Copy application code
WORKDIR /app
COPY . /app/

# Create directories for data persistence
RUN mkdir -p /data /ssl /media

# Copy run script
COPY hassio-addon/smarthome/run.sh /run.sh
RUN chmod a+x /run.sh

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:5050/healthz || exit 1

# Entry point using bashio
CMD ["/run.sh"]
