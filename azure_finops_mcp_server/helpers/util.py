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
        regions: Optional[List[str]] = None
    ) -> Tuple[Dict[Any, Any], ApiErrors]:
    """
    Get list of unattached managed disks for specified regions.
    Azure equivalent of unattached EBS volumes.
    
    Args:
        credential: Azure credential object
        subscription_id: Azure subscription ID
        regions: Optional list of Azure region names
    """
    unattached_disks = defaultdict(list)
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
                unattached_disks[disk_location].append({
                    "DiskName": disk.name,
                    "DiskSize": f"{disk.disk_size_gb} GB",
                    "DiskType": disk.sku.name,
                    "ResourceGroup": disk.id.split('/')[4]
                })
    except Exception as e:
        disk_errors["Error"] = str(e)
    
    return dict(unattached_disks), disk_errors

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