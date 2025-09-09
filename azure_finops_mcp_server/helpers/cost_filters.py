"""Cost filtering utilities for Azure FinOps."""

import logging
from typing import Any, Dict, List, Optional

from azure.mgmt.costmanagement.models import QueryComparisonExpression, QueryFilter

logger = logging.getLogger(__name__)


def cost_filters(tags: Optional[List[str]] = None, dimensions: Optional[List[str]] = None) -> Optional[QueryFilter]:
    """
    Create cost query filters based on tags and dimensions.

    Args:
        tags: List of tag filters in "key=value" format
        dimensions: List of dimension filters in "key=value" format

    Returns:
        QueryFilter object or None if no filters
    """
    filters = []

    # Process tag filters
    if tags:
        for tag in tags:
            if "=" in tag:
                key, value = tag.split("=", 1)
                tag_filter = QueryFilter(tags=QueryComparisonExpression(name=key, operator="In", values=[value]))
                filters.append(tag_filter)
            else:
                logger.warning(f"Invalid tag filter format: {tag}. Expected 'key=value'")

    # Process dimension filters
    if dimensions:
        for dimension in dimensions:
            if "=" in dimension:
                key, value = dimension.split("=", 1)

                # Map common dimension names
                dimension_map = {
                    "ResourceLocation": "ResourceLocation",
                    "Location": "ResourceLocation",
                    "ResourceGroup": "ResourceGroupName",
                    "ResourceGroupName": "ResourceGroupName",
                    "Service": "ServiceName",
                    "ServiceName": "ServiceName",
                    "ResourceType": "ResourceType",
                    "Meter": "MeterName",
                    "MeterName": "MeterName",
                }

                mapped_key = dimension_map.get(key, key)

                dimension_filter = QueryFilter(
                    dimensions=QueryComparisonExpression(name=mapped_key, operator="In", values=[value])
                )
                filters.append(dimension_filter)
            else:
                logger.warning(f"Invalid dimension filter format: {dimension}. Expected 'key=value'")

    # Combine filters if multiple exist
    if len(filters) == 0:
        return None
    elif len(filters) == 1:
        return filters[0]
    else:
        # For multiple filters, Azure Cost Management API requires combining with AND logic
        # This is a simplified implementation - full implementation would need proper filter combining
        return filters[0]  # Return first filter for now


def parse_filter_string(filter_string: str) -> Dict[str, List[str]]:
    """
    Parse a filter string into tags and dimensions.

    Args:
        filter_string: String containing filters like "tag:env=prod,dim:location=eastus"

    Returns:
        Dictionary with 'tags' and 'dimensions' lists
    """
    tags = []
    dimensions = []

    if not filter_string:
        return {"tags": tags, "dimensions": dimensions}

    parts = filter_string.split(",")
    for part in parts:
        part = part.strip()
        if part.startswith("tag:"):
            tags.append(part[4:])  # Remove 'tag:' prefix
        elif part.startswith("dim:"):
            dimensions.append(part[4:])  # Remove 'dim:' prefix
        elif "=" in part:
            # Default to dimension if no prefix
            dimensions.append(part)

    return {"tags": tags, "dimensions": dimensions}


def validate_filters(tags: Optional[List[str]] = None, dimensions: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Validate filter formats and return validation results.

    Args:
        tags: List of tag filters
        dimensions: List of dimension filters

    Returns:
        Dictionary with validation results
    """
    validation = {"valid": True, "errors": [], "warnings": []}

    # Validate tags
    if tags:
        for tag in tags:
            if "=" not in tag:
                validation["errors"].append(f"Invalid tag format: '{tag}'. Expected 'key=value'")
                validation["valid"] = False
            elif tag.count("=") > 1:
                validation["warnings"].append(f"Tag '{tag}' contains multiple '=' signs")

    # Validate dimensions
    valid_dimensions = {
        "ResourceLocation",
        "Location",
        "ResourceGroup",
        "ResourceGroupName",
        "Service",
        "ServiceName",
        "ResourceType",
        "Meter",
        "MeterName",
        "SubscriptionId",
        "SubscriptionName",
        "ResourceId",
    }

    if dimensions:
        for dimension in dimensions:
            if "=" not in dimension:
                validation["errors"].append(f"Invalid dimension format: '{dimension}'. Expected 'key=value'")
                validation["valid"] = False
            else:
                key = dimension.split("=", 1)[0]
                if key not in valid_dimensions:
                    validation["warnings"].append(
                        f"Dimension '{key}' may not be valid. Valid dimensions: {', '.join(valid_dimensions)}"
                    )

    return validation


def build_complex_filter(filter_groups: List[Dict[str, Any]]) -> Optional[QueryFilter]:
    """
    Build complex filters with AND/OR logic.

    Args:
        filter_groups: List of filter group dictionaries

    Returns:
        Complex QueryFilter object or None
    """
    # This would implement complex filter logic for advanced scenarios
    # Placeholder for now - would need full implementation based on requirements
    logger.info("Building complex filter from groups")

    if not filter_groups:
        return None

    # For now, return simple filter from first group
    first_group = filter_groups[0]
    return cost_filters(tags=first_group.get("tags"), dimensions=first_group.get("dimensions"))
