"""Configuration management for Azure FinOps MCP Server."""

import os
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import json
import logging

logger = logging.getLogger(__name__)

@dataclass
class AzureFinOpsConfig:
    """Configuration settings for Azure FinOps MCP Server."""
    
    # Azure settings
    subscription_id: Optional[str] = None
    subscription_ids: Optional[List[str]] = None
    resource_group_patterns: Optional[List[str]] = None
    default_regions: Optional[List[str]] = None
    
    # Performance settings
    max_parallel_workers: int = 5
    request_timeout: int = 30
    cache_ttl_seconds: int = 300
    enable_caching: bool = True
    
    # API settings
    azure_management_url: str = "https://management.azure.com"
    api_version: str = "2023-03-01"
    
    # Retry settings
    max_retries: int = 3
    retry_backoff_factor: float = 2.0
    
    # Logging settings
    log_level: str = "INFO"
    enable_detailed_logging: bool = False
    
    @classmethod
    def from_environment(cls) -> 'AzureFinOpsConfig':
        """
        Load configuration from environment variables.
        
        Environment variables:
        - AZURE_SUBSCRIPTION_ID: Primary subscription ID
        - AZURE_SUBSCRIPTION_IDS: Comma-separated list of subscription IDs
        - AZURE_RESOURCE_GROUP_PATTERNS: Comma-separated patterns
        - AZURE_DEFAULT_REGIONS: Comma-separated list of regions
        - AZURE_MAX_WORKERS: Maximum parallel workers (default: 5)
        - AZURE_REQUEST_TIMEOUT: Request timeout in seconds (default: 30)
        - AZURE_CACHE_TTL: Cache TTL in seconds (default: 300)
        - AZURE_ENABLE_CACHE: Enable caching (default: true)
        - AZURE_MANAGEMENT_URL: Azure management endpoint
        - AZURE_MAX_RETRIES: Maximum retry attempts (default: 3)
        - AZURE_LOG_LEVEL: Logging level (default: INFO)
        """
        config = cls()
        
        # Azure settings
        config.subscription_id = os.environ.get('AZURE_SUBSCRIPTION_ID')
        
        subscription_ids_str = os.environ.get('AZURE_SUBSCRIPTION_IDS')
        if subscription_ids_str:
            config.subscription_ids = [
                sid.strip() for sid in subscription_ids_str.split(',')
            ]
        
        rg_patterns_str = os.environ.get('AZURE_RESOURCE_GROUP_PATTERNS')
        if rg_patterns_str:
            config.resource_group_patterns = [
                pattern.strip() for pattern in rg_patterns_str.split(',')
            ]
        
        regions_str = os.environ.get('AZURE_DEFAULT_REGIONS')
        if regions_str:
            config.default_regions = [
                region.strip() for region in regions_str.split(',')
            ]
        
        # Performance settings
        config.max_parallel_workers = int(
            os.environ.get('AZURE_MAX_WORKERS', '5')
        )
        config.request_timeout = int(
            os.environ.get('AZURE_REQUEST_TIMEOUT', '30')
        )
        config.cache_ttl_seconds = int(
            os.environ.get('AZURE_CACHE_TTL', '300')
        )
        config.enable_caching = os.environ.get(
            'AZURE_ENABLE_CACHE', 'true'
        ).lower() == 'true'
        
        # API settings
        config.azure_management_url = os.environ.get(
            'AZURE_MANAGEMENT_URL',
            'https://management.azure.com'
        )
        
        # Retry settings
        config.max_retries = int(
            os.environ.get('AZURE_MAX_RETRIES', '3')
        )
        
        # Logging settings
        config.log_level = os.environ.get('AZURE_LOG_LEVEL', 'INFO')
        config.enable_detailed_logging = os.environ.get(
            'AZURE_DETAILED_LOGGING', 'false'
        ).lower() == 'true'
        
        return config
    
    @classmethod
    def from_file(cls, config_file: str) -> 'AzureFinOpsConfig':
        """
        Load configuration from a JSON file.
        
        Args:
            config_file: Path to configuration file
            
        Returns:
            AzureFinOpsConfig instance
        """
        with open(config_file, 'r') as f:
            config_data = json.load(f)
        
        return cls(**config_data)
    
    def validate(self) -> List[str]:
        """
        Validate configuration settings.
        
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Check for at least one subscription
        if not self.subscription_id and not self.subscription_ids:
            errors.append(
                "No Azure subscription configured. Set AZURE_SUBSCRIPTION_ID or AZURE_SUBSCRIPTION_IDS"
            )
        
        # Validate performance settings
        if self.max_parallel_workers < 1:
            errors.append("max_parallel_workers must be at least 1")
        
        if self.request_timeout < 1:
            errors.append("request_timeout must be at least 1 second")
        
        if self.cache_ttl_seconds < 0:
            errors.append("cache_ttl_seconds cannot be negative")
        
        if self.max_retries < 0:
            errors.append("max_retries cannot be negative")
        
        # Validate URL
        if not self.azure_management_url.startswith('https://'):
            errors.append("azure_management_url must use HTTPS")
        
        return errors
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "subscription_id": self.subscription_id,
            "subscription_ids": self.subscription_ids,
            "resource_group_patterns": self.resource_group_patterns,
            "default_regions": self.default_regions,
            "max_parallel_workers": self.max_parallel_workers,
            "request_timeout": self.request_timeout,
            "cache_ttl_seconds": self.cache_ttl_seconds,
            "enable_caching": self.enable_caching,
            "azure_management_url": self.azure_management_url,
            "api_version": self.api_version,
            "max_retries": self.max_retries,
            "retry_backoff_factor": self.retry_backoff_factor,
            "log_level": self.log_level,
            "enable_detailed_logging": self.enable_detailed_logging
        }

# Global configuration instance
_config: Optional[AzureFinOpsConfig] = None

def get_config() -> AzureFinOpsConfig:
    """
    Get the global configuration instance.
    
    Returns:
        AzureFinOpsConfig instance
    """
    global _config
    
    if _config is None:
        _config = AzureFinOpsConfig.from_environment()
        
        # Validate configuration
        errors = _config.validate()
        if errors:
            logger.warning(f"Configuration validation warnings: {errors}")
    
    return _config

def set_config(config: AzureFinOpsConfig) -> None:
    """
    Set the global configuration instance.
    
    Args:
        config: AzureFinOpsConfig instance to use
    """
    global _config
    
    errors = config.validate()
    if errors:
        raise ValueError(f"Invalid configuration: {errors}")
    
    _config = config
    logger.info("Configuration updated")

def reset_config() -> None:
    """Reset configuration to reload from environment."""
    global _config
    _config = None
    logger.info("Configuration reset")