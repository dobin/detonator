#!/usr/bin/env python3
"""
Test script for Azure VM integration
Run this to test VM creation without starting the full application
"""

import asyncio
import os
import sys
from datetime import datetime

# Add the detonator package to path
sys.path.insert(0, os.path.dirname(__file__))

from detonator.vm_manager import initialize_vm_manager, get_vm_manager
from detonator.vm_monitor import VMMonitorTask

async def test_azure_integration():
    """Test Azure VM integration"""
    print("Testing Azure VM Integration...")
    print("=" * 50)
    
    # Check environment variables
    subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")
    resource_group = os.getenv("AZURE_RESOURCE_GROUP", "detonator-rg")
    location = os.getenv("AZURE_LOCATION", "East US")
    
    print(f"Subscription ID: {subscription_id}")
    print(f"Resource Group: {resource_group}")
    print(f"Location: {location}")
    print()
    
    if not subscription_id:
        print("❌ ERROR: AZURE_SUBSCRIPTION_ID not set in environment")
        print("Please set up your .env file based on .env.template")
        return False
    
    try:
        # Initialize VM manager
        print("Initializing VM Manager...")
        initialize_vm_manager(subscription_id, resource_group, location)
        vm_manager = get_vm_manager()
        print("✅ VM Manager initialized successfully")
        
        # Test VM creation (but don't actually create - just test connection)
        print("\nTesting Azure connection...")
        
        # This will fail if credentials are not set up correctly
        # We'll catch the exception to test the connection
        try:
            # Just test that we can initialize the clients
            vm_manager.compute_client.virtual_machines.list(resource_group)
            print("✅ Azure connection successful")
            
        except Exception as e:
            if "ResourceGroupNotFound" in str(e):
                print(f"⚠️  Resource group '{resource_group}' not found, but connection is working")
                print(f"   Create it with: az group create --name {resource_group} --location '{location}'")
            else:
                print(f"❌ Azure connection failed: {str(e)}")
                return False
        
        # Test VM monitor
        print("\nTesting VM Monitor...")
        monitor = VMMonitorTask()
        await monitor.start_monitoring()
        print("✅ VM Monitor started successfully")
        
        # Stop monitor
        await monitor.stop_monitoring()
        print("✅ VM Monitor stopped successfully")
        
        print("\n" + "=" * 50)
        print("✅ All tests passed! Azure integration is ready.")
        print("\nNext steps:")
        print("1. Ensure resource group exists:")
        print(f"   az group create --name {resource_group} --location '{location}'")
        print("2. Start the application:")
        print("   poetry run python -m detonator both")
        print("3. Create a scan to test VM provisioning")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        print("\nTroubleshooting:")
        print("1. Make sure you're logged in: az login")
        print("2. Check your subscription: az account list")
        print("3. Verify .env file is set up correctly")
        return False

if __name__ == "__main__":
    # Load environment variables from .env file if it exists
    env_file = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_file):
        print(f"Loading environment from {env_file}")
        with open(env_file) as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value
    
    # Run the test
    success = asyncio.run(test_azure_integration())
    sys.exit(0 if success else 1)
