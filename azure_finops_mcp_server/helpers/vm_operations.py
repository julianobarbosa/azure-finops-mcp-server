"""Virtual Machine operations for Azure FinOps."""

from typing import List, Optional, Dict, Tuple
from azure.mgmt.compute import ComputeManagementClient
import logging

logger = logging.getLogger(__name__)

ApiErrors = Dict[str, str]

def get_stopped_vms(
        credential,
        subscription_id: str,
        regions: Optional[List[str]] = None
    ) -> Tuple[Dict[str, List[Dict[str, str]]], ApiErrors]:
    """
    Get all stopped/deallocated VMs in a subscription.
    
    Args:
        credential: Azure credential for authentication
        subscription_id: Azure subscription ID
        regions: Optional list of regions to filter by
        
    Returns:
        Tuple of:
        - Dictionary with 'stopped_vms' key containing list of VM details
        - Dictionary of any errors encountered
    """
    api_errors: ApiErrors = {}
    stopped_vms = []
    
    try:
        # Create compute client
        compute_client = ComputeManagementClient(credential, subscription_id)
        
        # Get all VMs in the subscription
        for vm in compute_client.virtual_machines.list_all():
            # Filter by region if specified
            if regions and vm.location not in regions:
                continue
            
            # Get the instance view to check power state
            try:
                instance_view = compute_client.virtual_machines.instance_view(
                    resource_group_name=vm.id.split('/')[4],
                    vm_name=vm.name
                )
                
                # Check if VM is stopped/deallocated
                if instance_view.statuses:
                    for status in instance_view.statuses:
                        if status.code and 'PowerState/deallocated' in status.code:
                            stopped_vms.append({
                                'name': vm.name,
                                'resource_group': vm.id.split('/')[4],
                                'location': vm.location,
                                'vm_size': vm.hardware_profile.vm_size if vm.hardware_profile else 'Unknown',
                                'id': vm.id
                            })
                            break
            except Exception as e:
                logger.warning(f"Failed to get instance view for VM {vm.name}: {str(e)}")
                continue
                
    except Exception as e:
        api_errors['stopped_vms'] = f"Failed to get stopped VMs: {str(e)}"
    
    return {'stopped_vms': stopped_vms}, api_errors

def estimate_vm_monthly_cost(vm_size: str, location: str) -> float:
    """
    Estimate monthly cost for a VM based on size and location.
    
    Note: These are rough estimates. Actual costs vary by region and pricing tier.
    
    Args:
        vm_size: Azure VM size (e.g., 'Standard_B2s')
        location: Azure region
        
    Returns:
        Estimated monthly cost in USD
    """
    # Simplified cost estimates (actual costs vary by region)
    vm_cost_map = {
        # B-series (Burstable)
        'Standard_B1s': 7.59,
        'Standard_B1ms': 15.18,
        'Standard_B2s': 30.37,
        'Standard_B2ms': 60.74,
        'Standard_B4ms': 121.47,
        'Standard_B8ms': 242.94,
        
        # D-series (General Purpose)
        'Standard_D2s_v3': 96.36,
        'Standard_D4s_v3': 192.72,
        'Standard_D8s_v3': 385.44,
        'Standard_D16s_v3': 770.88,
        'Standard_D32s_v3': 1541.76,
        
        # E-series (Memory Optimized)
        'Standard_E2s_v3': 126.29,
        'Standard_E4s_v3': 252.58,
        'Standard_E8s_v3': 505.15,
        'Standard_E16s_v3': 1010.30,
        
        # F-series (Compute Optimized)
        'Standard_F2s_v2': 85.41,
        'Standard_F4s_v2': 170.82,
        'Standard_F8s_v2': 341.64,
        'Standard_F16s_v2': 683.28,
    }
    
    # Return estimate if available, otherwise return a default based on size pattern
    if vm_size in vm_cost_map:
        return vm_cost_map[vm_size]
    
    # Rough estimate based on VM size pattern
    if 'B1' in vm_size:
        return 15.0
    elif 'B2' in vm_size:
        return 30.0
    elif 'B4' in vm_size:
        return 120.0
    elif 'D2' in vm_size or 'E2' in vm_size or 'F2' in vm_size:
        return 100.0
    elif 'D4' in vm_size or 'E4' in vm_size or 'F4' in vm_size:
        return 200.0
    elif 'D8' in vm_size or 'E8' in vm_size or 'F8' in vm_size:
        return 400.0
    elif 'D16' in vm_size or 'E16' in vm_size or 'F16' in vm_size:
        return 800.0
    else:
        # Default estimate for unknown sizes
        return 150.0

def calculate_vm_waste(stopped_vms: List[Dict[str, str]]) -> Dict[str, float]:
    """
    Calculate potential cost savings from stopped VMs.
    
    Args:
        stopped_vms: List of stopped VM dictionaries
        
    Returns:
        Dictionary with total and per-VM waste estimates
    """
    total_waste = 0.0
    vm_waste = {}
    
    for vm in stopped_vms:
        vm_size = vm.get('vm_size', 'Unknown')
        location = vm.get('location', 'eastus')
        monthly_cost = estimate_vm_monthly_cost(vm_size, location)
        
        vm_waste[vm['name']] = monthly_cost
        total_waste += monthly_cost
    
    return {
        'total_monthly_waste': round(total_waste, 2),
        'vm_breakdown': vm_waste,
        'annual_waste': round(total_waste * 12, 2)
    }