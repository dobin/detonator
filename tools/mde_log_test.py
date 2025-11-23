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

from detonatorapi.edr_cloud.mde_client import MDEClient
from detonatorapi.database import get_db, Profile

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
    db = get_db()
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
        client = MDEClient(config)
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
        
        alerts, server_time = client.fetch_alerts(
            device_id=config.get('device_id'),
            hostname=config.get('hostname'),
            start_time=start_time
        )
        
        print(f"✓ Found {len(alerts)} alert(s)")
        if server_time:
            print(f"  MDE Server Time: {server_time}")
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
        
        # Fetch alert evidence if we have alerts
        if alerts:
            print_section("Step 4: Fetch Alert Evidence")
            alert_ids = [str(alert.get("AlertId")) for alert in alerts if alert.get("AlertId")]
            
            if alert_ids:
                print(f"Fetching evidence for {len(alert_ids)} alert(s)...")
                print(f"Alert IDs: {', '.join(str(aid) for aid in alert_ids[:5])}" + 
                      (f" ... and {len(alert_ids) - 5} more" if len(alert_ids) > 5 else ""))
                print()
                
                evidence_rows = client.fetch_alert_evidence(
                    alert_ids=alert_ids,
                    start_time=start_time,
                    chunk_size=20
                )
                
                print(f"✓ Found {len(evidence_rows)} evidence row(s)")
                print()
                
                if evidence_rows:
                    # Group evidence by alert
                    evidence_by_alert = {}
                    for row in evidence_rows:
                        alert_id = row.get("AlertId")
                        if alert_id:
                            evidence_by_alert.setdefault(alert_id, []).append(row)
                    
                    print(f"Evidence grouped by alert:")
                    for alert_id, evidence_list in evidence_by_alert.items():
                        print(f"  Alert {alert_id}: {len(evidence_list)} evidence item(s)")
                    print()
                    
                    # Show first evidence item in detail
                    print("First Evidence Item (full data):")
                    print_json(evidence_rows[0])
                    print()
                    
                    # Show evidence statistics
                    print("Evidence Statistics:")
                    entity_types = {}
                    evidence_roles = {}
                    for row in evidence_rows:
                        entity_type = row.get("EntityType", "Unknown")
                        entity_types[entity_type] = entity_types.get(entity_type, 0) + 1
                        
                        evidence_role = row.get("EvidenceRole", "Unknown")
                        evidence_roles[evidence_role] = evidence_roles.get(evidence_role, 0) + 1
                    
                    print("  Entity Types:")
                    for entity_type, count in sorted(entity_types.items()):
                        print(f"    {entity_type}: {count}")
                    
                    print("  Evidence Roles:")
                    for role, count in sorted(evidence_roles.items()):
                        print(f"    {role}: {count}")
                else:
                    print("ℹ No evidence found for the alerts")
            else:
                print("⚠ No valid alert IDs found to fetch evidence")
        
        print_section("Test Completed Successfully")
        print("✓ All tests passed!")
        print()
        print("Summary:")
        print(f"  - Authenticated successfully")
        print(f"  - Found {len(alerts)} alert(s)")
        if alerts:
            alert_ids = [str(alert.get("AlertId")) for alert in alerts if alert.get("AlertId")]
            evidence_rows = client.fetch_alert_evidence(alert_ids, start_time) if alert_ids else []
            print(f"  - Found {len(evidence_rows)} evidence row(s)")
        
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
