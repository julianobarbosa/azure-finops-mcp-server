"""Refactored budget operations for Azure FinOps with smaller, focused functions."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from azure.mgmt.consumption import ConsumptionManagementClient

from azure_finops_mcp_server.config import get_config
from azure_finops_mcp_server.helpers.azure_client_factory import get_client_factory
from azure_finops_mcp_server.helpers.azure_utils import format_cost

logger = logging.getLogger(__name__)

ApiErrors = Dict[str, str]


def fetch_budgets(consumption_client: Any, subscription_id: str) -> List[Any]:
    """
    Fetch all budgets for a subscription.

    Args:
        consumption_client: Azure consumption management client
        subscription_id: Azure subscription ID

    Returns:
        List of budget objects
    """
    scope = f"/subscriptions/{subscription_id}"
    return list(consumption_client.budgets.list(scope))


def process_budget_detail(budget: Any) -> Dict[str, Any]:
    """
    Process a single budget into detailed information.

    Args:
        budget: Azure budget object

    Returns:
        Dictionary with budget details
    """
    budget_detail = {
        "name": budget.name,
        "amount": float(budget.amount) if budget.amount else 0,
        "time_grain": budget.time_grain,
        "category": budget.category,
        "time_period": extract_time_period(budget),
        "current_spend": extract_current_spend(budget),
        "forecast_spend": extract_forecast_spend(budget),
        "notifications": extract_notifications(budget),
    }

    # Calculate usage percentages
    budget_detail["percentage_used"] = calculate_usage_percentage(
        budget_detail["current_spend"]["amount"], budget_detail["amount"]
    )

    if budget_detail.get("forecast_spend"):
        budget_detail["forecast_percentage"] = calculate_usage_percentage(
            budget_detail["forecast_spend"]["amount"], budget_detail["amount"]
        )

    # Determine status
    budget_detail["status"] = determine_budget_status(budget_detail["percentage_used"])

    return budget_detail


def extract_time_period(budget: Any) -> Dict[str, Optional[str]]:
    """
    Extract time period information from budget.

    Args:
        budget: Azure budget object

    Returns:
        Dictionary with start and end dates
    """
    if budget.time_period:
        return {
            "start_date": budget.time_period.start_date.isoformat() if budget.time_period.start_date else None,
            "end_date": budget.time_period.end_date.isoformat() if budget.time_period.end_date else None,
        }
    return {"start_date": None, "end_date": None}


def extract_current_spend(budget: Any) -> Dict[str, Any]:
    """
    Extract current spend information from budget.

    Args:
        budget: Azure budget object

    Returns:
        Dictionary with current spend details
    """
    if hasattr(budget, "current_spend") and budget.current_spend:
        return {
            "amount": float(budget.current_spend.amount) if budget.current_spend.amount else 0,
            "unit": budget.current_spend.unit,
        }
    return {"amount": 0, "unit": "USD"}


def extract_forecast_spend(budget: Any) -> Optional[Dict[str, Any]]:
    """
    Extract forecast spend information from budget.

    Args:
        budget: Azure budget object

    Returns:
        Dictionary with forecast spend details or None
    """
    if hasattr(budget, "forecast_spend") and budget.forecast_spend:
        return {
            "amount": float(budget.forecast_spend.amount) if budget.forecast_spend.amount else 0,
            "unit": budget.forecast_spend.unit,
        }
    return None


def extract_notifications(budget: Any) -> List[Dict[str, Any]]:
    """
    Extract notification settings from budget.

    Args:
        budget: Azure budget object

    Returns:
        List of notification configurations
    """
    notifications = []

    if budget.notifications:
        for key, notification in budget.notifications.items():
            notif_info = {
                "threshold": notification.threshold,
                "enabled": notification.enabled,
                "operator": notification.operator,
                "threshold_type": notification.threshold_type,
                "contact_emails": notification.contact_emails if notification.contact_emails else [],
            }
            notifications.append(notif_info)

    return notifications


def calculate_usage_percentage(current: float, total: float) -> float:
    """
    Calculate usage percentage.

    Args:
        current: Current amount spent
        total: Total budget amount

    Returns:
        Percentage used (0-100+)
    """
    if total > 0:
        return round((current / total) * 100, 2)
    return 0.0


def determine_budget_status(percentage_used: float) -> str:
    """
    Determine budget status based on usage percentage.

    Args:
        percentage_used: Current usage percentage

    Returns:
        Status string (EXCEEDED, CRITICAL, WARNING, or OK)
    """
    if percentage_used >= 100:
        return "EXCEEDED"
    elif percentage_used >= 90:
        return "CRITICAL"
    elif percentage_used >= 75:
        return "WARNING"
    else:
        return "OK"


def check_threshold_alerts(budget_detail: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Check for budgets over notification thresholds.

    Args:
        budget_detail: Processed budget details

    Returns:
        List of threshold violations
    """
    alerts = []

    for notification in budget_detail.get("notifications", []):
        if notification["enabled"] and budget_detail["percentage_used"] >= notification["threshold"]:
            alerts.append(
                {
                    "budget_name": budget_detail["name"],
                    "threshold": notification["threshold"],
                    "current_percentage": budget_detail["percentage_used"],
                }
            )

    return alerts


