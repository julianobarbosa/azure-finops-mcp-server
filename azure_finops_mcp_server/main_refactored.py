"""Refactored main module with parallel processing and improved architecture."""

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from azure.mgmt.costmanagement import CostManagementClient
from azure.mgmt.costmanagement.models import (
    QueryAggregation,
    QueryDataset,
    QueryDefinition,
    QueryGrouping,
    QueryTimePeriod,
)
from mcp.server.fastmcp import FastMCP

from azure_finops_mcp_server.config import get_config
from azure_finops_mcp_server.helpers.parallel_processor import ParallelSubscriptionProcessor, parallel_cost_aggregation
from azure_finops_mcp_server.helpers.util import (
    ApiErrors,
    cost_filters,
    get_budget_data,
    get_credential,
    get_stopped_vms,
    get_unassociated_public_ips,
    get_unattached_disks,
    profiles_to_use,
)

logger = logging.getLogger(__name__)

mcp = FastMCP("azure_finops")


def process_single_subscription_cost(
    credential,
    subscription_id: str,
    subscription_name: str,
    period_start_date: date,
    period_end_date: date,
    tags: Optional[List[str]],
    dimensions: Optional[List[str]],
    azure_group_by: str,
) -> Dict[str, Any]:
    """
    Process cost data for a single subscription.

    Args:
        credential: Azure credential
        subscription_id: Subscription ID
        subscription_name: Subscription name
        period_start_date: Start date for cost period
        period_end_date: End date for cost period
        tags: Optional tag filters
        dimensions: Optional dimension filters
        azure_group_by: Grouping dimension

    Returns:
        Cost data dictionary for the subscription
    """
    try:
        cost_mgmt_client = CostManagementClient(credential, base_url="https://management.azure.com")

        # Create query definition
        time_period = QueryTimePeriod(from_property=period_start_date, to=period_end_date)

        # Build filters
        filter_kwargs = cost_filters(tags, dimensions)

        # Create dataset with grouping
        dataset = QueryDataset(
            granularity="None",
            aggregation={"totalCost": QueryAggregation(name="Cost", function="Sum")},
            grouping=[QueryGrouping(type="Dimension", name=azure_group_by)],
        )

        if filter_kwargs.get("filter"):
            dataset.filter = filter_kwargs["filter"]

        query_definition = QueryDefinition(type="Usage", timeframe="Custom", time_period=time_period, dataset=dataset)

        # Execute query
        scope = f"/subscriptions/{subscription_id}"
        query_result = cost_mgmt_client.query.usage(scope=scope, parameters=query_definition)

        # Process results
        total_cost = 0.0
        service_costs = defaultdict(float)

        if query_result.rows:
            for row in query_result.rows:
                if len(row) >= 2:
                    cost = float(row[0]) if row[0] else 0.0
                    service = row[1] if row[1] else "Unknown"
                    total_cost += cost
                    service_costs[service] += cost

        # Sort and filter service costs
        sorted_service_costs = dict(sorted(service_costs.items(), key=lambda item: item[1], reverse=True))
        processed_service_costs = {k: round(v, 2) for k, v in sorted_service_costs.items() if v > 0.001}

        return {
            "Subscription ID": subscription_id,
            "Period Start Date": period_start_date.isoformat(),
            "Period End Date": period_end_date.isoformat(),
            "Total Cost": round(total_cost, 2),
            f"Cost By {azure_group_by}": processed_service_costs,
            "Status": "success",
        }

    except Exception as e:
        logger.error(f"Error processing cost for subscription {subscription_name}: {str(e)}")
        return {"subscription_name": subscription_name, "status": "error", "message": str(e)}


