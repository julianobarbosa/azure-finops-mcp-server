from azure.identity import AzureCliCredential, DefaultAzureCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.consumption import ConsumptionManagementClient
from typing import List, Optional, Any, Dict, Tuple
from collections import defaultdict
import subprocess
import json

ApiErrors = Dict[str, str]

def get_azure_subscriptions() -> List[Dict[str, str]]:
    """
    Get list of Azure subscriptions available via Azure CLI.
    Similar to AWS profiles but for Azure subscriptions.
    """
    try:
        result = subprocess.run(
            ["az", "account", "list", "--output", "json"],
            capture_output=True,
            text=True,
            check=True
        )
        subscriptions = json.loads(result.stdout)
        return subscriptions
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        return []

def profiles_to_use(
        profiles: Optional[List[str]] = None,
        all_profiles: Optional[bool] = False
    ) -> Tuple[Dict[str, List[str]], ApiErrors]:
    """
    Filters Azure subscriptions by name/ID, retrieves their details,
    and groups them for processing. Maps AWS profile concept to Azure subscriptions.
    
    Args:
        profiles: A list of subscription names or IDs to process.
        all_profiles: If True, retrieves all available subscriptions.
    
    Returns:
        A dictionary where keys are Subscription IDs and
        values are lists of subscription names that belong to that subscription.
        Subscriptions that don't exist or cause errors are skipped.
    """
    profile_errors: ApiErrors = {}
    subscription_to_names_map: Dict[str, List[str]] = defaultdict(list)
    
    available_subscriptions = get_azure_subscriptions()
    
    if not available_subscriptions:
        profile_errors["Error"] = "No Azure subscriptions found. Please run 'az login' first."
        return {}, profile_errors
    
    subscription_lookup = {
        sub['name']: sub for sub in available_subscriptions
    }
    subscription_lookup.update({
        sub['id']: sub for sub in available_subscriptions
    })
    
    if all_profiles:
        subscriptions_to_query = [sub['name'] for sub in available_subscriptions]
    else:
        subscriptions_to_query = profiles or []
    
    for profile in subscriptions_to_query:
        if profile in subscription_lookup:
            subscription = subscription_lookup[profile]
            subscription_id = subscription['id']
            subscription_name = subscription['name']
            subscription_to_names_map[subscription_id].append(subscription_name)
        else:
            profile_errors[f"Error processing profile {profile}"] = f"Subscription {profile} does not exist."
    
    return dict(subscription_to_names_map), profile_errors

def get_credential():
    """
    Get Azure credential using Azure CLI or DefaultAzureCredential.
    """
    try:
        # Try Azure CLI credential first (similar to AWS CLI profiles)
        return AzureCliCredential()
    except:
        # Fall back to DefaultAzureCredential
        return DefaultAzureCredential()

def get_stopped_vms(
        credential,
        subscription_id: str,
        regions: Optional[List[str]] = None
    ) -> Tuple[Dict[Any, Any], ApiErrors]:
    """
    Retrieves stopped/deallocated VMs for specified regions.
    Azure equivalent of stopped EC2 instances.
    
    Args:
        credential: Azure credential object
        subscription_id: Azure subscription ID
        regions: Optional list of Azure region names
    
    Returns:
        A tuple containing:
        - A dictionary mapping each region to a list of stopped VM details
        - A dictionary of errors that occurred while querying regions
    """
    stopped_vms = defaultdict(list)
    stopped_vm_errors: ApiErrors = {}
    
    try:
        compute_client = ComputeManagementClient(credential, subscription_id)
        
        # Get all VMs in subscription
        for vm in compute_client.virtual_machines.list_all():
            # Get VM location (region)
            vm_location = vm.location
            
            # Filter by regions if specified
            if regions and vm_location not in regions:
                continue
            
            # Get instance view to check power state
            instance_view = compute_client.virtual_machines.instance_view(
                resource_group_name=vm.id.split('/')[4],
                vm_name=vm.name
            )
            
            # Check if VM is stopped/deallocated
            for status in instance_view.statuses:
                if status.code == 'PowerState/deallocated' or status.code == 'PowerState/stopped':
                    stopped_vms[vm_location].append({
                        "VMName": vm.name,
                        "VMSize": vm.hardware_profile.vm_size,
                        "ResourceGroup": vm.id.split('/')[4]
                    })
                    break
    except Exception as e:
        stopped_vm_errors["Error"] = str(e)
    
    return dict(stopped_vms), stopped_vm_errors