def generate_budget_alerts(budget_detail: Dict[str, Any]) -> List[str]:
    """
    Generate alert messages for a budget.

    Args:
        budget_detail: Processed budget details

    Returns:
        List of alert messages
    """
    alerts = []
    percentage = budget_detail["percentage_used"]
    name = budget_detail["name"]

    if budget_detail["status"] == "EXCEEDED":
        alerts.append(f"Budget '{name}' has been exceeded ({percentage}%)")
    elif budget_detail["status"] == "CRITICAL":
        alerts.append(f"Budget '{name}' is at critical level ({percentage}%)")
    elif budget_detail["status"] == "WARNING":
        alerts.append(f"Budget '{name}' is at warning level ({percentage}%)")

    # Check forecast
    if budget_detail.get("forecast_percentage", 0) > 100:
        alerts.append(f"Budget '{name}' is forecasted to exceed by {budget_detail['forecast_percentage']-100:.1f}%")

    return alerts


def calculate_budget_summary(budgets: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculate summary statistics for all budgets.

    Args:
        budgets: List of processed budget details

    Returns:
        Summary dictionary with aggregated statistics
    """
    total_budget = sum(b["amount"] for b in budgets)
    total_spend = sum(b["current_spend"]["amount"] for b in budgets)

    return {
        "total_budgets": len(budgets),
        "total_budget_amount": round(total_budget, 2),
        "total_current_spend": round(total_spend, 2),
        "overall_percentage": calculate_usage_percentage(total_spend, total_budget),
        "budgets_exceeded": len([b for b in budgets if b["status"] == "EXCEEDED"]),
        "budgets_critical": len([b for b in budgets if b["status"] == "CRITICAL"]),
        "budgets_warning": len([b for b in budgets if b["status"] == "WARNING"]),
        "budgets_ok": len([b for b in budgets if b["status"] == "OK"]),
    }


def get_budget_data(credential, subscription_id: str) -> Tuple[Dict[str, Any], ApiErrors]:
    """
    Get budget information for a subscription including current spend and forecasts.
    Refactored version with smaller, focused functions.

    Args:
        credential: Azure credential for authentication
        subscription_id: Azure subscription ID

    Returns:
        Tuple of:
        - Dictionary with budget information
        - Dictionary of any errors encountered
    """
    api_errors: ApiErrors = {}
    budget_info = {"budgets": [], "summary": {}, "alerts": [], "threshold_violations": []}

    try:
        # Use factory pattern
        factory = get_client_factory()
        factory.credential = credential
        consumption_client = factory.create_consumption_client(subscription_id)

        # Step 1: Fetch all budgets
        raw_budgets = fetch_budgets(consumption_client, subscription_id)

        # Step 2: Process each budget
        for budget in raw_budgets:
            budget_detail = process_budget_detail(budget)

            # Step 3: Check for alerts
            budget_alerts = generate_budget_alerts(budget_detail)
            budget_info["alerts"].extend(budget_alerts)

            # Step 4: Check threshold violations
            threshold_alerts = check_threshold_alerts(budget_detail)
            budget_info["threshold_violations"].extend(threshold_alerts)

            budget_info["budgets"].append(budget_detail)

        # Step 5: Calculate summary
        budget_info["summary"] = calculate_budget_summary(budget_info["budgets"])

        # Step 6: Generate recommendations
        budget_info["recommendations"] = generate_budget_recommendations(budget_info)

    except Exception as e:
        api_errors["budgets"] = f"Failed to get budget data: {str(e)}"
        logger.error(f"Budget retrieval error: {str(e)}")

    return budget_info, api_errors


def generate_budget_recommendations(budget_info: Dict[str, Any]) -> List[str]:
    """
    Generate recommendations based on budget analysis.

    Args:
        budget_info: Budget information dictionary

    Returns:
        List of recommendation strings
    """
    recommendations = []
    summary = budget_info.get("summary", {})

    # Check for exceeded budgets
    if summary.get("budgets_exceeded", 0) > 0:
        recommendations.append(
            f"URGENT: {summary['budgets_exceeded']} budget(s) have been exceeded. Review spending immediately."
        )

    # Check for critical budgets
    if summary.get("budgets_critical", 0) > 0:
        recommendations.append(
            f"WARNING: {summary['budgets_critical']} budget(s) are at critical level (>90%). Consider cost optimization."
        )

    # Check overall spending
    overall_percentage = summary.get("overall_percentage", 0)
    if overall_percentage > 80:
        recommendations.append(f"Overall spending is at {overall_percentage}% of total budget. Review cost drivers.")

    # Check for budgets without notifications
    budgets_without_alerts = [b["name"] for b in budget_info.get("budgets", []) if not b.get("notifications")]

    if budgets_without_alerts:
        recommendations.append(
            f"Enable notifications for {len(budgets_without_alerts)} budget(s) to get timely alerts."
        )

    # If no budgets configured
    if summary.get("total_budgets", 0) == 0:
        recommendations.append("No budgets configured. Consider setting up budgets to track and control spending.")

    # Check forecast issues
    for budget in budget_info.get("budgets", []):
        if budget.get("forecast_percentage", 0) > 110:  # More than 10% over
            recommendations.append(
                f"Budget '{budget['name']}' forecasted to significantly exceed ({budget['forecast_percentage']}%)"
            )

    return recommendations


def analyze_budget_efficiency(budgets: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyze budget efficiency and utilization patterns.
    Pure function for business logic.

    Args:
        budgets: List of budget details

    Returns:
        Efficiency analysis dictionary
    """
    if not budgets:
        return {"message": "No budgets to analyze"}

    total_allocated = sum(b["amount"] for b in budgets)
    total_used = sum(b["current_spend"]["amount"] for b in budgets)

    # Categorize budgets by utilization
    underutilized = [b for b in budgets if b["percentage_used"] < 50]
    efficiently_used = [b for b in budgets if 50 <= b["percentage_used"] < 90]
    near_limit = [b for b in budgets if 90 <= b["percentage_used"] < 100]
    exceeded = [b for b in budgets if b["percentage_used"] >= 100]

    return {
        "total_allocated": round(total_allocated, 2),
        "total_used": round(total_used, 2),
        "efficiency_rate": round((total_used / total_allocated * 100), 2) if total_allocated > 0 else 0,
        "underutilized_budgets": len(underutilized),
        "efficiently_used_budgets": len(efficiently_used),
        "near_limit_budgets": len(near_limit),
        "exceeded_budgets": len(exceeded),
        "recommendations": generate_efficiency_recommendations(underutilized, efficiently_used, near_limit, exceeded),
    }


def generate_efficiency_recommendations(
    underutilized: List[Dict], efficiently_used: List[Dict], near_limit: List[Dict], exceeded: List[Dict]
) -> List[str]:
    """
    Generate recommendations based on budget efficiency analysis.
    Pure function for business logic.

    Args:
        underutilized: List of underutilized budgets
        efficiently_used: List of efficiently used budgets
        near_limit: List of budgets near limit
        exceeded: List of exceeded budgets

    Returns:
        List of efficiency recommendations
    """
    recommendations = []

    if len(underutilized) > 0:
        total_unused = sum(b["amount"] - b["current_spend"]["amount"] for b in underutilized)
        recommendations.append(
            f"Consider reallocating {format_cost(total_unused)} from {len(underutilized)} underutilized budgets"
        )

    if len(exceeded) > 0:
        total_overspend = sum(b["current_spend"]["amount"] - b["amount"] for b in exceeded)
        recommendations.append(
            f"Address {format_cost(total_overspend)} overspend across {len(exceeded)} exceeded budgets"
        )

    if len(near_limit) > len(efficiently_used):
        recommendations.append("Most budgets are near their limits - review allocation strategy")

    return recommendations


def analyze_spending_trends(budget_info: Dict[str, Any]) -> List[str]:
    """
    Analyze spending trends from budget information.

    Args:
        budget_info: Dictionary containing budget data

    Returns:
        List of trend analysis insights
    """
    trends = []

    if not budget_info.get("budgets"):
        return ["No budget data available for trend analysis"]

    # Analyze budget utilization
    budgets = budget_info["budgets"]
    high_utilization = [b for b in budgets if b.get("usage_percentage", 0) > 80]
    low_utilization = [b for b in budgets if b.get("usage_percentage", 0) < 20]

    if high_utilization:
        trends.append(f"{len(high_utilization)} budget(s) have high utilization (>80%)")

    if low_utilization:
        trends.append(f"{len(low_utilization)} budget(s) have low utilization (<20%)")

    # Analyze forecast vs actual
    for budget in budgets:
        if budget.get("forecast_spend") and budget.get("current_spend"):
            forecast = budget["forecast_spend"].get("amount", 0)
            current = budget["current_spend"].get("amount", 0)
            if forecast > budget.get("amount", 0) * 1.1:
                trends.append(f"{budget['name']} is forecasted to exceed budget by >10%")

    return trends if trends else ["Spending trends are within normal parameters"]
