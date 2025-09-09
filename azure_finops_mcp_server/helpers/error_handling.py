"""Consistent error handling framework for Azure FinOps MCP Server."""

import logging
from typing import Any, Optional, Dict, Callable
from functools import wraps
from datetime import datetime

logger = logging.getLogger(__name__)

class AzureFinOpsError(Exception):
    """Base exception for Azure FinOps operations."""
    pass

class AzureAuthenticationError(AzureFinOpsError):
    """Authentication-related errors."""
    pass

class AzureAPIError(AzureFinOpsError):
    """Azure API call errors."""
    pass

class AzureResourceNotFoundError(AzureFinOpsError):
    """Resource not found errors."""
    pass

class AzureRateLimitError(AzureFinOpsError):
    """Rate limiting errors."""
    pass

class AzureConfigurationError(AzureFinOpsError):
    """Configuration-related errors."""
    pass

class ErrorHandler:
    """Centralized error handling and logging."""
    
    @staticmethod
    def log_error(
        error: Exception,
        context: str,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log error with context and details.
        
        Args:
            error: The exception that occurred
            context: Context where the error occurred
            details: Additional details about the error
        """
        error_info = {
            "timestamp": datetime.now().isoformat(),
            "context": context,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "details": details or {}
        }
        
        logger.error(f"Error in {context}: {error_info}")
    
    @staticmethod
    def create_error_response(
        error: Exception,
        context: str,
        safe_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a standardized error response.
        
        Args:
            error: The exception that occurred
            context: Context where the error occurred
            safe_message: Safe message to return to user
            
        Returns:
            Standardized error response dictionary
        """
        return {
            "success": False,
            "error": {
                "type": type(error).__name__,
                "message": safe_message or "An error occurred processing your request",
                "context": context,
                "timestamp": datetime.now().isoformat()
            }
        }

def handle_azure_errors(context: str):
    """
    Decorator for consistent Azure error handling.
    
    Args:
        context: Description of the operation being performed
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except AzureAuthenticationError as e:
                ErrorHandler.log_error(e, context, {"operation": "authentication"})
                return ErrorHandler.create_error_response(
                    e, context, 
                    "Authentication failed. Please check your Azure credentials."
                )
            except AzureResourceNotFoundError as e:
                ErrorHandler.log_error(e, context, {"operation": "resource_access"})
                return ErrorHandler.create_error_response(
                    e, context,
                    "The requested resource was not found."
                )
            except AzureRateLimitError as e:
                ErrorHandler.log_error(e, context, {"operation": "api_call"})
                return ErrorHandler.create_error_response(
                    e, context,
                    "Azure API rate limit exceeded. Please try again later."
                )
            except AzureAPIError as e:
                ErrorHandler.log_error(e, context, {"operation": "api_call"})
                return ErrorHandler.create_error_response(
                    e, context,
                    "Azure API error occurred. Please try again."
                )
            except Exception as e:
                ErrorHandler.log_error(e, context, {"operation": "unknown"})
                return ErrorHandler.create_error_response(
                    e, context,
                    "An unexpected error occurred."
                )
        
        return wrapper
    return decorator

def handle_azure_errors_async(context: str):
    """
    Decorator for consistent Azure error handling in async functions.
    
    Args:
        context: Description of the operation being performed
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except AzureAuthenticationError as e:
                ErrorHandler.log_error(e, context, {"operation": "authentication"})
                return ErrorHandler.create_error_response(
                    e, context,
                    "Authentication failed. Please check your Azure credentials."
                )
            except AzureResourceNotFoundError as e:
                ErrorHandler.log_error(e, context, {"operation": "resource_access"})
                return ErrorHandler.create_error_response(
                    e, context,
                    "The requested resource was not found."
                )
            except AzureRateLimitError as e:
                ErrorHandler.log_error(e, context, {"operation": "api_call"})
                return ErrorHandler.create_error_response(
                    e, context,
                    "Azure API rate limit exceeded. Please try again later."
                )
            except AzureAPIError as e:
                ErrorHandler.log_error(e, context, {"operation": "api_call"})
                return ErrorHandler.create_error_response(
                    e, context,
                    "Azure API error occurred. Please try again."
                )
            except Exception as e:
                ErrorHandler.log_error(e, context, {"operation": "unknown"})
                return ErrorHandler.create_error_response(
                    e, context,
                    "An unexpected error occurred."
                )
        
        return wrapper
    return decorator

class RetryHandler:
    """Handle retries for transient failures."""
    
    @staticmethod
    def with_retry(
        func: Callable,
        max_retries: int = 3,
        backoff_factor: float = 2.0,
        retry_on: tuple = (AzureAPIError, AzureRateLimitError)
    ) -> Any:
        """
        Execute function with retry logic.
        
        Args:
            func: Function to execute
            max_retries: Maximum number of retry attempts
            backoff_factor: Exponential backoff factor
            retry_on: Tuple of exceptions to retry on
            
        Returns:
            Function result or raises exception after max retries
        """
        import time
        
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                return func()
            except retry_on as e:
                last_exception = e
                if attempt < max_retries - 1:
                    wait_time = backoff_factor ** attempt
                    logger.warning(
                        f"Retry {attempt + 1}/{max_retries} after {wait_time}s: {str(e)}"
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(f"Max retries ({max_retries}) exceeded: {str(e)}")
        
        if last_exception:
            raise last_exception

def validate_azure_response(response: Any, operation: str) -> Any:
    """
    Validate Azure API response and raise appropriate errors.
    
    Args:
        response: Azure API response
        operation: Description of the operation
        
    Returns:
        Validated response
        
    Raises:
        Appropriate AzureFinOpsError subclass
    """
    if response is None:
        raise AzureAPIError(f"Null response from Azure API for {operation}")
    
    # Check for common error patterns in Azure responses
    if hasattr(response, 'status_code'):
        if response.status_code == 401:
            raise AzureAuthenticationError(f"Authentication failed for {operation}")
        elif response.status_code == 404:
            raise AzureResourceNotFoundError(f"Resource not found for {operation}")
        elif response.status_code == 429:
            raise AzureRateLimitError(f"Rate limit exceeded for {operation}")
        elif response.status_code >= 500:
            raise AzureAPIError(f"Azure service error for {operation}: {response.status_code}")
    
    return response