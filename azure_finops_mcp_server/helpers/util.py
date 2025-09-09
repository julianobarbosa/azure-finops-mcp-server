"""
Utility module that re-exports functions from specialized modules for backward compatibility.

This module maintains the original API while delegating to focused modules.
"""

# Re-export from specialized modules for backward compatibility
from .subscription_manager import (
    get_azure_subscriptions,
    profiles_to_use,
    get_credential,
    ApiErrors
)

from .vm_operations import (
    get_stopped_vms,
    estimate_vm_monthly_cost,
    calculate_vm_waste
)

from .disk_operations import (
    get_unattached_disks,
    get_detailed_disk_audit,
    estimate_disk_cost,
    generate_disk_recommendations
)

from .network_operations import (
    get_unassociated_public_ips,
    estimate_public_ip_cost,
    calculate_network_waste,
    get_network_security_groups,
    analyze_network_usage
)

from .budget_operations import (
    get_budget_data,
    generate_budget_recommendations,
    analyze_spending_trends
)

from .cost_filters import (
    cost_filters,
    parse_filter_string,
    validate_filters,
    build_complex_filter
)

# Export all functions for backward compatibility
__all__ = [
    # Subscription management
    'get_azure_subscriptions',
    'profiles_to_use',
    'get_credential',
    'ApiErrors',
    
    # VM operations
    'get_stopped_vms',
    'estimate_vm_monthly_cost',
    'calculate_vm_waste',
    
    # Disk operations
    'get_unattached_disks',
    'get_detailed_disk_audit',
    'estimate_disk_cost',
    'generate_disk_recommendations',
    
    # Network operations
    'get_unassociated_public_ips',
    'estimate_public_ip_cost',
    'calculate_network_waste',
    'get_network_security_groups',
    'analyze_network_usage',
    
    # Budget operations
    'get_budget_data',
    'generate_budget_recommendations',
    'analyze_spending_trends',
    
    # Cost filters
    'cost_filters',
    'parse_filter_string',
    'validate_filters',
    'build_complex_filter'
]