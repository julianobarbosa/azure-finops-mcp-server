"""Input validation layer for Azure FinOps MCP Server."""

import logging
import re
from datetime import date, datetime
from functools import wraps
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Exception raised for validation errors."""

    def __init__(self, field: str, message: str):
        """
        Initialize validation error.

        Args:
            field: Field that failed validation
            message: Error message
        """
        self.field = field
        self.message = message
        super().__init__(f"Validation error for '{field}': {message}")


class Validators:
    """Collection of validation functions."""

    @staticmethod
    def validate_subscription_id(subscription_id: str) -> bool:
        """
        Validate Azure subscription ID format.

        Args:
            subscription_id: Subscription ID to validate

        Returns:
            True if valid

        Raises:
            ValidationError: If invalid
        """
        # Azure subscription ID is a GUID
        pattern = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"

        if not subscription_id:
            raise ValidationError("subscription_id", "Subscription ID cannot be empty")

        if not re.match(pattern, subscription_id):
            raise ValidationError("subscription_id", "Invalid subscription ID format (must be GUID)")

        return True

    @staticmethod
    def validate_region(region: str) -> bool:
        """
        Validate Azure region name.

        Args:
            region: Region name to validate

        Returns:
            True if valid

        Raises:
            ValidationError: If invalid
        """
        # Common Azure regions (not exhaustive)
        valid_regions = {
            "eastus",
            "eastus2",
            "westus",
            "westus2",
            "westus3",
            "centralus",
            "northcentralus",
            "southcentralus",
            "westcentralus",
            "northeurope",
            "westeurope",
            "uksouth",
            "ukwest",
            "eastasia",
            "southeastasia",
            "japaneast",
            "japanwest",
            "australiaeast",
            "australiasoutheast",
            "centralindia",
            "canadacentral",
            "canadaeast",
            "brazilsouth",
            "francecentral",
            "germanywestcentral",
            "norwayeast",
            "switzerlandnorth",
            "uaenorth",
            "southafricanorth",
            "koreacentral",
            "koreasouth",
        }

        if not region:
            raise ValidationError("region", "Region cannot be empty")

        if region.lower() not in valid_regions:
            raise ValidationError("region", f"Invalid region '{region}'. Must be a valid Azure region.")

        return True

    @staticmethod
    def validate_date_string(date_str: str, field_name: str = "date") -> date:
        """
        Validate and parse date string.

        Args:
            date_str: Date string in YYYY-MM-DD format
            field_name: Name of field for error messages

        Returns:
            Parsed date object

        Raises:
            ValidationError: If invalid
        """
        if not date_str:
            raise ValidationError(field_name, "Date cannot be empty")

        try:
            parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            return parsed_date
        except ValueError:
            raise ValidationError(field_name, "Invalid date format. Use YYYY-MM-DD")

    @staticmethod
    def validate_date_range(start_date: Union[str, date], end_date: Union[str, date]) -> tuple[date, date]:
        """
        Validate date range.

        Args:
            start_date: Start date (string or date object)
            end_date: End date (string or date object)

        Returns:
            Tuple of (start_date, end_date) as date objects

        Raises:
            ValidationError: If invalid
        """
        # Parse dates if strings
        if isinstance(start_date, str):
            start_date = Validators.validate_date_string(start_date, "start_date")
        if isinstance(end_date, str):
            end_date = Validators.validate_date_string(end_date, "end_date")

        # Check range validity
        if start_date > end_date:
            raise ValidationError("date_range", "Start date cannot be after end date")

        # Check not too far in future
        today = date.today()
        if start_date > today + timedelta(days=365):
            raise ValidationError("start_date", "Start date cannot be more than 1 year in the future")

        return start_date, end_date

    @staticmethod
    def validate_time_range_days(days: int) -> bool:
        """
        Validate time range in days.

        Args:
            days: Number of days

        Returns:
            True if valid

        Raises:
            ValidationError: If invalid
        """
        if not isinstance(days, int):
            raise ValidationError("time_range_days", "Must be an integer")

        if days <= 0:
            raise ValidationError("time_range_days", "Must be positive")

        if days > 365:
            raise ValidationError("time_range_days", "Cannot exceed 365 days")

        return True

    @staticmethod
    def validate_tag_filter(tag: str) -> tuple[str, str]:
        """
        Validate and parse tag filter.

        Args:
            tag: Tag filter in "key=value" format

        Returns:
            Tuple of (key, value)

        Raises:
            ValidationError: If invalid
        """
        if not tag:
            raise ValidationError("tag", "Tag cannot be empty")

        if "=" not in tag:
            raise ValidationError("tag", 'Tag must be in "key=value" format')

        key, value = tag.split("=", 1)

        if not key:
            raise ValidationError("tag", "Tag key cannot be empty")
        if not value:
            raise ValidationError("tag", "Tag value cannot be empty")

        # Azure tag key constraints
        if len(key) > 512:
            raise ValidationError("tag", "Tag key cannot exceed 512 characters")
        if len(value) > 256:
            raise ValidationError("tag", "Tag value cannot exceed 256 characters")

        return key, value

    @staticmethod
    def validate_resource_id(resource_id: str) -> bool:
        """
        Validate Azure resource ID format.

        Args:
            resource_id: Resource ID to validate

        Returns:
            True if valid

        Raises:
            ValidationError: If invalid
        """
        if not resource_id:
            raise ValidationError("resource_id", "Resource ID cannot be empty")

        # Basic Azure resource ID pattern
        pattern = r"^/subscriptions/[^/]+/resourceGroups/[^/]+/providers/[^/]+/.+$"

        if not re.match(pattern, resource_id):
            raise ValidationError("resource_id", "Invalid Azure resource ID format")

        return True

    @staticmethod
    def validate_percentage(value: float, field_name: str = "percentage") -> bool:
        """
        Validate percentage value.

        Args:
            value: Percentage value
            field_name: Field name for error messages

        Returns:
            True if valid

        Raises:
            ValidationError: If invalid
        """
        if not isinstance(value, (int, float)):
            raise ValidationError(field_name, "Must be a number")

        if value < 0:
            raise ValidationError(field_name, "Cannot be negative")

        if value > 100:
            logger.warning(f"Percentage value {value} exceeds 100%")

        return True

    @staticmethod
    def validate_cost_amount(amount: float, field_name: str = "amount") -> bool:
        """
        Validate cost amount.

        Args:
            amount: Cost amount
            field_name: Field name for error messages

        Returns:
            True if valid

        Raises:
            ValidationError: If invalid
        """
        if not isinstance(amount, (int, float)):
            raise ValidationError(field_name, "Must be a number")

        if amount < 0:
            raise ValidationError(field_name, "Cannot be negative")

        if amount > 1000000000:  # $1 billion
            logger.warning(f"Unusually high cost amount: ${amount}")

        return True


def validate_input(validation_rules: Dict[str, Any]):
    """
    Decorator for input validation.

    Args:
        validation_rules: Dictionary mapping parameter names to validation functions

    Returns:
        Decorated function with input validation
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get function signature
            import inspect

            sig = inspect.signature(func)
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()

            # Validate each parameter
            for param_name, validator in validation_rules.items():
                if param_name in bound.arguments:
                    value = bound.arguments[param_name]

                    # Skip None values if optional
                    param = sig.parameters.get(param_name)
                    if value is None and param and param.default is not inspect.Parameter.empty:
                        continue

                    try:
                        if callable(validator):
                            validator(value)
                        else:
                            # Assume it's a type to check
                            if not isinstance(value, validator):
                                raise ValidationError(
                                    param_name, f"Expected type {validator.__name__}, got {type(value).__name__}"
                                )
                    except ValidationError as e:
                        logger.error(f"Validation failed for {func.__name__}: {e}")
                        raise

            return func(*args, **kwargs)

        return wrapper

    return decorator


