"""Parallel processing utilities for Azure FinOps operations."""

from typing import List, Dict, Any, Callable, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from collections import defaultdict
import logging
import time

from azure_finops_mcp_server.config import get_config

logger = logging.getLogger(__name__)


class ParallelSubscriptionProcessor:
    """Process multiple Azure subscriptions in parallel."""
    
    def __init__(self, max_workers: Optional[int] = None):
        """
        Initialize the parallel processor.
        
        Args:
            max_workers: Maximum number of worker threads (uses config default if not specified)
        """
        config = get_config()
        self.max_workers = max_workers or config.max_parallel_workers
        self.results = {}
        self.errors = {}
        
    def process_subscriptions(
            self,
            subscriptions: Dict[str, List[str]],
            process_func: Callable,
            credential: Any,
            **kwargs
        ) -> Tuple[Dict[str, Any], Dict[str, str]]:
        """
        Process multiple subscriptions in parallel.
        
        Args:
            subscriptions: Dictionary mapping subscription IDs to names
            process_func: Function to process each subscription
            credential: Azure credential for authentication
            **kwargs: Additional arguments to pass to process_func
            
        Returns:
            Tuple of (results_dict, errors_dict)
        """
        results = {}
        errors = {}
        
        start_time = time.time()
        total_subs = len(subscriptions)
        
        logger.info(f"Starting parallel processing of {total_subs} subscriptions")
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_sub = {}
            for subscription_id, subscription_names in subscriptions.items():
                primary_name = subscription_names[0]
                future = executor.submit(
                    self._process_single_subscription,
                    subscription_id,
                    primary_name,
                    process_func,
                    credential,
                    **kwargs
                )
                future_to_sub[future] = (subscription_id, primary_name)
            
            # Collect results as they complete
            completed = 0
            for future in as_completed(future_to_sub):
                subscription_id, primary_name = future_to_sub[future]
                completed += 1
                
                try:
                    result = future.result()
                    if result:
                        if 'error' in result:
                            errors[primary_name] = result['error']
                        else:
                            results[f"Subscription: {primary_name}"] = result
                    
                    logger.info(f"Processed {completed}/{total_subs}: {primary_name}")
                    
                except Exception as e:
                    logger.error(f"Failed to process subscription {primary_name}: {str(e)}")
                    errors[primary_name] = f"Processing failed: {str(e)}"
        
        elapsed = time.time() - start_time
        logger.info(f"Completed processing {total_subs} subscriptions in {elapsed:.2f}s")
        
        return results, errors
    
    def _process_single_subscription(
            self,
            subscription_id: str,
            subscription_name: str,
            process_func: Callable,
            credential: Any,
            **kwargs
        ) -> Dict[str, Any]:
        """
        Process a single subscription.
        
        Args:
            subscription_id: Azure subscription ID
            subscription_name: Subscription name for reporting
            process_func: Function to process the subscription
            credential: Azure credential
            **kwargs: Additional arguments for process_func
            
        Returns:
            Processing result dictionary
        """
        try:
            return process_func(
                credential=credential,
                subscription_id=subscription_id,
                subscription_name=subscription_name,
                **kwargs
            )
        except Exception as e:
            logger.error(f"Error processing subscription {subscription_name}: {str(e)}")
            return {'error': str(e)}


class ParallelResourceProcessor:
    """Process multiple Azure resources in parallel."""
    
    def __init__(self, max_workers: Optional[int] = None):
        """
        Initialize the parallel processor.
        
        Args:
            max_workers: Maximum number of worker threads
        """
        config = get_config()
        self.max_workers = max_workers or config.max_parallel_workers
    
    def process_resources_batch(
            self,
            resources: List[Any],
            process_func: Callable,
            batch_size: Optional[int] = None
        ) -> List[Any]:
        """
        Process resources in parallel batches.
        
        Args:
            resources: List of resources to process
            process_func: Function to process each resource
            batch_size: Optional batch size for chunking
            
        Returns:
            List of processed results
        """
        results = []
        
        if batch_size:
            # Process in batches
            batches = [resources[i:i + batch_size] 
                      for i in range(0, len(resources), batch_size)]
            
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = [executor.submit(self._process_batch, batch, process_func) 
                          for batch in batches]
                
                for future in as_completed(futures):
                    try:
                        batch_results = future.result()
                        results.extend(batch_results)
                    except Exception as e:
                        logger.error(f"Batch processing failed: {str(e)}")
        else:
            # Process individually in parallel
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {executor.submit(process_func, resource): resource 
                          for resource in resources}
                
                for future in as_completed(futures):
                    try:
                        result = future.result()
                        if result:
                            results.append(result)
                    except Exception as e:
                        resource = futures[future]
                        logger.error(f"Failed to process resource: {str(e)}")
        
        return results
    
    def _process_batch(self, batch: List[Any], process_func: Callable) -> List[Any]:
        """
        Process a batch of resources.
        
        Args:
            batch: List of resources in the batch
            process_func: Function to process each resource
            
        Returns:
            List of processed results
        """
        results = []
        for resource in batch:
            try:
                result = process_func(resource)
                if result:
                    results.append(result)
            except Exception as e:
                logger.error(f"Failed to process resource in batch: {str(e)}")
        return results


def aggregate_parallel_results(
        results: Dict[str, Any],
        aggregation_key: str = 'total_cost'
    ) -> Dict[str, Any]:
    """
    Aggregate results from parallel processing.
    
    Args:
        results: Dictionary of results from parallel processing
        aggregation_key: Key to aggregate on
        
    Returns:
        Aggregated results dictionary
    """
    aggregated = {
        'total_subscriptions': len(results),
        'successful': 0,
        'failed': 0,
        'total_value': 0,
        'by_subscription': {}
    }
    
    for subscription, data in results.items():
        if 'error' in data or 'status' in data and data['status'] == 'error':
            aggregated['failed'] += 1
        else:
            aggregated['successful'] += 1
            if aggregation_key in data:
                aggregated['total_value'] += data[aggregation_key]
            
            aggregated['by_subscription'][subscription] = data
    
    return aggregated


def parallel_cost_aggregation(
        cost_data: Dict[str, Any]
    ) -> Dict[str, Any]:
    """
    Aggregate cost data from multiple subscriptions processed in parallel.
    
    Args:
        cost_data: Dictionary with cost data from multiple subscriptions
        
    Returns:
        Aggregated cost summary
    """
    total_cost = 0
    service_costs = defaultdict(float)
    subscription_costs = {}
    
    for subscription, data in cost_data.items():
        if 'Total Cost' in data:
            sub_cost = data['Total Cost']
            total_cost += sub_cost
            subscription_costs[subscription] = sub_cost
            
            # Aggregate service costs if available
            for service_key in data:
                if 'Cost By' in service_key and isinstance(data[service_key], dict):
                    for service, cost in data[service_key].items():
                        service_costs[service] += cost
    
    return {
        'total_cost': round(total_cost, 2),
        'subscription_costs': subscription_costs,
        'service_costs': dict(sorted(
            service_costs.items(), 
            key=lambda x: x[1], 
            reverse=True
        )),
        'subscription_count': len(subscription_costs)
    }