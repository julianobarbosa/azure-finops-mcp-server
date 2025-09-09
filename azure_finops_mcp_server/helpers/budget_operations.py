"""Budget operations for Azure FinOps."""

from typing import List, Optional, Dict, Tuple
from azure.mgmt.consumption import ConsumptionManagementClient
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

ApiErrors = Dict[str, str]

def get_budget_data(
        credential,
        subscription_id: str
    ) -> Tuple[Dict[str, Any], ApiErrors]:
    """
    Get budget information for a subscription including current spend and forecasts.
    
    Args:
        credential: Azure credential for authentication
        subscription_id: Azure subscription ID
        
    Returns:
        Tuple of:
        - Dictionary with budget information
        - Dictionary of any errors encountered
    """
    api_errors: ApiErrors = {}
    budget_info = {
        'budgets': [],
        'summary': {},
        'alerts': []
    }
    
    try:
        consumption_client = ConsumptionManagementClient(credential, subscription_id)
        scope = f'/subscriptions/{subscription_id}'
        
        # Get all budgets for the subscription
        budgets = consumption_client.budgets.list(scope)
        
        total_budget = 0
        total_current_spend = 0
        budgets_over_threshold = []
        
        for budget in budgets:
            budget_detail = {
                'name': budget.name,
                'amount': float(budget.amount) if budget.amount else 0,
                'time_grain': budget.time_grain,
                'category': budget.category,
                'time_period': {
                    'start_date': budget.time_period.start_date.isoformat() if budget.time_period and budget.time_period.start_date else None,
                    'end_date': budget.time_period.end_date.isoformat() if budget.time_period and budget.time_period.end_date else None
                }
            }
            
            # Get current spend if available
            if hasattr(budget, 'current_spend') and budget.current_spend:
                budget_detail['current_spend'] = {
                    'amount': float(budget.current_spend.amount) if budget.current_spend.amount else 0,
                    'unit': budget.current_spend.unit
                }
                budget_detail['percentage_used'] = round(
                    (budget_detail['current_spend']['amount'] / budget_detail['amount']) * 100, 2
                ) if budget_detail['amount'] > 0 else 0
                
                total_current_spend += budget_detail['current_spend']['amount']
            else:
                budget_detail['current_spend'] = {'amount': 0, 'unit': 'USD'}
                budget_detail['percentage_used'] = 0
            
            # Get forecast if available
            if hasattr(budget, 'forecast_spend') and budget.forecast_spend:
                budget_detail['forecast_spend'] = {
                    'amount': float(budget.forecast_spend.amount) if budget.forecast_spend.amount else 0,
                    'unit': budget.forecast_spend.unit
                }
                budget_detail['forecast_percentage'] = round(
                    (budget_detail['forecast_spend']['amount'] / budget_detail['amount']) * 100, 2
                ) if budget_detail['amount'] > 0 else 0
            
            # Check notifications/alerts
            if budget.notifications:
                budget_detail['notifications'] = []
                for key, notification in budget.notifications.items():
                    notif_info = {
                        'threshold': notification.threshold,
                        'enabled': notification.enabled,
                        'operator': notification.operator,
                        'threshold_type': notification.threshold_type,
                        'contact_emails': notification.contact_emails if notification.contact_emails else []
                    }
                    budget_detail['notifications'].append(notif_info)
                    
                    # Check if budget is over threshold
                    if notification.enabled and budget_detail.get('percentage_used', 0) >= notification.threshold:
                        budgets_over_threshold.append({
                            'budget_name': budget.name,
                            'threshold': notification.threshold,
                            'current_percentage': budget_detail['percentage_used']
                        })
            
            # Determine budget status
            percentage = budget_detail.get('percentage_used', 0)
            if percentage >= 100:
                budget_detail['status'] = 'EXCEEDED'
                budget_info['alerts'].append(f"Budget '{budget.name}' has been exceeded ({percentage}%)")
            elif percentage >= 90:
                budget_detail['status'] = 'CRITICAL'
                budget_info['alerts'].append(f"Budget '{budget.name}' is at critical level ({percentage}%)")
            elif percentage >= 75:
                budget_detail['status'] = 'WARNING'
                budget_info['alerts'].append(f"Budget '{budget.name}' is at warning level ({percentage}%)")
            else:
                budget_detail['status'] = 'OK'
            
            budget_info['budgets'].append(budget_detail)
            total_budget += budget_detail['amount']
        
        # Calculate summary
        budget_info['summary'] = {
            'total_budgets': len(budget_info['budgets']),
            'total_budget_amount': round(total_budget, 2),
            'total_current_spend': round(total_current_spend, 2),
            'overall_percentage': round((total_current_spend / total_budget) * 100, 2) if total_budget > 0 else 0,
            'budgets_exceeded': len([b for b in budget_info['budgets'] if b.get('status') == 'EXCEEDED']),
            'budgets_critical': len([b for b in budget_info['budgets'] if b.get('status') == 'CRITICAL']),
            'budgets_warning': len([b for b in budget_info['budgets'] if b.get('status') == 'WARNING']),
            'budgets_ok': len([b for b in budget_info['budgets'] if b.get('status') == 'OK'])
        }
        
        # Add recommendations
        budget_info['recommendations'] = generate_budget_recommendations(budget_info)
        
    except Exception as e:
        api_errors['budgets'] = f"Failed to get budget data: {str(e)}"
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
    
    summary = budget_info.get('summary', {})
    
    # Check for exceeded budgets
    if summary.get('budgets_exceeded', 0) > 0:
        recommendations.append(
            f"URGENT: {summary['budgets_exceeded']} budget(s) have been exceeded. Review spending immediately."
        )
    
    # Check for critical budgets
    if summary.get('budgets_critical', 0) > 0:
        recommendations.append(
            f"WARNING: {summary['budgets_critical']} budget(s) are at critical level (>90%). Consider cost optimization."
        )
    
    # Check overall spending
    overall_percentage = summary.get('overall_percentage', 0)
    if overall_percentage > 80:
        recommendations.append(
            f"Overall spending is at {overall_percentage}% of total budget. Review cost drivers."
        )
    
    # Check for budgets without notifications
    budgets_without_alerts = []
    for budget in budget_info.get('budgets', []):
        if not budget.get('notifications'):
            budgets_without_alerts.append(budget['name'])
    
    if budgets_without_alerts:
        recommendations.append(
            f"Enable notifications for {len(budgets_without_alerts)} budget(s) to get timely alerts."
        )
    
    # Check for forecast issues
    for budget in budget_info.get('budgets', []):
        if budget.get('forecast_percentage', 0) > 100:
            recommendations.append(
                f"Budget '{budget['name']}' is forecasted to exceed by {budget['forecast_percentage']-100:.1f}%"
            )
    
    # If no budgets configured
    if summary.get('total_budgets', 0) == 0:
        recommendations.append(
            "No budgets configured. Consider setting up budgets to track and control spending."
        )
    
    return recommendations

def analyze_spending_trends(
        credential,
        subscription_id: str,
        months: int = 6
    ) -> Tuple[Dict[str, Any], ApiErrors]:
    """
    Analyze spending trends over time.
    
    Args:
        credential: Azure credential for authentication
        subscription_id: Azure subscription ID
        months: Number of months to analyze
        
    Returns:
        Tuple of:
        - Dictionary with spending trend analysis
        - Dictionary of any errors encountered
    """
    api_errors: ApiErrors = {}
    trends = {
        'monthly_spend': [],
        'average_monthly': 0,
        'trend': 'stable',
        'projection': {}
    }
    
    try:
        # This would require additional API calls to get historical data
        # Placeholder for trend analysis logic
        logger.info(f"Analyzing spending trends for {months} months")
        
        # Would implement actual trend analysis here
        # For now, return placeholder
        trends['message'] = "Trend analysis requires historical data implementation"
        
    except Exception as e:
        api_errors['trends'] = f"Failed to analyze spending trends: {str(e)}"
    
    return trends, api_errors