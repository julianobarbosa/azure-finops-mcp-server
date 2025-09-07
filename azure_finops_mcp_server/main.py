from azure.mgmt.costmanagement import CostManagementClient
from azure.mgmt.costmanagement.models import QueryDefinition, QueryDataset, QueryTimePeriod, QueryAggregation, QueryGrouping
from mcp.server.fastmcp import FastMCP
from datetime import date, datetime, timedelta
from typing import Dict, Any, Optional, List
from collections import defaultdict

from azure_finops_mcp_server.helpers.util import (
    profiles_to_use,
    ApiErrors,
    get_stopped_vms,
    get_unattached_disks,
    get_unassociated_public_ips,
    get_budget_data,
    cost_filters,
    get_credential,
)

mcp = FastMCP("azure_finops")

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
    
    cost_data = {}
    credential = get_credential()
    
    # Map AWS group_by values to Azure equivalents
    group_by_map = {
        "SERVICE": "ServiceName",
        "REGION": "ResourceLocation",
        "INSTANCE_TYPE": "MeterSubcategory",
        "RESOURCE_ID": "ResourceId",
        "RESOURCE_GROUP": "ResourceGroupName"
    }
    azure_group_by = group_by_map.get(group_by, group_by)
    
    for subscription_id, subscription_names in profiles_to_query.items():
        primary_name = subscription_names[0]
        
        try:
            cost_mgmt_client = CostManagementClient(credential, subscription_id)
            
            # Prepare time period
            today = date.today()
            period_start_date: date
            period_end_date: date
            
            if start_date_iso and end_date_iso:
                try:
                    period_start_date = datetime.strptime(start_date_iso, "%Y-%m-%d").date()
                    period_end_date = datetime.strptime(end_date_iso, "%Y-%m-%d").date()
                    if period_start_date > period_end_date:
                        return {"profile_name": primary_name, "status": "error", "message": "Start date cannot be after end date."}
                except ValueError:
                    return {"profile_name": primary_name, "status": "error", "message": "Invalid date format. Use YYYY-MM-DD."}
            elif time_range_days is not None:
                if time_range_days <= 0:
                    return {"profile_name": primary_name, "status": "error", "message": "time_range_days must be positive."}
                period_end_date = today
                period_start_date = today - timedelta(days=time_range_days - 1)
            else:  # Default to current month to date
                period_start_date = today.replace(day=1)
                period_end_date = today
            
            # Create query definition
            time_period = QueryTimePeriod(
                from_property=period_start_date,
                to=period_end_date
            )
            
            # Build filters
            filter_kwargs = cost_filters(tags, dimensions)
            
            # Create dataset with grouping
            dataset = QueryDataset(
                granularity="None",
                aggregation={
                    "totalCost": QueryAggregation(
                        name="Cost",
                        function="Sum"
                    )
                },
                grouping=[
                    QueryGrouping(
                        type="Dimension",
                        name=azure_group_by
                    )
                ]
            )
            
            if filter_kwargs.get("filter"):
                dataset.filter = filter_kwargs["filter"]
            
            query_definition = QueryDefinition(
                type="Usage",
                timeframe="Custom",
                time_period=time_period,
                dataset=dataset
            )
            
            # Execute query
            scope = f"/subscriptions/{subscription_id}"
            query_result = cost_mgmt_client.query.usage(
                scope=scope,
                parameters=query_definition
            )
            
            # Process results
            total_cost = 0.0
            service_costs = defaultdict(float)
            
            if query_result.rows:
                for row in query_result.rows:
                    # Row format: [cost_value, dimension_value]
                    if len(row) >= 2:
                        cost = float(row[0]) if row[0] else 0.0
                        service = row[1] if row[1] else "Unknown"
                        total_cost += cost
                        service_costs[service] += cost
            
            # Sort and filter service costs
            sorted_service_costs = dict(sorted(service_costs.items(), key=lambda item: item[1], reverse=True))
            processed_service_costs = {k: round(v, 2) for k, v in sorted_service_costs.items() if v > 0.001}
            
            cost_data[f"Subscription: {primary_name}"] = {
                "Subscription ID": subscription_id,
                "Period Start Date": period_start_date.isoformat(),
                "Period End Date": period_end_date.isoformat(),
                "Total Cost": round(total_cost, 2),
                f"Cost By {azure_group_by}": processed_service_costs,
                "Status": "success"
            }
            
        except Exception as e:
            cost_data[primary_name] = {
                "subscription_name": primary_name,
                "status": "error",
                "message": str(e)
            }
    
    return {"accounts_cost_data": cost_data, "errors_for_profiles": errors_for_profiles}


@mcp.tool(annotations={"readOnlyHint": True})
async def run_finops_audit(
    regions: Optional[List[str]] = None,
    profiles: Optional[List[str]] = None,
    all_profiles: bool = False,
) -> Dict[Any, Any]:
    """
    Get FinOps Audit Report findings for your Azure subscriptions.
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
    audit_report: Dict[str, Any] = defaultdict(list)
    
    if all_profiles:
        profiles_to_query, errors_for_profiles = profiles_to_use(all_profiles=True)
        if not profiles_to_query:
            return {"error": "No valid Azure subscriptions found. Please run 'az login' first."}
    else:
        profiles_to_query, errors_for_profiles = profiles_to_use(profiles)
        if not profiles_to_query:
            return {"error": "No valid Azure subscriptions found."}
    
    credential = get_credential()
    
    for subscription_id, subscription_names in profiles_to_query.items():
        primary_name = subscription_names[0]
        
        # Get stopped VMs
        stopped_vms, vm_errors = get_stopped_vms(credential, subscription_id, regions)
        
        # Get unattached disks
        unattached_disks, disk_errors = get_unattached_disks(credential, subscription_id, regions)
        
        # Get unassociated public IPs
        unassociated_ips, ip_errors = get_unassociated_public_ips(credential, subscription_id, regions)
        
        # Get budget data
        budget_status, budget_errors = get_budget_data(credential, subscription_id)
        
        audit_report[f"Subscription: {primary_name}"].append({
            "Subscription ID": subscription_id,
            "Stopped/Deallocated VMs": stopped_vms,
            "Unattached Managed Disks": unattached_disks,
            "Unassociated Public IPs": unassociated_ips,
            "Budget Status": budget_status,
            "Errors getting VMs": vm_errors,
            "Errors getting Disks": disk_errors,
            "Errors getting Public IPs": ip_errors,
            "Errors getting Budgets": budget_errors
        })
    
    return {
        "Audit Report": dict(audit_report),
        "Error processing subscriptions": errors_for_profiles
    }


def run_server():
    """
    Entry point to the FastMCP server.
    """
    mcp.run(transport='stdio')


if __name__ == "__main__":
    run_server()