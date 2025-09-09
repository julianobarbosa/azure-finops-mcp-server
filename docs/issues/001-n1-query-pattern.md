# Critical: N+1 Query Pattern in VM Status Checking

## Problem
The code makes individual API calls for each VM's power state, creating an N+1 query pattern that severely impacts performance.

## Location
- File: `azure_finops_mcp_server/helpers/util.py`
- Lines: 115-128
- Function: `get_stopped_vms()`

## Current Implementation
```python
for vm in compute_client.virtual_machines.list_all():
    instance_view = compute_client.virtual_machines.instance_view(
        resource_group_name=vm.id.split('/')[4],
        vm_name=vm.name
    )
```

## Impact
- With 100 VMs, this creates 101 API calls instead of 1-2
- Adds 10-30 seconds of execution time for typical workloads
- Azure API rate limiting risk

## Proposed Solution
Use batch operations or the `list_all()` method with expanded view parameter:
```python
# Option 1: Use expand parameter
vms = compute_client.virtual_machines.list_all(expand='instanceView')

# Option 2: Batch fetch instance views
vm_list = list(compute_client.virtual_machines.list_all())
# Then use batch operation if available
```

## Priority
**Critical** - This is the single biggest performance bottleneck in the codebase

## Acceptance Criteria
- [ ] Replace individual API calls with batch operation
- [ ] Verify performance improvement with timing logs
- [ ] Test with 50+ VMs to confirm scaling improvement

## Labels
- bug
- performance
- critical