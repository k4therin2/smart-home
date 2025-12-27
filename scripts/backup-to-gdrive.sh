#!/bin/bash
# Smarthome Backup Script - Backs up to Google Drive
# Runs daily via cron

set -euo pipefail

# Configuration
BACKUP_NAME="smarthome-backup"
SOURCE_DIR="/home/k4therin2/projects/Smarthome"
LOCAL_BACKUP_DIR="/home/k4therin2/backups"
GDRIVE_REMOTE="gdrive:smarthome-backups"
RETENTION_DAYS=30
LOG_FILE="/home/k4therin2/backups/backup.log"

# Create backup directory if needed
mkdir -p "$LOCAL_BACKUP_DIR"

# Timestamp for this backup
TIMESTAMP=$(date +%Y-%m-%d_%H%M%S)
BACKUP_FILE="${BACKUP_NAME}-${TIMESTAMP}.tar.gz"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "Starting backup..."

# Stop containers for consistent backup (optional - comment out if you don't want downtime)
# docker stop homeassistant wyoming-whisper wyoming-piper 2>/dev/null || true

# Create compressed archive
log "Creating archive: $BACKUP_FILE"
tar -czf "${LOCAL_BACKUP_DIR}/${BACKUP_FILE}" \
    --exclude='venv' \
    --exclude='__pycache__' \
    --exclude='.git' \
    --exclude='*.pyc' \
    --exclude='.coverage' \
    --exclude='.pytest_cache' \
    -C "$(dirname "$SOURCE_DIR")" \
    "$(basename "$SOURCE_DIR")"

# Restart containers (if stopped above)
# docker start homeassistant wyoming-whisper wyoming-piper 2>/dev/null || true

# Get backup size
BACKUP_SIZE=$(du -h "${LOCAL_BACKUP_DIR}/${BACKUP_FILE}" | cut -f1)
log "Backup created: ${BACKUP_SIZE}"

# Upload to Google Drive
log "Uploading to Google Drive..."
if rclone copy "${LOCAL_BACKUP_DIR}/${BACKUP_FILE}" "$GDRIVE_REMOTE" --progress 2>&1 | tee -a "$LOG_FILE"; then
    log "Upload complete!"
else
    log "ERROR: Upload failed!"
    exit 1
fi

# Clean up old local backups (keep last 7)
log "Cleaning up old local backups..."
ls -t "${LOCAL_BACKUP_DIR}"/${BACKUP_NAME}-*.tar.gz 2>/dev/null | tail -n +8 | xargs -r rm -f

# Clean up old remote backups (keep last 30 days)
log "Cleaning up old remote backups..."
rclone delete "$GDRIVE_REMOTE" --min-age "${RETENTION_DAYS}d" 2>&1 | tee -a "$LOG_FILE" || true

log "Backup complete: ${BACKUP_FILE}"

# Summary
echo ""
echo "=== Backup Summary ==="
echo "File: ${BACKUP_FILE}"
echo "Size: ${BACKUP_SIZE}"
echo "Local: ${LOCAL_BACKUP_DIR}/${BACKUP_FILE}"
echo "Remote: ${GDRIVE_REMOTE}/${BACKUP_FILE}"
