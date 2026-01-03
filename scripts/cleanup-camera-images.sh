#!/bin/bash
# Camera Image Cleanup Script
#
# Removes camera images older than the retention period (default 14 days).
# Designed to run daily via cron job.
#
# WP-11.2: Storage System (SQLite + Image Retention)
#
# Usage:
#   ./scripts/cleanup-camera-images.sh         # Normal run
#   ./scripts/cleanup-camera-images.sh --dry-run  # Preview only
#
# Cron example (run daily at 3am):
#   0 3 * * * /home/k4therin2/projects/Smarthome/scripts/cleanup-camera-images.sh >> /home/k4therin2/projects/Smarthome/data/logs/cleanup.log 2>&1

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Activate virtual environment
source venv/bin/activate

# Run cleanup
if [[ "$1" == "--dry-run" ]]; then
    echo "[$(date)] Starting camera image cleanup (DRY RUN)..."
    python -c "
from src.camera_store import get_camera_store
store = get_camera_store()
result = store.cleanup_old_images(dry_run=True)
print(f\"Would delete {result['deleted_files']} files ({result['deleted_bytes_mb']} MB)\")
print(f\"Would delete {result.get('deleted_records', 0)} database records\")
"
else
    echo "[$(date)] Starting camera image cleanup..."
    python -c "
from src.camera_store import get_camera_store
store = get_camera_store()
result = store.cleanup_old_images(dry_run=False)
print(f\"Deleted {result['deleted_files']} files ({result['deleted_bytes_mb']} MB)\")
print(f\"Deleted {result.get('deleted_records', 0)} database records\")

# Check disk space
stats = store.get_storage_stats()
alert = store.check_disk_space_alert()
if alert:
    print(f\"ALERT: {alert['severity']} - {alert['message']}\")
"
fi

echo "[$(date)] Cleanup complete."
