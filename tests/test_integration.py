"""Integration tests with mock Azure responses."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import date, datetime, timedelta
from typing import List, Dict, Any

from azure_finops_mcp_server.helpers.azure_client_factory import set_client_factory, reset_client_factory
from azure_finops_mcp_server.helpers.cache_manager import reset_cache
from azure_finops_mcp_server.helpers.retry_handler import reset_retry_handler


class MockAzureResources:
    """Mock Azure resources for testing."""
    
    @staticmethod
    def create_mock_vm(name: str, location: str, status: str = 'running') -> Mock:
        """Create a mock VM object."""
        vm = Mock()
        vm.name = name
        vm.location = location
        vm.id = f"/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/{name}"
        vm.hardware_profile = Mock()
        vm.hardware_profile.vm_size = 'Standard_B2s'
        
        # Create instance view
        instance_view = Mock()
        instance_view.statuses = []
        
        if status == 'deallocated':
            status_obj = Mock()
            status_obj.code = 'PowerState/deallocated'
            instance_view.statuses.append(status_obj)
        elif status == 'running':
            status_obj = Mock()
            status_obj.code = 'PowerState/running'
            instance_view.statuses.append(status_obj)
        
        return vm, instance_view
    
    @staticmethod
    def create_mock_disk(name: str, location: str, size_gb: int, attached: bool = False) -> Mock:
        """Create a mock disk object."""
        disk = Mock()
        disk.name = name
        disk.location = location
        disk.id = f"/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/disks/{name}"
        disk.disk_size_gb = size_gb
        disk.sku = Mock()
        disk.sku.name = 'Standard_LRS'
        disk.managed_by = f"/subscriptions/test-sub/.../vms/vm1" if attached else None
        disk.time_created = datetime.now()
        
        return disk
    
    @staticmethod
    def create_mock_public_ip(name: str, location: str, associated: bool = False) -> Mock:
        """Create a mock public IP object."""
        ip = Mock()
        ip.name = name
        ip.location = location
        ip.id = f"/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/publicIPAddresses/{name}"
        ip.ip_address = f"10.0.0.{name[-1]}" if name[-1].isdigit() else "10.0.0.1"
        ip.sku = Mock()
        ip.sku.name = 'Basic'
        ip.public_ip_allocation_method = 'Static'
        ip.ip_configuration = Mock() if associated else None
        
        return ip
    
    @staticmethod
    def create_mock_budget(name: str, amount: float, current_spend: float) -> Mock:
        """Create a mock budget object."""
        budget = Mock()
        budget.name = name
        budget.amount = amount
        budget.time_grain = 'Monthly'
        budget.category = 'Cost'
        
        budget.time_period = Mock()
        budget.time_period.start_date = datetime(2024, 1, 1)
        budget.time_period.end_date = datetime(2024, 12, 31)
        
        budget.current_spend = Mock()
        budget.current_spend.amount = current_spend
        budget.current_spend.unit = 'USD'
        
        budget.forecast_spend = Mock()
        budget.forecast_spend.amount = current_spend * 1.1  # 10% increase forecast
        budget.forecast_spend.unit = 'USD'
        
        # Add notifications
        budget.notifications = {
            'notification1': Mock(
                threshold=80,
                enabled=True,
                operator='GreaterThan',
                threshold_type='Actual',
                contact_emails=['admin@example.com']
            )
        }
        
        return budget


class TestVMOperationsIntegration:
    """Integration tests for VM operations."""
    
    def setup_method(self):
        """Set up test environment."""
        reset_client_factory()
        reset_cache()
        reset_retry_handler()
    
    def teardown_method(self):
        """Clean up after tests."""
        reset_client_factory()
        reset_cache()
        reset_retry_handler()
    
    @patch('azure_finops_mcp_server.helpers.vm_operations.get_client_factory')
    def test_get_stopped_vms_with_parallel_processing(self, mock_get_factory):
        """Test getting stopped VMs with parallel instance view fetching."""
        from azure_finops_mcp_server.helpers.vm_operations import get_stopped_vms
        
        # Create mock VMs
        vm1, instance1 = MockAzureResources.create_mock_vm('vm1', 'eastus', 'deallocated')
        vm2, instance2 = MockAzureResources.create_mock_vm('vm2', 'eastus', 'running')
        vm3, instance3 = MockAzureResources.create_mock_vm('vm3', 'westus', 'deallocated')
        
        # Set up mock factory and client
        mock_factory = Mock()
        mock_compute_client = Mock()
        
        mock_compute_client.virtual_machines.list_all.return_value = [vm1, vm2, vm3]
        mock_compute_client.virtual_machines.instance_view.side_effect = [
            instance1, instance2, instance3
        ]
        
        mock_factory.create_compute_client.return_value = mock_compute_client
        mock_get_factory.return_value = mock_factory
        
        # Execute
        result, errors = get_stopped_vms(Mock(), 'test-sub', regions=['eastus'])
        
        # Verify
        assert len(result['stopped_vms']) == 1  # Only vm1 is deallocated in eastus
        assert result['stopped_vms'][0]['name'] == 'vm1'
        assert result['statistics']['total_stopped'] == 1
        assert result['statistics']['total_vms_checked'] == 2  # vm1 and vm2 in eastus
        assert errors == {}
    
    @patch('azure_finops_mcp_server.helpers.vm_operations.get_client_factory')
    def test_vm_operations_with_error_handling(self, mock_get_factory):
        """Test VM operations with API errors."""
        from azure_finops_mcp_server.helpers.vm_operations import get_stopped_vms
        from azure.core.exceptions import ServiceRequestError
        
        # Set up mock factory to raise error
        mock_factory = Mock()
        mock_compute_client = Mock()
        mock_compute_client.virtual_machines.list_all.side_effect = ServiceRequestError("API Error")
        
        mock_factory.create_compute_client.return_value = mock_compute_client
        mock_get_factory.return_value = mock_factory
        
        # Execute
        result, errors = get_stopped_vms(Mock(), 'test-sub')
        
        # Verify error handling
        assert result == {'stopped_vms': [], 'statistics': {}}
        assert 'stopped_vms' in errors
        assert 'Failed to get stopped VMs' in errors['stopped_vms']


class TestDiskOperationsIntegration:
    """Integration tests for disk operations."""
    
    @patch('azure_finops_mcp_server.helpers.disk_operations.get_client_factory')
    def test_get_detailed_disk_audit(self, mock_get_factory):
        """Test detailed disk audit with cost calculation."""
        from azure_finops_mcp_server.helpers.disk_operations import get_detailed_disk_audit
        
        # Create mock disks
        disk1 = MockAzureResources.create_mock_disk('disk1', 'eastus', 100, attached=False)
        disk2 = MockAzureResources.create_mock_disk('pvc-disk', 'eastus', 50, attached=False)
        disk3 = MockAzureResources.create_mock_disk('disk3', 'westus', 200, attached=True)
        
        # Set up mock factory and client
        mock_factory = Mock()
        mock_compute_client = Mock()
        mock_compute_client.disks.list.return_value = [disk1, disk2, disk3]
        
        mock_factory.create_compute_client.return_value = mock_compute_client
        mock_get_factory.return_value = mock_factory
        
        # Execute
        result, errors = get_detailed_disk_audit(Mock(), 'test-sub', regions=['eastus'])
        
        # Verify
        assert len(result['orphaned_disks']) == 1  # disk1
        assert len(result['pvc_disks']) == 1  # pvc-disk
        assert result['summary']['total_unattached_disks'] == 2
        assert result['summary']['orphaned_count'] == 1
        assert result['summary']['pvc_count'] == 1
        assert errors == {}


class TestBudgetOperationsIntegration:
    """Integration tests for budget operations."""
    
    @patch('azure_finops_mcp_server.helpers.budget_operations_refactored.get_client_factory')
    def test_get_budget_data_with_alerts(self, mock_get_factory):
        """Test getting budget data with alert generation."""
        from azure_finops_mcp_server.helpers.budget_operations_refactored import get_budget_data
        
        # Create mock budgets
        budget1 = MockAzureResources.create_mock_budget('Budget1', 1000, 950)  # 95% - Critical
        budget2 = MockAzureResources.create_mock_budget('Budget2', 2000, 1000)  # 50% - OK
        budget3 = MockAzureResources.create_mock_budget('Budget3', 500, 600)  # 120% - Exceeded
        
        # Set up mock factory and client
        mock_factory = Mock()
        mock_consumption_client = Mock()
        mock_consumption_client.budgets.list.return_value = [budget1, budget2, budget3]
        
        mock_factory.create_consumption_client.return_value = mock_consumption_client
        mock_get_factory.return_value = mock_factory
        
        # Execute
        result, errors = get_budget_data(Mock(), 'test-sub')
        
        # Verify
        assert len(result['budgets']) == 3
        assert result['summary']['total_budgets'] == 3
        assert result['summary']['budgets_exceeded'] == 1
        assert result['summary']['budgets_critical'] == 1
        assert result['summary']['budgets_ok'] == 1
        
        # Check alerts
        assert len(result['alerts']) >= 2  # At least critical and exceeded alerts
        assert any('exceeded' in alert for alert in result['alerts'])
        assert any('critical' in alert for alert in result['alerts'])
        
        assert errors == {}


class TestParallelProcessingIntegration:
    """Integration tests for parallel subscription processing."""
    
    @patch('azure_finops_mcp_server.helpers.vm_operations.get_client_factory')
    def test_parallel_subscription_processing(self, mock_get_factory):
        """Test processing multiple subscriptions in parallel."""
        from azure_finops_mcp_server.helpers.parallel_processor import ParallelSubscriptionProcessor
        from azure_finops_mcp_server.helpers.vm_operations import get_stopped_vms
        
        # Create mock data for multiple subscriptions
        subscriptions = {
            'sub1': ['Subscription 1'],
            'sub2': ['Subscription 2'],
            'sub3': ['Subscription 3']
        }
        
        # Mock VMs for each subscription
        vm1, instance1 = MockAzureResources.create_mock_vm('vm1', 'eastus', 'deallocated')
        vm2, instance2 = MockAzureResources.create_mock_vm('vm2', 'eastus', 'running')
        
        # Set up mock factory
        mock_factory = Mock()
        mock_compute_client = Mock()
        mock_compute_client.virtual_machines.list_all.return_value = [vm1, vm2]
        mock_compute_client.virtual_machines.instance_view.side_effect = [
            instance1, instance2
        ] * 3  # For 3 subscriptions
        
        mock_factory.create_compute_client.return_value = mock_compute_client
        mock_get_factory.return_value = mock_factory
        
        # Create processor and execute
        processor = ParallelSubscriptionProcessor(max_workers=2)
        
        def process_func(credential, subscription_id, subscription_name, **kwargs):
            result, errors = get_stopped_vms(credential, subscription_id)
            return result
        
        results, errors = processor.process_subscriptions(
            subscriptions=subscriptions,
            process_func=process_func,
            credential=Mock()
        )
        
        # Verify parallel processing
        assert len(results) == 3
        for sub_name in ['Subscription: Subscription 1', 
                        'Subscription: Subscription 2', 
                        'Subscription: Subscription 3']:
            assert sub_name in results
            assert 'stopped_vms' in results[sub_name]


class TestCachingIntegration:
    """Integration tests for caching functionality."""
    
    def test_cache_hit_and_miss(self):
        """Test cache hit and miss scenarios."""
        from azure_finops_mcp_server.helpers.cache_manager import get_cache, reset_cache
        
        reset_cache()
        cache = get_cache()
        
        # Test cache miss
        result = cache.get('test_key')
        assert result is None
        
        # Set value
        cache.set('test_key', {'data': 'test_value'}, ttl=60)
        
        # Test cache hit
        result = cache.get('test_key')
        assert result == {'data': 'test_value'}
        
        # Check stats
        stats = cache.get_stats()
        assert stats['hits'] == 1
        assert stats['misses'] == 1
        assert stats['hit_rate'] == 50.0
    
    @patch('time.time')
    def test_cache_expiration(self, mock_time):
        """Test cache expiration."""
        from azure_finops_mcp_server.helpers.cache_manager import get_cache, reset_cache
        
        reset_cache()
        cache = get_cache()
        
        # Set current time
        mock_time.return_value = 1000
        
        # Set value with 60 second TTL
        cache.set('test_key', 'test_value', ttl=60)
        
        # Move time forward 30 seconds - should still be valid
        mock_time.return_value = 1030
        assert cache.get('test_key') == 'test_value'
        
        # Move time forward 70 seconds - should be expired
        mock_time.return_value = 1070
        assert cache.get('test_key') is None


class TestRetryLogicIntegration:
    """Integration tests for retry logic."""
    
    def test_retry_on_transient_error(self):
        """Test retry logic on transient errors."""
        from azure_finops_mcp_server.helpers.retry_handler import RetryHandler, RetryConfig
        from azure.core.exceptions import ServiceRequestError
        
        # Create handler with fast retry for testing
        config = RetryConfig(max_retries=2, initial_backoff=0.1, jitter=False)
        handler = RetryHandler(config)
        
        # Create function that fails twice then succeeds
        call_count = {'count': 0}
        
        def flaky_function():
            call_count['count'] += 1
            if call_count['count'] < 3:
                raise ServiceRequestError("Temporary failure")
            return "Success"
        
        # Execute with retry
        result = handler.execute_with_retry(flaky_function)
        
        # Verify
        assert result == "Success"
        assert call_count['count'] == 3
        assert handler.stats['total_retries'] == 2
        assert handler.stats['successful_retries'] == 1
    
    def test_no_retry_on_auth_error(self):
        """Test that auth errors are not retried."""
        from azure_finops_mcp_server.helpers.retry_handler import RetryHandler, RetryConfig
        from azure.core.exceptions import ClientAuthenticationError
        
        # Create handler
        config = RetryConfig(max_retries=3, initial_backoff=0.1)
        handler = RetryHandler(config)
        
        # Create function that raises auth error
        call_count = {'count': 0}
        
        def auth_failing_function():
            call_count['count'] += 1
            raise ClientAuthenticationError("Authentication failed")
        
        # Execute and expect immediate failure
        with pytest.raises(ClientAuthenticationError):
            handler.execute_with_retry(auth_failing_function)
        
        # Verify no retries for auth error
        assert call_count['count'] == 1
        assert handler.stats['total_retries'] == 0