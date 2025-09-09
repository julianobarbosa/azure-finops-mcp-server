"""Concurrent utilities for parallel processing of Azure subscriptions."""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ConcurrentProcessor:
    """Handles concurrent processing of multiple Azure subscriptions."""

    def __init__(self, max_workers: int = 5, timeout_per_task: int = 30):
        """
        Initialize the concurrent processor.

        Args:
            max_workers: Maximum number of parallel workers
            timeout_per_task: Timeout in seconds for each subscription task
        """
        self.max_workers = max_workers
        self.timeout_per_task = timeout_per_task

    def process_subscriptions_parallel(
        self, subscription_ids: List[str], process_func: Callable, *args, **kwargs
    ) -> Dict[str, Any]:
        """
        Process multiple subscriptions in parallel.

        Args:
            subscription_ids: List of subscription IDs to process
            process_func: Function to call for each subscription
            *args: Additional arguments for process_func
            **kwargs: Additional keyword arguments for process_func

        Returns:
            Dictionary mapping subscription_id to results or errors
        """
        results = {}
        errors = {}

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_sub = {
                executor.submit(self._process_with_timeout, process_func, sub_id, *args, **kwargs): sub_id
                for sub_id in subscription_ids
            }

            # Collect results as they complete
            for future in as_completed(future_to_sub):
                sub_id = future_to_sub[future]
                try:
                    result = future.result(timeout=self.timeout_per_task)
                    if result is not None:
                        results[sub_id] = result
                    logger.info(f"Successfully processed subscription: {sub_id}")
                except Exception as e:
                    error_msg = f"Failed to process subscription {sub_id}: {str(e)}"
                    logger.error(error_msg)
                    errors[sub_id] = error_msg

        return {
            "results": results,
            "errors": errors,
            "summary": {
                "total": len(subscription_ids),
                "successful": len(results),
                "failed": len(errors),
                "processing_time": datetime.now().isoformat(),
            },
        }

    def _process_with_timeout(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a function with timeout protection.

        Args:
            func: Function to execute
            *args: Arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            Function result or raises TimeoutError
        """
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in concurrent processing: {str(e)}")
            raise


async def process_subscriptions_async(
    subscription_ids: List[str], async_process_func: Callable, max_concurrent: int = 5, **kwargs
) -> Dict[str, Any]:
    """
    Process subscriptions using asyncio for better performance.

    Args:
        subscription_ids: List of subscription IDs
        async_process_func: Async function to process each subscription
        max_concurrent: Maximum concurrent operations
        **kwargs: Additional arguments for the process function

    Returns:
        Dictionary with results and errors
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    async def process_with_semaphore(sub_id):
        async with semaphore:
            try:
                return sub_id, await async_process_func(sub_id, **kwargs)
            except Exception as e:
                logger.error(f"Error processing {sub_id}: {str(e)}")
                return sub_id, {"error": str(e)}

    tasks = [process_with_semaphore(sub_id) for sub_id in subscription_ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    successful = {}
    errors = {}

    for result in results:
        if isinstance(result, Exception):
            errors["unknown"] = str(result)
        elif isinstance(result, tuple):
            sub_id, data = result
            if isinstance(data, dict) and "error" in data:
                errors[sub_id] = data["error"]
            else:
                successful[sub_id] = data

    return {
        "results": successful,
        "errors": errors,
        "summary": {"total": len(subscription_ids), "successful": len(successful), "failed": len(errors)},
    }


def batch_process_with_retry(
    items: List[Any], process_func: Callable, batch_size: int = 10, max_retries: int = 3, retry_delay: int = 1
) -> Tuple[List[Any], List[Any]]:
    """
    Process items in batches with retry logic.

    Args:
        items: List of items to process
        process_func: Function to process each item
        batch_size: Size of each batch
        max_retries: Maximum retry attempts
        retry_delay: Delay between retries in seconds

    Returns:
        Tuple of (successful_results, failed_items)
    """
    import time

    successful = []
    failed = []

    for i in range(0, len(items), batch_size):
        batch = items[i : i + batch_size]

        for item in batch:
            retry_count = 0
            while retry_count < max_retries:
                try:
                    result = process_func(item)
                    successful.append(result)
                    break
                except Exception as e:
                    retry_count += 1
                    if retry_count >= max_retries:
                        logger.error(f"Failed to process {item} after {max_retries} attempts: {str(e)}")
                        failed.append(item)
                    else:
                        logger.warning(f"Retry {retry_count}/{max_retries} for {item}")
                        time.sleep(retry_delay * retry_count)

    return successful, failed