@mcp.tool(annotations={"readOnlyHint": True})
async def get_cost(
    profiles: Optional[List[str]] = None,
    all_profiles: bool = False,
    time_range_days: Optional[int] = None,
    start_date_iso: Optional[str] = None,
    end_date_iso: Optional[str] = None,
    tags: Optional[List[str]] = None,
    dimensions: Optional[List[str]] = None,
    group_by: Optional[str] = "ServiceName",
) -> Dict[str, Any]:
    """
    Get cost data for specified Azure subscriptions for a defined period.
    Now with PARALLEL PROCESSING for multiple subscriptions.

    The period can be defined by 'time_range_days' (last N days including today)
    OR by explicit 'start_date_iso' and 'end_date_iso'.
    If 'start_date_iso' and 'end_date_iso' are provided, they take precedence.
    If no period is defined, defaults to the current month to date.
    Tags can be provided as a list of "Key=Value" strings to filter costs.
    Dimensions can be provided as a list of "Key=Value" strings to filter costs by specific dimensions.
    If no tags or dimensions are provided, all costs will be returned.
    Grouping can be done by a specific dimension, default is "ServiceName".

    Args:
        profiles: List of Azure subscription names or IDs to use.
        all_profiles: If True, use all available subscriptions; otherwise, use the specified profiles.
        time_range_days: Optional. Number of days for the cost data (e.g., last 7 days).
        start_date_iso: Optional. The start date of the period (inclusive) in YYYY-MM-DD format.
        end_date_iso: Optional. The end date of the period (inclusive) in YYYY-MM-DD format.
        tags: Optional. List of tags (e.g., ["Team=DevOps", "Env=Prod"]).
        dimensions: Optional. List of dimensions to filter costs by (e.g., ["ResourceLocation=eastus"]).
        group_by: Optional. The dimension to group costs by (default is "ServiceName").
    Returns:
        Dict: Processed cost data for the specified period.
    """
    if all_profiles:
        profiles_to_query, errors_for_profiles = profiles_to_use(all_profiles=True)
        if not profiles_to_query:
            return {"error": "No valid Azure subscriptions found. Please run 'az login' first."}
    else:
        profiles_to_query, errors_for_profiles = profiles_to_use(profiles)
        if not profiles_to_query:
            return {"error": "No valid Azure subscriptions found."}

    credential = get_credential()

    # Map AWS group_by values to Azure equivalents
    group_by_map = {
        "SERVICE": "ServiceName",
        "REGION": "ResourceLocation",
        "INSTANCE_TYPE": "MeterSubcategory",
        "RESOURCE_ID": "ResourceId",
        "RESOURCE_GROUP": "ResourceGroupName",
    }
    azure_group_by = group_by_map.get(group_by, group_by)

    # Prepare time period
    today = date.today()
    period_start_date: date
    period_end_date: date

    if start_date_iso and end_date_iso:
        try:
            period_start_date = datetime.strptime(start_date_iso, "%Y-%m-%d").date()
            period_end_date = datetime.strptime(end_date_iso, "%Y-%m-%d").date()
            if period_start_date > period_end_date:
                return {"status": "error", "message": "Start date cannot be after end date."}
        except ValueError:
            return {"status": "error", "message": "Invalid date format. Use YYYY-MM-DD."}
    elif time_range_days is not None:
        if time_range_days <= 0:
            return {"status": "error", "message": "time_range_days must be positive."}
        period_end_date = today
        period_start_date = today - timedelta(days=time_range_days - 1)
    else:  # Default to current month to date
        period_start_date = today.replace(day=1)
        period_end_date = today

    # Process subscriptions in parallel
    processor = ParallelSubscriptionProcessor()
    cost_data, processing_errors = processor.process_subscriptions(
        subscriptions=profiles_to_query,
        process_func=process_single_subscription_cost,
        credential=credential,
        period_start_date=period_start_date,
        period_end_date=period_end_date,
        tags=tags,
        dimensions=dimensions,
        azure_group_by=azure_group_by,
    )

    # Merge errors
    all_errors = {**errors_for_profiles, **processing_errors}

    # Add aggregation summary
    aggregation = parallel_cost_aggregation(cost_data)

    return {"accounts_cost_data": cost_data, "aggregation_summary": aggregation, "errors_for_profiles": all_errors}


