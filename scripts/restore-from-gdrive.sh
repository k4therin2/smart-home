#!/bin/bash
# Restore a backup from Google Drive
# Usage: ./restore-from-gdrive.sh [backup-filename]

set -euo pipefail

GDRIVE_REMOTE="gdrive:smarthome-backups"
LOCAL_BACKUP_DIR="/home/k4therin2/backups"
RESTORE_DIR="/home/k4therin2/projects"

if [ $# -eq 0 ]; then
    echo "Available backups on Google Drive:"
    echo ""
    rclone ls "$GDRIVE_REMOTE" | sort -r | head -20
    echo ""
    echo "Usage: $0 <backup-filename>"
    echo "Example: $0 smarthome-backup-2024-01-15_020000.tar.gz"
    exit 0
fi

BACKUP_FILE="$1"

echo "Downloading $BACKUP_FILE from Google Drive..."
rclone copy "${GDRIVE_REMOTE}/${BACKUP_FILE}" "$LOCAL_BACKUP_DIR" --progress

echo ""
echo "Backup downloaded to: ${LOCAL_BACKUP_DIR}/${BACKUP_FILE}"
echo ""
echo "To restore, run:"
echo "  cd $RESTORE_DIR"
echo "  mv Smarthome Smarthome.old  # backup current"
echo "  tar -xzf ${LOCAL_BACKUP_DIR}/${BACKUP_FILE}"
echo "  # Then restart your services"
