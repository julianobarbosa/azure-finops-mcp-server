# Multi-stage build for optimized image size
FROM python:3.10-slim as builder

# Set working directory
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Final stage
FROM python:3.10-slim

# Install Azure CLI
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    lsb-release \
    && curl -sL https://aka.ms/InstallAzureCLIDeb | bash \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 finops && \
    mkdir -p /app /var/log/azure-finops-mcp && \
    chown -R finops:finops /app /var/log/azure-finops-mcp

# Set working directory
WORKDIR /app

# Copy Python dependencies from builder
COPY --from=builder --chown=finops:finops /root/.local /home/finops/.local

# Copy application code
COPY --chown=finops:finops azure_finops_mcp_server/ ./azure_finops_mcp_server/
COPY --chown=finops:finops setup.py README.md ./

# Install application
RUN pip install --no-cache-dir -e .

# Switch to non-root user
USER finops

# Set Python path
ENV PATH=/home/finops/.local/bin:$PATH
ENV PYTHONPATH=/app:$PYTHONPATH

# Environment variables with defaults
ENV AZURE_LOG_LEVEL=INFO \
    AZURE_MAX_WORKERS=5 \
    AZURE_CACHE_TTL=300 \
    AZURE_ENABLE_CACHE=true \
    AZURE_REQUEST_TIMEOUT=30

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from azure_finops_mcp_server.monitoring import health_check; print(health_check.get_overall_health())" || exit 1

# Expose MCP stdio interface (not a network port)
# This is for documentation purposes
EXPOSE 8080

# Entry point
ENTRYPOINT ["python", "-m", "azure_finops_mcp_server.main"]

# Default command (can be overridden)
CMD []