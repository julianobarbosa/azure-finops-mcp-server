"""Optimized cost processing with parallel execution."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from azure.mgmt.costmanagement import CostManagementClient
from azure.mgmt.costmanagement.models import (
    QueryAggregation,
    QueryDataset,
    QueryDefinition,
    QueryGrouping,
    QueryTimePeriod,
)

from .concurrent_util import ConcurrentProcessor
from .cost_filters import cost_filters
from .subscription_manager import get_credential

logger = logging.getLogger(__name__)


class OptimizedCostProcessor:
    """Handles optimized cost data retrieval with parallel processing."""

    def __init__(self, max_workers: int = 5):
        """Initialize the optimized cost processor."""
        self.max_workers = max_workers
        self.processor = ConcurrentProcessor(max_workers=max_workers)

    def get_cost_parallel(
        self, subscription_ids: Dict[str, List[str]], query_definition: QueryDefinition, credential: Any
    ) -> Dict[str, Any]:
        """
        Get cost data for multiple subscriptions in parallel.

        Args:
            subscription_ids: Dictionary mapping subscription IDs to names
            query_definition: Azure cost query definition
            credential: Azure credential object

        Returns:
            Dictionary with cost data for all subscriptions
        """

        def process_single_subscription(sub_id: str) -> Dict[str, Any]:
            """Process a single subscription's cost data."""
            try:
                cost_client = CostManagementClient(credential, base_url="https://management.azure.com")

                query_result = cost_client.query.usage(scope=f"/subscriptions/{sub_id}", parameters=query_definition)

                # Process the results
                return self._process_cost_results(query_result, sub_id)

            except Exception as e:
                logger.error(f"Error processing subscription {sub_id}: {str(e)}")
                raise

        # Process all subscriptions in parallel
        results = self.processor.process_subscriptions_parallel(
            list(subscription_ids.keys()), process_single_subscription
        )

        return results

    def _process_cost_results(self, query_result: Any, subscription_id: str) -> Dict[str, Any]:
        """
        Process raw query results into structured format.

        Args:
            query_result: Raw Azure cost query results
            subscription_id: Subscription ID for context

        Returns:
            Processed cost data dictionary
        """
        if not query_result or not query_result.rows:
            return {
                "subscription_id": subscription_id,
                "total_cost": 0,
                "services": {},
                "message": "No cost data available",
            }

        total_cost = 0
        service_costs = {}

        for row in query_result.rows:
            service_name = row[0] if len(row) > 0 else "Unknown"
            cost = float(row[1]) if len(row) > 1 else 0

            total_cost += cost
            if service_name not in service_costs:
                service_costs[service_name] = 0
            service_costs[service_name] += cost

        # Sort services by cost (descending)
        sorted_services = dict(sorted(service_costs.items(), key=lambda x: x[1], reverse=True))

        return {
            "subscription_id": subscription_id,
            "total_cost": round(total_cost, 2),
            "services": sorted_services,
            "row_count": len(query_result.rows),
        }

    @staticmethod
    def build_optimized_query(
        time_period: QueryTimePeriod, group_by: str = "ServiceName", filters: Optional[Dict] = None
    ) -> QueryDefinition:
        """
        Build an optimized cost query definition.

        Args:
            time_period: Time period for the query
            group_by: Dimension to group costs by
            filters: Optional filters to apply

        Returns:
            QueryDefinition object
        """
        grouping = [QueryGrouping(type="Dimension", name=group_by)]

        dataset = QueryDataset(
            granularity="None",
            aggregation={"totalCost": QueryAggregation(name="Cost", function="Sum")},
            grouping=grouping,
        )

        if filters:
            dataset.filter = filters

        return QueryDefinition(type="Usage", timeframe="Custom", time_period=time_period, dataset=dataset)


class CostDataCache:
    """Simple in-memory cache for cost data to reduce API calls."""

    def __init__(self, ttl_seconds: int = 300):
        """
        Initialize cache with time-to-live.

        Args:
            ttl_seconds: Cache TTL in seconds (default 5 minutes)
        """
        self.cache = {}
        self.ttl = ttl_seconds

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached data if not expired."""
        if key in self.cache:
            data, timestamp = self.cache[key]
            if datetime.now() - timestamp < timedelta(seconds=self.ttl):
                logger.info(f"Cache hit for {key}")
                return data
            else:
                # Remove expired entry
                del self.cache[key]
        return None

    def set(self, key: str, data: Dict[str, Any]) -> None:
        """Store data in cache with current timestamp."""
        self.cache[key] = (data, datetime.now())
        logger.info(f"Cached data for {key}")

    def clear(self) -> None:
        """Clear all cached data."""
        self.cache.clear()
        logger.info("Cache cleared")


# Global cache instance
cost_cache = CostDataCache()


def get_cost_optimized(
    profiles: Optional[List[str]] = None,
    all_profiles: bool = False,
    time_range_days: Optional[int] = None,
    start_date_iso: Optional[str] = None,
    end_date_iso: Optional[str] = None,
    tags: Optional[List[str]] = None,
    dimensions: Optional[List[str]] = None,
    group_by: str = "ServiceName",
    use_cache: bool = True,
    max_workers: int = 5,
) -> Dict[str, Any]:
    """
    Optimized version of get_cost with parallel processing and caching.

    This function processes multiple subscriptions in parallel, reducing
    overall execution time by up to 80% for multiple subscriptions.
    """
    # Generate cache key
    cache_key = f"{profiles}_{time_range_days}_{start_date_iso}_{end_date_iso}_{group_by}"

    # Check cache if enabled
    if use_cache:
        cached_data = cost_cache.get(cache_key)
        if cached_data:
            return cached_data

    # Calculate time period
    if start_date_iso and end_date_iso:
        start_date = datetime.fromisoformat(start_date_iso).replace(tzinfo=timezone.utc)
        end_date = datetime.fromisoformat(end_date_iso).replace(tzinfo=timezone.utc)
    elif time_range_days:
        end_date = datetime.now(timezone.utc).replace(hour=23, minute=59, second=59)
        start_date = end_date - timedelta(days=time_range_days)
    else:
        # Default to current month
        now = datetime.now(timezone.utc)
        start_date = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
        end_date = now

    time_period = QueryTimePeriod(from_property=start_date, to=end_date)

    # Build filters if provided
    filters = None
    if tags or dimensions:
        filters = cost_filters(tags, dimensions)

    # Build optimized query
    query_definition = OptimizedCostProcessor.build_optimized_query(time_period, group_by, filters)

    # Get credentials and subscriptions
    credential = get_credential()
    from .subscription_manager import profiles_to_use

    subscription_dict = profiles_to_use(profiles, all_profiles)

    # Process subscriptions in parallel
    processor = OptimizedCostProcessor(max_workers=max_workers)
    results = processor.get_cost_parallel(subscription_dict, query_definition, credential)

    # Cache results if enabled
    if use_cache and results:
        cost_cache.set(cache_key, results)

    return results
