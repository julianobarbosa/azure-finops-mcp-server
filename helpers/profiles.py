import boto3
from typing import List, Optional, Any, Dict, Tuple
from collections import defaultdict
from boto3.session import Session

ApiErrors = Dict[str, str]

def profiles_to_use(
        profiles: List[str]
    )-> Tuple[Dict[str, List[str]], ApiErrors]:
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

    profile_errors: ApiErrors =  {}
    

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
            

def get_accessible_regions(profile: str) -> Tuple[List[str], ApiErrors]:
    """
    Retrieves the list of AWS regions accessible with the given profile.

    Args:
        profile: The AWS CLI profile name to use.

    Returns:
        A list of accessible AWS regions for the specified profile.
    """
    region_errors: ApiErrors = {}
    try:
        session = boto3.Session(profile_name=profile)
        accessible_regions =  session.get_available_regions('ec2')
    except Exception as e:
        region_errors[f"Error retrieving regions for profile {profile}"] = str(e)

    return accessible_regions, region_errors


def get_stopped_ec2(
        session: Session,
        regions: List[str]
    ) -> Tuple[Dict[Any, Any], ApiErrors]: 

    """
    Retrieves stopped EC2 instances for each region using the provided session.

    Args:
        session: A boto3 Session object with a specific profile.
        regions: A list of AWS region names.

    Returns:
        A tuple containing:
        - A dictionary mapping each region to a list of stopped EC2 instance IDs.
        - A dictionary of errors that occurred while querying regions.
    """

    stopped_ec2 = defaultdict(list)
    stopped_ec2_errors: ApiErrors = {}
    for region in regions:
        try:
            ec2client = session.client("ec2", region_name=region)
            paginator = ec2client.get_paginator("describe_instances")

            for page in paginator.paginate(
                Filters=[
                    {"Name": "instance-state-name", "Values": ["stopped"]}
                     ]
            ):
                for reservation in page["Reservations"]:
                    for instance in reservation["Instances"]:
                        stopped_ec2[region].append({
                            "InstanceID" : instance["InstanceId"],
                            "Instance Type": instance["InstanceType"]
                            })
        except Exception as e:
            stopped_ec2_errors[region] = str(e)

    return dict(stopped_ec2), stopped_ec2_errors


def get_unattached_ebs_volumes(
        session: Session,
        regions: List[str]
) -> Tuple[Dict[Any, Any], ApiErrors]:
    
    """
    Get a list of un-attached EBS volumes for specified regions. 

    Args: boto3 session and a list of AWS regions
    """
    
    available_ebs_volumes = defaultdict(list)
    errors_getting_ebs_volumes: ApiErrors = {}
    
    for region in regions:
        try:
            ebsClient = session.client("ec2", region_name=region)
            paginator = ebsClient.get_paginator("describe_volumes")

            for page in paginator.paginate(
                Filters=[
                    {"Name": "status",
                    "Values": ["available"]
                    }
                ]):
                for volume in page["Volumes"]:
                    available_ebs_volumes[region].append({
                        "VolumeId": volume["VolumeId"],
                        "Volume Type": volume["VolumeType"],
                        "Volume Size": f"{volume["Size"]} GB"
                    })
        except Exception as e:
            errors_getting_ebs_volumes[region] = str(e)

    return dict(available_ebs_volumes), errors_getting_ebs_volumes

def get_unassociated_eips(
        session: Session,
        regions: List[str]
    ) -> Tuple[Dict[str, Any], ApiErrors]:

    """
    Get a list of un-associated EIPs for specified regions. 

    Args: boto3 session and a list of AWS regions
    """

    un_associated_eips = defaultdict(list)
    errors_getting_eips: ApiErrors = {}
    
    for region in regions:
        try:
            eipClient = session.client("ec2", region_name=region)
            response = eipClient.describe_addresses()
            for address in response["Addresses"]:
                if "AssociationId" not in address:
                    un_associated_eips[region].append({
                            "Allocation ID": address["AllocationId"],
                            "Public IP": address["PublicIp"]
                        })
        except Exception as e:
            errors_getting_eips[region] = str(e)

    return dict(un_associated_eips), errors_getting_eips

def get_budget_data(
        session: Session,
        accountId: str,
    ) -> Dict[str, str]:

    """
    Get a list of Budgets for specied AWS Account

    Args: boto3 session and accountId
    """

    budget_data: Dict[str, str] = defaultdict(list)
    budgetClient = session.client('budgets', region_name="us-east-1")
    error_getting_budgets: Dict[str, str] = {}

    try:
        budgetClient = session.client('budgets', region_name="us-east-1")
        response = budgetClient.describe_budgets(AccountId=accountId)

        for budget in response.get("Budgets", []):
            name = budget["BudgetName"]
            limit = float(budget["BudgetLimit"]["Amount"])
            actual = float(budget["CalculatedSpend"]["ActualSpend"]["Amount"])
            forecast = float(budget["CalculatedSpend"].get("ForecastedSpend", {}).get("Amount", 0.0))

            if actual > limit:
                status = "Over Budget"
            elif forecast > limit:
                status = "Forecasted to Exceed"
            else:
                status = "Under Budget"

            budget_data[name] = {
                "Limit": f"{limit:.2f}",
                "Actual Spend": f"{actual:.2f}",
                "Forecasted Spend": f"{forecast:.2f}" if forecast else "N/A",
                "Status": status
            }

    except Exception as e:
        error_getting_budgets["Budget Error"] = str(e)

    return budget_data, error_getting_budgets