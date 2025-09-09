# High: Poor Testability Due to Tight Azure SDK Coupling

## Problem
The codebase directly instantiates Azure SDK clients throughout, making it impossible to unit test business logic without real Azure credentials and API calls.

## Affected Areas
1. **Main Module**
   - File: `azure_finops_mcp_server/main.py`
   - Lines: 81, 113, 171, 220-262
   - Direct client instantiation in business logic

2. **Utility Module**
   - File: `azure_finops_mcp_server/helpers/util.py`
   - Lines: 113, 175, 363
   - Azure clients created inside utility functions

## Current Anti-Pattern
```python
def get_stopped_vms(credential, subscription_id, regions=None):
    # Direct instantiation - cannot mock
    compute_client = ComputeManagementClient(credential, subscription_id)
    
    for vm in compute_client.virtual_machines.list_all():
        # Business logic mixed with Azure SDK calls
        instance_view = compute_client.virtual_machines.instance_view(...)
```

## Testing Impact
- **Cannot unit test** without Azure credentials
- **Cannot test edge cases** (API failures, specific responses)
- **Slow test execution** due to real API calls
- **Costly testing** (Azure API usage charges)
- **Flaky tests** due to network/service dependencies

## Proposed Solution

### 1. Introduce Abstraction Layer
```python
# azure_client_interface.py
from abc import ABC, abstractmethod
from typing import List, Optional

class AzureComputeClient(ABC):
    @abstractmethod
    def list_all_vms(self) -> List[VirtualMachine]:
        pass
    
    @abstractmethod
    def get_vm_power_state(self, resource_group: str, vm_name: str) -> str:
        pass

class AzureCostClient(ABC):
    @abstractmethod
    def query_usage(self, scope: str, parameters: QueryDefinition) -> QueryResult:
        pass
```

### 2. Implement Concrete Adapters
```python
# azure_client_impl.py
class AzureComputeClientImpl(AzureComputeClient):
    def __init__(self, credential, subscription_id):
        self._client = ComputeManagementClient(credential, subscription_id)
    
    def list_all_vms(self) -> List[VirtualMachine]:
        return list(self._client.virtual_machines.list_all())
    
    def get_vm_power_state(self, resource_group: str, vm_name: str) -> str:
        view = self._client.virtual_machines.instance_view(resource_group, vm_name)
        return self._extract_power_state(view)
```

### 3. Dependency Injection
```python
# refactored_util.py
def get_stopped_vms(compute_client: AzureComputeClient, regions: Optional[List[str]] = None):
    """Now testable with mock client"""
    vms = compute_client.list_all_vms()
    
    stopped_vms = []
    for vm in vms:
        if regions and vm.location not in regions:
            continue
            
        power_state = compute_client.get_vm_power_state(
            resource_group=extract_resource_group(vm.id),
            vm_name=vm.name
        )
        
        if power_state == "stopped":
            stopped_vms.append(vm)
    
    return stopped_vms
```

### 4. Easy Testing with Mocks
```python
# test_util.py
from unittest.mock import Mock
import pytest

def test_get_stopped_vms_filters_by_region():
    # Arrange
    mock_client = Mock(spec=AzureComputeClient)
    mock_client.list_all_vms.return_value = [
        create_mock_vm("vm1", "eastus"),
        create_mock_vm("vm2", "westus"),
    ]
    mock_client.get_vm_power_state.return_value = "stopped"
    
    # Act
    result = get_stopped_vms(mock_client, regions=["eastus"])
    
    # Assert
    assert len(result) == 1
    assert result[0].name == "vm1"
```

## Implementation Strategy

### Phase 1: Create Abstractions
- Define interfaces for all Azure SDK interactions
- Create adapter implementations

### Phase 2: Refactor Core Functions
- Update functions to accept client interfaces
- Remove direct SDK instantiation

### Phase 3: Add Dependency Injection
- Implement factory pattern for client creation
- Add configuration-based client management

### Phase 4: Comprehensive Testing
- Add unit tests with mocked clients
- Create integration tests with real clients
- Add performance tests

## Priority
**High** - Blocks effective testing and CI/CD implementation

## Acceptance Criteria
- [ ] Define abstraction interfaces for Azure clients
- [ ] Implement concrete adapters wrapping Azure SDK
- [ ] Refactor all functions to use dependency injection
- [ ] Add unit tests achieving >80% coverage
- [ ] Document testing approach
- [ ] Ensure no regression in functionality

## Benefits
- **Fast unit tests** (milliseconds vs seconds)
- **Reliable tests** (no network dependencies)
- **Edge case testing** (simulate errors, timeouts)
- **Cost savings** (no API calls in tests)
- **Better design** (clear separation of concerns)

## Labels
- testing
- refactoring
- high-priority
- technical-debt