"""Virtual Machine operations for Azure FinOps."""

from typing import List, Optional, Dict, Tuple, Any
from azure.mgmt.compute import ComputeManagementClient
from azure.core.exceptions import ResourceNotFoundError
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from azure_finops_mcp_server.helpers.azure_utils import (
    extract_resource_group,
    format_cost,
    calculate_yearly_cost
)
from azure_finops_mcp_server.config import get_config

logger = logging.getLogger(__name__)

ApiErrors = Dict[str, str]


def get_vm_instance_view_batch(
        compute_client: ComputeManagementClient,
        vm_list: List[Any]
    ) -> Dict[str, Any]:
    """
    Get instance views for multiple VMs in parallel to avoid N+1 queries.
    
    Args:
        compute_client: Azure compute management client
        vm_list: List of VM objects
        
    Returns:
        Dictionary mapping VM ID to instance view
    """
    config = get_config()
    instance_views = {}
    
    def fetch_instance_view(vm):
        """Fetch instance view for a single VM."""
        try:
            resource_group = extract_resource_group(vm.id)
            instance_view = compute_client.virtual_machines.instance_view(
                resource_group_name=resource_group,
                vm_name=vm.name
            )
            return vm.id, instance_view
        except Exception as e:
            logger.warning(f"Failed to get instance view for VM {vm.name}: {str(e)}")
            return vm.id, None
    
    # Use ThreadPoolExecutor for parallel fetching
    with ThreadPoolExecutor(max_workers=config.max_parallel_workers) as executor:
        future_to_vm = {executor.submit(fetch_instance_view, vm): vm for vm in vm_list}
        
        for future in as_completed(future_to_vm):
            vm_id, instance_view = future.result()
            if instance_view:
                instance_views[vm_id] = instance_view
    
    return instance_views


def get_stopped_vms(
        credential,
        subscription_id: str,
        regions: Optional[List[str]] = None
    ) -> Tuple[Dict[str, Any], ApiErrors]:
    """
    Get all stopped/deallocated VMs in a subscription with optimized batch processing.
    
    Args:
        credential: Azure credential for authentication
        subscription_id: Azure subscription ID
        regions: Optional list of regions to filter by
        
    Returns:
        Tuple of:
        - Dictionary with stopped VMs and statistics
        - Dictionary of any errors encountered
    """
    api_errors: ApiErrors = {}
    stopped_vms = []
    
    try:
        compute_client = ComputeManagementClient(credential, subscription_id)
        
        # Step 1: Get all VMs (single API call)
        all_vms = list(compute_client.virtual_machines.list_all())
        
        # Filter by region if specified
        if regions:
            filtered_vms = [vm for vm in all_vms if vm.location in regions]
        else:
            filtered_vms = all_vms
        
        # Step 2: Get instance views in batch (parallel calls)
        instance_views = get_vm_instance_view_batch(compute_client, filtered_vms)
        
        # Step 3: Process results
        for vm in filtered_vms:
            instance_view = instance_views.get(vm.id)
            if instance_view and instance_view.statuses:
                for status in instance_view.statuses:
                    if status.code and 'PowerState/deallocated' in status.code:
                        vm_info = {
                            'name': vm.name,
                            'resource_group': extract_resource_group(vm.id),
                            'location': vm.location,
                            'vm_size': vm.hardware_profile.vm_size if vm.hardware_profile else 'Unknown',
                            'id': vm.id
                        }
                        
                        # Add cost estimation
                        monthly_cost = estimate_vm_monthly_cost(vm_info['vm_size'])
                        vm_info['estimated_monthly_cost'] = monthly_cost
                        vm_info['estimated_annual_cost'] = calculate_yearly_cost(monthly_cost)
                        
                        stopped_vms.append(vm_info)
                        break
        
        # Calculate statistics
        total_monthly_waste = sum(vm['estimated_monthly_cost'] for vm in stopped_vms)
        
        result = {
            'stopped_vms': stopped_vms,
            'statistics': {
                'total_stopped': len(stopped_vms),
                'total_vms_checked': len(filtered_vms),
                'total_monthly_waste': round(total_monthly_waste, 2),
                'total_annual_waste': round(calculate_yearly_cost(total_monthly_waste), 2)
            }
        }
        
    except Exception as e:
        api_errors['stopped_vms'] = f"Failed to get stopped VMs: {str(e)}"
        result = {'stopped_vms': [], 'statistics': {}}
    
    return result, api_errors


def estimate_vm_monthly_cost(vm_size: str) -> float:
    """
    Estimate monthly cost for a VM based on size.
    
    Args:
        vm_size: Azure VM size (e.g., 'Standard_B2s')
        
    Returns:
        Estimated monthly cost in USD
    """
    config = get_config()
    
    # Use hourly rates from config and convert to monthly
    hourly_rate = config.vm_cost_rates.get(vm_size, config.vm_cost_rates.get('default', 0.10))
    monthly_cost = hourly_rate * config.hours_per_month
    
    return round(monthly_cost, 2)


def calculate_vm_waste(stopped_vms: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculate potential cost savings from stopped VMs.
    
    Args:
        stopped_vms: List of stopped VM dictionaries
        
    Returns:
        Dictionary with total and per-VM waste estimates
    """
    total_waste = 0.0
    vm_waste = {}
    vm_by_size = {}
    
    for vm in stopped_vms:
        vm_size = vm.get('vm_size', 'Unknown')
        monthly_cost = vm.get('estimated_monthly_cost', estimate_vm_monthly_cost(vm_size))
        
        vm_waste[vm['name']] = monthly_cost
        total_waste += monthly_cost
        
        # Group by VM size for analysis
        if vm_size not in vm_by_size:
            vm_by_size[vm_size] = {'count': 0, 'total_cost': 0}
        vm_by_size[vm_size]['count'] += 1
        vm_by_size[vm_size]['total_cost'] += monthly_cost
    
    return {
        'total_monthly_waste': round(total_waste, 2),
        'total_annual_waste': round(calculate_yearly_cost(total_waste), 2),
        'vm_breakdown': vm_waste,
        'waste_by_size': vm_by_size,
        'recommendations': generate_vm_recommendations(stopped_vms, total_waste)
    }


def generate_vm_recommendations(stopped_vms: List[Dict[str, Any]], total_waste: float) -> List[str]:
    """
    Generate recommendations based on stopped VMs analysis.
    
    Args:
        stopped_vms: List of stopped VM dictionaries
        total_waste: Total monthly waste from stopped VMs
        
    Returns:
        List of recommendation strings
    """
    recommendations = []
    
    vm_count = len(stopped_vms)
    
    if vm_count > 0:
        recommendations.append(
            f"Consider deleting {vm_count} stopped VMs to save {format_cost(total_waste)}/month"
        )
    
    if vm_count > 10:
        recommendations.append(
            "High number of stopped VMs detected - consider implementing auto-shutdown policies"
        )
    
    # Check for expensive stopped VMs
    expensive_vms = [vm for vm in stopped_vms 
                     if vm.get('estimated_monthly_cost', 0) > 500]
    if expensive_vms:
        recommendations.append(
            f"Found {len(expensive_vms)} high-cost stopped VMs (>{format_cost(500)}/month each)"
        )
    
    if total_waste > 1000:
        annual_savings = calculate_yearly_cost(total_waste)
        recommendations.append(
            f"Significant savings opportunity: {format_cost(annual_savings)}/year"
        )
    
    return recommendations