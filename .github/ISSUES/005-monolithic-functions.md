# High: Monolithic Functions with High Complexity

## Problem
Several functions are too large and handle multiple responsibilities, violating the Single Responsibility Principle and making the code difficult to maintain, test, and understand.

## Primary Offender: get_cost() Function

### Location
- File: `azure_finops_mcp_server/main.py`
- Lines: 22-181
- **Size: 160 lines**
- **Cyclomatic Complexity: ~20+**

### Current Responsibilities (All in One Function!)
1. Parameter validation
2. Date parsing and time period calculation
3. Azure credential management
4. Query definition building
5. Subscription filtering
6. API call execution
7. Result processing and aggregation
8. Response formatting
9. Error handling

## Code Smell Indicators
```python
def get_cost(...):  # 160 lines!
    # Parameter validation (lines 30-45)
    # Date processing (lines 46-75)
    # Query building (lines 76-100)
    # Subscription loop (lines 101-150)
    # Result processing (lines 151-175)
    # Response formatting (lines 176-181)
```

## Impact
- **Cognitive Load**: Developers need to understand 160 lines to make any change
- **Testing Nightmare**: Cannot test individual components
- **Bug-Prone**: Changes affect multiple concerns
- **Poor Reusability**: Logic cannot be reused elsewhere
- **Difficult Debugging**: Hard to isolate issues

## Proposed Refactoring

### Step 1: Extract Parameter Validation
```python
def validate_cost_parameters(start_date: Optional[str],
                            end_date: Optional[str],
                            time_range_days: Optional[int]) -> None:
    """Validate input parameters for cost query."""
    if not start_date and not time_range_days:
        raise ValueError("Either start_date or time_range_days must be provided")

    if start_date and not end_date:
        raise ValueError("end_date required when start_date is provided")
```

### Step 2: Extract Time Period Calculation
```python
def calculate_time_period(start_date: Optional[str],
                         end_date: Optional[str],
                         time_range_days: Optional[int]) -> QueryTimePeriod:
    """Calculate the time period for cost query."""
    if start_date and end_date:
        return QueryTimePeriod(
            from_property=datetime.fromisoformat(start_date),
            to=datetime.fromisoformat(end_date)
        )
    else:
        end = datetime.now(timezone.utc).replace(hour=23, minute=59)
        start = end - timedelta(days=time_range_days)
        return QueryTimePeriod(from_property=start, to=end)
```

### Step 3: Extract Query Building
```python
def build_cost_query(time_period: QueryTimePeriod,
                    group_by: List[str],
                    filters: Optional[Dict] = None) -> QueryDefinition:
    """Build Azure Cost Management query definition."""
    grouping = [
        QueryGrouping(type='Dimension', name=dimension)
        for dimension in group_by
    ]

    dataset = QueryDataset(
        granularity='None',
        aggregation={'totalCost': QueryAggregation(name='Cost', function='Sum')},
        grouping=grouping
    )

    if filters:
        dataset.filter = build_query_filter(filters)

    return QueryDefinition(
        type='Usage',
        timeframe='Custom',
        time_period=time_period,
        dataset=dataset
    )
```

### Step 4: Extract Cost Data Fetching
```python
class CostDataFetcher:
    def __init__(self, credential):
        self.credential = credential

    def fetch_subscription_costs(self,
                                subscription_id: str,
                                query: QueryDefinition) -> Dict:
        """Fetch cost data for a single subscription."""
        client = CostManagementClient(
            self.credential,
            base_url="https://management.azure.com"
        )

        result = client.query.usage(
            scope=f"/subscriptions/{subscription_id}",
            parameters=query
        )

        return self._process_query_result(result)

    def _process_query_result(self, result) -> Dict:
        """Process raw query results into structured format."""
        # Processing logic here
        pass
```

### Step 5: Refactored Main Function
```python
@mcp.tool()
async def get_cost(
    start_date_iso: Optional[str] = None,
    end_date_iso: Optional[str] = None,
    time_range_days: Optional[int] = 30,
    group_by_dimensions: Optional[str] = "ServiceName",
    filter_subscription_names: Optional[str] = None,
    filter_subscription_ids: Optional[str] = None,
    tags: Optional[str] = None
) -> str:
    """Refactored, clean main function."""
    # Step 1: Validate
    validate_cost_parameters(start_date_iso, end_date_iso, time_range_days)

    # Step 2: Prepare query
    time_period = calculate_time_period(start_date_iso, end_date_iso, time_range_days)
    query = build_cost_query(time_period, group_by_dimensions.split(','), tags)

    # Step 3: Get subscriptions
    subscriptions = get_target_subscriptions(filter_subscription_names, filter_subscription_ids)

    # Step 4: Fetch costs
    fetcher = CostDataFetcher(get_credential())
    all_costs = {}

    for sub_id in subscriptions:
        try:
            costs = fetcher.fetch_subscription_costs(sub_id, query)
            all_costs[sub_id] = costs
        except Exception as e:
            logger.error(f"Failed to fetch costs for {sub_id}: {e}")

    # Step 5: Format response
    return format_cost_response(all_costs, time_period)
```

## Other Functions Needing Refactoring

### get_detailed_disk_audit()
- File: `azure_finops_mcp_server/helpers/util.py`
- Lines: 222-326 (104 lines)
- Should be split into: disk fetching, categorization, cost calculation

### run_finops_audit()
- File: `azure_finops_mcp_server/main.py`
- Lines: 184-263 (79 lines)
- Should be split into: individual audit functions

## Priority
**High** - Major maintainability and testing blocker

## Acceptance Criteria
- [ ] Break get_cost() into 5+ smaller functions (<30 lines each)
- [ ] Extract reusable components (validation, query building)
- [ ] Add unit tests for each extracted function
- [ ] Ensure no regression in functionality
- [ ] Document the refactored architecture
- [ ] Apply same principles to other large functions

## Benefits After Refactoring
- **Testability**: Each component can be unit tested
- **Maintainability**: Changes isolated to specific functions
- **Readability**: Each function has clear, single purpose
- **Reusability**: Components can be used elsewhere
- **Debugging**: Issues easier to isolate

## Labels
- refactoring
- maintainability
- high-priority
- technical-debt
