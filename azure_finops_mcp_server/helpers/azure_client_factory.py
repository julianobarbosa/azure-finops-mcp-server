"""Azure client factory for dependency injection and better testability."""

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional, Protocol

from azure.identity import DefaultAzureCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.consumption import ConsumptionManagementClient
from azure.mgmt.costmanagement import CostManagementClient
from azure.mgmt.network import NetworkManagementClient

from azure_finops_mcp_server.config import get_config

logger = logging.getLogger(__name__)


class ComputeClientProtocol(Protocol):
    """Protocol for compute client operations."""

    def list_all_vms(self) -> Any:
        """List all virtual machines."""
        ...

    def get_instance_view(self, resource_group: str, vm_name: str) -> Any:
        """Get VM instance view."""
        ...

    def list_disks(self) -> Any:
        """List all managed disks."""
        ...


class NetworkClientProtocol(Protocol):
    """Protocol for network client operations."""

    def list_public_ips(self) -> Any:
        """List all public IP addresses."""
        ...


class ConsumptionClientProtocol(Protocol):
    """Protocol for consumption client operations."""

    def list_budgets(self, scope: str) -> Any:
        """List budgets for a scope."""
        ...

    def get_usage(self, scope: str) -> Any:
        """Get usage details for a scope."""
        ...


class CostClientProtocol(Protocol):
    """Protocol for cost management client operations."""

    def query_usage(self, scope: str, parameters: Any) -> Any:
        """Query cost usage data."""
        ...


class AzureClientFactory(ABC):
    """Abstract base class for Azure client factories."""

    @abstractmethod
    def create_compute_client(self, subscription_id: str) -> ComputeClientProtocol:
        """Create a compute management client."""
        pass

    @abstractmethod
    def create_network_client(self, subscription_id: str) -> NetworkClientProtocol:
        """Create a network management client."""
        pass

    @abstractmethod
    def create_consumption_client(self, subscription_id: str) -> ConsumptionClientProtocol:
        """Create a consumption management client."""
        pass

    @abstractmethod
    def create_cost_client(self) -> CostClientProtocol:
        """Create a cost management client."""
        pass


class DefaultAzureClientFactory(AzureClientFactory):
    """Default implementation of Azure client factory using real Azure SDK."""

    def __init__(self, credential=None):
        """
        Initialize the factory with Azure credentials.

        Args:
            credential: Azure credential object (uses DefaultAzureCredential if not provided)
        """
        self.credential = credential or DefaultAzureCredential()
        self.config = get_config()

    def create_compute_client(self, subscription_id: str) -> ComputeManagementClient:
        """Create a real Azure compute management client."""
        return ComputeManagementClient(self.credential, subscription_id)

    def create_network_client(self, subscription_id: str) -> NetworkManagementClient:
        """Create a real Azure network management client."""
        return NetworkManagementClient(self.credential, subscription_id)

    def create_consumption_client(self, subscription_id: str) -> ConsumptionManagementClient:
        """Create a real Azure consumption management client."""
        return ConsumptionManagementClient(self.credential, subscription_id)

    def create_cost_client(self) -> CostManagementClient:
        """Create a real Azure cost management client."""
        return CostManagementClient(self.credential, base_url=self.config.azure_management_url)


class ComputeClientAdapter:
    """Adapter for compute client to provide a consistent interface."""

    def __init__(self, client: ComputeManagementClient):
        """
        Initialize adapter with Azure compute client.

        Args:
            client: Azure ComputeManagementClient instance
        """
        self.client = client

    def list_all_vms(self):
        """List all virtual machines."""
        return self.client.virtual_machines.list_all()

    def get_instance_view(self, resource_group: str, vm_name: str):
        """Get VM instance view."""
        return self.client.virtual_machines.instance_view(resource_group_name=resource_group, vm_name=vm_name)

    def list_disks(self):
        """List all managed disks."""
        return self.client.disks.list()


class NetworkClientAdapter:
    """Adapter for network client to provide a consistent interface."""

    def __init__(self, client: NetworkManagementClient):
        """
        Initialize adapter with Azure network client.

        Args:
            client: Azure NetworkManagementClient instance
        """
        self.client = client

    def list_public_ips(self):
        """List all public IP addresses."""
        return self.client.public_ip_addresses.list_all()


class ConsumptionClientAdapter:
    """Adapter for consumption client to provide a consistent interface."""

    def __init__(self, client: ConsumptionManagementClient):
        """
        Initialize adapter with Azure consumption client.

        Args:
            client: Azure ConsumptionManagementClient instance
        """
        self.client = client

    def list_budgets(self, scope: str):
        """List budgets for a scope."""
        return self.client.budgets.list(scope)

    def get_usage(self, scope: str):
        """Get usage details for a scope."""
        return self.client.usage_details.list(scope)


class CostClientAdapter:
    """Adapter for cost management client to provide a consistent interface."""

    def __init__(self, client: CostManagementClient):
        """
        Initialize adapter with Azure cost management client.

        Args:
            client: Azure CostManagementClient instance
        """
        self.client = client

    def query_usage(self, scope: str, parameters: Any):
        """Query cost usage data."""
        return self.client.query.usage(scope=scope, parameters=parameters)


# Global factory instance
_factory: Optional[AzureClientFactory] = None


def get_client_factory() -> AzureClientFactory:
    """
    Get the global Azure client factory instance.

    Returns:
        AzureClientFactory instance
    """
    global _factory

    if _factory is None:
        _factory = DefaultAzureClientFactory()

    return _factory


def set_client_factory(factory: AzureClientFactory) -> None:
    """
    Set the global Azure client factory instance.

    This is useful for testing with mock factories.

    Args:
        factory: AzureClientFactory instance to use
    """
    global _factory
    _factory = factory
    logger.info("Azure client factory updated")


def reset_client_factory() -> None:
    """Reset the client factory to default."""
    global _factory
    _factory = None
    logger.info("Azure client factory reset")
