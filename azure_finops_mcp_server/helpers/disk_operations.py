"""Disk operations for Azure FinOps."""

from typing import List, Optional, Dict, Tuple, Any
from collections import defaultdict
import logging

from azure_finops_mcp_server.helpers.azure_utils import (
    extract_resource_group,
    is_orphaned_disk,
    format_cost,
    calculate_yearly_cost
)
from azure_finops_mcp_server.config import get_config
from azure_finops_mcp_server.helpers.azure_client_factory import (
    get_client_factory,
    ComputeClientAdapter
)

logger = logging.getLogger(__name__)

ApiErrors = Dict[str, str]

def get_unattached_disks(
        credential,
        subscription_id: str,
        regions: Optional[List[str]] = None,
        include_pvc_disks: bool = False,
        include_aks_managed_disks: bool = False
    ) -> Tuple[Dict[str, Any], ApiErrors]:
    """
    Get all unattached managed disks in a subscription with improved filtering.
    
    Args:
        credential: Azure credential for authentication
        subscription_id: Azure subscription ID
        regions: Optional list of regions to filter by
        include_pvc_disks: Include Kubernetes PVC disks (default: False)
        include_aks_managed_disks: Include AKS-managed disks (default: False)
        
    Returns:
        Tuple of:
        - Dictionary with disk information and statistics
        - Dictionary of any errors encountered
    """
    api_errors: ApiErrors = {}
    unattached_disks = []
    disk_categories = {
        'orphaned': [],
        'pvc': [],
        'aks_managed': []
    }
    
    try:
        # Use factory pattern for better testability
        factory = get_client_factory()
        factory.credential = credential  # Use provided credential
        compute_client = factory.create_compute_client(subscription_id)
        
        for disk in compute_client.disks.list():
            # Filter by region if specified
            if regions and disk.location not in regions:
                continue
            
            # Check if disk is unattached
            if disk.managed_by is None:
                resource_group = extract_resource_group(disk.id)
                
                disk_info = {
                    'name': disk.name,
                    'resource_group': resource_group,
                    'location': disk.location,
                    'size_gb': disk.disk_size_gb,
                    'sku': disk.sku.name if disk.sku else 'Unknown',
                    'id': disk.id
                }
                
                # Categorize the disk
                if disk.name.startswith('pvc-'):
                    disk_categories['pvc'].append(disk_info)
                    if include_pvc_disks:
                        unattached_disks.append(disk_info)
                elif resource_group.startswith('MC_'):
                    disk_categories['aks_managed'].append(disk_info)
                    if include_aks_managed_disks:
                        unattached_disks.append(disk_info)
                else:
                    # Truly orphaned disk
                    disk_categories['orphaned'].append(disk_info)
                    unattached_disks.append(disk_info)
                    
    except Exception as e:
        api_errors['unattached_disks'] = f"Failed to get unattached disks: {str(e)}"
    
    return {
        'unattached_disks': unattached_disks,
        'categories': disk_categories,
        'statistics': {
            'total_unattached': len(disk_categories['orphaned']) + len(disk_categories['pvc']) + len(disk_categories['aks_managed']),
            'orphaned_count': len(disk_categories['orphaned']),
            'pvc_count': len(disk_categories['pvc']),
            'aks_managed_count': len(disk_categories['aks_managed']),
            'included_in_results': len(unattached_disks)
        }
    }, api_errors


