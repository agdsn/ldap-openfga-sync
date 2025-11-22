#!/bin/bash
set -e

# Default interval: every 6 hours (in seconds)
SYNC_INTERVAL_SECONDS="${SYNC_INTERVAL_SECONDS:-21600}"

echo "Starting LDAP to OpenFGA sync service..."
echo "Sync interval: ${SYNC_INTERVAL_SECONDS} seconds ($(($SYNC_INTERVAL_SECONDS / 3600)) hours)"
echo ""

# Run sync immediately on startup
echo "Running initial sync..."
python sync.py 2>&1 | tee -a /var/log/ldap-openfga-sync/sync.log

echo ""
echo "Initial sync complete. Starting periodic sync loop..."
echo "Next sync in ${SYNC_INTERVAL_SECONDS} seconds"

# Continuous loop with sleep
while true; do
    sleep "$SYNC_INTERVAL_SECONDS"
    echo ""
    echo "========================================"
    echo "Starting scheduled sync at $(date)"
    echo "========================================"
    python sync.py 2>&1 | tee -a /var/log/ldap-openfga-sync/sync.log
    echo "Sync complete. Next sync in ${SYNC_INTERVAL_SECONDS} seconds"
done

