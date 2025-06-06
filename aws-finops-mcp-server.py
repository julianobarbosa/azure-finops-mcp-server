import boto3
from mcp.server.fastmcp import FastMCP
from datetime import date, datetime, timedelta
from typing import Dict, Any, Optional, List
from collections import defaultdict

from helpers.profiles import profiles_to_use, ProfileErrors

mcp = FastMCP("aws_finops")

@mcp.tool()
async def get_cost(
    profiles: List[str], 
    time_range_days: Optional[int] = None,
    start_date_iso: Optional[str] = None, 
    end_date_iso: Optional[str] = None,   
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Get cost data for a specified AWS profile for a single defined period.
    The period can be defined by 'time_range_days' (last N days including today)
    OR by explicit 'start_date_iso' and 'end_date_iso'.
    If 'start_date_iso' and 'end_date_iso' are provided, they take precedence.
    If no period is defined, defaults to the current month to date.
    Tags can be provided as a list of "Key=Value" strings to filter costs.
    
    Args:
        profile_name: The AWS CLI profile name to use.
        time_range_days: Optional. Number of days for the cost data (e.g., last 7 days).
        start_date_iso: Optional. The start date of the period (inclusive) in YYYY-MM-DD format.
        end_date_iso: Optional. The end date of the period (inclusive) in YYYY-MM-DD format.
        tags: Optional. List of cost allocation tags (e.g., ["Team=DevOps", "Env=Prod"]).
    Returns:
        Dict: Processed cost data for the specified period.
    """
    profiles_to_query, errors_for_profiles = profiles_to_use(profiles)
    if not profiles_to_query:
        return {"error": "No valid profiles found."}
    
    cost_data = {}
    
    for account_id, profile in profiles_to_query.items():
        primary_profile = profile[0]

        try:
            session = boto3.Session(profile_name=primary_profile)
            account_id = session.client("sts").get_caller_identity().get("Account")
            ce = session.client("ce")

            tag_filters_list: List[Dict[str, Any]] = []
            if tags:
                for t_str in tags:
                    if "=" in t_str:
                        key, value = t_str.split("=", 1)
                        tag_filters_list.append({"Key": key, "Values": [value]})
            filter_param: Optional[Dict[str, Any]] = None
            if tag_filters_list:
                if len(tag_filters_list) == 1:
                    filter_param = {"Tags": tag_filters_list[0]}
                else:
                    filter_param = {"And": [{"Tags": f} for f in tag_filters_list]}
            cost_explorer_kwargs: Dict[str, Any] = {}
            if filter_param:
                cost_explorer_kwargs["Filter"] = filter_param

            today = date.today()
            period_start_date: date
            period_api_end_date: date # Exclusive end date for Cost Explorer API
            period_display_end_date: date # Inclusive end date for display in results

            if start_date_iso and end_date_iso:
                try:
                    period_start_date = datetime.strptime(start_date_iso, "%Y-%m-%d").date()
                    period_display_end_date = datetime.strptime(end_date_iso, "%Y-%m-%d").date()
                    period_api_end_date = period_display_end_date + timedelta(days=1)
                    if period_start_date > period_display_end_date:
                        return {"profile_name": primary_profile, "status": "error", "message": "Start date cannot be after end date."}
                except ValueError:
                    return {"profile_name": primary_profile, "status": "error", "message": "Invalid date format. Use YYYY-MM-DD."}
            elif time_range_days is not None:
                if time_range_days <= 0:
                    return {"profile_name": primary_profile, "status": "error", "message": "time_range_days must be positive."}
                period_display_end_date = today
                period_start_date = today - timedelta(days=time_range_days - 1) # -1 to make it inclusive of N days
                period_api_end_date = today + timedelta(days=1)
            else: # Default to current month to date
                period_start_date = today.replace(day=1)
                period_display_end_date = today
                period_api_end_date = today + timedelta(days=1)
            
            # Period Total Cost
            total_cost_response = ce.get_cost_and_usage(
                TimePeriod={"Start": period_start_date.isoformat(), "End": period_api_end_date.isoformat()},
                Granularity="MONTHLY" if not time_range_days and not (start_date_iso and end_date_iso) else "DAILY",
                Metrics=["UnblendedCost"],
                **cost_explorer_kwargs,
            )
            period_total_cost = 0.0
            if total_cost_response.get("ResultsByTime"):
                for month_result in total_cost_response["ResultsByTime"]:
                    if "Total" in month_result and \
                    "UnblendedCost" in month_result["Total"] and \
                    "Amount" in month_result["Total"]["UnblendedCost"]:
                        period_total_cost += float(month_result["Total"]["UnblendedCost"]["Amount"])
                
            # Period Cost by Service
            service_granularity = "DAILY"
            if not time_range_days and not (start_date_iso and end_date_iso):
                service_granularity = "MONTHLY"

            cost_by_service_response = ce.get_cost_and_usage(
                TimePeriod={"Start": period_start_date.isoformat(), "End": period_api_end_date.isoformat()},
                Granularity=service_granularity,
                Metrics=["UnblendedCost"],
                GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
                **cost_explorer_kwargs,
            )
            
            aggregated_service_costs: Dict[str, float] = defaultdict(float)
            if cost_by_service_response.get("ResultsByTime"):
                for result_by_time in cost_by_service_response["ResultsByTime"]:
                    for group in result_by_time.get("Groups", []):
                        service = group["Keys"][0]
                        amount = float(group["Metrics"]["UnblendedCost"]["Amount"])
                        aggregated_service_costs[service] += amount
            
            sorted_service_costs = dict(sorted(aggregated_service_costs.items(), key=lambda item: item[1], reverse=True))
            processed_service_costs = {k: round(v, 2) for k, v in sorted_service_costs.items() if v > 0.001}

            cost_data[primary_profile] = {
                "profile_name": primary_profile,
                "account_id": account_id,
                "period_start_date": period_start_date.isoformat(),
                "period_end_date": period_display_end_date.isoformat(),
                "period_total_cost": round(period_total_cost, 2),
                "period_cost_by_service": processed_service_costs,
                "status": "success"
            }

        except Exception as e:
            cost_data[primary_profile] = {
                "profile_name": primary_profile,
                "status": "error",
                "message": str(e)
            } 
    return {"accounts_cost_data": cost_data, "errors_for_profiles": errors_for_profiles}







if __name__ == "__main__":
    mcp.run(transport='stdio')