def process_single_subscription_audit(
    credential, subscription_id: str, subscription_name: str, regions: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Process audit data for a single subscription.

    Args:
        credential: Azure credential
        subscription_id: Subscription ID
        subscription_name: Subscription name
        regions: Optional list of regions to filter

    Returns:
        Audit data dictionary for the subscription
    """
    try:
        # Get stopped VMs
        stopped_vms, vm_errors = get_stopped_vms(credential, subscription_id, regions)

        # Get unattached disks
        unattached_disks, disk_errors = get_unattached_disks(credential, subscription_id, regions)

        # Get unassociated public IPs
        unassociated_ips, ip_errors = get_unassociated_public_ips(credential, subscription_id, regions)

        # Get budget data
        budget_status, budget_errors = get_budget_data(credential, subscription_id)

        return {
            "Subscription ID": subscription_id,
            "Stopped/Deallocated VMs": stopped_vms,
            "Unattached Managed Disks": unattached_disks,
            "Unassociated Public IPs": unassociated_ips,
            "Budget Status": budget_status,
            "Errors getting VMs": vm_errors,
            "Errors getting Disks": disk_errors,
            "Errors getting Public IPs": ip_errors,
            "Errors getting Budgets": budget_errors,
        }

    except Exception as e:
        logger.error(f"Error processing audit for subscription {subscription_name}: {str(e)}")
        return {"subscription_name": subscription_name, "status": "error", "message": str(e)}


@mcp.tool(annotations={"readOnlyHint": True})
async def run_finops_audit(
    regions: Optional[List[str]] = None,
    profiles: Optional[List[str]] = None,
    all_profiles: bool = False,
) -> Dict[Any, Any]:
    """
    Get FinOps Audit Report findings for your Azure subscriptions.
    Now with PARALLEL PROCESSING for multiple subscriptions.

    Each Audit Report includes:
        Stopped/Deallocated VMs,
        Unattached Managed Disks,
        Unassociated Public IPs,
        Budget Status for one or more specified Azure subscriptions.

    Args:
        regions: Optional list of Azure regions as strings (e.g., ["eastus", "westus"]).
        profiles: List of Azure subscription names or IDs as strings.
        all_profiles: If True, use all available subscriptions; otherwise, use the specified profiles.

    Returns:
        Processed Audit data for specified subscriptions and regions in JSON(dict) format with errors caught from APIs.
    """
    if all_profiles:
        profiles_to_query, errors_for_profiles = profiles_to_use(all_profiles=True)
        if not profiles_to_query:
            return {"error": "No valid Azure subscriptions found. Please run 'az login' first."}
    else:
        profiles_to_query, errors_for_profiles = profiles_to_use(profiles)
        if not profiles_to_query:
            return {"error": "No valid Azure subscriptions found."}

    credential = get_credential()

    # Process subscriptions in parallel
    processor = ParallelSubscriptionProcessor()
    audit_results, processing_errors = processor.process_subscriptions(
        subscriptions=profiles_to_query,
        process_func=process_single_subscription_audit,
        credential=credential,
        regions=regions,
    )

    # Merge errors
    all_errors = {**errors_for_profiles, **processing_errors}

    # Add summary statistics
    summary = {
        "total_subscriptions_audited": len(audit_results),
        "total_stopped_vms": sum(
            len(data.get("Stopped/Deallocated VMs", {}).get("stopped_vms", []))
            for data in audit_results.values()
            if isinstance(data, dict) and "Stopped/Deallocated VMs" in data
        ),
        "total_unattached_disks": sum(
            len(data.get("Unattached Managed Disks", {}).get("unattached_disks", []))
            for data in audit_results.values()
            if isinstance(data, dict) and "Unattached Managed Disks" in data
        ),
        "total_unassociated_ips": sum(
            len(data.get("Unassociated Public IPs", {}).get("unassociated_ips", []))
            for data in audit_results.values()
            if isinstance(data, dict) and "Unassociated Public IPs" in data
        ),
    }

    return {"Audit Report": audit_results, "Summary": summary, "Error processing subscriptions": all_errors}


def run_server():
    """
    Entry point to the FastMCP server.
    """
    # Configure logging
    config = get_config()
    logging.basicConfig(
        level=getattr(logging, config.log_level), format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    logger.info("Starting Azure FinOps MCP Server (Refactored)")
    logger.info(f"Parallel workers: {config.max_parallel_workers}")
    logger.info(f"Cache enabled: {config.enable_caching}")

    mcp.run(transport="stdio")


if __name__ == "__main__":
    run_server()
