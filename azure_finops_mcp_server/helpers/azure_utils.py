"""Common Azure resource utilities to eliminate code duplication."""

from typing import Any, Dict, Optional


def extract_resource_group(resource_id: str) -> str:
    """
    Extract resource group name from Azure resource ID.

    Azure resource IDs follow the pattern:
    /subscriptions/{subscription}/resourceGroups/{resource_group}/providers/{provider}/{type}/{name}

    Args:
        resource_id: Full Azure resource ID

    Returns:
        Resource group name

    Example:
        >>> extract_resource_group("/subscriptions/123/resourceGroups/myRG/providers/Microsoft.Compute/virtualMachines/myVM")
        'myRG'
    """
    try:
        parts = resource_id.split("/")
        # Resource group is always at index 4 in standard Azure resource IDs
        if len(parts) > 4 and parts[3].lower() == "resourcegroups":
            return parts[4]
        raise ValueError(f"Invalid Azure resource ID format: {resource_id}")
    except (IndexError, AttributeError) as e:
        raise ValueError(f"Failed to parse resource ID: {resource_id}") from e


def extract_subscription_id(resource_id: str) -> str:
    """
    Extract subscription ID from Azure resource ID.

    Args:
        resource_id: Full Azure resource ID

    Returns:
        Subscription ID

    Example:
        >>> extract_subscription_id("/subscriptions/123-456/resourceGroups/myRG/...")
        '123-456'
    """
    try:
        parts = resource_id.split("/")
        if len(parts) > 2 and parts[1].lower() == "subscriptions":
            return parts[2]
        raise ValueError(f"Invalid Azure resource ID format: {resource_id}")
    except (IndexError, AttributeError) as e:
        raise ValueError(f"Failed to parse resource ID: {resource_id}") from e


def extract_resource_name(resource_id: str) -> str:
    """
    Extract resource name from Azure resource ID.

    Args:
        resource_id: Full Azure resource ID

    Returns:
        Resource name (last component of the ID)

    Example:
        >>> extract_resource_name("/subscriptions/123/resourceGroups/myRG/.../virtualMachines/myVM")
        'myVM'
    """
    try:
        return resource_id.rstrip("/").split("/")[-1]
    except (IndexError, AttributeError) as e:
        raise ValueError(f"Failed to parse resource ID: {resource_id}") from e


def parse_resource_id(resource_id: str) -> Dict[str, str]:
    """
    Parse Azure resource ID into its components.

    Args:
        resource_id: Full Azure resource ID

    Returns:
        Dictionary with subscription_id, resource_group, and resource_name

    Example:
        >>> parse_resource_id("/subscriptions/123/resourceGroups/myRG/.../virtualMachines/myVM")
        {'subscription_id': '123', 'resource_group': 'myRG', 'resource_name': 'myVM'}
    """
    return {
        "subscription_id": extract_subscription_id(resource_id),
        "resource_group": extract_resource_group(resource_id),
        "resource_name": extract_resource_name(resource_id),
    }


def format_cost(cost: float, currency: str = "USD") -> str:
    """
    Format cost value for display.

    Args:
        cost: Cost value
        currency: Currency code (default: USD)

    Returns:
        Formatted cost string

    Example:
        >>> format_cost(1234.567)
        '$1,234.57'
    """
    if currency == "USD":
        return f"${cost:,.2f}"
    return f"{cost:,.2f} {currency}"


def is_orphaned_disk(disk_name: str, resource_group: str) -> bool:
    """
    Check if a disk is likely orphaned based on naming patterns.

    Args:
        disk_name: Name of the disk
        resource_group: Resource group name

    Returns:
        True if disk appears to be orphaned
    """
    # PVC disks (Persistent Volume Claims from Kubernetes)
    if disk_name.startswith("pvc-"):
        return True

    # AKS managed resource groups
    if resource_group.startswith("MC_"):
        return True

    return False


def calculate_monthly_cost(daily_cost: float) -> float:
    """
    Calculate monthly cost from daily cost.

    Args:
        daily_cost: Daily cost value

    Returns:
        Estimated monthly cost (using 30.44 days average)
    """
    DAYS_PER_MONTH = 30.44  # Average days per month
    return daily_cost * DAYS_PER_MONTH


def calculate_yearly_cost(monthly_cost: float) -> float:
    """
    Calculate yearly cost from monthly cost.

    Args:
        monthly_cost: Monthly cost value

    Returns:
        Yearly cost
    """
    return monthly_cost * 12
