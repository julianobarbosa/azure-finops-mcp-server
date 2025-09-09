#!/usr/bin/env python3
"""Get costs for RS_Hypera_Cafehyna resource group."""

import os
from datetime import datetime, timedelta
from azure.identity import DefaultAzureCredential
from azure.mgmt.costmanagement import CostManagementClient
from azure.mgmt.costmanagement.models import QueryDefinition, QueryDataset, QueryAggregation, QueryGrouping, QueryFilter, QueryComparisonExpression, QueryTimePeriod
import json

def get_cafehyna_costs():
    """Get costs for RS_Hypera_Cafehyna resource group."""
    
    credential = DefaultAzureCredential()
    subscription_id = os.environ.get('AZURE_SUBSCRIPTION_ID')
    
    if not subscription_id:
        raise ValueError("AZURE_SUBSCRIPTION_ID environment variable is required")
    
    # Create cost management client
    cost_client = CostManagementClient(credential)
    
    # Define the scope
    scope = f'/subscriptions/{subscription_id}'
    
    # Current month date range
    now = datetime.now()
    start_date = datetime(now.year, now.month, 1)
    end_date = now
    
    print(f'\nAzure Costs for RS_Hypera_Cafehyna Resource Group')
    print(f'Subscription: hypera-pharma')
    print(f'Period: {start_date.strftime("%Y-%m-%d")} to {end_date.strftime("%Y-%m-%d")}')
    print('=' * 70)
    
    # Try multiple resource group name variations
    rg_variations = [
        'RS_Hypera_Cafehyna',
        'RS_HYPERA_CAFEHYNA', 
        'rs_hypera_cafehyna',
        'Rs_Hypera_Cafehyna'
    ]
    
    for rg_name in rg_variations:
        try:
            # Create query
            query = QueryDefinition(
                type='Usage',
                timeframe='Custom',
                time_period=QueryTimePeriod(
                    from_property=start_date,
                    to=end_date
                ),
                dataset=QueryDataset(
                    granularity='Daily',
                    aggregation={
                        'totalCost': QueryAggregation(
                            name='Cost',
                            function='Sum'
                        )
                    },
                    grouping=[
                        QueryGrouping(
                            type='Dimension',
                            name='ServiceName'
                        )
                    ],
                    filter=QueryFilter(
                        dimensions=QueryComparisonExpression(
                            name='ResourceGroupName',
                            operator='In',
                            values=[rg_name]
                        )
                    )
                )
            )
            
            result = cost_client.query.usage(scope=scope, parameters=query)
            
            if result.rows and len(result.rows) > 0:
                print(f'\nFound costs for resource group: {rg_name}')
                print('-' * 70)
                
                service_costs = {}
                total_cost = 0
                
                for row in result.rows:
                    if row and len(row) >= 2:
                        cost = float(row[0]) if row[0] else 0
                        service = row[2] if len(row) > 2 else 'Unknown Service'
                        
                        if service not in service_costs:
                            service_costs[service] = 0
                        service_costs[service] += cost
                        total_cost += cost
                
                # Display costs by service
                print('\nCosts by Service:')
                for service, cost in sorted(service_costs.items(), key=lambda x: x[1], reverse=True):
                    if cost > 0:
                        print(f'  {service}: ${cost:.2f}')
                
                print('-' * 70)
                print(f'TOTAL COST (Month-to-Date): ${total_cost:.2f}')
                print('=' * 70)
                return total_cost
                
        except Exception as e:
            continue
    
    # If no data found with any variation
    print('\nNo cost data found for RS_Hypera_Cafehyna resource group.')
    print('\nPossible reasons:')
    print('1. No resources currently incurring costs in this resource group')
    print('2. Cost data processing delay (typically 24-48 hours)')
    print('3. Resource group might be in a different subscription')
    
    # Try to list all resource groups with costs
    print('\n\nChecking all resource groups with costs in this subscription...')
    try:
        query_all = QueryDefinition(
            type='Usage',
            timeframe='Custom',
            time_period=QueryTimePeriod(
                from_property=start_date,
                to=end_date
            ),
            dataset=QueryDataset(
                granularity='None',
                aggregation={
                    'totalCost': QueryAggregation(
                        name='Cost',
                        function='Sum'
                    )
                },
                grouping=[
                    QueryGrouping(
                        type='Dimension',
                        name='ResourceGroupName'
                    )
                ]
            )
        )
        
        result_all = cost_client.query.usage(scope=scope, parameters=query_all)
        
        if result_all.rows:
            print('\nResource Groups with costs this month:')
            cafehyna_found = False
            for row in result_all.rows:
                if row and len(row) >= 2:
                    cost = float(row[0]) if row[0] else 0
                    rg = row[1] if len(row) > 1 else 'Unknown'
                    if cost > 0:
                        if 'cafehyna' in rg.lower():
                            print(f'  ➡️  {rg}: ${cost:.2f} (CAFEHYNA RELATED)')
                            cafehyna_found = True
                        elif cost > 100:  # Only show RGs with significant costs
                            print(f'  {rg}: ${cost:.2f}')
            
            if not cafehyna_found:
                print('\n❌ No resource groups containing "cafehyna" found with costs.')
    except Exception as e:
        print(f'Error listing all resource groups: {e}')
    
    return 0

if __name__ == "__main__":
    get_cafehyna_costs()