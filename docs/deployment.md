# Deployment & Operations Guide

## Overview

This guide covers deployment, operations, monitoring, and rollback procedures for the Azure FinOps MCP Server.

## Table of Contents

1. [Deployment Strategies](#deployment-strategies)
2. [Environment Configuration](#environment-configuration)
3. [Monitoring & Alerting](#monitoring--alerting)
4. [Health Checks](#health-checks)
5. [Rollback Procedures](#rollback-procedures)
6. [Disaster Recovery](#disaster-recovery)
7. [Performance Tuning](#performance-tuning)
8. [Troubleshooting](#troubleshooting)

## Deployment Strategies

### Local Development Deployment

```bash
# 1. Clone repository
git clone https://github.com/julianobarbosa/azure-finops-mcp-server.git
cd azure-finops-mcp-server

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
pip install -e .

# 4. Configure environment
cp .env.example .env
# Edit .env with your settings

# 5. Run tests
pytest tests/

# 6. Start server
python -m azure_finops_mcp_server.main
```

### Production Deployment via PyPI

```bash
# 1. Install from PyPI
pip install azure-finops-mcp-server

# 2. Configure environment variables
export AZURE_SUBSCRIPTION_ID="your-subscription-id"
export AZURE_MAX_WORKERS=10
export AZURE_CACHE_TTL=600

# 3. Run server
azure-finops-mcp-server
```

### Docker Deployment

```bash
# 1. Build Docker image
docker build -t azure-finops-mcp:latest .

# 2. Run container
docker run -d \
  --name azure-finops-mcp \
  -e AZURE_SUBSCRIPTION_ID="your-subscription-id" \
  -e AZURE_LOG_LEVEL="INFO" \
  -p 8080:8080 \
  azure-finops-mcp:latest
```

### Infrastructure as Code Deployment

```bash
# 1. Navigate to infrastructure directory
cd infrastructure/terraform

# 2. Initialize Terraform
terraform init

# 3. Plan deployment
terraform plan -var="environment=production" -out=tfplan

# 4. Apply infrastructure
terraform apply tfplan

# 5. Get outputs
terraform output -json > outputs.json
```

## Environment Configuration

### Required Environment Variables

```bash
# Azure Configuration
AZURE_SUBSCRIPTION_ID=<subscription-id>
AZURE_SUBSCRIPTION_IDS=<comma-separated-ids>  # For multiple subscriptions
AZURE_DEFAULT_REGIONS=eastus,westus

# Performance Settings
AZURE_MAX_WORKERS=5              # Parallel processing workers
AZURE_REQUEST_TIMEOUT=30         # Request timeout in seconds
AZURE_CACHE_TTL=300             # Cache TTL in seconds
AZURE_ENABLE_CACHE=true         # Enable/disable caching

# Monitoring
AZURE_LOG_LEVEL=INFO            # DEBUG, INFO, WARNING, ERROR, CRITICAL
AZURE_DETAILED_LOGGING=false    # Verbose logging
AZURE_METRICS_ENABLED=true      # Enable metrics collection

# Azure Management URLs (for different clouds)
AZURE_MANAGEMENT_URL=https://management.azure.com  # Commercial
# AZURE_MANAGEMENT_URL=https://management.usgovcloudapi.net  # Government
# AZURE_MANAGEMENT_URL=https://management.chinacloudapi.cn   # China
```

### Configuration Validation

```python
# Validate configuration before deployment
from azure_finops_mcp_server.config import get_config

config = get_config()
errors = config.validate()
if errors:
    print(f"Configuration errors: {errors}")
    exit(1)
```

## Monitoring & Alerting

### Metrics Collection

The server automatically collects the following metrics:

```python
# Available metrics
- get_cost.calls              # Number of cost queries
- get_cost.success            # Successful queries
- get_cost.failures           # Failed queries
- get_cost.duration           # Query duration (p50, p95, p99)
- run_finops_audit.calls      # Audit executions
- api.errors                  # API error count
- cache.hits                  # Cache hit rate
- cache.misses               # Cache miss rate
- memory_usage_mb            # Memory consumption
- health.azure_connection    # Azure connectivity status
```

### Setting Alert Thresholds

```python
from azure_finops_mcp_server.monitoring import alert_manager

# Configure alert thresholds
alert_manager.set_threshold('get_cost.failures', 5, 'gt', window_seconds=300)
alert_manager.set_threshold('get_cost.duration.p95', 10.0, 'gt')
alert_manager.set_threshold('memory_usage_mb', 500, 'gt')
alert_manager.set_threshold('api.errors', 10, 'gt', window_seconds=600)
```

### Custom Alert Callbacks

```python
def send_slack_alert(alert):
    """Send alert to Slack."""
    webhook_url = os.environ.get('SLACK_WEBHOOK_URL')
    if webhook_url:
        requests.post(webhook_url, json={
            'text': f"🚨 Alert: {alert['metric']} = {alert['value']} (threshold: {alert['threshold']})"
        })

# Register callback
alert_manager.register_callback(send_slack_alert)
```

## Health Checks

### Built-in Health Checks

```python
# Health check endpoint returns:
{
  "status": "healthy",
  "healthy_checks": 2,
  "unhealthy_checks": 0,
  "total_checks": 2,
  "details": {
    "azure_connection": {
      "status": "healthy",
      "message": "Connected to 3 subscription(s)",
      "timestamp": "2025-01-09T10:00:00Z"
    },
    "memory_usage": {
      "status": "healthy",
      "message": "Memory usage: 125.3MB",
      "timestamp": "2025-01-09T10:00:00Z"
    }
  }
}
```

### Custom Health Checks

```python
from azure_finops_mcp_server.monitoring import health_check

def check_database_connection():
    """Custom health check for database."""
    try:
        # Check database connection
        conn = get_db_connection()
        conn.ping()
        return True, "Database connected"
    except Exception as e:
        return False, f"Database error: {str(e)}"

# Register custom check
health_check.register_check('database', check_database_connection, interval_seconds=60)
```

## Rollback Procedures

### Version Rollback

#### PyPI Package Rollback

```bash
# 1. Check current version
pip show azure-finops-mcp-server

# 2. Uninstall current version
pip uninstall azure-finops-mcp-server

# 3. Install previous stable version
pip install azure-finops-mcp-server==1.2.3  # Specify previous version

# 4. Verify rollback
python -c "import azure_finops_mcp_server; print(azure_finops_mcp_server.__version__)"
```

#### Docker Rollback

```bash
# 1. Stop current container
docker stop azure-finops-mcp

# 2. Remove current container
docker rm azure-finops-mcp

# 3. Run previous version
docker run -d \
  --name azure-finops-mcp \
  -e AZURE_SUBSCRIPTION_ID="your-subscription-id" \
  azure-finops-mcp:v1.2.3  # Previous version tag

# 4. Verify health
docker logs azure-finops-mcp
```

#### Git Rollback

```bash
# 1. Identify last known good commit
git log --oneline -10

# 2. Create rollback branch
git checkout -b rollback/issue-fix

# 3. Revert to previous commit
git revert HEAD  # Or specific commit hash

# 4. Test rollback
pytest tests/

# 5. Deploy rollback
git push origin rollback/issue-fix
```

### Infrastructure Rollback

```bash
# Terraform state rollback
cd infrastructure/terraform

# 1. List state versions
terraform state list

# 2. Show previous state
terraform show -json > current_state.json

# 3. Rollback to previous version
terraform state pull > terraform.tfstate.backup
terraform state push terraform.tfstate.1  # Previous state file

# 4. Apply rolled back state
terraform apply
```

### Database/Config Rollback

```bash
# 1. Backup current configuration
cp .env .env.backup

# 2. Restore previous configuration
cp .env.previous .env

# 3. Restart service
systemctl restart azure-finops-mcp

# 4. Verify configuration
python -m azure_finops_mcp_server.config validate
```

## Disaster Recovery

### Backup Procedures

```bash
# Daily backup script
#!/bin/bash
BACKUP_DIR="/backup/azure-finops-mcp"
DATE=$(date +%Y%m%d)

# Backup configuration
cp -r /etc/azure-finops-mcp $BACKUP_DIR/config-$DATE

# Backup logs
tar -czf $BACKUP_DIR/logs-$DATE.tar.gz /var/log/azure-finops-mcp

# Backup metrics data
tar -czf $BACKUP_DIR/metrics-$DATE.tar.gz /var/lib/azure-finops-mcp/metrics

# Rotate old backups (keep 30 days)
find $BACKUP_DIR -type f -mtime +30 -delete
```

### Recovery Procedures

```bash
# 1. Stop current service
systemctl stop azure-finops-mcp

# 2. Restore configuration
cp -r /backup/azure-finops-mcp/config-20250108/* /etc/azure-finops-mcp/

# 3. Restore data if needed
tar -xzf /backup/azure-finops-mcp/metrics-20250108.tar.gz -C /

# 4. Start service
systemctl start azure-finops-mcp

# 5. Verify recovery
curl http://localhost:8080/health
```

### High Availability Setup

```yaml
# docker-compose.yml for HA setup
version: '3.8'

services:
  azure-finops-mcp-1:
    image: azure-finops-mcp:latest
    environment:
      - AZURE_SUBSCRIPTION_ID=${AZURE_SUBSCRIPTION_ID}
      - INSTANCE_ID=1
    ports:
      - "8081:8080"
    restart: always

  azure-finops-mcp-2:
    image: azure-finops-mcp:latest
    environment:
      - AZURE_SUBSCRIPTION_ID=${AZURE_SUBSCRIPTION_ID}
      - INSTANCE_ID=2
    ports:
      - "8082:8080"
    restart: always

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    depends_on:
      - azure-finops-mcp-1
      - azure-finops-mcp-2
```

## Performance Tuning

### Optimization Settings

```bash
# Optimize for high load
export AZURE_MAX_WORKERS=20          # Increase parallel workers
export AZURE_CACHE_TTL=1800         # Increase cache duration (30 min)
export AZURE_REQUEST_TIMEOUT=60     # Increase timeout for slow queries
export AZURE_ENABLE_CACHE=true      # Ensure caching is enabled

# Memory optimization
export PYTHONOPTIMIZE=1             # Enable Python optimizations
export PYTHONHASHSEED=random        # Improve dict performance
```

### Performance Monitoring

```python
# Monitor performance metrics
from azure_finops_mcp_server.monitoring import metrics

# Get performance summary
summary = metrics.get_metrics_summary()
print(f"Average response time: {summary['timers']['get_cost.duration']['mean']:.2f}s")
print(f"P95 response time: {summary['timers']['get_cost.duration']['p95']:.2f}s")
print(f"Cache hit rate: {summary['counters']['cache.hits'] / (summary['counters']['cache.hits'] + summary['counters']['cache.misses']) * 100:.1f}%")
```

## Troubleshooting

### Common Issues

#### Issue: Authentication Failures

```bash
# Debug authentication
az account show
az account list

# Clear Azure CLI cache
az account clear
az login

# Test with specific subscription
export AZURE_SUBSCRIPTION_ID="your-subscription-id"
python -c "from azure_finops_mcp_server.helpers.subscription_manager import get_credential; get_credential()"
```

#### Issue: High Memory Usage

```bash
# Check memory usage
ps aux | grep azure-finops

# Enable memory profiling
export AZURE_MEMORY_PROFILING=true
python -m memory_profiler azure_finops_mcp_server.main

# Reduce memory usage
export AZURE_MAX_WORKERS=3  # Reduce parallel workers
export AZURE_CACHE_TTL=60   # Reduce cache duration
```

#### Issue: Slow Performance

```bash
# Enable performance profiling
export AZURE_PERFORMANCE_PROFILING=true

# Run with profiling
python -m cProfile -s cumtime azure_finops_mcp_server.main

# Check slow queries
grep "duration" /var/log/azure-finops-mcp/metrics.log | awk '{if ($NF > 10) print}'
```

### Debug Mode

```bash
# Enable debug mode
export AZURE_LOG_LEVEL=DEBUG
export AZURE_DETAILED_LOGGING=true

# Run with verbose output
python -m azure_finops_mcp_server.main --debug

# Check debug logs
tail -f /var/log/azure-finops-mcp/debug.log
```

### Support Channels

- **GitHub Issues**: [Report bugs](https://github.com/julianobarbosa/azure-finops-mcp-server/issues)
- **Documentation**: [Read the docs](https://github.com/julianobarbosa/azure-finops-mcp-server/docs)
- **Community**: Join discussions on GitHub

---

*Last Updated: 2025-01-09*
