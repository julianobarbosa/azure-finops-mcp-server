"""Disk operations for Azure FinOps."""

from typing import List, Optional, Dict, Tuple, Any
from azure.mgmt.compute import ComputeManagementClient
from collections import defaultdict
import logging

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
        compute_client = ComputeManagementClient(credential, subscription_id)
        
        for disk in compute_client.disks.list():
            # Filter by region if specified
            if regions and disk.location not in regions:
                continue
            
            # Check if disk is unattached
            if disk.managed_by is None:
                resource_group = disk.id.split('/')[4]
                
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
        compute_client = ComputeManagementClient(credential, subscription_id)
        
        total_cost = 0
        disk_type_stats = defaultdict(lambda: {'count': 0, 'total_gb': 0, 'cost': 0})
        
        for disk in compute_client.disks.list():
            if regions and disk.location not in regions:
                continue
            
            if disk.managed_by is None:
                resource_group = disk.id.split('/')[4]
                size_gb = disk.disk_size_gb or 0
                sku_name = disk.sku.name if disk.sku else 'Standard_LRS'
                
                # Estimate monthly cost
                monthly_cost = estimate_disk_cost(size_gb, sku_name)
                
                disk_detail = {
                    'name': disk.name,
                    'resource_group': resource_group,
                    'location': disk.location,
                    'size_gb': size_gb,
                    'sku': sku_name,
                    'monthly_cost': round(monthly_cost, 2),
                    'annual_cost': round(monthly_cost * 12, 2),
                    'id': disk.id,
                    'created_time': disk.time_created.isoformat() if disk.time_created else None
                }
                
                # Categorize and add to appropriate list
                if disk.name.startswith('pvc-'):
                    category = 'pvc'
                    audit_results['pvc_disks'].append(disk_detail)
                elif resource_group.startswith('MC_'):
                    category = 'aks_managed'
                    audit_results['aks_managed_disks'].append(disk_detail)
                else:
                    category = 'orphaned'
                    audit_results['orphaned_disks'].append(disk_detail)
                
                # Update statistics
                disk_type_stats[sku_name]['count'] += 1
                disk_type_stats[sku_name]['total_gb'] += size_gb
                disk_type_stats[sku_name]['cost'] += monthly_cost
                total_cost += monthly_cost
        
        # Compile summary
        audit_results['summary'] = {
            'total_unattached_disks': (
                len(audit_results['orphaned_disks']) + 
                len(audit_results['pvc_disks']) + 
                len(audit_results['aks_managed_disks'])
            ),
            'orphaned_count': len(audit_results['orphaned_disks']),
            'pvc_count': len(audit_results['pvc_disks']),
            'aks_managed_count': len(audit_results['aks_managed_disks']),
            'total_monthly_cost': round(total_cost, 2),
            'total_annual_cost': round(total_cost * 12, 2),
            'orphaned_monthly_cost': round(
                sum(d['monthly_cost'] for d in audit_results['orphaned_disks']), 2
            ),
            'orphaned_annual_cost': round(
                sum(d['annual_cost'] for d in audit_results['orphaned_disks']), 2
            )
        }
        
        # Cost analysis by disk type
        audit_results['cost_analysis'] = {
            'by_sku': dict(disk_type_stats),
            'recommendations': generate_disk_recommendations(audit_results)
        }
        
    except Exception as e:
        api_errors['disk_audit'] = f"Failed to perform disk audit: {str(e)}"
    
    return audit_results, api_errors

def estimate_disk_cost(size_gb: int, sku_name: str) -> float:
    """
    Estimate monthly cost for a managed disk.
    
    Args:
        size_gb: Size of the disk in GB
        sku_name: SKU name (Standard_LRS, StandardSSD_LRS, Premium_LRS, etc.)
        
    Returns:
        Estimated monthly cost in USD
    """
    # Approximate costs per GB per month (varies by region)
    cost_per_gb = {
        'Standard_LRS': 0.05,      # Standard HDD
        'StandardSSD_LRS': 0.08,   # Standard SSD
        'Premium_LRS': 0.15,       # Premium SSD
        'UltraSSD_LRS': 0.30,      # Ultra SSD
    }
    
    # Get cost rate or use default
    rate = cost_per_gb.get(sku_name, 0.05)
    
    # Calculate monthly cost
    return size_gb * rate

def generate_disk_recommendations(audit_results: Dict[str, Any]) -> List[str]:
    """
    Generate recommendations based on disk audit results.
    
    Args:
        audit_results: Disk audit results dictionary
        
    Returns:
        List of recommendation strings
    """
    recommendations = []
    
    orphaned_cost = audit_results['summary'].get('orphaned_monthly_cost', 0)
    orphaned_count = audit_results['summary'].get('orphaned_count', 0)
    
    if orphaned_count > 0:
        recommendations.append(
            f"Delete {orphaned_count} orphaned disks to save ${orphaned_cost}/month"
        )
    
    if audit_results['pvc_disks']:
        recommendations.append(
            f"Review {len(audit_results['pvc_disks'])} PVC disks for potential cleanup"
        )
    
    if audit_results['aks_managed_disks']:
        recommendations.append(
            f"Verify {len(audit_results['aks_managed_disks'])} AKS-managed disks are still needed"
        )
    
    # Check for oversized disks
    for disk in audit_results['orphaned_disks']:
        if disk['size_gb'] > 500:
            recommendations.append(
                f"Large disk '{disk['name']}' ({disk['size_gb']}GB) - verify if needed"
            )
    
    return recommendations