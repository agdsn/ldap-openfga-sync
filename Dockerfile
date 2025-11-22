# Use Python 3.13 slim image
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libldap2-dev \
    libsasl2-dev \
    gcc \
    cron \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY *.py ./

# Create log directory
RUN mkdir -p /var/log/ldap-openfga-sync

# Create cron job to run sync every 6 hours
RUN echo "0 */6 * * * cd /app && /usr/local/bin/python sync.py >> /var/log/ldap-openfga-sync/sync.log 2>&1" > /etc/cron.d/ldap-sync && \
    chmod 0644 /etc/cron.d/ldap-sync && \
    crontab /etc/cron.d/ldap-sync

# Copy and setup entrypoint script
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Expose volume for logs
VOLUME ["/var/log/ldap-openfga-sync"]

# Health check - verify the process is running
HEALTHCHECK --interval=1h --timeout=10s --start-period=30s --retries=3 \
    CMD pgrep cron || exit 1

# Run entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]

