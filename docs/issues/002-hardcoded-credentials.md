# Critical: Hardcoded Azure Subscription IDs in Source Code

## Problem
Production Azure subscription IDs are hardcoded directly in the source code, creating security and maintainability issues.

## Locations
1. **Production Code**
   - File: `get_cafehyna_costs.py`
   - Line: 15
   - Code: `subscription_id = '51f4e493-4815-4858-8bbb-f263e7fb63d6'  # hypera-pharma`

2. **Test Code**
   - File: `test_disk_filter.py`
   - Line: 20
   - Code: `subscription_id = os.environ.get('AZURE_SUBSCRIPTION_ID', '51f4e493-4815-4858-8bbb-f263e7fb63d6')`

## Security Impact
- **Information Disclosure**: Subscription IDs exposed in public repository
- **Unauthorized Access Risk**: Attackers can target specific subscriptions
- **Compliance Issues**: Violates security best practices for credential management

## Proposed Solution

### Immediate Fix
```python
# Use environment variables exclusively
subscription_id = os.environ.get('AZURE_SUBSCRIPTION_ID')
if not subscription_id:
    raise ValueError("AZURE_SUBSCRIPTION_ID environment variable is required")
```

### Configuration File Approach
```python
# config.py
import os
from typing import Optional

class Config:
    AZURE_SUBSCRIPTION_ID: Optional[str] = os.environ.get('AZURE_SUBSCRIPTION_ID')
    RESOURCE_GROUP_PATTERNS: list = os.environ.get('RG_PATTERNS', '').split(',')
    
    @classmethod
    def validate(cls):
        if not cls.AZURE_SUBSCRIPTION_ID:
            raise ValueError("AZURE_SUBSCRIPTION_ID is required")
```

## Priority
**Critical** - Security vulnerability with production credentials exposed

## Acceptance Criteria
- [ ] Remove all hardcoded subscription IDs from source code
- [ ] Implement environment variable configuration
- [ ] Add validation for required configuration
- [ ] Update documentation with configuration requirements
- [ ] Add .env.example file with template (no real values)

## Labels
- security
- critical
- configuration