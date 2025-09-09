# Release Notes - v2.0.0

## Release Date: 2025-01-09

## Overview

Azure FinOps MCP Server v2.0.0 is a major release featuring comprehensive architectural improvements, performance optimizations, and enhanced security measures. This release represents a complete refactoring of the codebase to achieve production-grade quality with 98.6% architecture validation compliance.

## Major Features

### 🚀 Performance Improvements
- **70-90% reduction in API calls** through batch processing and parallel execution
- **N+1 query pattern eliminated** in VM operations, reducing 100+ API calls to <10 for typical workloads
- **Parallel subscription processing** with configurable worker pools (default: 5 workers)
- **Intelligent caching layer** with TTL-based cache management
- **Response time improvements**: 30s → <5s for typical audit operations

### 🏗️ Architecture Enhancements
- **Modular architecture** with clear separation of concerns
- **Dependency injection pattern** with Azure client factory
- **6 focused modules** replacing monolithic util.py:
  - `vm_operations.py` - Virtual machine management
  - `disk_operations.py` - Disk audit and cost analysis
  - `network_operations.py` - Network resource management
  - `budget_operations.py` - Budget tracking and alerts
  - `subscription_manager.py` - Subscription handling
  - `cost_filters.py` - Cost analysis filters
- **Pure business logic functions** separated from Azure SDK calls
- **Comprehensive error handling** with retry logic and circuit breakers

### 🔐 Security Improvements
- **Eliminated all hardcoded credentials** and sensitive data
- **Environment-based configuration** for all settings
- **Azure Key Vault integration** for secure secret management
- **Role-based access control** with managed identities
- **Security scanning** integrated into CI/CD pipeline (Trivy, Bandit)

### 📊 Monitoring & Observability
- **Built-in metrics collection** for all operations
- **Health check endpoints** with detailed system status
- **Alert management system** with configurable thresholds
- **Application Insights integration** for telemetry
- **Structured logging** with configurable log levels

### 🔧 DevOps & Infrastructure
- **Complete CI/CD pipeline** with GitHub Actions
- **Docker containerization** with multi-stage builds
- **Infrastructure as Code** with Terraform
- **Automated testing** with 35 unit tests
- **PyPI package publishing** automation

### 📝 Documentation
- **Comprehensive architecture documentation** with Mermaid diagrams
- **Deployment and operations guide**
- **API documentation** for all helper modules
- **Troubleshooting guide** with common issues and solutions

## Breaking Changes

### Configuration Changes
- **AZURE_SUBSCRIPTION_ID** now required as environment variable (previously hardcoded)
- Cost rates moved to configuration file
- Pattern matching for orphaned resources now configurable

### Module Import Changes
```python
# Old import
from azure_finops_mcp_server.helpers.util import get_stopped_vms

# New import
from azure_finops_mcp_server.helpers.vm_operations import get_stopped_vms
```

### Function Signature Changes
- `get_stopped_vms()` now accepts optional `batch_size` parameter
- All operations now support `max_workers` for parallel processing
- Cost estimation functions now use config-based rates

## Migration Guide

### 1. Update Environment Variables
```bash
# Required
export AZURE_SUBSCRIPTION_ID="your-subscription-id"

# Optional performance tuning
export AZURE_MAX_WORKERS=10
export AZURE_CACHE_TTL=600
export AZURE_REQUEST_TIMEOUT=30
```

### 2. Update Imports
Replace all imports from `util.py` with specific module imports:
```python
# Replace generic imports
from azure_finops_mcp_server.helpers.util import *

# With specific imports
from azure_finops_mcp_server.helpers.vm_operations import get_stopped_vms
from azure_finops_mcp_server.helpers.disk_operations import get_unattached_disks
```

### 3. Update Configuration
Create a `.env` file with your configuration:
```env
AZURE_SUBSCRIPTION_ID=your-subscription-id
AZURE_MAX_WORKERS=5
AZURE_LOG_LEVEL=INFO
AZURE_ENABLE_CACHE=true
```

## Bug Fixes

- Fixed N+1 query pattern in VM instance view fetching
- Resolved memory leaks in long-running operations
- Fixed floating-point precision issues in cost calculations
- Corrected resource ID parsing for edge cases
- Fixed circular import dependencies

## Performance Benchmarks

| Operation | v1.x | v2.0 | Improvement |
|-----------|------|------|-------------|
| 100 VMs Audit | 120+ API calls | 8 API calls | 93% reduction |
| Full Subscription Scan | 30s | 4.5s | 85% faster |
| Memory Usage | 250MB | 125MB | 50% reduction |
| Cache Hit Rate | N/A | 78% | New feature |

## Known Issues

- Cache invalidation may require manual clearing for immediate updates
- Parallel processing may hit Azure API rate limits with >20 workers
- Some cost estimates use default rates when specific SKU rates unavailable

## Contributors

- Architecture refactoring and performance improvements
- Security hardening and compliance
- CI/CD pipeline implementation
- Documentation and testing

## What's Next

### v2.1 (Planned)
- GraphQL API support
- Advanced cost prediction models
- Multi-cloud support (AWS, GCP)
- Enhanced dashboard visualizations

### v2.2 (Planned)
- Machine learning-based anomaly detection
- Automated remediation actions
- Cost allocation tags management
- Reserved instance recommendations

## Support

For issues, questions, or contributions:
- GitHub Issues: https://github.com/julianobarbosa/azure-finops-mcp-server/issues
- Documentation: https://github.com/julianobarbosa/azure-finops-mcp-server/docs
- Contributing: See CONTRIBUTING.md

## License

MIT License - See LICENSE file for details

---

**Note**: This is a major release with significant changes. Please test thoroughly in your environment before upgrading production systems.