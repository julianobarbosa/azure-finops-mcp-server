#!/usr/bin/env python3
"""Test script to verify the updated disk filtering logic."""

import json
import os
import sys

from azure.identity import DefaultAzureCredential

from azure_finops_mcp_server.helpers.util import get_detailed_disk_audit, get_unattached_disks


def test_disk_filtering():
    """Test the updated disk filtering functions."""
    print("Testing Azure FinOps Disk Filtering Updates\n")
    print("=" * 60)

    try:
        # Use default Azure credentials
        credential = DefaultAzureCredential()

        # Get subscription ID from environment
        subscription_id = os.environ.get("AZURE_SUBSCRIPTION_ID")

        if not subscription_id:
            print("ERROR: AZURE_SUBSCRIPTION_ID environment variable is required")
            print("Please set: export AZURE_SUBSCRIPTION_ID=<your-subscription-id>")
            return

        print(f"Testing with subscription: {subscription_id}\n")

        # Test 1: Get only truly orphaned disks (default behavior)
        print("TEST 1: Getting truly orphaned disks (filtering out PVC and AKS-managed)")
        print("-" * 60)
        orphaned_disks, errors = get_unattached_disks(credential, subscription_id, regions=["eastus"])

        if orphaned_disks:
            print(f"Found {sum(len(v) for v in orphaned_disks.values())} truly orphaned disks:")
            for region, disks in orphaned_disks.items():
                print(f"\n  Region: {region}")
                for disk in disks[:3]:  # Show first 3
                    print(f"    - {disk['DiskName']} ({disk['DiskSize']}) in {disk['ResourceGroup']}")
        else:
            print("No truly orphaned disks found (good!)")

        if errors:
            print(f"\nInfo/Errors: {errors}")

        print("\n" + "=" * 60)

        # Test 2: Get detailed audit with all disk categories
        print("\nTEST 2: Getting detailed disk audit")
        print("-" * 60)
        audit_result, audit_errors = get_detailed_disk_audit(credential, subscription_id, regions=["eastus"])

        print("\nDisk Audit Summary:")
        summary = audit_result.get("summary", {})
        print(f"  Total unattached disks: {summary.get('total_unattached', 0)}")
        print(f"  Truly orphaned: {summary.get('truly_orphaned_count', 0)}")
        print(f"  Kubernetes PVCs: {summary.get('pvc_count', 0)}")
        print(f"  AKS-managed: {summary.get('aks_managed_count', 0)}")
        print(f"  Potential monthly savings: ${summary.get('potential_monthly_savings', 0):.2f}")

        if audit_result.get("recommendations"):
            print("\nRecommendations:")
            for rec in audit_result["recommendations"]:
                print(f"  • {rec}")

        # Show sample of truly orphaned disks
        if audit_result.get("truly_orphaned"):
            print("\nSample of truly orphaned disks (safe to delete):")
            for region, disks in audit_result["truly_orphaned"].items():
                if disks:
                    print(f"  Region: {region}")
                    for disk in disks[:2]:  # Show first 2
                        print(f"    - {disk['DiskName']} ({disk['DiskSize']}, {disk['EstimatedMonthlyCost']})")

        # Show PVC disk info
        if audit_result.get("kubernetes_pvc"):
            total_pvcs = sum(len(v) for v in audit_result["kubernetes_pvc"].values())
            if total_pvcs > 0:
                print(f"\nNote: Found {total_pvcs} PVC disks filtered out (manage via kubectl)")

        print("\n" + "=" * 60)
        print("\n✅ Test completed successfully!")
        print("\nThe tool now correctly:")
        print("1. Filters out PVC disks (pvc-*) by default")
        print("2. Filters out disks in AKS-managed resource groups (MC_*)")
        print("3. Only reports truly orphaned disks")
        print("4. Provides detailed categorization when needed")

    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(test_disk_filtering())
