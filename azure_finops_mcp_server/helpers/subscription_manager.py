"""Azure subscription management utilities.

Security Note: This module uses subprocess to execute Azure CLI commands.
All subprocess calls are made with hardcoded, trusted commands only.
No user input is directly passed to subprocess.run() - only Azure CLI
commands with fixed arguments are executed. The use of check=True and
explicit command lists (not shell=True) provides additional safety.
"""

import json
import logging
import subprocess  # Used only for trusted Azure CLI commands
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from azure.identity import AzureCliCredential, DefaultAzureCredential

logger = logging.getLogger(__name__)

ApiErrors = Dict[str, str]


def get_azure_subscriptions() -> List[Dict[str, str]]:
    """
    Get list of Azure subscriptions available via Azure CLI.
    Similar to AWS profiles but for Azure subscriptions.

    Returns:
        List of subscription dictionaries with id, name, and other metadata
    """
    try:
        # Security: Hardcoded Azure CLI command - no user input injected
        result = subprocess.run(
            ["az", "account", "list", "--output", "json"], capture_output=True, text=True, check=True
        )
        subscriptions = json.loads(result.stdout)
        return subscriptions
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        logger.error(f"Failed to get Azure subscriptions: {str(e)}")
        return []


def profiles_to_use(
    profiles: Optional[List[str]] = None, all_profiles: Optional[bool] = False
) -> Tuple[Dict[str, List[str]], ApiErrors]:
    """
    Filters Azure subscriptions by name/ID, retrieves their details,
    and groups them for processing. Maps AWS profile concept to Azure subscriptions.

    Args:
        profiles: A list of subscription names or IDs to process.
        all_profiles: If True, retrieves all available subscriptions.

    Returns:
        Tuple of:
        - Dictionary where keys are Subscription IDs and values are lists of subscription names
        - Dictionary of errors encountered
    """
    profile_errors: ApiErrors = {}
    subscription_to_names_map: Dict[str, List[str]] = defaultdict(list)

    available_subscriptions = get_azure_subscriptions()

    if not available_subscriptions:
        profile_errors["azure_cli"] = "No Azure subscriptions found. Please run 'az login'"
        return subscription_to_names_map, profile_errors

    # Create lookup dictionaries for fast access
    subscription_by_name = {sub["name"]: sub for sub in available_subscriptions}
    subscription_by_id = {sub["id"]: sub for sub in available_subscriptions}

    if all_profiles:
        # Return all available subscriptions
        for sub in available_subscriptions:
            subscription_to_names_map[sub["id"]].append(sub["name"])
    elif profiles:
        # Filter to specified profiles
        for profile in profiles:
            if profile in subscription_by_name:
                sub = subscription_by_name[profile]
                subscription_to_names_map[sub["id"]].append(sub["name"])
            elif profile in subscription_by_id:
                sub = subscription_by_id[profile]
                subscription_to_names_map[sub["id"]].append(sub["name"])
            else:
                profile_errors[profile] = f"Subscription '{profile}' not found"
    else:
        # Default to current subscription
        try:
            # Security: Hardcoded Azure CLI command - no user input injected
            result = subprocess.run(
                ["az", "account", "show", "--output", "json"], capture_output=True, text=True, check=True
            )
            current_sub = json.loads(result.stdout)
            subscription_to_names_map[current_sub["id"]].append(current_sub["name"])
        except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
            profile_errors["current"] = f"Failed to get current subscription: {str(e)}"

    return subscription_to_names_map, profile_errors


def get_credential():
    """
    Get Azure credential for authentication.
    First tries AzureCliCredential, falls back to DefaultAzureCredential.

    Returns:
        Azure credential object for authentication
    """
    try:
        # Try Azure CLI credential first (most common for local development)
        credential = AzureCliCredential()
        # Test the credential by attempting to get a token
        credential.get_token("https://management.azure.com/.default")
        logger.info("Using Azure CLI credential")
        return credential
    except Exception as e:
        logger.warning(f"Azure CLI credential failed: {str(e)}, falling back to DefaultAzureCredential")
        # Fall back to DefaultAzureCredential which tries multiple methods
        return DefaultAzureCredential()
