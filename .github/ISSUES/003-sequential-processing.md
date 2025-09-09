# High: Sequential Subscription Processing Causing Performance Bottleneck

## Problem
All Azure subscriptions are processed sequentially, blocking on each subscription's API calls. This creates unnecessary delays when analyzing multiple subscriptions.

## Locations
1. **Cost Analysis**
   - File: `azure_finops_mcp_server/main.py`
   - Lines: 77-181
   - Function: `get_cost()`

2. **Resource Audit**
   - File: `azure_finops_mcp_server/main.py`
   - Lines: 219-244
   - Function: `run_finops_audit()`

## Current Implementation
```python
# Sequential processing
for subscription_id, subscription_names in profiles_to_query.items():
    cost_mgmt_client = CostManagementClient(credential, base_url="https://management.azure.com")
    query_result = cost_mgmt_client.query.usage(
        scope=f"/subscriptions/{subscription_id}",
        parameters=query_definition
    )
    # Process results...
```

## Performance Impact
- With 5 subscriptions taking 10 seconds each: **50 seconds total**
- With parallel processing: **~10 seconds total** (80% improvement)
- Blocks UI/user experience during long operations

## Proposed Solution

### Option 1: asyncio with aiohttp
```python
import asyncio
from typing import List, Dict

async def get_subscription_cost(subscription_id: str, credential, query_definition) -> Dict:
    # Async Azure SDK call
    async with CostManagementClient(credential) as client:
        result = await client.query.usage(
            scope=f"/subscriptions/{subscription_id}",
            parameters=query_definition
        )
    return process_result(result)

async def get_all_costs(subscriptions: List[str], credential, query_definition):
    tasks = [get_subscription_cost(sub_id, credential, query_definition)
             for sub_id in subscriptions]
    results = await asyncio.gather(*tasks)
    return results
```

### Option 2: concurrent.futures
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def process_subscription(args):
    subscription_id, credential, query_definition = args
    client = CostManagementClient(credential)
    result = client.query.usage(
        scope=f"/subscriptions/{subscription_id}",
        parameters=query_definition
    )
    return subscription_id, result

def get_all_costs_parallel(subscriptions, credential, query_definition):
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        for sub_id in subscriptions:
            future = executor.submit(process_subscription,
                                   (sub_id, credential, query_definition))
            futures.append(future)

        results = {}
        for future in as_completed(futures):
            sub_id, result = future.result()
            results[sub_id] = result
    return results
```

## Implementation Considerations
- Add timeout handling for individual subscription queries
- Implement retry logic for failed subscriptions
- Consider rate limiting to avoid Azure API throttling
- Add progress reporting for long-running operations

## Priority
**High** - Major performance impact on user experience

## Acceptance Criteria
- [ ] Implement parallel processing for subscription queries
- [ ] Add configurable concurrency limit (default: 5)
- [ ] Include timeout handling (30s per subscription)
- [ ] Add retry logic for transient failures
- [ ] Measure and log performance improvement
- [ ] Ensure error handling doesn't fail entire operation

## Expected Performance Improvement
- Current: O(n) where n = number of subscriptions
- Target: O(1) with parallel processing (bounded by slowest subscription)
- Expected improvement: 60-80% reduction in execution time

## Labels
- performance
- enhancement
- high-priority