def get_unattached_disks(
        credential,
        subscription_id: str,
        regions: Optional[List[str]] = None,
        include_pvc: bool = False,
        include_aks_managed: bool = False
    ) -> Tuple[Dict[Any, Any], ApiErrors]:
    """
    Get list of truly unattached managed disks for specified regions.
    Filters out Kubernetes PVC disks and AKS-managed disks by default.
    
    Args:
        credential: Azure credential object
        subscription_id: Azure subscription ID
        regions: Optional list of Azure region names
        include_pvc: Whether to include PVC disks (default: False)
        include_aks_managed: Whether to include disks in MC_* resource groups (default: False)
    
    Returns:
        Dict with categorized unattached disks and any errors
    """
    unattached_disks = defaultdict(list)
    pvc_disks = defaultdict(list)
    aks_managed_disks = defaultdict(list)
    disk_errors: ApiErrors = {}
    
    try:
        compute_client = ComputeManagementClient(credential, subscription_id)
        
        # Get all disks in subscription
        for disk in compute_client.disks.list():
            # Get disk location (region)
            disk_location = disk.location
            
            # Filter by regions if specified
            if regions and disk_location not in regions:
                continue
            
            # Check if disk is unattached
            if disk.disk_state == 'Unattached':
                resource_group = disk.id.split('/')[4]
                disk_info = {
                    "DiskName": disk.name,
                    "DiskSize": f"{disk.disk_size_gb} GB",
                    "DiskType": disk.sku.name,
                    "ResourceGroup": resource_group
                }
                
                # Categorize the disk
                if disk.name.startswith('pvc-'):
                    # This is a Kubernetes PVC disk
                    pvc_disks[disk_location].append(disk_info)
                    if include_pvc:
                        disk_info["Note"] = "Kubernetes PVC - Manage via kubectl"
                        unattached_disks[disk_location].append(disk_info)
                elif resource_group.startswith('MC_'):
                    # This is in an AKS-managed resource group
                    aks_managed_disks[disk_location].append(disk_info)
                    if include_aks_managed:
                        disk_info["Note"] = "AKS-managed resource group"
                        unattached_disks[disk_location].append(disk_info)
                else:
                    # This is truly orphaned
                    unattached_disks[disk_location].append(disk_info)
    except Exception as e:
        disk_errors["Error"] = str(e)
    
    # Add metadata about filtered disks if any were found
    result = dict(unattached_disks)
    if pvc_disks and not include_pvc:
        disk_errors["Info"] = f"Filtered out {sum(len(v) for v in pvc_disks.values())} PVC disks"
    if aks_managed_disks and not include_aks_managed:
        existing_info = disk_errors.get("Info", "")
        filtered_aks = sum(len(v) for v in aks_managed_disks.values())
        disk_errors["Info"] = f"{existing_info}; Filtered out {filtered_aks} AKS-managed disks" if existing_info else f"Filtered out {filtered_aks} AKS-managed disks"
    
    return result, disk_errors