class InputSanitizer:
    """Sanitize and normalize input values."""

    @staticmethod
    def sanitize_string(value: str, max_length: int = 1000) -> str:
        """
        Sanitize string input.

        Args:
            value: String to sanitize
            max_length: Maximum allowed length

        Returns:
            Sanitized string
        """
        if not value:
            return ""

        # Remove control characters
        value = "".join(char for char in value if ord(char) >= 32 or char == "\n")

        # Trim whitespace
        value = value.strip()

        # Limit length
        if len(value) > max_length:
            value = value[:max_length]
            logger.warning(f"String truncated to {max_length} characters")

        return value

    @staticmethod
    def sanitize_region_list(regions: Optional[List[str]]) -> Optional[List[str]]:
        """
        Sanitize list of regions.

        Args:
            regions: List of region names

        Returns:
            Sanitized region list
        """
        if not regions:
            return None

        sanitized = []
        for region in regions:
            if isinstance(region, str):
                region = region.lower().strip()
                try:
                    Validators.validate_region(region)
                    sanitized.append(region)
                except ValidationError as e:
                    logger.warning(f"Invalid region filtered out: {e}")

        return sanitized if sanitized else None

    @staticmethod
    def sanitize_tag_list(tags: Optional[List[str]]) -> Optional[List[str]]:
        """
        Sanitize list of tags.

        Args:
            tags: List of tag filters

        Returns:
            Sanitized tag list
        """
        if not tags:
            return None

        sanitized = []
        for tag in tags:
            if isinstance(tag, str):
                try:
                    key, value = Validators.validate_tag_filter(tag)
                    sanitized.append(f"{key}={value}")
                except ValidationError as e:
                    logger.warning(f"Invalid tag filtered out: {e}")

        return sanitized if sanitized else None


# Example usage with decorated functions
from datetime import timedelta


@validate_input(
    {
        "subscription_id": Validators.validate_subscription_id,
        "regions": lambda x: all(Validators.validate_region(r) for r in x) if x else True,
        "time_range_days": lambda x: Validators.validate_time_range_days(x) if x is not None else True,
    }
)
def example_validated_function(
    subscription_id: str, regions: Optional[List[str]] = None, time_range_days: Optional[int] = None
) -> Dict[str, Any]:
    """Example function with input validation."""
    return {"subscription_id": subscription_id, "regions": regions, "time_range_days": time_range_days}
