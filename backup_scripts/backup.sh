#!/bin/sh
# Simple backup script for crypto_analytics database

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="/backups/crypto_analytics_${TIMESTAMP}.sql"

echo "Starting backup at $(date)"
pg_dump -h postgres -U crypto_user -d crypto_analytics > "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    echo "Backup completed successfully: $BACKUP_FILE"
    ls -lh "$BACKUP_FILE"
else
    echo "Backup failed!"
    exit 1
fi