def get_detailed_disk_audit(
        credential,
        subscription_id: str,
        regions: Optional[List[str]] = None
    ) -> Tuple[Dict[str, Any], ApiErrors]:
    """
    Get detailed audit of all disk types including orphaned, PVC, and AKS-managed.
    Provides categorized reporting for better cost optimization decisions.
    
    Args:
        credential: Azure credential object
        subscription_id: Azure subscription ID
        regions: Optional list of Azure region names
    
    Returns:
        Dict with detailed disk categorization and any errors
    """
    audit_result = {
        "truly_orphaned": defaultdict(list),
        "kubernetes_pvc": defaultdict(list),
        "aks_managed_other": defaultdict(list),
        "summary": {
            "total_unattached": 0,
            "truly_orphaned_count": 0,
            "pvc_count": 0,
            "aks_managed_count": 0,
            "potential_monthly_savings": 0.0
        }
    }
    disk_errors: ApiErrors = {}
    
    # Approximate monthly costs per disk type (USD)
    disk_costs = {
        "Standard_LRS": 0.05,  # per GB
        "StandardSSD_LRS": 0.08,  # per GB
        "Premium_LRS": 0.15,  # per GB
        "UltraSSD_LRS": 0.30  # per GB
    }
    
    try:
        compute_client = ComputeManagementClient(credential, subscription_id)
        
        for disk in compute_client.disks.list():
            disk_location = disk.location
            
            if regions and disk_location not in regions:
                continue
            
            if disk.disk_state == 'Unattached':
                resource_group = disk.id.split('/')[4]
                disk_size_gb = disk.disk_size_gb or 0
                disk_type = disk.sku.name if disk.sku else "Unknown"
                
                # Calculate approximate monthly cost
                cost_per_gb = disk_costs.get(disk_type, 0.10)  # Default to mid-range
                monthly_cost = disk_size_gb * cost_per_gb
                
                disk_info = {
                    "DiskName": disk.name,
                    "DiskSize": f"{disk_size_gb} GB",
                    "DiskType": disk_type,
                    "ResourceGroup": resource_group,
                    "EstimatedMonthlyCost": f"${monthly_cost:.2f}",
                    "CreatedTime": disk.time_created.isoformat() if disk.time_created else "Unknown"
                }
                
                audit_result["summary"]["total_unattached"] += 1
                
                # Categorize the disk
                if disk.name.startswith('pvc-'):
                    disk_info["ManagementNote"] = "Kubernetes PVC - Check with: kubectl get pv | grep Released"
                    audit_result["kubernetes_pvc"][disk_location].append(disk_info)
                    audit_result["summary"]["pvc_count"] += 1
                elif resource_group.startswith('MC_'):
                    disk_info["ManagementNote"] = "AKS-managed - Review AKS cluster health"
                    audit_result["aks_managed_other"][disk_location].append(disk_info)
                    audit_result["summary"]["aks_managed_count"] += 1
                else:
                    disk_info["ManagementNote"] = "Truly orphaned - Safe to delete"
                    audit_result["truly_orphaned"][disk_location].append(disk_info)
                    audit_result["summary"]["truly_orphaned_count"] += 1
                    audit_result["summary"]["potential_monthly_savings"] += monthly_cost
                    
    except Exception as e:
        disk_errors["Error"] = str(e)
    
    # Convert defaultdicts to regular dicts for clean JSON serialization
    audit_result["truly_orphaned"] = dict(audit_result["truly_orphaned"])
    audit_result["kubernetes_pvc"] = dict(audit_result["kubernetes_pvc"])
    audit_result["aks_managed_other"] = dict(audit_result["aks_managed_other"])
    
    # Add recommendations
    if audit_result["summary"]["truly_orphaned_count"] > 0:
        audit_result["recommendations"] = [
            f"Delete {audit_result['summary']['truly_orphaned_count']} truly orphaned disks to save ~${audit_result['summary']['potential_monthly_savings']:.2f}/month",
            "Review the 'truly_orphaned' section for disks safe to delete"
        ]
    if audit_result["summary"]["pvc_count"] > 0:
        if "recommendations" not in audit_result:
            audit_result["recommendations"] = []
        audit_result["recommendations"].append(
            f"Review {audit_result['summary']['pvc_count']} Kubernetes PVCs using: kubectl get pv --all-namespaces | grep Released"
        )
    
    return audit_result, disk_errors

