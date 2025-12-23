#!/usr/bin/env python3
"""
Test script for MDE (Microsoft Defender for Endpoint) alert monitoring.
Tests the MDEClient directly using configuration from a database profile.
"""

import sys
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path to import detonatorapi
sys.path.insert(0, str(Path(__file__).parent.parent))

from detonatorapi.edr_cloud.mde_cloud_client import MdeCloudClient
from detonatorapi.database import get_db_direct, Profile

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_section(title: str):
    """Print a section header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def print_json(data, indent=2):
    """Pretty print JSON data"""
    print(json.dumps(data, indent=indent, default=str))


def test_mde_client(profile_name: str = "win10dev"):
    """
    Test the MDEClient with configuration from a database profile.
    
    Configure the following before running:
    1. Set environment variable: export MDE_AZURE_CLIENT_SECRET="your-secret"
    2. Ensure the profile exists in the database with 'mde' configuration in profile.data
    
    Args:
        profile_name: Name of the profile to load from the database
    """
    
    print_section("MDE Client Test Script")
    
    # Load configuration from database
    db = get_db_direct()
    try:
        profile = db.query(Profile).filter(Profile.name == profile_name).first()
        if not profile:
            print(f"❌ Profile '{profile_name}' not found in database!")
            print("\nAvailable profiles:")
            all_profiles = db.query(Profile).all()
            for p in all_profiles:
                has_mde = "✓" if p.data.get("edr_mde") else "✗"
                print(f"  {has_mde} {p.name}")
            return False
        
        # Get MDE config from profile.data["edr_mde"]
        config = profile.data.get("edr_mde")
        if not config:
            print(f"❌ Profile '{profile_name}' has no 'edr_mde' configuration in data field!")
            print(f"\nProfile data keys: {list(profile.data.keys())}")
            return False
        
        # Add hostname/device_id if not in mde config but available elsewhere
        if "hostname" not in config and "hostname" in profile.data.get("edr_mde", {}):
            config["hostname"] = profile.data["edr_mde"]["hostname"]
        if "device_id" not in config and "device_id" in profile.data.get("edr_mde", {}):
            config["device_id"] = profile.data["edr_mde"]["device_id"]
            
    finally:
        db.close()
    
    # Test parameters
    # Go back 70 days to ensure we find some alerts
    days_back = 70
    start_time = datetime.utcnow() - timedelta(days=days_back)
    
    print(f"Profile: {profile_name}")
    print(f"Configuration:")
    print(f"  Tenant ID: {config.get('tenant_id')}")
    print(f"  Client ID: {config.get('client_id')}")
    print(f"  Hostname: {config.get('hostname')}")
    print(f"  Device ID: {config.get('device_id')}")
    print(f"  Start Time: {start_time.isoformat()}Z (last {days_back} days)")
    print()
    
    # Check environment variable
    import os
    if not os.getenv("MDE_AZURE_CLIENT_SECRET"):
        print("ERROR: Environment variable MDE_AZURE_CLIENT_SECRET is not set!")
        print("Please set it with: export MDE_AZURE_CLIENT_SECRET='your-secret'")
        return False
    
    try:
        # Initialize the client
        print_section("Step 1: Initialize MDEClient")
        client = MdeCloudClient(config)
        print("✓ Client initialized successfully")
        
        # Test authentication
        print_section("Step 2: Test Authentication")
        token = client._get_access_token()
        print(f"✓ Access token obtained: {token[:50]}...")
        
        # Fetch alerts
        print_section("Step 3: Fetch Alerts")
        print(f"Querying for alerts on:")
        print(f"  Device ID: {config.get('device_id') or 'N/A'}")
        print(f"  Hostname: {config.get('hostname') or 'N/A'}")
        print(f"  Since: {start_time.isoformat()}Z")
        print()
        
        alerts = client.fetch_alerts(
            device_id=config.get('device_id'),
            hostname=config.get('hostname'),
            start_time=start_time,
            end_time=datetime.utcnow(),
        )
        
        print(f"✓ Found {len(alerts)} alert(s)")
        print()
        
        if alerts:
            print("Alert Summary:")
            for idx, alert in enumerate(alerts, 1):
                alert_id = alert.get("AlertId")
                timestamp = alert.get("Timestamp")
                print(f"  {idx}. Alert ID: {alert_id}")
                print(f"     Timestamp: {timestamp}")
            print()
            
            # Show first alert in detail
            print("First Alert (full data):")
            print_json(alerts[0])
        else:
            print("ℹ No alerts found in the specified time range")
            print("  Try increasing the 'days_back' value or check the device configuration")
                
        print_section("Test Completed Successfully")
        print("✓ All tests passed!")
        print()
        print("Summary:")
        print(f"  - Authenticated successfully")
        print(f"  - Found {len(alerts)} alert(s)")
        
        return True
        
    except ValueError as e:
        print(f"\n❌ Configuration Error: {e}")
        return False
    except RuntimeError as e:
        print(f"\n❌ API Error: {e}")
        return False
    except Exception as e:
        logger.exception("Unexpected error during test")
        print(f"\n❌ Unexpected Error: {e}")
        return False


if __name__ == "__main__":
    print("\nMicrosoft Defender for Endpoint (MDE) Client Test")
    print("=" * 80)
    print()
    print("This script tests the MDE alert monitoring functionality by loading")
    print("configuration from a database profile.")
    print()
    
    # Allow profile name as command line argument
    profile_name = sys.argv[1] if len(sys.argv) > 1 else "win10dev"
    
    success = test_mde_client(profile_name)
    
    if success:
        print("\n✓ Test completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Test failed!")
        print("\nTroubleshooting:")
        print("1. Ensure MDE_AZURE_CLIENT_SECRET environment variable is set")
        print("2. Verify the profile exists and has 'mde' configuration in data field")
        print("3. Check that tenant_id, client_id, and hostname are correct")
        print("4. Confirm the app registration has the required permissions:")
        print("   - ThreatHunting.Read.All")
        print("   - SecurityAlert.Read.All")
        print("   - SecurityIncident.Read.All")
        print("\nUsage: ./mde_log_test.py [profile_name]")
        print("Example: ./mde_log_test.py win10dev")
        sys.exit(1)
