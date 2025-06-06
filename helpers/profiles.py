import boto3
from typing import List, Optional, Any, Dict, Tuple
from collections import defaultdict

ProfileErrors = Dict[str, str]

def profiles_to_use(
        profiles: List[str]
    )-> Tuple[Dict[str, List[str]], ProfileErrors]:
    """
    Filters a list of AWS profiles, checks if they exist, retrieves their
    AWS Account ID, and groups the profiles by these Account IDs.

    Args:
        profiles: A list of profile names to process.

    Returns:
        A dictionary where keys are AWS Account IDs (str) and
        values are lists of profile names (List[str]) that belong to that account.
        Profiles that don't exist or cause errors during Account ID retrieval are skipped.
    """

    profile_errors: ProfileErrors =  {}
    

    session = boto3.Session()
    available_profiles = session.available_profiles
    account_to_profiles_map: Dict[str, List[str]] = defaultdict(list)
    for profile in profiles:
        if profile in available_profiles:
            try:
                session = boto3.Session(profile_name=profile)
                accountId = session.client('sts').get_caller_identity().get('Account')
                if accountId:
                    account_to_profiles_map[accountId].append(profile)
            except Exception as e:
                profile_errors[f"Error processing profile {profile}"] = str(e)
                continue
        else:
            profile_errors[f"Error processing for profile {profile}"] = f"Profile {profile} does not exist."

    return dict(account_to_profiles_map), profile_errors 
            

RegionErrors = Dict[str, str]

def get_accessible_regions(profile: str) -> Tuple[List[str], RegionErrors]:
    """
    Retrieves the list of AWS regions accessible with the given profile.

    Args:
        profile: The AWS CLI profile name to use.

    Returns:
        A list of accessible AWS regions for the specified profile.
    """
    region_errors: RegionErrors = {}
    try:
        session = boto3.Session(profile_name=profile)
        accessible_regions =  session.get_available_regions('ec2')
    except Exception as e:
        region_errors[f"Error retrieving regions for profile {profile}"] = str(e)

    return accessible_regions, region_errors