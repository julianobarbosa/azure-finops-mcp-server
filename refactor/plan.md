# Refactor Plan - 2025-09-09T10:00:00

## Initial State Analysis

### Current Architecture
- **Framework**: Azure MCP Server using FastMCP with Azure SDK
- **Structure**: Main module + helpers package with specialized operation modules
- **Dependencies**: Azure SDK, MCP framework, asyncio
- **Test Coverage**: Limited - only integration tests exist, no unit tests

### Critical Problem Areas
1. **N+1 Query Pattern**: VM operations making individual API calls per resource
2. **Direct SDK Coupling**: All helpers directly instantiate Azure clients
3. **Sequential Processing**: Subscriptions processed one by one despite concurrent utilities
4. **Poor Testability**: No dependency injection, mixed pure/impure functions
5. **Monolithic Functions**: Functions exceeding 100 lines with multiple responsibilities

### Dependencies
- External: azure-mgmt-*, mcp.server.fastmcp
- Internal: Heavy coupling between helpers and util module

## Refactoring Tasks

### Priority 1: Critical Performance Issues
- [x] Fix N+1 query pattern in vm_operations.py
- [x] Implement batch API calls for VM instance views
- [ ] Add parallel processing for subscription queries
- [ ] Optimize API usage patterns

### Priority 2: Testability & Abstraction
- [ ] Create Azure client factory/interface
- [ ] Implement dependency injection pattern
- [ ] Extract pure functions for business logic
- [ ] Create mock-friendly abstractions

### Priority 3: Configuration Management
- [x] Extract hardcoded cost rates to config
- [x] Move Azure patterns to configuration
- [ ] Create environment-based config loading
- [ ] Add configuration validation

### Priority 4: Code Organization
- [x] Extract common utilities (resource ID parsing)
- [x] Split monolithic functions (>50 lines)
- [ ] Separate presentation from business logic
- [ ] Remove circular dependencies

### Priority 5: Error Handling
- [ ] Standardize error response format
- [ ] Implement consistent error wrapping
- [ ] Create exception hierarchy
- [ ] Add proper logging

### Priority 6: Code Duplication
- [ ] Extract resource ID parsing utility
- [ ] Consolidate cost estimation logic
- [ ] Unify client initialization patterns
- [ ] Create shared validation functions

## Validation Checklist
- [ ] All N+1 queries eliminated
- [ ] No direct Azure client instantiation in business logic
- [ ] All hardcoded values moved to config
- [ ] All functions < 50 lines
- [ ] No circular imports
- [ ] Unit tests can mock all dependencies
- [ ] Build successful
- [ ] Integration tests passing

## De-Para Mapping

| Before | After | Status |
|--------|-------|--------|
| Direct ComputeManagementClient() | AzureClientFactory.compute() | Pending |
| vm.id.split('/')[4] | extract_resource_group(vm.id) | Pending |
| Hardcoded cost rates | config.COST_RATES | Pending |
| Sequential subscription processing | Parallel with concurrent_util | Pending |
| Individual VM API calls | Batch API operations | Pending |
| Mixed business/API logic | Separated layers | Pending |
| 100+ line functions | Multiple focused functions | Pending |
| Scattered error handling | Centralized error wrapper | Pending |

## Risk Assessment

### High Risk
- N+1 query fix - could affect data accuracy if not done correctly
- Parallel processing - needs proper error aggregation

### Medium Risk
- Dependency injection - requires touching all modules
- Configuration extraction - needs careful validation

### Low Risk
- Utility extraction - simple refactoring
- Function splitting - preserves existing logic

## Implementation Order

### Phase 1: Quick Wins (Low Risk, High Impact)
1. Extract resource ID parsing utility
2. Create configuration module for hardcoded values
3. Split largest functions (budget_operations, disk_operations)

### Phase 2: Performance Critical (High Risk, High Impact)
1. Fix N+1 query in vm_operations
2. Implement parallel subscription processing
3. Add batch API operations

### Phase 3: Architecture (Medium Risk, High Value)
1. Create Azure client factory
2. Implement dependency injection
3. Separate business logic from API calls

### Phase 4: Quality & Maintenance
1. Standardize error handling
2. Add comprehensive logging
3. Create unit test structure

## Success Metrics
- API call reduction: 100+ → <10 for 100 VMs
- Function size: All <50 lines
- Test coverage: 0% → 80%+ unit test coverage
- Performance: 30s → <5s for typical audit
- Maintainability: Clear separation of concerns

## Notes
- Preserve all existing functionality
- Maintain backward compatibility
- Create incremental commits for rollback capability
- Document breaking changes if any
