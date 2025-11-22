#!/bin/bash
set -e

# Default schedule: every 6 hours
CRON_SCHEDULE="${CRON_SCHEDULE:-0 */6 * * *}"

echo "Starting LDAP to OpenFGA sync service..."
echo "Sync schedule: $CRON_SCHEDULE"
echo ""

# Setup cron job with the schedule from environment
echo "$CRON_SCHEDULE cd /app && /usr/local/bin/python sync.py >> /var/log/ldap-openfga-sync/sync.log 2>&1" > /etc/cron.d/ldap-sync
chmod 0644 /etc/cron.d/ldap-sync
crontab /etc/cron.d/ldap-sync

echo "Cron job configured:"
crontab -l

# Run sync immediately on startup
echo ""
echo "Running initial sync..."
python sync.py

echo ""
echo "Initial sync complete. Starting cron daemon..."

# Start cron in foreground
cron -f

