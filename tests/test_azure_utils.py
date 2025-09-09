"""Unit tests for azure_utils module."""

import pytest

from azure_finops_mcp_server.helpers.azure_utils import (
    calculate_monthly_cost,
    calculate_yearly_cost,
    extract_resource_group,
    extract_resource_name,
    extract_subscription_id,
    format_cost,
    is_orphaned_disk,
    parse_resource_id,
)


class TestResourceIdParsing:
    """Test Azure resource ID parsing functions."""

    def test_extract_resource_group_valid(self):
        """Test extracting resource group from valid resource ID."""
        resource_id = "/subscriptions/12345/resourceGroups/myRG/providers/Microsoft.Compute/virtualMachines/myVM"
        assert extract_resource_group(resource_id) == "myRG"

    def test_extract_resource_group_invalid(self):
        """Test extracting resource group from invalid resource ID."""
        with pytest.raises(ValueError):
            extract_resource_group("invalid/resource/id")

    def test_extract_subscription_id_valid(self):
        """Test extracting subscription ID from valid resource ID."""
        resource_id = "/subscriptions/12345-6789/resourceGroups/myRG/providers/Microsoft.Compute/virtualMachines/myVM"
        assert extract_subscription_id(resource_id) == "12345-6789"

    def test_extract_resource_name_valid(self):
        """Test extracting resource name from valid resource ID."""
        resource_id = "/subscriptions/12345/resourceGroups/myRG/providers/Microsoft.Compute/virtualMachines/myVM"
        assert extract_resource_name(resource_id) == "myVM"

    def test_parse_resource_id_complete(self):
        """Test parsing complete resource ID."""
        resource_id = "/subscriptions/sub123/resourceGroups/testRG/providers/Microsoft.Network/publicIPAddresses/myIP"
        result = parse_resource_id(resource_id)

        assert result["subscription_id"] == "sub123"
        assert result["resource_group"] == "testRG"
        assert result["resource_name"] == "myIP"


class TestCostFormatting:
    """Test cost formatting functions."""

    def test_format_cost_usd(self):
        """Test formatting cost in USD."""
        assert format_cost(1234.567) == "$1,234.57"
        assert format_cost(0.99) == "$0.99"
        assert format_cost(1000000) == "$1,000,000.00"

    def test_format_cost_other_currency(self):
        """Test formatting cost in other currencies."""
        assert format_cost(100, "EUR") == "100.00 EUR"
        assert format_cost(999.999, "GBP") == "1,000.00 GBP"


class TestCostCalculations:
    """Test cost calculation functions."""

    def test_calculate_monthly_cost(self):
        """Test monthly cost calculation."""
        daily_cost = 10.0
        monthly = calculate_monthly_cost(daily_cost)
        assert abs(monthly - 304.4) < 0.01  # 10 * 30.44 with floating point tolerance

    def test_calculate_yearly_cost(self):
        """Test yearly cost calculation."""
        monthly_cost = 100.0
        yearly = calculate_yearly_cost(monthly_cost)
        assert yearly == 1200.0  # 100 * 12


class TestDiskIdentification:
    """Test disk identification functions."""

    def test_is_orphaned_disk_pvc(self):
        """Test identifying PVC disks as orphaned."""
        assert is_orphaned_disk("pvc-12345", "anyRG") is True
        assert is_orphaned_disk("pvc-disk-name", "testRG") is True

    def test_is_orphaned_disk_aks_managed(self):
        """Test identifying AKS managed disks as orphaned."""
        assert is_orphaned_disk("anydisk", "MC_aksRG") is True
        assert is_orphaned_disk("disk1", "MC_test") is True

    def test_is_orphaned_disk_normal(self):
        """Test normal disks are not identified as orphaned."""
        assert is_orphaned_disk("mydisk", "myRG") is False
        assert is_orphaned_disk("data-disk-1", "prod-rg") is False
