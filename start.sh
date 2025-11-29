#!/bin/bash
#
# Startup script for Home Automation Agent
#
# This script starts all necessary services:
# 1. Home Assistant (Docker)
# 2. Agent web server
# 3. Cloudflare Tunnel (public HTTPS access)
#
# Usage:
#   ./start.sh           # Start all services
#   ./start.sh --help    # Show help
#

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${PROJECT_DIR}/venv"
SERVER_PORT=5001
TUNNEL_LOG="${PROJECT_DIR}/logs/tunnel.log"
SERVER_LOG="${PROJECT_DIR}/logs/server.log"

# Create logs directory
mkdir -p "${PROJECT_DIR}/logs"

# Function to print colored messages
print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# Function to check if a process is running
is_running() {
    pgrep -f "$1" > /dev/null 2>&1
}

# Function to start Home Assistant
start_home_assistant() {
    print_status "Starting Home Assistant..."

    if docker ps | grep -q homeassistant; then
        print_warning "Home Assistant already running"
    else
        cd "${PROJECT_DIR}"
        docker compose up -d
        print_status "Home Assistant started"
        print_status "Access at: http://localhost:8123"
    fi
}

# Function to start agent server
start_server() {
    print_status "Starting agent server..."

    if is_running "python.*server.py"; then
        print_warning "Agent server already running"
    else
        cd "${PROJECT_DIR}"
        source "${VENV_DIR}/bin/activate"
        nohup python server.py > "${SERVER_LOG}" 2>&1 &
        sleep 2

        if is_running "python.*server.py"; then
            print_status "Agent server started on port ${SERVER_PORT}"
            print_status "Web UI: http://localhost:${SERVER_PORT}"
        else
            print_error "Failed to start agent server"
            exit 1
        fi
    fi
}

# Function to start Cloudflare Tunnel
start_tunnel() {
    print_status "Starting Cloudflare Tunnel..."

    if is_running "cloudflared.*tunnel"; then
        print_warning "Tunnel already running"
        # Extract URL from running process
        TUNNEL_URL=$(grep -o 'https://[^[:space:]]*\.trycloudflare\.com' "${TUNNEL_LOG}" 2>/dev/null | tail -1)
        if [ -n "$TUNNEL_URL" ]; then
            print_status "Tunnel URL: ${TUNNEL_URL}"
        fi
    else
        nohup cloudflared tunnel --url "http://localhost:${SERVER_PORT}" > "${TUNNEL_LOG}" 2>&1 &

        # Wait for tunnel to start and extract URL
        print_status "Waiting for tunnel to initialize..."
        for i in {1..30}; do
            TUNNEL_URL=$(grep -o 'https://[^[:space:]]*\.trycloudflare\.com' "${TUNNEL_LOG}" 2>/dev/null | tail -1)
            if [ -n "$TUNNEL_URL" ]; then
                break
            fi
            sleep 1
        done

        if [ -n "$TUNNEL_URL" ]; then
            print_status "Tunnel created: ${TUNNEL_URL}"
            print_warning "⚠️  Free tunnel URL changes on restart!"
            print_warning "⚠️  Update Lambda env var AGENT_URL if needed"
            echo ""
            echo "Update Lambda with:"
            echo "  AGENT_URL=${TUNNEL_URL}"
        else
            print_error "Failed to get tunnel URL"
            exit 1
        fi
    fi
}

# Function to show status
show_status() {
    echo ""
    echo "═══════════════════════════════════════════════════"
    echo "  Home Automation Agent - Service Status"
    echo "═══════════════════════════════════════════════════"
    echo ""

    # Home Assistant
    if docker ps | grep -q homeassistant; then
        print_status "Home Assistant: RUNNING (http://localhost:8123)"
    else
        print_error "Home Assistant: STOPPED"
    fi

    # Agent Server
    if is_running "python.*server.py"; then
        print_status "Agent Server: RUNNING (http://localhost:${SERVER_PORT})"
    else
        print_error "Agent Server: STOPPED"
    fi

    # Cloudflare Tunnel
    if is_running "cloudflared.*tunnel"; then
        TUNNEL_URL=$(grep -o 'https://[^[:space:]]*\.trycloudflare\.com' "${TUNNEL_LOG}" 2>/dev/null | tail -1)
        if [ -n "$TUNNEL_URL" ]; then
            print_status "Cloudflare Tunnel: RUNNING (${TUNNEL_URL})"
        else
            print_warning "Cloudflare Tunnel: RUNNING (URL unknown)"
        fi
    else
        print_error "Cloudflare Tunnel: STOPPED"
    fi

    echo ""
}

# Function to stop all services
stop_all() {
    print_status "Stopping all services..."

    # Stop tunnel
    if is_running "cloudflared.*tunnel"; then
        pkill -f "cloudflared.*tunnel"
        print_status "Stopped Cloudflare Tunnel"
    fi

    # Stop server
    if is_running "python.*server.py"; then
        pkill -f "python.*server.py"
        print_status "Stopped agent server"
    fi

    # Stop Home Assistant
    if docker ps | grep -q homeassistant; then
        cd "${PROJECT_DIR}"
        docker compose down
        print_status "Stopped Home Assistant"
    fi

    echo ""
    print_status "All services stopped"
}

# Main script
case "${1:-start}" in
    start)
        echo ""
        echo "🏠 Starting Home Automation Services..."
        echo ""
        start_home_assistant
        start_server
        start_tunnel
        show_status
        echo "═══════════════════════════════════════════════════"
        echo ""
        print_status "All services started!"
        echo ""
        print_warning "Logs:"
        echo "  Server: ${SERVER_LOG}"
        echo "  Tunnel: ${TUNNEL_LOG}"
        echo ""
        ;;

    stop)
        stop_all
        ;;

    restart)
        stop_all
        sleep 2
        exec "$0" start
        ;;

    status)
        show_status
        ;;

    logs)
        echo "Server logs:"
        tail -20 "${SERVER_LOG}"
        echo ""
        echo "Tunnel logs:"
        tail -20 "${TUNNEL_LOG}"
        ;;

    --help|-h|help)
        echo "Home Automation Agent Startup Script"
        echo ""
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  start    - Start all services (default)"
        echo "  stop     - Stop all services"
        echo "  restart  - Restart all services"
        echo "  status   - Show service status"
        echo "  logs     - Show recent logs"
        echo "  help     - Show this message"
        echo ""
        ;;

    *)
        print_error "Unknown command: $1"
        echo "Run '$0 help' for usage"
        exit 1
        ;;
esac
