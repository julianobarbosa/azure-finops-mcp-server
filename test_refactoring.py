#!/usr/bin/env python3
"""Test script to verify refactored code works correctly."""

import sys
import os

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from azure_finops_mcp_server.helpers.azure_utils import (
    extract_resource_group,
    extract_subscription_id,
    extract_resource_name,
    parse_resource_id,
    format_cost,
    calculate_monthly_cost,
    calculate_yearly_cost
)
from azure_finops_mcp_server.config import get_config, AzureFinOpsConfig


def test_azure_utils():
    """Test the Azure utility functions."""
    print("Testing Azure Utilities...")
    
    # Test resource ID parsing
    resource_id = "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/myRG/providers/Microsoft.Compute/virtualMachines/myVM"
    
    assert extract_resource_group(resource_id) == "myRG"
    assert extract_subscription_id(resource_id) == "12345678-1234-1234-1234-123456789012"
    assert extract_resource_name(resource_id) == "myVM"
    
    parsed = parse_resource_id(resource_id)
    assert parsed['resource_group'] == "myRG"
    assert parsed['subscription_id'] == "12345678-1234-1234-1234-123456789012"
    assert parsed['resource_name'] == "myVM"
    
    # Test cost formatting
    assert format_cost(1234.567) == "$1,234.57"
    assert format_cost(0.99) == "$0.99"
    
    # Test cost calculations
    assert abs(calculate_monthly_cost(10) - 304.4) < 0.01  # 10 * 30.44
    assert abs(calculate_yearly_cost(100) - 1200) < 0.01  # 100 * 12
    
    print("✓ Azure utilities tests passed")


def test_config():
    """Test the configuration module."""
    print("\nTesting Configuration...")
    
    # Create a test config
    config = AzureFinOpsConfig()
    
    # Test that defaults are loaded
    assert config.max_parallel_workers == 5
    assert config.request_timeout == 30
    assert config.days_per_month == 30.44
    assert config.hours_per_month == 730
    
    # Test that cost rates are loaded
    assert config.disk_cost_rates is not None
    assert 'standard_hdd' in config.disk_cost_rates
    assert 'premium_ssd' in config.disk_cost_rates
    
    assert config.public_ip_cost_rates is not None
    assert 'basic_static' in config.public_ip_cost_rates
    
    assert config.vm_cost_rates is not None
    assert 'Standard_B1s' in config.vm_cost_rates
    assert 'default' in config.vm_cost_rates
    
    # Test patterns
    assert config.orphaned_disk_patterns is not None
    assert 'pvc-' in config.orphaned_disk_patterns
    
    assert config.managed_resource_group_patterns is not None
    assert 'MC_' in config.managed_resource_group_patterns
    
    print("✓ Configuration tests passed")


def test_imports():
    """Test that all refactored modules can be imported."""
    print("\nTesting Module Imports...")
    
    try:
        from azure_finops_mcp_server.helpers.disk_operations import (
            get_unattached_disks,
            get_detailed_disk_audit,
            estimate_disk_cost
        )
        print("✓ disk_operations imports successfully")
    except ImportError as e:
        print(f"✗ Failed to import disk_operations: {e}")
        return False
    
    try:
        from azure_finops_mcp_server.helpers.vm_operations import (
            get_stopped_vms,
            estimate_vm_monthly_cost,
            calculate_vm_waste
        )
        print("✓ vm_operations imports successfully")
    except ImportError as e:
        print(f"✗ Failed to import vm_operations: {e}")
        return False
    
    try:
        from azure_finops_mcp_server.helpers.network_operations import (
            get_unassociated_public_ips,
            estimate_public_ip_cost
        )
        print("✓ network_operations imports successfully")
    except ImportError as e:
        print(f"✗ Failed to import network_operations: {e}")
        return False
    
    return True


def test_cost_calculations():
    """Test cost calculation functions."""
    print("\nTesting Cost Calculations...")
    
    from azure_finops_mcp_server.helpers.disk_operations import estimate_disk_cost
    from azure_finops_mcp_server.helpers.vm_operations import estimate_vm_monthly_cost
    from azure_finops_mcp_server.helpers.network_operations import estimate_public_ip_cost
    
    # Test disk cost estimation
    cost = estimate_disk_cost(100, 'Standard_LRS')  # 100GB standard HDD
    assert cost == 5.0  # 100 * 0.05
    print(f"✓ 100GB Standard HDD: ${cost}/month")
    
    cost = estimate_disk_cost(100, 'Premium_LRS')  # 100GB premium SSD
    assert cost == 18.0  # 100 * 0.18
    print(f"✓ 100GB Premium SSD: ${cost}/month")
    
    # Test VM cost estimation
    cost = estimate_vm_monthly_cost('Standard_B1s')
    assert abs(cost - 7.59) < 0.01  # 0.0104 * 730
    print(f"✓ Standard_B1s VM: ${cost}/month")
    
    cost = estimate_vm_monthly_cost('UnknownSize')
    assert abs(cost - 73.0) < 0.01  # default 0.10 * 730
    print(f"✓ Unknown VM size (default): ${cost}/month")
    
    # Test public IP cost estimation
    cost = estimate_public_ip_cost('Standard', 'Static')
    assert cost == 4.38
    print(f"✓ Standard Static IP: ${cost}/month")
    
    cost = estimate_public_ip_cost('Basic', 'Dynamic')
    assert cost == 2.88
    print(f"✓ Basic Dynamic IP: ${cost}/month")
    
    print("✓ All cost calculations passed")


def main():
    """Run all tests."""
    print("=" * 50)
    print("Running Refactoring Tests")
    print("=" * 50)
    
    try:
        test_azure_utils()
        test_config()
        
        if test_imports():
            test_cost_calculations()
            
            print("\n" + "=" * 50)
            print("✅ All tests passed successfully!")
            print("=" * 50)
            return 0
        else:
            print("\n" + "=" * 50)
            print("❌ Some imports failed")
            print("=" * 50)
            return 1
            
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())