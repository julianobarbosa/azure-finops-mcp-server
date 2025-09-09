# MCP Tools API Reference

The Azure FinOps MCP Server exposes two main tools through the Model Context Protocol.

## get_cost

Retrieves Azure cost data with flexible filtering and grouping options.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `subscription_id` | string | No | Specific subscription ID or "all" for all subscriptions |
| `time_period` | string | No | Time range: "last_7_days", "last_30_days", "last_90_days", "current_month", "last_month" |
| `start_date` | string | No | Custom start date (YYYY-MM-DD) |
| `end_date` | string | No | Custom end date (YYYY-MM-DD) |
| `granularity` | string | No | Data granularity: "daily", "monthly", "accumulated" |
| `group_by` | array | No | Dimensions to group by: ["subscription", "service", "location", "resource_group"] |
| `filter_tag` | array | No | Tag filters in "key=value" format |
| `filter_dimension` | array | No | Dimension filters like "ServiceName=Virtual Machines" |

### Response Schema

```json
{
  "subscriptions": {
    "subscription-id": {
      "subscription_name": "string",
      "subscription_id": "string",
      "time_period": {
        "start": "string",
        "end": "string"
      },
      "costs": [
        {
          "date": "string",
          "cost": "number",
          "currency": "string",
          "grouped_costs": {
            "dimension": "value"
          }
        }
      ],
      "summary": {
        "total_cost": "number",
        "average_daily_cost": "number",
        "currency": "string",
        "cost_by_service": {},
        "cost_by_location": {},
        "cost_by_resource_group": {}
      }
    }
  },
  "overall_summary": {
    "total_cost_all_subscriptions": "number",
    "subscription_count": "number",
    "date_range": {
      "start": "string",
      "end": "string"
    }
  },
  "api_errors": {}
}
```

### Example Usage

```python
# Get last 30 days costs grouped by service
result = get_cost(
    subscription_id="all",
    time_period="last_30_days",
    group_by=["service"]
)

# Get costs for specific date range with filters
result = get_cost(
    start_date="2024-01-01",
    end_date="2024-01-31",
    filter_dimension=["ServiceName=Virtual Machines"],
    group_by=["location", "resource_group"]
)
```

## run_finops_audit

Performs comprehensive FinOps audit to identify cost optimization opportunities.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `subscription_id` | string | No | Specific subscription ID or "all" for all subscriptions |
| `regions` | array | No | List of Azure regions to audit |
| `resource_types` | array | No | Resource types to audit: ["vms", "disks", "ips", "all"] |
| `include_recommendations` | boolean | No | Include optimization recommendations (default: true) |

### Response Schema

```json
{
  "subscriptions": {
    "subscription-id": {
      "subscription_name": "string",
      "subscription_id": "string",
      "audit_results": {
        "stopped_vms": {
          "resources": [],
          "total_count": "number",
          "potential_monthly_savings": "number"
        },
        "unattached_disks": {
          "resources": [],
          "total_count": "number",
          "potential_monthly_savings": "number"
        },
        "unassociated_ips": {
          "resources": [],
          "total_count": "number",
          "potential_monthly_savings": "number"
        }
      },
      "summary": {
        "total_resources_flagged": "number",
        "total_potential_monthly_savings": "number",
        "total_potential_annual_savings": "number"
      },
      "recommendations": []
    }
  },
  "overall_summary": {
    "total_subscriptions_audited": "number",
    "total_resources_flagged": "number",
    "total_potential_monthly_savings": "number",
    "total_potential_annual_savings": "number",
    "top_recommendations": []
  },
  "api_errors": {}
}
```

### Resource Details

#### Stopped VMs
```json
{
  "name": "string",
  "resource_group": "string",
  "location": "string",
  "vm_size": "string",
  "estimated_monthly_cost": "number"
}
```

#### Unattached Disks
```json
{
  "name": "string",
  "resource_group": "string",
  "location": "string",
  "disk_size_gb": "number",
  "disk_sku": "string",
  "estimated_monthly_cost": "number"
}
```

#### Unassociated IPs
```json
{
  "name": "string",
  "resource_group": "string",
  "location": "string",
  "allocation_method": "string",
  "sku": "string",
  "estimated_monthly_cost": "number"
}
```

### Example Usage

```python
# Audit all resources in specific regions
result = run_finops_audit(
    subscription_id="all",
    regions=["eastus", "westus2"],
    resource_types=["all"]
)

# Quick VM audit for single subscription
result = run_finops_audit(
    subscription_id="12345-67890",
    resource_types=["vms"],
    include_recommendations=False
)
```

## Error Handling

Both tools implement comprehensive error handling:

### Error Response Format
```json
{
  "api_errors": {
    "subscription-id": "Error message",
    "general": "General error message"
  }
}
```

### Common Error Codes

| Error | Description | Resolution |
|-------|-------------|------------|
| `AuthorizationFailed` | Insufficient permissions | Check RBAC roles |
| `SubscriptionNotFound` | Invalid subscription ID | Verify subscription exists |
| `RateLimitExceeded` | Too many API requests | Implement retry logic |
| `InvalidDateRange` | Invalid date parameters | Check date format |

## Performance Considerations

### Caching
- Results are cached for 5 minutes by default
- Cache TTL can be configured via environment variables
- Use `cache_bypass=true` to force fresh data

### Parallel Processing
- Multiple subscriptions processed in parallel
- Default: 5 concurrent workers
- Configurable via `AZURE_MAX_WORKERS` environment variable

### Rate Limiting
- Automatic retry with exponential backoff
- Maximum 3 retries per request
- Configurable via `AZURE_MAX_RETRIES` environment variable

## Best Practices

1. **Use Specific Filters**: Always filter by regions or resource types when possible
2. **Batch Requests**: Process multiple subscriptions in single calls
3. **Cache Results**: Leverage caching for frequently accessed data
4. **Handle Errors**: Implement proper error handling for API failures
5. **Monitor Usage**: Track API call patterns to optimize performance