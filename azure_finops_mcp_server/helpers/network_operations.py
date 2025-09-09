"""Network operations for Azure FinOps."""

from typing import List, Optional, Dict, Tuple, Any
from azure.mgmt.network import NetworkManagementClient
import logging

from azure_finops_mcp_server.helpers.azure_utils import (
    extract_resource_group,
    format_cost,
    calculate_yearly_cost
)
from azure_finops_mcp_server.config import get_config

logger = logging.getLogger(__name__)

ApiErrors = Dict[str, str]

def get_unassociated_public_ips(
        credential,
        subscription_id: str,
        regions: Optional[List[str]] = None
    ) -> Tuple[Dict[str, List[Dict[str, str]]], ApiErrors]:
    """
    Get all unassociated public IP addresses in a subscription.
    
    Args:
        credential: Azure credential for authentication
        subscription_id: Azure subscription ID
        regions: Optional list of regions to filter by
        
    Returns:
        Tuple of:
        - Dictionary with 'unassociated_ips' key containing list of IP details
        - Dictionary of any errors encountered
    """
    api_errors: ApiErrors = {}
    unassociated_ips = []
    
    try:
        network_client = NetworkManagementClient(credential, subscription_id)
        
        for public_ip in network_client.public_ip_addresses.list_all():
            # Filter by region if specified
            if regions and public_ip.location not in regions:
                continue
            
            # Check if IP is associated with any resource
            if public_ip.ip_configuration is None:
                ip_info = {
                    'name': public_ip.name,
                    'resource_group': extract_resource_group(public_ip.id),
                    'location': public_ip.location,
                    'ip_address': public_ip.ip_address or 'Not Assigned',
                    'sku': public_ip.sku.name if public_ip.sku else 'Basic',
                    'allocation_method': public_ip.public_ip_allocation_method,
                    'id': public_ip.id
                }
                
                # Add cost estimate
                ip_info['monthly_cost'] = estimate_public_ip_cost(
                    ip_info['sku'],
                    ip_info['allocation_method']
                )
                
                unassociated_ips.append(ip_info)
                
    except Exception as e:
        api_errors['unassociated_ips'] = f"Failed to get unassociated IPs: {str(e)}"
    
    return {'unassociated_ips': unassociated_ips}, api_errors

def estimate_public_ip_cost(sku: str, allocation_method: str) -> float:
    """
    Estimate monthly cost for a public IP address.
    
    Args:
        sku: IP SKU (Basic or Standard)
        allocation_method: Static or Dynamic
        
    Returns:
        Estimated monthly cost in USD
    """
    config = get_config()
    
    # Determine cost key based on SKU and allocation
    if sku == 'Standard':
        if allocation_method == 'Static':
            cost_key = 'standard_static'
        else:
            cost_key = 'standard_dynamic'
    else:  # Basic SKU
        if allocation_method == 'Static':
            cost_key = 'basic_static'
        else:
            cost_key = 'basic_dynamic'
    
    return config.public_ip_cost_rates.get(cost_key, 3.65)
    
def calculate_network_waste(unassociated_ips: List[Dict[str, str]]) -> Dict[str, float]:
    """
    Calculate potential cost savings from unassociated public IPs.
    
    Args:
        unassociated_ips: List of unassociated IP dictionaries
        
    Returns:
        Dictionary with total and per-IP waste estimates
    """
    total_waste = 0.0
    ip_waste = {}
    
    for ip in unassociated_ips:
        monthly_cost = ip.get('monthly_cost', 3.65)
        ip_waste[ip['name']] = monthly_cost
        total_waste += monthly_cost
    
    return {
        'total_monthly_waste': round(total_waste, 2),
        'ip_breakdown': ip_waste,
        'annual_waste': round(total_waste * 12, 2),
        'count': len(unassociated_ips)
    }

def get_network_security_groups(
        credential,
        subscription_id: str,
        regions: Optional[List[str]] = None
    ) -> Tuple[Dict[str, List[Dict[str, str]]], ApiErrors]:
    """
    Get all network security groups with their rules.
    
    Args:
        credential: Azure credential for authentication
        subscription_id: Azure subscription ID
        regions: Optional list of regions to filter by
        
    Returns:
        Tuple of:
        - Dictionary with NSG information
        - Dictionary of any errors encountered
    """
    api_errors: ApiErrors = {}
    nsgs = []
    
    try:
        network_client = NetworkManagementClient(credential, subscription_id)
        
        for nsg in network_client.network_security_groups.list_all():
            if regions and nsg.location not in regions:
                continue
            
            nsg_info = {
                'name': nsg.name,
                'resource_group': nsg.id.split('/')[4],
                'location': nsg.location,
                'rules_count': len(nsg.security_rules) if nsg.security_rules else 0,
                'default_rules_count': len(nsg.default_security_rules) if nsg.default_security_rules else 0,
                'subnets': len(nsg.subnets) if nsg.subnets else 0,
                'interfaces': len(nsg.network_interfaces) if nsg.network_interfaces else 0,
                'id': nsg.id
            }
            
            # Check if NSG is unused
            if nsg_info['subnets'] == 0 and nsg_info['interfaces'] == 0:
                nsg_info['status'] = 'Unused'
            else:
                nsg_info['status'] = 'In Use'
            
            nsgs.append(nsg_info)
    
    except Exception as e:
        api_errors['nsgs'] = f"Failed to get network security groups: {str(e)}"
    
    return {'network_security_groups': nsgs}, api_errors

def analyze_network_usage(
        credential,
        subscription_id: str,
        regions: Optional[List[str]] = None
    ) -> Tuple[Dict[str, Any], ApiErrors]:
    """
    Comprehensive network resource analysis.
    
    Args:
        credential: Azure credential for authentication
        subscription_id: Azure subscription ID
        regions: Optional list of regions to filter by
        
    Returns:
        Tuple of:
        - Dictionary with comprehensive network analysis
        - Dictionary of any errors encountered
    """
    api_errors: ApiErrors = {}
    analysis = {
        'public_ips': {},
        'network_security_groups': {},
        'virtual_networks': {},
        'recommendations': []
    }
    
    # Get unassociated public IPs
    ips_result, ip_errors = get_unassociated_public_ips(credential, subscription_id, regions)
    if not ip_errors:
        analysis['public_ips'] = ips_result
        if ips_result.get('unassociated_ips'):
            waste = calculate_network_waste(ips_result['unassociated_ips'])
            analysis['public_ips']['waste_analysis'] = waste
            analysis['recommendations'].append(
                f"Delete {waste['count']} unassociated public IPs to save ${waste['total_monthly_waste']}/month"
            )
    else:
        api_errors.update(ip_errors)
    
    # Get NSG information
    nsg_result, nsg_errors = get_network_security_groups(credential, subscription_id, regions)
    if not nsg_errors:
        analysis['network_security_groups'] = nsg_result
        unused_nsgs = [nsg for nsg in nsg_result.get('network_security_groups', []) 
                      if nsg.get('status') == 'Unused']
        if unused_nsgs:
            analysis['recommendations'].append(
                f"Review {len(unused_nsgs)} unused Network Security Groups for deletion"
            )
    else:
        api_errors.update(nsg_errors)
    
    return analysis, api_errors