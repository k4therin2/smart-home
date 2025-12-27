#!/bin/bash
#
# Start the notification worker for SmartHome reminders
#
# This script starts the background notification worker that checks
# for due reminders and sends Slack notifications.
#
# Usage:
#   ./scripts/start_notification_worker.sh              # Start in foreground
#   ./scripts/start_notification_worker.sh --daemon     # Start as daemon
#   ./scripts/start_notification_worker.sh --stop       # Stop the daemon
#
# Part of WP-67.2: SmartHome Background Notification Worker
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_DIR/venv"
PID_FILE="$PROJECT_DIR/data/notification_worker.pid"
LOG_FILE="$PROJECT_DIR/data/logs/notification_worker.log"

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

# Activate virtual environment
if [ -d "$VENV_DIR" ]; then
    source "$VENV_DIR/bin/activate"
else
    echo "Error: Virtual environment not found at $VENV_DIR"
    exit 1
fi

# Load environment variables
if [ -f "$PROJECT_DIR/.env" ]; then
    export $(grep -v '^#' "$PROJECT_DIR/.env" | xargs)
fi

start_foreground() {
    echo "Starting notification worker in foreground..."
    cd "$PROJECT_DIR"
    python -m src.notification_worker
}

start_daemon() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            echo "Notification worker is already running (PID: $PID)"
            exit 1
        else
            echo "Removing stale PID file"
            rm -f "$PID_FILE"
        fi
    fi

    echo "Starting notification worker as daemon..."
    cd "$PROJECT_DIR"
    nohup python -m src.notification_worker >> "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    echo "Notification worker started (PID: $(cat "$PID_FILE"))"
    echo "Log file: $LOG_FILE"
}

stop_daemon() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            echo "Stopping notification worker (PID: $PID)..."
            kill -TERM "$PID"
            # Wait for graceful shutdown
            for i in {1..10}; do
                if ! kill -0 "$PID" 2>/dev/null; then
                    echo "Notification worker stopped"
                    rm -f "$PID_FILE"
                    exit 0
                fi
                sleep 1
            done
            # Force kill if still running
            echo "Force stopping notification worker..."
            kill -9 "$PID" 2>/dev/null || true
            rm -f "$PID_FILE"
            echo "Notification worker stopped"
        else
            echo "Notification worker is not running (stale PID file)"
            rm -f "$PID_FILE"
        fi
    else
        echo "Notification worker is not running (no PID file)"
    fi
}

status() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            echo "Notification worker is running (PID: $PID)"
            exit 0
        else
            echo "Notification worker is not running (stale PID file)"
            exit 1
        fi
    else
        echo "Notification worker is not running"
        exit 1
    fi
}

case "${1:-}" in
    --daemon)
        start_daemon
        ;;
    --stop)
        stop_daemon
        ;;
    --status)
        status
        ;;
    --help|-h)
        echo "Usage: $0 [--daemon|--stop|--status|--help]"
        echo ""
        echo "Options:"
        echo "  (no args)  Start in foreground"
        echo "  --daemon   Start as background daemon"
        echo "  --stop     Stop the daemon"
        echo "  --status   Check daemon status"
        echo "  --help     Show this help"
        ;;
    *)
        start_foreground
        ;;
esac
