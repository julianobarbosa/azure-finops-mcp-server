"""Retry logic with exponential backoff for Azure API calls."""

import time
import random
import logging
from typing import Callable, Any, Optional, Type, Tuple, List
from functools import wraps
from azure.core.exceptions import (
    ResourceNotFoundError,
    ClientAuthenticationError,
    HttpResponseError,
    ServiceRequestError,
    ResourceExistsError
)

from azure_finops_mcp_server.config import get_config

logger = logging.getLogger(__name__)


class RetryConfig:
    """Configuration for retry behavior."""
    
    def __init__(
            self,
            max_retries: int = 3,
            initial_backoff: float = 1.0,
            max_backoff: float = 60.0,
            backoff_factor: float = 2.0,
            jitter: bool = True
        ):
        """
        Initialize retry configuration.
        
        Args:
            max_retries: Maximum number of retry attempts
            initial_backoff: Initial backoff time in seconds
            max_backoff: Maximum backoff time in seconds
            backoff_factor: Multiplier for exponential backoff
            jitter: Add random jitter to backoff times
        """
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self.max_backoff = max_backoff
        self.backoff_factor = backoff_factor
        self.jitter = jitter
    
    @classmethod
    def from_config(cls) -> 'RetryConfig':
        """Create retry config from application configuration."""
        config = get_config()
        return cls(
            max_retries=config.max_retries,
            backoff_factor=config.retry_backoff_factor
        )


class RetryHandler:
    """Handle retry logic for Azure API calls."""
    
    # Exceptions that should not be retried
    NON_RETRYABLE_EXCEPTIONS = (
        ClientAuthenticationError,  # Auth failures won't be fixed by retry
        ResourceNotFoundError,       # Resource doesn't exist
        ResourceExistsError,         # Resource already exists
    )
    
    # HTTP status codes that should be retried
    RETRYABLE_STATUS_CODES = {
        408,  # Request Timeout
        429,  # Too Many Requests
        500,  # Internal Server Error
        502,  # Bad Gateway
        503,  # Service Unavailable
        504,  # Gateway Timeout
    }
    
    def __init__(self, config: Optional[RetryConfig] = None):
        """
        Initialize retry handler.
        
        Args:
            config: Retry configuration (uses default if not provided)
        """
        self.config = config or RetryConfig.from_config()
        self.stats = {
            'total_retries': 0,
            'successful_retries': 0,
            'failed_operations': 0
        }
    
    def calculate_backoff(self, attempt: int) -> float:
        """
        Calculate backoff time for given attempt.
        
        Args:
            attempt: Attempt number (0-based)
            
        Returns:
            Backoff time in seconds
        """
        backoff = min(
            self.config.initial_backoff * (self.config.backoff_factor ** attempt),
            self.config.max_backoff
        )
        
        if self.config.jitter:
            # Add random jitter (±25%)
            jitter_range = backoff * 0.25
            backoff += random.uniform(-jitter_range, jitter_range)
        
        return max(0, backoff)
    
    def should_retry(self, exception: Exception) -> bool:
        """
        Determine if an exception should trigger a retry.
        
        Args:
            exception: The exception that occurred
            
        Returns:
            True if should retry, False otherwise
        """
        # Check for non-retryable exceptions
        if isinstance(exception, self.NON_RETRYABLE_EXCEPTIONS):
            return False
        
        # Check for HTTP response errors with retryable status codes
        if isinstance(exception, HttpResponseError):
            if hasattr(exception, 'status_code'):
                return exception.status_code in self.RETRYABLE_STATUS_CODES
        
        # Retry on service request errors (network issues, timeouts)
        if isinstance(exception, ServiceRequestError):
            return True
        
        # Check for specific error messages
        error_message = str(exception).lower()
        retryable_messages = [
            'timeout',
            'timed out',
            'connection',
            'temporarily unavailable',
            'throttled',
            'rate limit'
        ]
        
        return any(msg in error_message for msg in retryable_messages)
    
    def execute_with_retry(
            self,
            func: Callable,
            *args,
            **kwargs
        ) -> Any:
        """
        Execute a function with retry logic.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Last exception if all retries fail
        """
        last_exception = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                result = func(*args, **kwargs)
                
                if attempt > 0:
                    self.stats['successful_retries'] += 1
                    logger.info(f"Operation succeeded after {attempt} retry(ies)")
                
                return result
                
            except Exception as e:
                last_exception = e
                
                if attempt < self.config.max_retries and self.should_retry(e):
                    backoff = self.calculate_backoff(attempt)
                    self.stats['total_retries'] += 1
                    
                    logger.warning(
                        f"Operation failed (attempt {attempt + 1}/{self.config.max_retries + 1}): {str(e)}. "
                        f"Retrying in {backoff:.2f} seconds..."
                    )
                    
                    time.sleep(backoff)
                else:
                    # No more retries or non-retryable exception
                    break
        
        self.stats['failed_operations'] += 1
        logger.error(f"Operation failed after {self.config.max_retries} retries: {str(last_exception)}")
        raise last_exception
    
    def get_stats(self) -> dict:
        """Get retry statistics."""
        return {
            'total_retries': self.stats['total_retries'],
            'successful_retries': self.stats['successful_retries'],
            'failed_operations': self.stats['failed_operations'],
            'retry_success_rate': (
                self.stats['successful_retries'] / self.stats['total_retries'] * 100
                if self.stats['total_retries'] > 0 else 0
            )
        }


