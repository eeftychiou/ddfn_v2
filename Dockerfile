# Multi-stage build for DDFN v2
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY src/ ./src/
COPY web/ ./web/
COPY data/ ./data/
COPY AIXM/ ./AIXM/

# Create necessary directories
RUN mkdir -p logs data/node_configs uploads

# Set environment variables
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1
ENV DDFN_CONFIG_DIR=/app/data/node_configs
ENV DDFN_LOGS_DIR=/app/logs
ENV DDFN_DATA_DIR=/app/data

# Expose ports
EXPOSE 8001 8010 8011 8012 8013 8030 8031 8032 8050

# Default command (can be overridden)
CMD ["python", "-m", "ddfn_v2.core.broker"]