def get_unassociated_public_ips(
        credential,
        subscription_id: str,
        regions: Optional[List[str]] = None
    ) -> Tuple[Dict[str, Any], ApiErrors]:
    """
    Get list of unassociated public IPs for specified regions.
    Azure equivalent of unassociated Elastic IPs.
    
    Args:
        credential: Azure credential object
        subscription_id: Azure subscription ID
        regions: Optional list of Azure region names
    """
    unassociated_ips = defaultdict(list)
    ip_errors: ApiErrors = {}
    
    try:
        network_client = NetworkManagementClient(credential, subscription_id)
        
        # Get all public IPs in subscription
        for public_ip in network_client.public_ip_addresses.list_all():
            # Get IP location (region)
            ip_location = public_ip.location
            
            # Filter by regions if specified
            if regions and ip_location not in regions:
                continue
            
            # Check if IP is unassociated
            if not public_ip.ip_configuration:
                unassociated_ips[ip_location].append({
                    "Name": public_ip.name,
                    "IPAddress": public_ip.ip_address or "Not Assigned",
                    "SKU": public_ip.sku.name if public_ip.sku else "Basic",
                    "ResourceGroup": public_ip.id.split('/')[4]
                })
    except Exception as e:
        ip_errors["Error"] = str(e)
    
    return dict(unassociated_ips), ip_errors

def get_budget_data(
        credential,
        subscription_id: str,
    ) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """
    Get budget data for specified Azure subscription.
    Azure equivalent of AWS Budgets.
    
    Args:
        credential: Azure credential object
        subscription_id: Azure subscription ID
    """
    budget_data: Dict[str, Any] = {}
    budget_errors: Dict[str, str] = {}
    
    try:
        consumption_client = ConsumptionManagementClient(credential, subscription_id)
        
        # Get budgets for the subscription
        scope = f'/subscriptions/{subscription_id}'
        budgets = consumption_client.budgets.list(scope=scope)
        
        for budget in budgets:
            name = budget.name
            limit = float(budget.amount)
            
            # Get current spend (this is simplified - in reality you'd query usage details)
            # For now, we'll use the budget's current period if available
            actual = 0.0
            forecast = 0.0
            
            if hasattr(budget, 'current_spend'):
                actual = float(budget.current_spend.amount) if budget.current_spend else 0.0
            
            if hasattr(budget, 'forecast_spend'):
                forecast = float(budget.forecast_spend.amount) if budget.forecast_spend else 0.0
            
            if actual > limit:
                status = "Over Budget"
            elif forecast > limit:
                status = "Forecasted to Exceed"
            else:
                status = "Under Budget"
            
            budget_data[name] = {
                "Limit": f"{limit:.2f}",
                "Actual Spend": f"{actual:.2f}",
                "Forecasted Spend": f"{forecast:.2f}" if forecast else "N/A",
                "Status": status
            }
    
    except Exception as e:
        budget_errors["Budget Error"] = str(e)
    
    return budget_data, budget_errors

def cost_filters(
    tags: Optional[List[str]] = None,
    dimensions: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Constructs filter parameters for Azure Cost Management API query.
    Maps AWS Cost Explorer filters to Azure equivalents.
    """
    filters_list: List[Dict[str, Any]] = []
    query_filter: Optional[Dict[str, Any]] = None
    query_kwargs: Dict[str, Any] = {}
    
    if tags:
        for tag_str in tags:
            if "=" in tag_str:
                key, value = tag_str.split("=", 1)
                filters_list.append({
                    "tags": {
                        "name": key,
                        "operator": "In",
                        "values": [value]
                    }
                })
    
    if dimensions:
        for dim_str in dimensions:
            if "=" in dim_str:
                key, value = dim_str.split("=", 1)
                # Map common AWS dimensions to Azure
                azure_dim_map = {
                    "REGION": "ResourceLocation",
                    "SERVICE": "ServiceName",
                    "INSTANCE_TYPE": "MeterSubcategory",
                    "RESOURCE_ID": "ResourceId"
                }
                azure_key = azure_dim_map.get(key, key)
                filters_list.append({
                    "dimension": {
                        "name": azure_key,
                        "operator": "In",
                        "values": [value]
                    }
                })
    
    if len(filters_list) == 1:
        query_filter = filters_list[0]
    elif len(filters_list) > 1:
        query_filter = {"and": filters_list}
    
    if query_filter:
        query_kwargs["filter"] = query_filter
    
    return query_kwargs