def with_retry(
        max_retries: Optional[int] = None,
        backoff_factor: Optional[float] = None,
        retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None
    ):
    """
    Decorator to add retry logic to functions.
    
    Args:
        max_retries: Override max retries
        backoff_factor: Override backoff factor
        retryable_exceptions: Additional exceptions to retry on
        
    Returns:
        Decorated function with retry logic
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            config = RetryConfig.from_config()
            
            if max_retries is not None:
                config.max_retries = max_retries
            if backoff_factor is not None:
                config.backoff_factor = backoff_factor
            
            handler = RetryHandler(config)
            
            # Add custom retryable exceptions if provided
            if retryable_exceptions:
                original_should_retry = handler.should_retry
                
                def custom_should_retry(exception):
                    if isinstance(exception, retryable_exceptions):
                        return True
                    return original_should_retry(exception)
                
                handler.should_retry = custom_should_retry
            
            return handler.execute_with_retry(func, *args, **kwargs)
        
        return wrapper
    return decorator


class CircuitBreaker:
    """Circuit breaker pattern for preventing cascading failures."""
    
    def __init__(
            self,
            failure_threshold: int = 5,
            recovery_timeout: float = 60.0,
            expected_exception: Type[Exception] = Exception
        ):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Time to wait before attempting recovery
            expected_exception: Exception type to catch
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'closed'  # closed, open, half-open
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Call function through circuit breaker.
        
        Args:
            func: Function to call
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Exception: If circuit is open or function fails
        """
        if self.state == 'open':
            if self._should_attempt_reset():
                self.state = 'half-open'
            else:
                raise Exception(f"Circuit breaker is open (failures: {self.failure_count})")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
            
        except self.expected_exception as e:
            self._on_failure()
            raise e
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return True
        
        return time.time() - self.last_failure_time >= self.recovery_timeout
    
    def _on_success(self) -> None:
        """Handle successful call."""
        if self.state == 'half-open':
            logger.info("Circuit breaker: Recovered from failure state")
        
        self.failure_count = 0
        self.state = 'closed'
    
    def _on_failure(self) -> None:
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = 'open'
            logger.error(f"Circuit breaker: Opened after {self.failure_count} failures")
        elif self.state == 'half-open':
            self.state = 'open'
            logger.warning("Circuit breaker: Recovery attempt failed, reopening")
    
    def reset(self) -> None:
        """Manually reset the circuit breaker."""
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'closed'
        logger.info("Circuit breaker manually reset")
    
    def get_state(self) -> dict:
        """Get circuit breaker state."""
        return {
            'state': self.state,
            'failure_count': self.failure_count,
            'threshold': self.failure_threshold,
            'last_failure': self.last_failure_time
        }


# Global retry handler
_retry_handler: Optional[RetryHandler] = None


def get_retry_handler() -> RetryHandler:
    """Get global retry handler instance."""
    global _retry_handler
    
    if _retry_handler is None:
        _retry_handler = RetryHandler()
    
    return _retry_handler


def reset_retry_handler() -> None:
    """Reset global retry handler."""
    global _retry_handler
    _retry_handler = None