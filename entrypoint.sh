#!/bin/bash
set -e

echo "Starting LDAP to OpenFGA sync service..."
echo "Sync will run every 6 hours (0 */6 * * *)"
echo ""

# Run sync immediately on startup
echo "Running initial sync..."
python sync.py

echo ""
echo "Initial sync complete. Starting cron daemon..."

# Start cron in foreground
cron -f