def fetch_unattached_disks(
        compute_client: Any,
        regions: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
    """
    Fetch all unattached disks from Azure.
    
    Args:
        compute_client: Azure compute management client
        regions: Optional list of regions to filter by
        
    Returns:
        List of unattached disk information
    """
    unattached_disks = []
    
    for disk in compute_client.disks.list():
        if regions and disk.location not in regions:
            continue
        
        if disk.managed_by is None:
            resource_group = extract_resource_group(disk.id)
            size_gb = disk.disk_size_gb or 0
            sku_name = disk.sku.name if disk.sku else 'Standard_LRS'
            
            disk_detail = {
                'name': disk.name,
                'resource_group': resource_group,
                'location': disk.location,
                'size_gb': size_gb,
                'sku': sku_name,
                'id': disk.id,
                'created_time': disk.time_created.isoformat() if disk.time_created else None
            }
            unattached_disks.append(disk_detail)
    
    return unattached_disks


def categorize_disks(disks: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Categorize disks into orphaned, PVC, and AKS-managed.
    
    Args:
        disks: List of disk information dictionaries
        
    Returns:
        Dictionary with categorized disks
    """
    categories = {
        'orphaned': [],
        'pvc': [],
        'aks_managed': []
    }
    
    config = get_config()
    
    for disk in disks:
        name = disk['name']
        resource_group = disk['resource_group']
        
        # Check against configured patterns
        is_pvc = any(name.startswith(pattern) for pattern in ['pvc-'])
        is_aks = any(resource_group.startswith(pattern) 
                    for pattern in config.managed_resource_group_patterns)
        
        if is_pvc:
            categories['pvc'].append(disk)
        elif is_aks:
            categories['aks_managed'].append(disk)
        else:
            categories['orphaned'].append(disk)
    
    return categories


def calculate_disk_costs(disks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Calculate costs for a list of disks.
    
    Args:
        disks: List of disk information dictionaries
        
    Returns:
        List of disks with cost information added
    """
    config = get_config()
    
    for disk in disks:
        size_gb = disk['size_gb']
        sku_name = disk['sku']
        
        # Estimate monthly cost
        monthly_cost = estimate_disk_cost(size_gb, sku_name)
        
        disk['monthly_cost'] = round(monthly_cost, 2)
        disk['annual_cost'] = round(calculate_yearly_cost(monthly_cost), 2)
    
    return disks


def compile_audit_statistics(categories: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    """
    Compile statistics from categorized disks.
    
    Args:
        categories: Dictionary with categorized disks
        
    Returns:
        Dictionary with audit statistics
    """
    orphaned_cost = sum(d.get('monthly_cost', 0) for d in categories['orphaned'])
    pvc_cost = sum(d.get('monthly_cost', 0) for d in categories['pvc'])
    aks_cost = sum(d.get('monthly_cost', 0) for d in categories['aks_managed'])
    total_cost = orphaned_cost + pvc_cost + aks_cost
    
    return {
        'total_unattached_disks': sum(len(disks) for disks in categories.values()),
        'orphaned_count': len(categories['orphaned']),
        'pvc_count': len(categories['pvc']),
        'aks_managed_count': len(categories['aks_managed']),
        'total_monthly_cost': round(total_cost, 2),
        'total_annual_cost': round(calculate_yearly_cost(total_cost), 2),
        'orphaned_monthly_cost': round(orphaned_cost, 2),
        'orphaned_annual_cost': round(calculate_yearly_cost(orphaned_cost), 2)
    }


def get_detailed_disk_audit(
        credential,
        subscription_id: str,
        regions: Optional[List[str]] = None
    ) -> Tuple[Dict[str, Any], ApiErrors]:
    """
    Perform a detailed disk audit with cost estimates and categorization.
    
    Args:
        credential: Azure credential for authentication
        subscription_id: Azure subscription ID
        regions: Optional list of regions to filter by
        
    Returns:
        Tuple of:
        - Dictionary with detailed disk audit results
        - Dictionary of any errors encountered
    """
    api_errors: ApiErrors = {}
    audit_results = {
        'summary': {},
        'orphaned_disks': [],
        'pvc_disks': [],
        'aks_managed_disks': [],
        'cost_analysis': {}
    }
    
    try:
        # Step 1: Fetch unattached disks using factory
        factory = get_client_factory()
        factory.credential = credential  # Use provided credential
        compute_client = factory.create_compute_client(subscription_id)
        unattached_disks = fetch_unattached_disks(compute_client, regions)
        
        # Step 2: Calculate costs for all disks
        disks_with_costs = calculate_disk_costs(unattached_disks)
        
        # Step 3: Categorize disks
        categories = categorize_disks(disks_with_costs)
        
        # Step 4: Assign to audit results
        audit_results['orphaned_disks'] = categories['orphaned']
        audit_results['pvc_disks'] = categories['pvc']
        audit_results['aks_managed_disks'] = categories['aks_managed']
        
        # Step 5: Compile statistics
        audit_results['summary'] = compile_audit_statistics(categories)
        
        # Step 6: Generate cost analysis
        audit_results['cost_analysis'] = {
            'by_sku': analyze_costs_by_sku(disks_with_costs),
            'recommendations': generate_disk_recommendations(audit_results)
        }
        
    except Exception as e:
        api_errors['disk_audit'] = f"Failed to perform disk audit: {str(e)}"
    
    return audit_results, api_errors


def analyze_costs_by_sku(disks: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Analyze disk costs grouped by SKU type.
    
    Args:
        disks: List of disks with cost information
        
    Returns:
        Dictionary with cost analysis by SKU
    """
    sku_stats = defaultdict(lambda: {'count': 0, 'total_gb': 0, 'cost': 0})
    
    for disk in disks:
        sku = disk['sku']
        sku_stats[sku]['count'] += 1
        sku_stats[sku]['total_gb'] += disk['size_gb']
        sku_stats[sku]['cost'] += disk.get('monthly_cost', 0)
    
    return dict(sku_stats)


def estimate_disk_cost(size_gb: int, sku_name: str) -> float:
    """
    Estimate monthly cost for a managed disk.
    
    Args:
        size_gb: Size of the disk in GB
        sku_name: SKU name (e.g., 'Standard_LRS', 'Premium_LRS')
        
    Returns:
        Estimated monthly cost in USD
    """
    config = get_config()
    
    # Map SKU names to cost rate keys
    sku_mapping = {
        'Standard_LRS': 'standard_hdd',
        'StandardSSD_LRS': 'standard_ssd',
        'Premium_LRS': 'premium_ssd',
        'UltraSSD_LRS': 'ultra_disk'
    }
    
    rate_key = sku_mapping.get(sku_name, 'standard_hdd')
    rate_per_gb = config.disk_cost_rates.get(rate_key, 0.05)
    
    return size_gb * rate_per_gb


def generate_disk_recommendations(audit_results: Dict[str, Any]) -> List[str]:
    """
    Generate recommendations based on disk audit results.
    
    Args:
        audit_results: Dictionary with disk audit results
        
    Returns:
        List of recommendation strings
    """
    recommendations = []
    summary = audit_results.get('summary', {})
    
    orphaned_count = summary.get('orphaned_count', 0)
    orphaned_cost = summary.get('orphaned_monthly_cost', 0)
    
    if orphaned_count > 0:
        recommendations.append(
            f"Delete {orphaned_count} orphaned disks to save {format_cost(orphaned_cost)}/month"
        )
    
    pvc_count = summary.get('pvc_count', 0)
    if pvc_count > 10:
        recommendations.append(
            f"Review {pvc_count} PVC disks - consider cleaning up unused Kubernetes volumes"
        )
    
    aks_count = summary.get('aks_managed_count', 0)
    if aks_count > 0:
        recommendations.append(
            f"Found {aks_count} AKS-managed disks - verify AKS cluster health"
        )
    
    total_cost = summary.get('total_monthly_cost', 0)
    if total_cost > 100:
        annual_savings = calculate_yearly_cost(total_cost)
        recommendations.append(
            f"Total potential savings: {format_cost(annual_savings)}/year"
        )
    
    return recommendations