# Use Python 3.13 slim image
FROM python:3.13-slim

# Create non-root user
RUN groupadd -r syncuser && useradd -r -g syncuser -u 1000 syncuser

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libldap2-dev \
    libsasl2-dev \
    gcc \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY *.py ./

# Copy entrypoint script
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Create log directory and set ownership
RUN mkdir -p /var/log/ldap-openfga-sync && \
    chown -R syncuser:syncuser /app /var/log/ldap-openfga-sync

# Switch to non-root user
USER syncuser

# Expose volume for logs
VOLUME ["/var/log/ldap-openfga-sync"]

# Health check - verify the entrypoint process is running
HEALTHCHECK --interval=1h --timeout=10s --start-period=30s --retries=3 \
    CMD pgrep -f entrypoint.sh || exit 1

# Run entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]

