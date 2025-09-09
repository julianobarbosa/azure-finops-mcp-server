"""Unit tests for Azure client factory with mocks."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from azure_finops_mcp_server.helpers.azure_client_factory import (
    AzureClientFactory,
    ComputeClientAdapter,
    DefaultAzureClientFactory,
    NetworkClientAdapter,
    get_client_factory,
    reset_client_factory,
    set_client_factory,
)


class MockAzureClientFactory(AzureClientFactory):
    """Mock implementation of Azure client factory for testing."""

    def __init__(self):
        """Initialize mock factory."""
        self.compute_clients = {}
        self.network_clients = {}
        self.consumption_clients = {}
        self.cost_clients = {}

    def create_compute_client(self, subscription_id: str):
        """Create a mock compute client."""
        if subscription_id not in self.compute_clients:
            mock_client = Mock()
            mock_client.virtual_machines = Mock()
            mock_client.disks = Mock()
            self.compute_clients[subscription_id] = mock_client
        return self.compute_clients[subscription_id]

    def create_network_client(self, subscription_id: str):
        """Create a mock network client."""
        if subscription_id not in self.network_clients:
            mock_client = Mock()
            mock_client.public_ip_addresses = Mock()
            self.network_clients[subscription_id] = mock_client
        return self.network_clients[subscription_id]

    def create_consumption_client(self, subscription_id: str):
        """Create a mock consumption client."""
        if subscription_id not in self.consumption_clients:
            mock_client = Mock()
            mock_client.budgets = Mock()
            mock_client.usage_details = Mock()
            self.consumption_clients[subscription_id] = mock_client
        return self.consumption_clients[subscription_id]

    def create_cost_client(self):
        """Create a mock cost management client."""
        if not self.cost_clients:
            mock_client = Mock()
            mock_client.query = Mock()
            self.cost_clients["default"] = mock_client
        return self.cost_clients["default"]


class TestAzureClientFactory:
    """Test Azure client factory functionality."""

    def test_get_client_factory_singleton(self):
        """Test that get_client_factory returns singleton."""
        factory1 = get_client_factory()
        factory2 = get_client_factory()
        assert factory1 is factory2

    def test_set_client_factory(self):
        """Test setting custom client factory."""
        reset_client_factory()
        mock_factory = MockAzureClientFactory()
        set_client_factory(mock_factory)

        factory = get_client_factory()
        assert factory is mock_factory

    def test_reset_client_factory(self):
        """Test resetting client factory."""
        mock_factory = MockAzureClientFactory()
        set_client_factory(mock_factory)
        reset_client_factory()

        factory = get_client_factory()
        assert factory is not mock_factory
        assert isinstance(factory, DefaultAzureClientFactory)


class TestComputeClientAdapter:
    """Test compute client adapter."""

    def test_list_all_vms(self):
        """Test listing all VMs through adapter."""
        mock_client = Mock()
        mock_client.virtual_machines.list_all.return_value = ["vm1", "vm2"]

        adapter = ComputeClientAdapter(mock_client)
        result = adapter.list_all_vms()

        assert result == ["vm1", "vm2"]
        mock_client.virtual_machines.list_all.assert_called_once()

    def test_get_instance_view(self):
        """Test getting VM instance view through adapter."""
        mock_client = Mock()
        mock_view = {"statuses": ["running"]}
        mock_client.virtual_machines.instance_view.return_value = mock_view

        adapter = ComputeClientAdapter(mock_client)
        result = adapter.get_instance_view("myRG", "myVM")

        assert result == mock_view
        mock_client.virtual_machines.instance_view.assert_called_once_with(resource_group_name="myRG", vm_name="myVM")

    def test_list_disks(self):
        """Test listing disks through adapter."""
        mock_client = Mock()
        mock_client.disks.list.return_value = ["disk1", "disk2"]

        adapter = ComputeClientAdapter(mock_client)
        result = adapter.list_disks()

        assert result == ["disk1", "disk2"]
        mock_client.disks.list.assert_called_once()


class TestNetworkClientAdapter:
    """Test network client adapter."""

    def test_list_public_ips(self):
        """Test listing public IPs through adapter."""
        mock_client = Mock()
        mock_client.public_ip_addresses.list_all.return_value = ["ip1", "ip2"]

        adapter = NetworkClientAdapter(mock_client)
        result = adapter.list_public_ips()

        assert result == ["ip1", "ip2"]
        mock_client.public_ip_addresses.list_all.assert_called_once()


class TestMockFactory:
    """Test mock factory for unit testing."""

    def setup_method(self):
        """Set up test with mock factory."""
        reset_client_factory()
        self.mock_factory = MockAzureClientFactory()
        set_client_factory(self.mock_factory)

    def teardown_method(self):
        """Clean up after test."""
        reset_client_factory()

    def test_mock_compute_client(self):
        """Test mock compute client creation."""
        client1 = self.mock_factory.create_compute_client("sub1")
        client2 = self.mock_factory.create_compute_client("sub1")
        client3 = self.mock_factory.create_compute_client("sub2")

        # Same subscription returns same client
        assert client1 is client2
        # Different subscription returns different client
        assert client1 is not client3

        # Verify mock attributes exist
        assert hasattr(client1, "virtual_machines")
        assert hasattr(client1, "disks")

    def test_mock_network_client(self):
        """Test mock network client creation."""
        client = self.mock_factory.create_network_client("sub1")

        assert hasattr(client, "public_ip_addresses")
        assert isinstance(client.public_ip_addresses, Mock)

    def test_mock_consumption_client(self):
        """Test mock consumption client creation."""
        client = self.mock_factory.create_consumption_client("sub1")

        assert hasattr(client, "budgets")
        assert hasattr(client, "usage_details")

    def test_mock_cost_client(self):
        """Test mock cost client creation."""
        client1 = self.mock_factory.create_cost_client()
        client2 = self.mock_factory.create_cost_client()

        # Cost client is singleton
        assert client1 is client2
        assert hasattr(client1, "query")
