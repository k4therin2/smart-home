#!/bin/bash
#
# Setup Security Monitoring on Colby
#
# This script installs the security monitoring daemon and weekly report timer.
# Run this on colby after setting up the Slack webhook.
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Smarthome Security Monitoring Setup ==="
echo ""

# Check if running on colby
if [[ "$(hostname)" != "colby" ]]; then
    echo "Warning: This script is intended for colby. Current host: $(hostname)"
    read -p "Continue anyway? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check for .env file
if [[ ! -f "$PROJECT_DIR/.env" ]]; then
    echo "Error: .env file not found at $PROJECT_DIR/.env"
    echo "Please create it from .env.example first."
    exit 1
fi

# Check for Slack webhook
if ! grep -q "SLACK_SECURITY_WEBHOOK" "$PROJECT_DIR/.env"; then
    echo ""
    echo "SLACK_SECURITY_WEBHOOK not found in .env"
    echo ""
    echo "Please add it to your .env file:"
    echo "  SLACK_SECURITY_WEBHOOK=https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
    echo ""
    read -p "Have you added the webhook? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Please add the webhook and run this script again."
        exit 1
    fi
fi

# Create data directory
echo "Creating data directories..."
mkdir -p "$PROJECT_DIR/data/security"

# Ensure venv exists
if [[ ! -d "$PROJECT_DIR/venv" ]]; then
    echo "Creating virtual environment..."
    python3 -m venv "$PROJECT_DIR/venv"
fi

# Install dependencies (if any new ones needed)
echo "Checking dependencies..."
source "$PROJECT_DIR/venv/bin/activate"
pip install -q python-dotenv

# Copy systemd files
echo "Installing systemd services..."
sudo cp "$SCRIPT_DIR/systemd/smarthome-security.service" /etc/systemd/system/
sudo cp "$SCRIPT_DIR/systemd/smarthome-weekly-report.service" /etc/systemd/system/
sudo cp "$SCRIPT_DIR/systemd/smarthome-weekly-report.timer" /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable and start services
echo "Enabling services..."
sudo systemctl enable smarthome-security.service
sudo systemctl enable smarthome-weekly-report.timer

echo "Starting security monitoring daemon..."
sudo systemctl start smarthome-security.service

echo "Starting weekly report timer..."
sudo systemctl start smarthome-weekly-report.timer

# Show status
echo ""
echo "=== Status ==="
sudo systemctl status smarthome-security.service --no-pager || true
echo ""
sudo systemctl list-timers smarthome-weekly-report.timer --no-pager || true

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Security monitoring is now running!"
echo ""
echo "Useful commands:"
echo "  View logs:    journalctl -u smarthome-security -f"
echo "  Stop daemon:  sudo systemctl stop smarthome-security"
echo "  Test alert:   cd $PROJECT_DIR && ./venv/bin/python -m src.security.daemon --test"
echo "  Manual report: cd $PROJECT_DIR && ./venv/bin/python -m src.security.weekly_report"
echo ""
