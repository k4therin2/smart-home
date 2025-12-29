#!/usr/bin/with-contenv bashio
# SmartHome Add-on Entry Point
# Uses bashio for HA integration

set -e

bashio::log.info "Starting SmartHome Assistant..."

# Read configuration from Home Assistant
export OPENAI_API_KEY=$(bashio::config 'openai_api_key')
export OPENAI_MODEL=$(bashio::config 'openai_model')
export DAILY_COST_TARGET=$(bashio::config 'daily_cost_target')
export DAILY_COST_ALERT=$(bashio::config 'daily_cost_alert')
export LOG_LEVEL=$(bashio::config 'log_level')
export SLACK_WEBHOOK_URL=$(bashio::config 'slack_webhook_url')
export SPOTIFY_CLIENT_ID=$(bashio::config 'spotify_client_id')
export SPOTIFY_CLIENT_SECRET=$(bashio::config 'spotify_client_secret')

# Home Assistant integration
export HA_URL="http://supervisor/core"
export HA_TOKEN="${SUPERVISOR_TOKEN}"

# Data directories (mapped by add-on system)
export DATA_DIR="/data"
export CERTS_DIR="/ssl"

# Validate required configuration
if [ -z "${OPENAI_API_KEY}" ]; then
    bashio::log.warning "OpenAI API key not configured - LLM features will be unavailable"
fi

bashio::log.info "Configuration loaded"
bashio::log.info "  - OpenAI Model: ${OPENAI_MODEL}"
bashio::log.info "  - Log Level: ${LOG_LEVEL}"
bashio::log.info "  - Data Dir: ${DATA_DIR}"

# Create database directory if needed
mkdir -p "${DATA_DIR}"

bashio::log.info "Starting server on port 5050..."

# Start the server
cd /app
exec python src/server.py
